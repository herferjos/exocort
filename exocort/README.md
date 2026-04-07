# Exocort capturers

Minimal runner that boots the audio and screen capturers defined in `exocort/config.toml`.

1. Install dependencies (e.g., `pip install .`).
2. Adjust `exocort/config.toml` to toggle `audio.enabled`/`screen.enabled` and tweak chunk/interval settings.
3. Run:
   ```bash
   python -m exocort.runner --config exocort/config.toml
   ```
   or use the entry point `exocort` once the package is installed.

The runner starts only the enabled services, keeps their loops modular, and relies on the TOML file for configuration.
