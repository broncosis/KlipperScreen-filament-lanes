# KlipperScreen Filament Lanes

A custom [KlipperScreen](https://github.com/KlipperScreen/KlipperScreen) panel
for multi-tool filament management on toolchanger 3D printers.

Designed for StealthChanger / toolchanger setups using the
[Filament_feeder](https://github.com/broncosis/Filament_feeder) macros and
[spoolman-lane-sync](https://github.com/broncosis/spoolman-lane-sync) for live
spool data.

## Features

- One vertical column per tool, scales automatically (4, 5, 6+ tools)
- Tap the spool icon to change the active tool
- Live spool color, name, and material from Spoolman via Moonraker
- Active tool highlighted with a red underline
- Filament sensor status per lane (dimmed when empty)
- Unload button per lane (disabled during active print)
- Optional Load button (hidden by default — see configuration)
- Assign spool sub-panel: browse Spoolman spools and assign to any lane

## Requirements

- KlipperScreen (GTK3-based)
- Moonraker with Spoolman integration
- [spoolman-lane-sync](https://github.com/broncosis/spoolman-lane-sync) writing
  to the `lane_data` Moonraker database namespace
- [Filament_feeder](https://github.com/broncosis/Filament_feeder) macros
  (`UNLOAD_ANY_TOOL`, `LOAD_ANY_TOOL_DIST`)

## Installation

```bash
git clone https://github.com/Broncosis/KlipperScreen-filament-lanes.git
cd KlipperScreen-filament-lanes
bash install.sh
```

Then add the contents of `example_klipperscreen.conf` to your
`~/printer_data/config/KlipperScreen.conf` and restart KlipperScreen:

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

## License

GPL v3 — see [LICENSE](LICENSE).
