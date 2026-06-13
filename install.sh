#!/usr/bin/env bash
# Installs the filament-lanes panels into KlipperScreen's user override
# directory so they survive KlipperScreen updates.
#
# Run from the repo root:
#   bash install.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
KS_USER_DIR="${HOME}/.KlipperScreen"
PANELS_DST="${KS_USER_DIR}/panels"

echo "Installing filament-lanes panels to ${PANELS_DST}…"
mkdir -p "${PANELS_DST}"

for f in filament_lanes.py filament_lanes_spoolman.py; do
    src="${REPO_DIR}/panels/${f}"
    dst="${PANELS_DST}/${f}"
    if [ -L "${dst}" ]; then
        echo "  Updating symlink: ${dst}"
        ln -sf "${src}" "${dst}"
    elif [ -e "${dst}" ]; then
        echo "  WARNING: ${dst} already exists and is not a symlink — skipping."
        echo "           Remove it manually and re-run to create the symlink."
    else
        echo "  Creating symlink: ${dst} -> ${src}"
        ln -s "${src}" "${dst}"
    fi
done

echo ""
echo "Done.  Add the contents of example_klipperscreen.conf to your"
echo "~/printer_data/config/KlipperScreen.conf, then restart KlipperScreen:"
echo ""
echo "  sudo systemctl restart KlipperScreen"
