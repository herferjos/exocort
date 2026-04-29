# Exocort Frontend

This folder contains the Tauri desktop launcher for Exocort.

## What It Does

- Works directly on the real YAML files in the repository
- Lets you define backend environment variables from the UI
- Lets you manage multiple YAML profiles from the UI
- Persists the active profile and UI-only settings in `frontend/.exocort/ui.generated.yaml`
- Validates the selected YAML with the local backend executable before launch
- Starts and stops the backend process from the UI

The frontend does not load `backend/.env`.

## How It Works

The UI is built with plain HTML, CSS, and JavaScript. Tauri commands in `src-tauri/src/main.rs` handle the backend process lifecycle.

- The "Start" action serializes the active profile to YAML, validates it with the local backend executable, applies environment variables, and starts the backend.
- The "Stop" action terminates that process.

In development, the launcher uses `backend/.venv/bin/exocort` and the service launchers in each `services/*/.venv/bin/` directory.
No backend or service resources are copied into the app bundle.

## Project Layout

- `frontend/index.html`: Tauri entry page
- `frontend/src/main.js`: UI logic
- `frontend/src/styles.css`: launcher styling
- `frontend/src-tauri/`: Rust side of the Tauri app

## Install and Build

From the `frontend/` directory:

```bash
npm install
npm run tauri build
```

Before building, make sure Rust is installed. `cargo` and `rustc` must be available in your terminal. The recommended way is `rustup`, which installs both tools:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

On macOS, Tauri also needs the Xcode Command Line Tools:

```bash
xcode-select --install
```

After installing Rust, restart your terminal and verify:

```bash
rustc --version
cargo --version
```

## Config Layout

The UI mirrors the backend config structure, but storage locations are fixed in the repo-backed YAMLs and are not editable via the form:

- `log_level`
- `capturer.audio`
- `capturer.audio.vad`
- `capturer.screen`
- `processor.ocr`
- `processor.asr`
- `processor.content_filter.rules`
- `processor.notes`

The launcher writes audio, screen, and processor files under the repo-root `tmp/` folder, and notes under the repo-root `vault/` folder.
Default storage directories include `tmp/raw/audio`, `tmp/raw/screen`, `tmp/raw`, `tmp/processed`, `vault/`, and `tmp/processed/notes`.

## Config Path Rules

- YAML profiles are stored in the repository under `backend/`
- Service configs are in `services/*/config.yaml`
- Relative paths inside each YAML resolve from that YAML's own directory, so `../tmp/...` and `../vault` always point to the repo-root folders
