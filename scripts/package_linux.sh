#!/usr/bin/env bash
#
# GGUF Loader - Linux packaging script
#
# Bundles the prebuilt Linux binary, the installer, a generated icon and a
# README into a single .tar.gz for easy distribution. Requires a Linux
# environment (the binary itself is built for Linux).
#
# Usage:  ./scripts/package_linux.sh
# Output: dist/GGUFLoader_v<version>_linux_x86_64.tar.gz
#
# Set PYTHON to a Python with Pillow if you want icon.png generated
# (e.g.  PYTHON=~/.venv/bin/python ./scripts/package_linux.sh).
#
set -euo pipefail

VERSION="2.1.2"
BIN_NAME="GGUFLoader_v${VERSION}_linux_x86_64"
TARBALL="dist/GGUFLoader_v${VERSION}_linux_x86_64.tar.gz"
FOLDER="GGUFLoader-v${VERSION}-linux"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE="$(mktemp -d)"
PYTHON="${PYTHON:-python3}"

trap 'rm -rf "${STAGE}"' EXIT
cd "${ROOT}"

# --- sanity checks -----------------------------------------------------------
[ -f "dist/${BIN_NAME}" ] || { echo "Missing dist/${BIN_NAME} - build it first (scripts/build_linux.sh)." >&2; exit 1; }
[ -f "icon.ico" ] || echo "Warning: icon.ico not found - installer will run without an icon." >&2
[ -f "scripts/install_linux.sh" ] || { echo "Missing scripts/install_linux.sh" >&2; exit 1; }

mkdir -p "${STAGE}/${FOLDER}"

# --- binary ------------------------------------------------------------------
cp "dist/${BIN_NAME}" "${STAGE}/${FOLDER}/${BIN_NAME}"
chmod +x "${STAGE}/${FOLDER}/${BIN_NAME}"
echo "  + ${BIN_NAME}"

# --- installer ---------------------------------------------------------------
cp "scripts/install_linux.sh" "${STAGE}/${FOLDER}/install.sh"
chmod +x "${STAGE}/${FOLDER}/install.sh"
echo "  + install.sh"

# --- icon (icon.ico -> icon.png, best effort) --------------------------------
if [ -f "icon.ico" ] && "${PYTHON}" -c "import PIL" >/dev/null 2>&1; then
  "${PYTHON}" - "${STAGE}/${FOLDER}/icon.png" <<'PYEOF'
import sys
from PIL import Image

src = Image.open("icon.ico").convert("RGBA")
out = src.resize((512, 512), Image.LANCZOS)
out.save(sys.argv[1], "PNG")
print("  + icon.png (generated from icon.ico)")
PYEOF
else
  echo "  - icon.png skipped (Pillow unavailable or icon.ico missing)"
fi

# --- README ------------------------------------------------------------------
cat > "${STAGE}/${FOLDER}/README.txt" <<EOF
GGUF Loader v${VERSION} - Linux x86_64
======================================

A desktop app to load GGUF language models and chat with them locally.
This archive contains a prebuilt, self-contained binary - no Python or
other runtime dependencies required.

WHAT'S INSIDE
  ${BIN_NAME}   the standalone application
  install.sh    installer / uninstaller
  icon.png      application icon
  README.txt    this file

REQUIREMENTS
  - 64-bit x86_64 Linux (glibc 2.17 or newer - most distros since ~2014)
  - CPU-only build (no NVIDIA/AMD GPU or CUDA required)

QUICK START (per-user, no admin rights)
  tar -xzf ${TARBALL##*/}
  cd ${FOLDER}
  ./install.sh
  gguf-loader

SYSTEM-WIDE INSTALL
  sudo ./install.sh --system

RUN WITHOUT INSTALLING
  ./${BIN_NAME}

UNINSTALL
  ./install.sh --uninstall           (per-user)
  sudo ./install.sh --uninstall --system

VERIFY
  gguf-loader --version

TROUBLESHOOTING
  - "Permission denied":  chmod +x ${BIN_NAME}
  - Launcher not found:   ~/.local/bin is not on your PATH. Add it with:
        export PATH="\$HOME/.local/bin:\$PATH"
EOF
echo "  + README.txt"

# --- tarball -----------------------------------------------------------------
tar -C "${STAGE}" -czf "${TARBALL}" "${FOLDER}"
echo
echo "Packaged: ${TARBALL}"
ls -lh "${TARBALL}"
