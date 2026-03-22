#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_DIR="${HOME}/Applications"
APP_NAME="Exocort.app"
APP_PATH="${TARGET_DIR}/${APP_NAME}"
MANAGER_SCRIPT="${ROOT_DIR}/scripts/launchd/exocort-mac-daemon.sh"
ICON_PNG="${ROOT_DIR}/assessts/exocort.png"
CONFIG_PATH="${ROOT_DIR}/config/exocort.toml"

if ! command -v osacompile >/dev/null 2>&1; then
  echo "osacompile not found. This script must run on macOS."
  exit 1
fi

if [[ ! -x "${MANAGER_SCRIPT}" ]]; then
  echo "Manager script not executable. Run:"
  echo "  chmod +x \"${MANAGER_SCRIPT}\""
  exit 1
fi

mkdir -p "${TARGET_DIR}"

TMP_SCRIPT="$(mktemp)"
trap 'rm -f "${TMP_SCRIPT}"' EXIT

cat >"${TMP_SCRIPT}" <<EOF
set managerScript to "${MANAGER_SCRIPT}"

set optionsList to {"Install", "Start", "Stop", "Restart", "Status", "Logs", "Uninstall"}
set picked to choose from list optionsList with title "Exocort" with prompt "Select an action" default items {"Status"} OK button name "Run" cancel button name "Cancel"

if picked is false then
  return
end if

set actionName to item 1 of picked
set actionMap to {{"Install", "install"}, {"Start", "start"}, {"Stop", "stop"}, {"Restart", "restart"}, {"Status", "status"}, {"Logs", "logs"}, {"Uninstall", "uninstall"}}
set commandName to ""

repeat with pairItem in actionMap
  if item 1 of pairItem is actionName then
    set commandName to item 2 of pairItem
    exit repeat
  end if
end repeat

if commandName is "" then
  display alert "Unknown action"
  return
end if

try
  with timeout of 600 seconds
    set outputText to do shell script quoted form of managerScript & " " & commandName
  end timeout
  if outputText is "" then
    set outputText to "Completed: " & commandName & "\nConfig: " & "${CONFIG_PATH}"
  end if
  display dialog outputText buttons {"OK"} default button "OK" with title "Exocort"
on error errMsg number errNum
  if errNum is -1712 then
    -- AppleEvent timeout: command sigue trabajando o se ha colgado; mostramos un mensaje suave.
    display dialog "The action is still running or took too long.\nCheck logs in .logs/launchd/ if needed." buttons {"OK"} default button "OK" with title "Exocort"
  else
    display dialog errMsg buttons {"OK"} default button "OK" with icon stop with title "Exocort"
  end if
end try
EOF

rm -rf "${APP_PATH}"
osacompile -o "${APP_PATH}" "${TMP_SCRIPT}"

if [[ -f "${ICON_PNG}" ]]; then
  # Best-effort icon generation; if anything fails we still keep the app.
  if command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
    ICONSET_ROOT="$(mktemp -d)"
    ICONSET_DIR="${ICONSET_ROOT}/exocort.iconset"
    mkdir -p "${ICONSET_DIR}"

    set +e
    sips -z 16 16   "${ICON_PNG}" --out "${ICONSET_DIR}/icon_16x16.png" >/dev/null 2>&1
    sips -z 32 32   "${ICON_PNG}" --out "${ICONSET_DIR}/icon_16x16@2x.png" >/devnull 2>&1
    sips -z 32 32   "${ICON_PNG}" --out "${ICONSET_DIR}/icon_32x32.png" >/dev/null 2>&1
    sips -z 64 64   "${ICON_PNG}" --out "${ICONSET_DIR}/icon_32x32@2x.png" >/dev/null 2>&1
    sips -z 128 128 "${ICON_PNG}" --out "${ICONSET_DIR}/icon_128x128.png" >/dev/null 2>&1
    sips -z 256 256 "${ICON_PNG}" --out "${ICONSET_DIR}/icon_128x128@2x.png" >/dev/null 2>&1
    sips -z 256 256 "${ICON_PNG}" --out "${ICONSET_DIR}/icon_256x256.png" >/dev/null 2>&1
    sips -z 512 512 "${ICON_PNG}" --out "${ICONSET_DIR}/icon_256x256@2x.png" >/dev/null 2>&1
    cp "${ICON_PNG}" "${ICONSET_DIR}/icon_512x512.png" 2>/dev/null || true
    cp "${ICON_PNG}" "${ICONSET_DIR}/icon_512x512@2x.png" 2>/dev/null || true

    ICON_ICNS="$(mktemp -t exocort_icon).icns"
    iconutil -c icns "${ICONSET_DIR}" -o "${ICON_ICNS}" >/dev/null 2>&1
    set -e

    if [[ -f "${ICON_ICNS}" ]]; then
      mkdir -p "${APP_PATH}/Contents/Resources"
      cp "${ICON_ICNS}" "${APP_PATH}/Contents/Resources/applet.icns"
      touch "${APP_PATH}"
    fi
    rm -rf "${ICONSET_ROOT}" >/dev/null 2>&1 || true
  fi
fi

echo "Created app: ${APP_PATH}"
echo "You can pin it to Dock and run start/stop from Finder."
