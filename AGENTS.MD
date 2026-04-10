# Coding Guidelines

Project-specific design guidance lives in [coding_principles.md](instructions/coding_principles.md) and the linked follow-up docs.

**Note:** If there is a general wish or direction from the user to standardize something across the project, you should be proactive in applying or extending these rules—or any rules found in `instructions/`—in that context. If you’re uncertain about how to generalize or extend an instruction for a new case, raise the question or propose a standardization before proceeding.

## 1. Think Before Coding

**Don't overthink unless necessary. Take things step by step.**

Before you start coding:
- Say your assumptions out loud. If you aren't sure, ask.
- If there are multiple ways to understand something, mention them. Don't pick silently.
- Prefer simpler solutions when possible. If something looks needlessly complex, speak up.
- If something is unclear, stop and ask for clarification.

## 2. Simplicity First

**Do the minimum required to solve the problem. Don't add more than what's needed.**

- Only add requested features.
- Don't abstract or generalize code that's only used once.
- Only add flexibility or configuration if it's requested.
- Don't handle errors that can't actually happen.
- If your code is longer than necessary, shorten it.

Before finishing, ask: "Is this as simple as it could be?" If not, simplify.

## 3. Style Consistency

**Match the existing style of this codebase.**

- When adding or changing code, follow the existing conventions. Ignore your personal style if it conflicts.
- Don't introduce new formatting, naming, or architecture styles without discussion.
- Consistency is more important than making it "better".

## 4. Only Change What's Necessary

**Edit only what you need. Don't clean up things you didn't touch.**

When changing code:
- Don't "improve" nearby code, comments, or formatting.
- Don't refactor code unless it's actually broken.
- Stick to the project's style, even if it's not your favorite.
- If you find unrelated dead code, mention it, but don't remove it unless asked.

If your changes cause code to become unused:
- Remove only imports/variables/functions that your changes made unnecessary.
- Don't clean up old unused code unless requested.

Each changed line should directly relate to the user's request.

## 5. Work Towards Clear Goals

**Define what success looks like. Take it one step at a time.**

Break tasks into clear, checkable goals:
- "Add validation" → "Write a test for bad input, then make it pass"
- "Fix the bug" → "Write a test that reproduces the bug, then make it pass"
- "Refactor X" → "Make sure tests work before and after"

> **Important:** When running or writing tests, use the `.venv` virtual environment at the repository root.
> Only run or create tests if the user asks, and only if testing exists in this project.

For multi-step tasks, make a plan:
```
1. [Step] → verify: [Check]
2. [Step] → verify: [Check]
3. [Step] → verify: [Check]
```

Strong, clear goals let you work independently. Avoid vague goals ("just make it work").
