# KlipperScreen Filament Lanes

A custom [KlipperScreen](https://github.com/KlipperScreen/KlipperScreen) panel
for multi-tool filament management on toolchanger 3D printers.

Designed for StealthChanger / toolchanger setups using the
[Filament_feeder](https://github.com/broncosis/Filament_feeder) macros and
[spoolman-lane-sync](https://github.com/broncosis/spoolman-lane-sync) for live
spool data. Works without spoolman-lane-sync too — spool assignments are read
directly from Klipper's saved variables and Spoolman.

## Features

- One vertical column per tool, scales automatically (4, 5, 6+ tools)
- Tap the spool icon to change the active tool
- Live spool color, name, and material from Spoolman via Moonraker
- Active tool highlighted with a red underline
- Filament sensor status per lane (dimmed when empty)
- Unload button per lane (disabled during active print)
- Optional Load button (hidden by default — see configuration)
- Assign spool sub-panel: browse Spoolman spools and assign to any lane
- Works without spoolman-lane-sync: falls back to reading `t{N}__spool_id`
  from Klipper save_variables and fetching spool data directly from Spoolman

## Requirements

- KlipperScreen (GTK3-based)
- Moonraker with Spoolman integration
- [Filament_feeder](https://github.com/broncosis/Filament_feeder) macros
  (`UNLOAD_ANY_TOOL`, `LOAD_ANY_TOOL_DIST`)
- [spoolman-lane-sync](https://github.com/broncosis/spoolman-lane-sync)
  *(optional — panel works without it)*

## Installation

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Broncosis/KlipperScreen-filament-lanes/main/install.sh)
```

The script clones the repo to `~/KlipperScreen-filament-lanes` and symlinks
the panels into `~/.KlipperScreen/panels/`. Symlinks mean a `git pull` in
the install directory is all that's needed to update.

At the end it prints the config snippet to add to
`~/printer_data/config/KlipperScreen.conf`, then:

```bash
sudo systemctl restart KlipperScreen
```

## Configuration

In `KlipperScreen.conf`:

```ini
[menu __main filament_lanes]
name: Filament Lanes
icon: filament
panel: filament_lanes

# Uncomment to show a Load button on each lane:
#show_load_buttons: true
```

## Credits

This project builds on the work of several open-source projects:

### KlipperScreen
- **Source**: https://github.com/KlipperScreen/KlipperScreen
- **License**: GPL v3
- The spool icon SVG color-substitution pattern in `panels/filament_lanes.py`
  is adapted from `panels/spoolman.py` in KlipperScreen. The `ScreenPanel`
  base class and GTK helper infrastructure (`_gtk`, `_screen`, `_printer`)
  are part of KlipperScreen.

### Klipper / Moonraker
- **Source**: https://github.com/Klipper3d/klipper / https://github.com/Arksine/moonraker
- **License**: GPL v3
- The `save_variables` mechanism (`t{N}__spool_id`) and Moonraker's database
  and Spoolman proxy APIs are used for spool assignment persistence and data
  fetching.

### Spoolman
- **Source**: https://github.com/Donkie/Spoolman
- **License**: MIT
- Spool color, name, and material data is fetched from Spoolman via Moonraker's
  proxy API.

## License

GPL v3 — see [LICENSE](LICENSE).
