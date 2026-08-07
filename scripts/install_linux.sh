#!/usr/bin/env bash
#
# GGUF Loader - Linux installer / uninstaller
#
# Installs the prebuilt GGUF Loader binary to a per-user or system-wide
# location, wires up a launcher command and a desktop-menu entry, and can
# remove everything again.
#
# Usage:
#   ./install.sh                    Per-user install (no root needed)
#   ./install.sh --system           System-wide install (prompts via sudo)
#   ./install.sh --uninstall        Remove the per-user install
#   ./install.sh --uninstall --system   Remove the system-wide install
#   ./install.sh --help             Show this help
#
set -euo pipefail

VERSION="2.1.2"
BIN_NAME="GGUFLoader_v${VERSION}_linux_x86_64"
LAUNCHER_NAME="gguf-loader"
APP_NAME="GGUF Loader"

# --- options ---------------------------------------------------------------
SYSTEM=0
UNINSTALL=0
for arg in "$@"; do
  case "$arg" in
    --system)        SYSTEM=1 ;;
    --uninstall|-u)  UNINSTALL=1 ;;
    -h|--help)       awk 'NR>1 && /^#/ { sub(/^# ?/, ""); print }' "$0" ; exit 0 ;;
    *) echo "Unknown option: $arg" >&2 ; exit 1 ;;
  esac
done

# --- install locations ------------------------------------------------------
if [ "$SYSTEM" = 1 ]; then
  APP_DIR="/opt/${LAUNCHER_NAME}"
  BIN_DIR="/usr/local/bin"
  DESKTOP_DIR="/usr/share/applications"
  ICON_DIR="/usr/share/icons/hicolor/512x512/apps"
else
  APP_DIR="${XDG_DATA_HOME:-$HOME/.local}/opt/${LAUNCHER_NAME}"
  BIN_DIR="${XDG_BIN_HOME:-$HOME/.local}/bin"
  DESKTOP_DIR="$HOME/.local/share/applications"
  ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"
fi

ICON_NAME="${LAUNCHER_NAME}.png"
DESKTOP_FILE="${DESKTOP_DIR}/${LAUNCHER_NAME}.desktop"

# --- locate bundled files (tarball dir, or the repo's dist/ dir) ------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_BIN="${SCRIPT_DIR}/${BIN_NAME}"
[ -f "${SRC_BIN}" ] || SRC_BIN="${SCRIPT_DIR}/../dist/${BIN_NAME}"
SRC_ICON="${SCRIPT_DIR}/icon.png"

if [ ! -f "${SRC_BIN}" ]; then
  echo "Could not find ${BIN_NAME} next to this script or in ../dist." >&2
  echo "Keep install.sh and the binary together (extract the whole .tar.gz)." >&2
  exit 1
fi

# --- system-wide operations need root ----------------------------------------
if [ "$SYSTEM" = 1 ] && [ "$(id -u)" -ne 0 ]; then
  echo "This operation needs admin rights - re-running with sudo..."
  exec sudo "${SCRIPT_DIR}/install.sh" "$@"
fi

# --- uninstall ----------------------------------------------------------------
if [ "$UNINSTALL" = 1 ]; then
  echo "Removing ${APP_NAME}..."
  rm -f "${DESKTOP_FILE}" "${BIN_DIR}/${LAUNCHER_NAME}" "${ICON_DIR}/${ICON_NAME}"
  rm -rf "${APP_DIR}"
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${DESKTOP_DIR}" >/dev/null 2>&1 || true
  fi
  echo "Done. ${APP_NAME} has been removed."
  exit 0
fi

# --- install -----------------------------------------------------------------
echo "Installing ${APP_NAME} v${VERSION}..."

# 1. application binary
mkdir -p "${APP_DIR}"
install -m 0755 "${SRC_BIN}" "${APP_DIR}/${BIN_NAME}"
echo "  binary    -> ${APP_DIR}/${BIN_NAME}"

# 2. launcher on PATH
mkdir -p "${BIN_DIR}"
ln -sf "${APP_DIR}/${BIN_NAME}" "${BIN_DIR}/${LAUNCHER_NAME}"
echo "  launcher  -> ${BIN_DIR}/${LAUNCHER_NAME}"

# 3. desktop menu entry + icon
if [ -f "${SRC_ICON}" ]; then
  mkdir -p "${ICON_DIR}"
  install -m 0644 "${SRC_ICON}" "${ICON_DIR}/${ICON_NAME}"
  echo "  icon      -> ${ICON_DIR}/${ICON_NAME}"
fi
mkdir -p "${DESKTOP_DIR}"
cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Type=Application
Version=${VERSION}
Name=${APP_NAME}
GenericName=AI Model Loader
Comment=Load and chat with local GGUF language models
Exec=${BIN_DIR}/${LAUNCHER_NAME}
Icon=${LAUNCHER_NAME}
Terminal=false
Categories=Utility;AI;Science;
StartupNotify=true
EOF
chmod 0644 "${DESKTOP_FILE}"
echo "  menu      -> ${DESKTOP_FILE}"

# refresh desktop/icon caches (best effort)
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${DESKTOP_DIR}" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "${ICON_DIR%/512x512/apps}" >/dev/null 2>&1 || true
fi

# --- done --------------------------------------------------------------------
echo
echo "OK - ${APP_NAME} v${VERSION} installed."
if [ "$SYSTEM" = 1 ]; then
  echo "Run it with:  ${LAUNCHER_NAME}"
else
  if ! printf '%s' "${PATH}" | tr ':' '\n' | grep -qx "${BIN_DIR}"; then
    echo
    echo "NOTE: ${BIN_DIR} is not on your PATH."
    echo "      Add it once with:  export PATH=\"${BIN_DIR}:\$PATH\""
  fi
  echo "Run it with:  ${LAUNCHER_NAME}"
fi
echo "Uninstall with: $0 --uninstall"
