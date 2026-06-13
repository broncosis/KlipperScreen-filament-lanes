# KlipperScreen Filament Lanes Panel — Project Context

## Goal

Build a custom KlipperScreen panel that shows all filament tool lanes on one
screen, divided evenly by tool count. Designed for toolchanger setups using
the `Filament_feeder` macros and `spoolman-lane-sync` for spool data.

---

## Hardware Context

- **Bobby**: 5-tool StealthChanger toolchanger, 5" touchscreen
- **Ricky**: 4-tool (expanding to 6) — same panel must scale automatically
- **Screen**: 5" KlipperScreen touchscreen (800×480 or similar)
- **Feeder system**: Per-tool BMG feeder steppers (`_tool{N}_feeder`) on a
  separate `feeder` MCU, controlled via Klipper macros

---

## Finalized Design Decisions

| Decision | Choice |
|----------|--------|
| Load button | **No** — unload only |
| Empty slot appearance | **Dimmed lane, no color swatch** |
| Active tool indicator | **Static red underline** on the active lane |
| Repo | **Separate new repo** (not folded into Filament_feeder) |
| Menu location | **Top-level main menu** button → opens filament lanes panel |

---

## File Structure (new repo)

```
klipperscreen-filament-lanes/
├── panels/
│   ├── filament_lanes.py          # main panel — vertical columns, data fetch, updates
│   └── filament_lanes_spoolman.py # sub-panel — Spoolman spool browser/assign
├── widgets/
│   └── spool_widget.py            # custom Gtk.DrawingArea spool graphic (or inline)
├── example_klipperscreen.conf     # KlipperScreen.conf snippet to copy in
├── install.sh                     # symlinks panels/ into ~/.KlipperScreen/panels/
└── README.md
```

### Installation path on printer
```
~/.KlipperScreen/panels/filament_lanes.py
~/.KlipperScreen/panels/filament_lanes_spoolman.py
~/.KlipperScreen/widgets/spool_widget.py   # or inline in filament_lanes.py
```

### Load button config flag
In `KlipperScreen.conf`:
```ini
[menu __main filament_lanes]
name: Filament Lanes
icon: filament
panel: filament_lanes
show_load_buttons: true    # omit or set false to hide Load buttons
```

---

## Data Sources

### Spool color / name / material
Moonraker database, namespace `lane_data`, key `tools`:

```
GET http://<moonraker>/server/database/item?namespace=lane_data&key=tools
```

Returns a dict keyed `"0"` through `"N"`:
```json
{
  "0": { "material": "PLA",  "color": "FF3D00", "vendor": "eSun",  "name": "eSun PLA+" },
  "1": { "material": "PETG", "color": "0047AB", "vendor": "Bambu", "name": "PETG HF"  },
  "2": { "material": "",     "color": "",        "vendor": "",      "name": ""          }
}
```

Color is a 6-char hex string **without** `#`. Empty string = no spool assigned.

Kept live by `spoolman-lane-sync` (systemd service, WebSocket-driven).
Repo: https://github.com/broncosis/spoolman-lane-sync

### Active tool
`printer.toolchanger.tool_number` — integer, from Moonraker printer objects

### Filament present at toolhead
`printer["filament_switch_sensor filament_sensor_at_tool{N}"].filament_detected`
— boolean per tool

### Tool count
Derived dynamically from the number of keys in `lane_data.tools`.
Do **not** hardcode — must work for 4, 5, 6+ tools.

---

## Klipper Macros (from feeder.cfg)

### Unload (the only button on the panel)
```
UNLOAD_ANY_TOOL T=<n> D=1400 S=30
```
Tip-shapes, retracts through nozzle, then drives `_tool{N}_feeder` stepper
backward `D` mm. Heats to 220°C if needed. Calls `_CHECK_READY` internally.

### Load (sensor-based) — for reference, not on panel
```
LOAD_ANY_TOOL T=<n> S=30 D=1360
```

### Load (fixed distance, no sensor) — for reference, not on panel
```
LOAD_ANY_TOOL_DIST T=<n> S=30 D=1400
```

### Safety guard
All macros call `_CHECK_READY` — aborts if not homed, QGL not applied, or
printing without pause. The panel should disable Unload buttons while printing
(i.e. when `printer.print_stats.state == "printing"` and not paused).

### Sensor naming convention
```
filament_switch_sensor filament_sensor_at_tool0
filament_switch_sensor filament_sensor_at_tool1
...
```

---

## Feeder Config Summary (feeder.cfg)

- **MCU**: `[mcu feeder]` — separate board via USB serial
- **Steppers**: `[extruder_stepper _tool{N}_feeder]` — BMG, 50:17 gear ratio
- **Belay tensioners**: `[belay tool{N}_belay]` — auto speed modulation,
  no UI interaction needed
- **Physical unload buttons**: `[gcode_button t{N}_unload_button]` — same
  `UNLOAD_ANY_TOOL` macro as the panel buttons

---

## Panel Design Spec

### Layout
- Single screen, no scrolling
- N equal-width **vertical columns** (one per tool), filling the screen width
- Columns scale automatically based on tool count

### Per-column content (top → bottom)
1. **Spool widget** — circular/oval `Gtk.DrawingArea` rendered with Cairo,
   filled with the hex color from `lane_data`. Grey outline only if no spool.
   Tapping the spool widget triggers a tool change (`T0`, `T1`, … raw gcode).
   See Spool Widget section below.
2. **Tool label** — "T0", "T1", etc.
3. **Spool info** — `name · material` (e.g. "eSun PLA+ · PLA").
   Omitted / greyed if empty.
4. **Assign spool button** — opens Spoolman browser sub-panel to pick a spool
   for this lane (see Sub-Panels section below).
5. **Unload button** — fires `UNLOAD_ANY_TOOL T={N} D=1400 S=30`.
   Disabled (insensitive) during active print.
6. **Load button** *(optional)* — fires `LOAD_ANY_TOOL_DIST T={N} S=30 D=1400`.
   Hidden by default; shown only when `show_load_buttons: true` is set in the
   panel's KlipperScreen.conf config block.

### Visual states

| State | Appearance |
|-------|------------|
| Active tool | Static red underline on the column |
| Filament loaded | Spool widget filled with color, info text at full opacity |
| No filament / empty slot | Spool widget grey outline, column dimmed (reduced opacity) |
| Printing (not paused) | Unload and Load buttons disabled/greyed |
| No Spoolman data | Graceful fallback — show tool label + status only, no crash |

---

## Sub-Panels

### Spoolman Browser (`filament_lanes_spoolman.py`)
Opened when the user taps **Assign spool** on any column.

- Lists all spools available in Spoolman
- Shows spool color, name, material, vendor
- Tapping a spool assigns it to the lane by writing to Moonraker database
  (`lane_data` namespace, `tools` key) and closes the sub-panel
- The parent panel refreshes lane data immediately after assignment
- "Clear" option to unassign the current spool from the lane

File location:
```
~/.KlipperScreen/panels/filament_lanes_spoolman.py
```

Spoolman API endpoint for listing spools:
```
GET http://<moonraker>/server/spoolman/spools
```
Returns spool objects including `id`, `filament.name`, `filament.material`,
`filament.vendor.name`, `filament.color_hex`.

---

## Spool Widget

Custom `Gtk.DrawingArea` subclass, drawn with Cairo.

### Visual design
- Circular or slightly oval shape (to suggest a spool face-on)
- Filled with the lane color when loaded
- Centre hub: small dark circle (like a spool core)
- Outer ring: slightly darker stroke of the fill color
- Empty/no spool: grey outline only, no fill

### Implementation approach
KlipperScreen's built-in Spoolman panel (`panels/spoolman.py`) already
colorizes an SVG spool icon using this pattern:
```python
# from KlipperScreen/panels/spoolman.py
loader = GdkPixbuf.PixbufLoader()
color = self.filament.color_hex if hasattr(self.filament, 'color_hex') else '000000'
loader.write(
    SpoolmanSpool._spool_icon.replace('var(--filament-color)', f'#{color}').encode()
)
loader.close()
self._icon = loader.get_pixbuf()
```

Options:
1. **Reuse KlipperScreen's `styles/spool.svg`** with color substitution via
   `GdkPixbuf.PixbufLoader` (same approach as `spoolman.py`) — simplest
2. **Cairo DrawingArea** — draw programmatically, more control over size/shape

Preference: try option 1 first (reuse existing SVG), fall back to Cairo if
the SVG path or substitution isn't reliable outside the main panel context.

---

## KlipperScreen Panel Architecture

### Base class
```python
from panels.base_panel import BasePanel  # or ScreenPanel in some versions
```

Current KlipperScreen uses `ScreenPanel` as the base for all panels:
```python
class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Filament Lanes")
        super().__init__(screen, title)
        # build UI here
```

### Useful inherited members
| Member | Purpose |
|--------|---------|
| `self._screen` | KlipperScreen main window |
| `self._printer` | Printer state object |
| `self._gtk` | KlippyGtk helper (buttons, images, etc.) |
| `self.ks_printer_cfg` | Per-printer KlipperScreen config |

### Sending GCode
```python
self._screen._send_action(None, "printer.gcode.script",
    {"script": f"UNLOAD_ANY_TOOL T={tool_n} D=1400 S=30"})
```

### Registering subscriptions (required for process_update to fire)
`process_update` only receives data for objects you explicitly subscribe to.
Do this in `__init__` after tool count is known:
```python
self.add_subscription("toolchanger")
for n in range(self.tool_count):
    self.add_subscription(f"filament_switch_sensor filament_sensor_at_tool{n}")
```
Without these calls, `process_update` will be invoked but `data` will never
contain toolchanger or sensor keys — updates silently do nothing.

### Listening for state updates
```python
def process_update(self, action, data):
    # called by KlipperScreen on Moonraker subscription events
    # action = "notify_status_update", data = dict of changed objects
    if "toolchanger" in data:
        active = data["toolchanger"].get("tool_number")
        if active is not None:
            self._update_active_tool(active)
    for n in range(self.tool_count):
        key = f"filament_switch_sensor filament_sensor_at_tool{n}"
        if key in data:
            detected = data[key].get("filament_detected")
            if detected is not None:
                self._update_sensor_state(n, detected)
```

### Fetching lane_data (not a printer object — needs HTTP)
`lane_data` lives in Moonraker's database, not in Klipper printer objects,
so it won't arrive via `process_update`. Fetch it explicitly:

```python
# On panel init
self._screen.apiclient.send_request(
    "server/database/item",
    params={"namespace": "lane_data", "key": "tools"},
    callback=self._on_lane_data_received
)

# Refresh strategy: poll on GLib timer every 10s
# Callback must return True or the timer fires once and stops.
# Store the source ID so it can be cancelled when the panel is torn down.
self._lane_data_timer = GLib.timeout_add_seconds(10, self._refresh_lane_data)

def _refresh_lane_data(self):
    self._fetch_lane_data()
    return True  # keep timer alive
```

---

## KlipperScreen.conf Entry

```ini
[menu __main filament_lanes]
name: Filament Lanes
icon: filament
panel: filament_lanes
```

Place this in `~/printer_data/config/KlipperScreen.conf` (or wherever your
KlipperScreen conf lives).

---

## Related Repos

| Repo | Purpose |
|------|---------|
| https://github.com/broncosis/Filament_feeder | Macros, feeder config, load/unload logic |
| https://github.com/broncosis/spoolman-lane-sync | Syncs Spoolman → Moonraker `lane_data` |
| https://github.com/broncosis/stealthchanger-backup | Bobby printer config backup |

---

## Implementation Notes & Gotchas

- `FORCE_MOVE` is used for feeder steppers (not `G1`) because they are
  `extruder_stepper` objects, not the primary extruder
- `_CHECK_READY` aborts if print is active and not paused — disable Unload
  buttons in the UI during printing rather than letting the macro error out
- Belay tensioners run automatically; no UI interaction needed
- `lane_data` color hex has **no leading `#`** — prepend it when passing to
  Cairo or SVG substitution
- KlipperScreen's existing `panels/spoolman.py` uses `styles/spool.svg` for
  its spool icon — worth reading that file to understand the color substitution
  pattern before writing `spool_widget.py`
- KlipperScreen custom panels live in `~/.KlipperScreen/panels/` (user
  override directory), not in the KlipperScreen install directory — changes
  there survive KlipperScreen updates
- **GLib timer cleanup**: `GLib.timeout_add_seconds` runs forever until
  explicitly stopped. Store the returned source ID and cancel it when the
  panel is deactivated, otherwise it fires on a torn-down object:
  ```python
  # in __init__:
  self._lane_data_timer = GLib.timeout_add_seconds(10, self._refresh_lane_data)

  # in panel teardown (check how other KlipperScreen panels handle this):
  if hasattr(self, "_lane_data_timer") and self._lane_data_timer:
      GLib.source_remove(self._lane_data_timer)
      self._lane_data_timer = None
  ```