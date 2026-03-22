# Exocort macOS Launchd Scripts

This folder contains two scripts that work together to install and manage Exocort services on macOS using `launchd`.

## What Each Script Does

- `exocort-mac-daemon.sh`
  - The **manager**: creates/updates the `launchd` plist files and starts/stops the services.
  - Use this from Terminal (or by the control app).

- `create_exocort_control_app.sh`
  - The **control app generator**: builds a small `.app` with a UI to run the manager commands.
  - The app **does not manage services by itself**; it only calls the manager script.

## Install / Start / Stop (Terminal)

From the repo root:

```bash
scripts/launchd/exocort-mac-daemon.sh install
```

This will:
- Sync dependencies
- Create/update `launchd` plists
- Start the services
- Set them to auto-start on login

Other commands:

```bash
scripts/launchd/exocort-mac-daemon.sh start
scripts/launchd/exocort-mac-daemon.sh stop
scripts/launchd/exocort-mac-daemon.sh restart
scripts/launchd/exocort-mac-daemon.sh status
scripts/launchd/exocort-mac-daemon.sh logs
scripts/launchd/exocort-mac-daemon.sh uninstall
```

## Install / Start / Stop (Control App)

Create the UI app:

```bash
scripts/launchd/create_exocort_control_app.sh
```

Then open `~/Applications/Exocort.app` and choose actions like Install/Start/Stop/Status from the UI.

## Config Used

The manager injects this shared config file:

```
config/exocort.toml
```

Update that file if you need to change runtime flags, audio/screen endpoints, or processor settings.

## Logs

Logs are written to:

```
.logs/launchd/
```

## Notes

- macOS system audio capture requires Screen Recording permission (prompted on first run).
- If the control app reports “still running or took too long”, check `.logs/launchd/`.
