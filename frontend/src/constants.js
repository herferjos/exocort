export const INTERNAL_PATHS = {
  audio_output_dir: "../tmp/raw/audio",
  screen_output_dir: "../tmp/raw/screen",
  watch_dir: "../tmp/raw",
  processor_output_dir: "../tmp/processed",
  notes_vault_dir: "../vault",
  notes_state_dir: "../tmp/processed/notes",
};

export const SUPPORTED_PROVIDERS = ["openai", "gemini", "anthropic", "mistral"];
export const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];
export const FORMAT_OPTIONS = ["asr", "ocr", "llm"];
export const APP_VIEWS = [
  { id: "home", label: "Inicio" },
  { id: "configurations", label: "Configuraciones" },
  { id: "services", label: "Servicios" },
];
export const CONFIG_TABS = [
  { id: "general", label: "General" },
  { id: "capture", label: "Capture" },
  { id: "processing", label: "Processing" },
  { id: "environment", label: "Environment" },
];
