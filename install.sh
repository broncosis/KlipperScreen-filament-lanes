#!/usr/bin/env bash
# Installs KlipperScreen Filament Lanes panels.
#
# One-line install (recommended):
#   bash <(curl -fsSL https://raw.githubusercontent.com/Broncosis/KlipperScreen-filament-lanes/main/install.sh)
#
# Or clone and run locally:
#   git clone https://github.com/Broncosis/KlipperScreen-filament-lanes.git
#   bash KlipperScreen-filament-lanes/install.sh

set -e

REPO_URL="https://github.com/Broncosis/KlipperScreen-filament-lanes.git"
INSTALL_DIR="${HOME}/KlipperScreen-filament-lanes"
KS_PANELS="${HOME}/.KlipperScreen/panels"

# ── Clone or update the repo ──────────────────────────────────────────────────

if [ -d "${INSTALL_DIR}/.git" ]; then
    echo "Updating existing install at ${INSTALL_DIR}…"
    git -C "${INSTALL_DIR}" pull
else
    echo "Cloning repo to ${INSTALL_DIR}…"
    git clone "${REPO_URL}" "${INSTALL_DIR}"
fi

# ── Symlink panels ────────────────────────────────────────────────────────────

mkdir -p "${KS_PANELS}"

for f in filament_lanes.py filament_lanes_spoolman.py; do
    src="${INSTALL_DIR}/panels/${f}"
    dst="${KS_PANELS}/${f}"
    if [ -L "${dst}" ]; then
        echo "  Updating symlink: ${dst}"
        ln -sf "${src}" "${dst}"
    elif [ -e "${dst}" ]; then
        echo ""
        echo "  WARNING: ${dst} already exists and is not a symlink."
        echo "           Remove it manually and re-run to create the symlink."
    else
        echo "  Creating symlink: ${dst} -> ${src}"
        ln -s "${src}" "${dst}"
    fi
done

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "─────────────────────────────────────────────────"
echo " Installation complete!"
echo "─────────────────────────────────────────────────"
echo ""
echo "Add the following to ~/printer_data/config/KlipperScreen.conf"
echo "then restart KlipperScreen:"
echo ""
cat "${INSTALL_DIR}/example_klipperscreen.conf"
echo ""
echo "  sudo systemctl restart KlipperScreen"
echo ""
