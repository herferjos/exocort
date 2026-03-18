#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_DIR="${HOME}/Library/LaunchAgents"
LOG_DIR="${ROOT_DIR}/.logs/launchd"
UID_VALUE="$(id -u)"

LABEL_OCR="com.exocort.mac.ocr"
LABEL_ASR="com.exocort.faster_whisper"
LABEL_EXOCORT="com.exocort.app"

PLIST_OCR="${PLIST_DIR}/${LABEL_OCR}.plist"
PLIST_ASR="${PLIST_DIR}/${LABEL_ASR}.plist"
PLIST_EXOCORT="${PLIST_DIR}/${LABEL_EXOCORT}.plist"

# Try to resolve uv once, so it also works when called from GUI apps.
UV_BIN="$(command -v uv 2>/dev/null || true)"
if [[ -z "${UV_BIN}" ]]; then
  # Fallbacks for common Homebrew locations; if still missing, leave as 'uv'.
  for candidate in /opt/homebrew/bin/uv /usr/local/bin/uv; do
    if [[ -x "${candidate}" ]]; then
      UV_BIN="${candidate}"
      break
    fi
  done
fi
UV_BIN="${UV_BIN:-uv}"

UV_DIR="$(dirname "${UV_BIN}")"
PATH_VALUE="${UV_DIR}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

write_plist() {
  local label="$1"
  local cwd="$2"
  local command="$3"
  local plist_path="$4"
  local stdout_log="$5"
  local stderr_log="$6"

  cat >"${plist_path}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>${label}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ProcessType</key>
    <string>Background</string>
    <key>WorkingDirectory</key>
    <string>${cwd}</string>
    <key>ProgramArguments</key>
    <array>
      <string>/bin/zsh</string>
      <string>-lc</string>
      <string>${command}</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
      <key>PATH</key>
      <string>${PATH_VALUE}</string>
      <key>PYTHONUNBUFFERED</key>
      <string>1</string>
      <key>COLLECTOR_CONFIG</key>
      <string>${ROOT_DIR}/config/config.local.json</string>
    </dict>
    <key>StandardOutPath</key>
    <string>${stdout_log}</string>
    <key>StandardErrorPath</key>
    <string>${stderr_log}</string>
  </dict>
</plist>
EOF
}

unload_if_present() {
  local plist_path="$1"
  launchctl bootout "gui/${UID_VALUE}" "${plist_path}" >/dev/null 2>&1 || true
}

load_plist() {
  local plist_path="$1"
  launchctl bootstrap "gui/${UID_VALUE}" "${plist_path}"
  launchctl enable "gui/${UID_VALUE}/$(basename "${plist_path}" .plist)"
  launchctl kickstart -k "gui/${UID_VALUE}/$(basename "${plist_path}" .plist)"
}

bootstrap_dependencies() {
  (
    cd "${ROOT_DIR}/services/mac_ocr"
    "${UV_BIN}" sync
  )
  (
    cd "${ROOT_DIR}/services/faster_whisper"
    "${UV_BIN}" sync
  )
  (
    cd "${ROOT_DIR}"
    "${UV_BIN}" sync --all-extras
  )
}

install_daemons() {
  bootstrap_dependencies
  mkdir -p "${PLIST_DIR}" "${LOG_DIR}"

  write_plist \
    "${LABEL_OCR}" \
    "${ROOT_DIR}/services/mac_ocr" \
    "\"${UV_BIN}\" run mac-ocr-service" \
    "${PLIST_OCR}" \
    "${LOG_DIR}/mac_ocr.out.log" \
    "${LOG_DIR}/mac_ocr.err.log"

  write_plist \
    "${LABEL_ASR}" \
    "${ROOT_DIR}/services/faster_whisper" \
    "\"${UV_BIN}\" run faster-whisper-service" \
    "${PLIST_ASR}" \
    "${LOG_DIR}/faster_whisper.out.log" \
    "${LOG_DIR}/faster_whisper.err.log"

  write_plist \
    "${LABEL_EXOCORT}" \
    "${ROOT_DIR}" \
    "\"${UV_BIN}\" run exocort" \
    "${PLIST_EXOCORT}" \
    "${LOG_DIR}/exocort.out.log" \
    "${LOG_DIR}/exocort.err.log"

  unload_if_present "${PLIST_OCR}"
  unload_if_present "${PLIST_ASR}"
  unload_if_present "${PLIST_EXOCORT}"

  load_plist "${PLIST_OCR}"
  load_plist "${PLIST_ASR}"
  load_plist "${PLIST_EXOCORT}"
}

stop_daemons() {
  unload_if_present "${PLIST_EXOCORT}"
  unload_if_present "${PLIST_ASR}"
  unload_if_present "${PLIST_OCR}"
}

start_daemons() {
  load_plist "${PLIST_OCR}"
  load_plist "${PLIST_ASR}"
  load_plist "${PLIST_EXOCORT}"
}

print_label_status() {
  local label="$1"
  echo "== ${label} =="
  if launchctl print "gui/${UID_VALUE}/${label}" >/tmp/exocort-launchd-status.txt 2>/dev/null; then
    rg "state =|pid =|last exit code =" /tmp/exocort-launchd-status.txt || true
  else
    echo "not loaded"
  fi
  echo
}

status_daemons() {
  print_label_status "${LABEL_OCR}"
  print_label_status "${LABEL_ASR}"
  print_label_status "${LABEL_EXOCORT}"
}

uninstall_daemons() {
  stop_daemons
  rm -f "${PLIST_OCR}" "${PLIST_ASR}" "${PLIST_EXOCORT}"
}

show_logs() {
  echo "Logs directory: ${LOG_DIR}"
  ls -1 "${LOG_DIR}" 2>/dev/null || true
}

usage() {
  cat <<'EOF'
Usage:
  scripts/launchd/exocort-mac-daemon.sh install     # install + start + auto-start at login
  scripts/launchd/exocort-mac-daemon.sh start       # start all services
  scripts/launchd/exocort-mac-daemon.sh stop        # stop all services
  scripts/launchd/exocort-mac-daemon.sh restart     # restart all services
  scripts/launchd/exocort-mac-daemon.sh status      # show launchd state
  scripts/launchd/exocort-mac-daemon.sh logs        # show logs directory
  scripts/launchd/exocort-mac-daemon.sh uninstall   # remove launch agents
EOF
}

case "${1:-}" in
  install)
    install_daemons
    ;;
  start)
    start_daemons
    ;;
  stop)
    stop_daemons
    ;;
  restart)
    stop_daemons
    start_daemons
    ;;
  status)
    status_daemons
    ;;
  logs)
    show_logs
    ;;
  uninstall)
    uninstall_daemons
    ;;
  *)
    usage
    exit 1
    ;;
esac
