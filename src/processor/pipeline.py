"""
Main processing pipeline: orchestrates agents to build the vault.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque
from pathlib import Path
from queue import Queue

import settings
from .agents import OrchestratorAgent, WorkerAgent
from .domain.models import Task
from ai.llm import get_client, get_llm_config
from .storage.state_db import get_events_by_day, init_db, ingest_jsonl

log = logging.getLogger("processor.pipeline")


def run_pipeline(
    days: list[str],
    provider_override: str | None = None,
    rebuild_only: bool = False,
    dry_run: bool = False,
) -> None:
    """Ingest events and run the agent-based pipeline."""
    vault_dir = settings.vault_dir()
    data_dir = settings.data_dir()
    events_dir = data_dir / "events"

    db_path = init_db(vault_dir)
    log.info("State DB: %s", db_path)

    if not rebuild_only:
        n = ingest_jsonl(
            db_path,
            events_dir,
            days,
            max_events=settings.max_events_per_run(),
        )
        log.info("Ingested %d events", n)

    try:
        llm = get_client(provider_override)
    except Exception as e:
        log.error("Failed to init LLM client: %s", e)
        return

    all_events = []
    for day in days:
        all_events.extend(get_events_by_day(db_path, day))

    if not all_events:
        log.info("No events to process for the selected days.")
        return

    # 1. Orchestrator creates the plan
    orchestrator = OrchestratorAgent(llm)
    plan = orchestrator.create_plan(all_events)
    if not plan:
        log.warning("Orchestrator did not produce a plan. Exiting.")
        return

    # 2. Execute the plan
    concurrency = get_llm_config().concurrency
    log.info("Executing plan with concurrency=%d", concurrency)
    worker_pool = _create_worker_pool(llm, db_path, vault_dir, all_events, concurrency)
    _execute_plan(plan, worker_pool, concurrency, dry_run)


def _create_worker_pool(llm, db_path: Path, vault_dir: Path, all_events: list[dict], size: int) -> Queue:
    """Build a queue of reusable WorkerAgents."""
    pool = Queue()
    for _ in range(size):
        pool.put(WorkerAgent(llm_client=llm, db_path=db_path, vault_dir=vault_dir, all_events=all_events))
    return pool


def _execute_plan(
    plan: list[Task],
    worker_pool: Queue,
    concurrency: int,
    dry_run: bool,
) -> None:
    """Run tasks in parallel, respecting dependencies."""
    completed_tasks = set()

    # Using a deque as a queue of tasks ready to run
    task_queue = deque([t for t in plan if not t.dependencies])

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(_run_task, task, worker_pool, dry_run): task for task in task_queue}

        while futures:
            for future in as_completed(futures):
                task = futures[future]
                try:
                    future.result()  # Raise exception if task failed
                    completed_tasks.add(task.task_id)
                    task.status = "completed"
                    log.info(f"Task {task.task_id} completed successfully.")

                    # Find new tasks that can now be run
                    for potential_task in plan:
                        if potential_task.status == "pending" and set(potential_task.dependencies).issubset(completed_tasks):
                            potential_task.status = "running"
                            new_future = executor.submit(_run_task, potential_task, worker_pool, dry_run)
                            futures[new_future] = potential_task

                except Exception as e:
                    task.status = "failed"
                    log.error(f"Task {task.task_id} failed: {e}", exc_info=True)

                # Remove the completed/failed future
                del futures[future]

    num_completed = len([t for t in plan if t.status == "completed"])
    num_failed = len(plan) - num_completed
    log.info(f"Plan execution finished. Completed: {num_completed}, Failed: {num_failed}")


def _run_task(task: Task, worker_pool: Queue, dry_run: bool) -> None:
    """Get a worker from the pool, execute the task, then return the worker to the pool."""
    if dry_run:
        log.info("[Dry Run] Would execute task: %s (%s)", task.task_id, task.task_type)
        return

    worker = worker_pool.get()
    try:
        worker.execute_task(task)
    finally:
        worker_pool.put(worker)
