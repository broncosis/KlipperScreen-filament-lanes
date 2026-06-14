import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GdkPixbuf, Gdk, Pango
import logging
import os

from panels.base_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen")

# Based on work by KlipperScreen Contributors (https://github.com/KlipperScreen/KlipperScreen)
# Original license: GPL v3
# Spool SVG color-substitution pattern adapted from panels/spoolman.py

# Minimal spool SVG used when KlipperScreen's own styles/spool.svg isn't found.
# Uses var(--filament-color) as a substitution target, same as KlipperScreen's
# own spool.svg, so the same replacement code works for both.
_FALLBACK_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="47" fill="var(--filament-color)" stroke="#33333388" stroke-width="3"/>
  <circle cx="50" cy="50" r="32" fill="none" stroke="#00000028" stroke-width="28"/>
  <circle cx="50" cy="50" r="15" fill="#2a2a2a" stroke="#33333388" stroke-width="2"/>
</svg>"""

# CSS injected once to colour the active-tool indicator bar.
# Guarded by a class variable so it only runs once across panel visits.
_CSS_INJECTED = False
_INDICATOR_CSS = b"""
.lane-active-indicator { background-color: #CC0000; }
"""


def create_panel(*args):
    return Panel(*args)


class Panel(ScreenPanel):

    def __init__(self, screen, title, **kwargs):
        title = title or _("Filament Lanes")
        super().__init__(screen, title)

        self.tool_count = 0
        self.lane_data = {}          # str(n) -> {color, name, material, vendor, spool_id}
        self.active_tool = None
        self.sensor_states = {}      # int(n) -> bool
        self._is_printing = False
        self._pending_spool_ids = {} # n -> spool_id, in-flight during Spoolman fetch

        # Per-column widget references
        self._col_wraps = {}         # n -> outer Gtk.Box (wrap + indicator)
        self._col_boxes = {}         # n -> inner Gtk.Box (can be dimmed)
        self._active_indicators = {} # n -> Gtk.Box (red bar)
        self._spool_images = {}      # n -> Gtk.Image inside the spool button
        self._info_labels = {}       # n -> Gtk.Label
        self._unload_btns = {}       # n -> Gtk.Button
        self._load_btns = {}         # n -> Gtk.Button (only when show_load_buttons)

        # KlipperScreen.conf option — set show_load_buttons: true to reveal Load
        cfg = self.ks_printer_cfg
        raw = cfg.get("show_load_buttons", "false") if cfg else "false"
        self.show_load_buttons = raw.strip().lower() in ("true", "1", "yes")

        global _CSS_INJECTED
        if not _CSS_INJECTED:
            provider = Gtk.CssProvider()
            provider.load_from_data(_INDICATOR_CSS)
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(), provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            _CSS_INJECTED = True

        self._spool_svg_template = self._load_spool_svg()

        self._build_placeholder()
        self._fetch_data()

    # ------------------------------------------------------------------ #
    # SVG template loader                                                  #
    # ------------------------------------------------------------------ #

    def _load_spool_svg(self):
        # Prefer KlipperScreen's own spool.svg so our spools match theirs.
        try:
            from panels.spoolman import SpoolmanSpool
            tpl = getattr(SpoolmanSpool, "_spool_icon", None)
            if tpl:
                return tpl.encode() if isinstance(tpl, str) else tpl
        except Exception:
            pass

        candidates = []
        if hasattr(self._screen, "klipperscreendir"):
            candidates.append(
                os.path.join(self._screen.klipperscreendir, "styles", "spool.svg")
            )
        candidates += [
            os.path.expanduser("~/KlipperScreen/styles/spool.svg"),
            "/home/pi/KlipperScreen/styles/spool.svg",
        ]
        for path in candidates:
            if os.path.isfile(path):
                try:
                    with open(path, "rb") as f:
                        return f.read()
                except Exception:
                    pass

        return _FALLBACK_SVG

    # ------------------------------------------------------------------ #
    # Data layer — Spoolman + Klipper save_variables                       #
    # ------------------------------------------------------------------ #

    def _fetch_data(self):
        """
        Primary data fetch.  Reads t{N}__spool_id from Klipper save_variables,
        then fetches spool details from Spoolman via Moonraker.  No dependency
        on spoolman-lane-sync or any external sync service.
        """
        tool_count = self._detect_tool_count()
        if tool_count == 0:
            logger.warning("filament_lanes: could not determine tool count")
            return

        if tool_count != self.tool_count:
            self.tool_count = tool_count
            self._register_subscriptions()

        save_vars = self._printer.get_stat("save_variables") if self._printer else {}
        variables = (save_vars or {}).get("variables", {})

        spool_ids = {}
        for n in range(tool_count):
            sid = variables.get(f"t{n}__spool_id")
            if sid is not None:
                try:
                    sid_int = int(sid)
                    if sid_int > 0:
                        spool_ids[n] = sid_int
                except (ValueError, TypeError):
                    pass

        # Reset lane data to empty slots; Spoolman callback fills them in.
        self.lane_data = {
            str(n): {"name": "", "material": "", "vendor": "", "color": ""}
            for n in range(tool_count)
        }

        if not spool_ids:
            GLib.idle_add(self._build_ui)
            return

        self._pending_spool_ids = spool_ids
        self._screen.apiclient.send_request(
            "server/spoolman/spools",
            params={},
            callback=self._on_spoolman_received
        )
        # Build the UI immediately with empty slots; spool data fills in when
        # the Spoolman response arrives.
        GLib.idle_add(self._build_ui)

    def _on_spoolman_received(self, result, **kwargs):
        if isinstance(result, dict) and "result" in result:
            spools = result["result"]
        elif isinstance(result, list):
            spools = result
        else:
            spools = []

        spool_by_id = {s["id"]: s for s in spools if "id" in s}

        for n, sid in self._pending_spool_ids.items():
            if sid not in spool_by_id:
                continue
            filament = spool_by_id[sid].get("filament") or {}
            vendor = (filament.get("vendor") or {}).get("name", "")
            self.lane_data[str(n)] = {
                "name":     filament.get("name", ""),
                "material": filament.get("material", ""),
                "vendor":   vendor,
                "color":    filament.get("color_hex", ""),
                "spool_id": sid,
            }

        self._pending_spool_ids = {}
        GLib.idle_add(self._update_all_lanes)

    def _detect_tool_count(self):
        """Count tools by probing extruder objects (extruder, extruder1, …)."""
        if not self._printer:
            return 0
        if not self._printer.get_stat("extruder"):
            return 0
        count = 1
        while self._printer.get_stat(f"extruder{count}"):
            count += 1
        return count

    def _register_subscriptions(self):
        self.add_subscription("toolchanger")
        self.add_subscription("print_stats")
        self.add_subscription("save_variables")
        for n in range(self.tool_count):
            self.add_subscription(
                f"filament_switch_sensor filament_sensor_at_tool{n}"
            )

        # Seed live state from whatever the printer object already has cached.
        if not self._printer:
            return
        tc = self._printer.get_stat("toolchanger")
        if tc:
            self.active_tool = tc.get("tool_number")
        ps = self._printer.get_stat("print_stats")
        if ps:
            self._is_printing = ps.get("state") == "printing"
        for n in range(self.tool_count):
            key = f"filament_switch_sensor filament_sensor_at_tool{n}"
            sensor = self._printer.get_stat(key)
            if sensor:
                self.sensor_states[n] = sensor.get("filament_detected", False)

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _clear_content(self):
        for child in self.content.get_children():
            self.content.remove(child)
        self._col_wraps.clear()
        self._col_boxes.clear()
        self._active_indicators.clear()
        self._spool_images.clear()
        self._info_labels.clear()
        self._unload_btns.clear()
        self._load_btns.clear()

    def _build_placeholder(self):
        self._clear_content()
        lbl = Gtk.Label(label=_("Loading spool data…"))
        lbl.set_valign(Gtk.Align.CENTER)
        lbl.set_halign(Gtk.Align.CENTER)
        self.content.pack_start(lbl, True, True, 0)
        self.content.show_all()

    def _build_ui(self):
        self._clear_content()

        if self.tool_count == 0:
            lbl = Gtk.Label(
                label=_("No tools detected.\n"
                        "Check that extruder objects are configured in Klipper.")
            )
            lbl.set_line_wrap(True)
            lbl.set_justify(Gtk.Justification.CENTER)
            lbl.set_valign(Gtk.Align.CENTER)
            self.content.pack_start(lbl, True, True, 0)
            self.content.show_all()
            return

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        outer.set_homogeneous(True)  # equal-width columns

        for n in range(self.tool_count):
            outer.pack_start(self._build_column(n), True, True, 0)

        self.content.pack_start(outer, True, True, 0)
        self.content.show_all()

        self._update_all_lanes()

    def _build_column(self, n):
        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Active-tool indicator bar (coloured via CSS class)
        indicator = Gtk.Box()
        indicator.set_size_request(-1, 5)
        self._active_indicators[n] = indicator
        wrap.pack_start(indicator, False, False, 0)

        # Inner content box (opacity dimmed when slot is empty)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(4)
        box.set_margin_end(4)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        wrap.pack_start(box, True, True, 0)

        # Spool image — tapping fires a tool change (T0, T1, …)
        spool_btn = Gtk.Button()
        spool_btn.set_relief(Gtk.ReliefStyle.NONE)
        spool_btn.set_halign(Gtk.Align.CENTER)
        spool_btn.connect("clicked", self._on_spool_clicked, n)
        spool_img = Gtk.Image()
        spool_btn.add(spool_img)
        box.pack_start(spool_btn, False, False, 0)
        self._spool_images[n] = spool_img

        # Tool label
        tool_lbl = Gtk.Label()
        tool_lbl.set_markup(f"<b>T{n}</b>")
        box.pack_start(tool_lbl, False, False, 0)

        # Spool info (name · material)
        info_lbl = Gtk.Label(label="")
        info_lbl.set_line_wrap(True)
        info_lbl.set_justify(Gtk.Justification.CENTER)
        info_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        info_lbl.set_max_width_chars(14)
        box.pack_start(info_lbl, False, False, 0)
        self._info_labels[n] = info_lbl

        # Assign spool button
        assign_btn = self._gtk.Button("filament", _("Assign"), "color1")
        assign_btn.connect("clicked", self._on_assign_clicked, n)
        box.pack_start(assign_btn, False, False, 0)

        # Unload button
        unload_btn = self._gtk.Button("arrow-down", _("Unload"), "color2")
        unload_btn.connect("clicked", self._on_unload_clicked, n)
        box.pack_start(unload_btn, False, False, 0)
        self._unload_btns[n] = unload_btn

        # Optional load button (hidden by default)
        if self.show_load_buttons:
            load_btn = self._gtk.Button("arrow-up", _("Load"), "color3")
            load_btn.connect("clicked", self._on_load_clicked, n)
            box.pack_start(load_btn, False, False, 0)
            self._load_btns[n] = load_btn

        self._col_wraps[n] = wrap
        self._col_boxes[n] = box
        return wrap

    # ------------------------------------------------------------------ #
    # State update helpers                                                 #
    # ------------------------------------------------------------------ #

    def _update_all_lanes(self):
        for n in range(self.tool_count):
            self._update_lane(n)
        self._update_active_indicator()
        self._update_print_buttons()

    def _update_lane(self, n):
        data = self.lane_data.get(str(n), {})
        color = data.get("color", "")
        name = data.get("name", "")
        material = data.get("material", "")

        has_spool = bool(color or name or material)
        filament_detected = self.sensor_states.get(n, False)

        self._render_spool(n, color if has_spool else None)

        info = self._info_labels[n]
        if has_spool:
            parts = [p for p in [name, material] if p]
            info.set_text(" · ".join(parts) if parts else "—")
        else:
            info.set_text(_("Empty"))

        dim = not has_spool and not filament_detected
        self._col_boxes[n].set_opacity(0.35 if dim else 1.0)

    def _render_spool(self, n, color_hex):
        img = self._spool_images[n]

        # Scale spool icon to fit the column width.
        col_px = max(1, self.content.get_allocated_width() // max(1, self.tool_count))
        size = max(40, min(96, int(col_px * 0.55)))

        svg = self._spool_svg_template
        if color_hex:
            svg = svg.replace(b"var(--filament-color)", f"#{color_hex}".encode())
        else:
            svg = svg.replace(b"var(--filament-color)", b"#808080")

        try:
            loader = GdkPixbuf.PixbufLoader()
            loader.set_size(size, size)
            loader.write(svg)
            loader.close()
            img.set_from_pixbuf(loader.get_pixbuf())
            return
        except Exception as e:
            logger.warning("filament_lanes: spool render failed T%d: %s", n, e)

        # Fallback: KlipperScreen's built-in filament icon
        try:
            icon = self._gtk.Image("filament", size)
            if hasattr(icon, "get_pixbuf"):
                img.set_from_pixbuf(icon.get_pixbuf())
        except Exception:
            pass

    def _update_active_indicator(self):
        for n, indicator in self._active_indicators.items():
            ctx = indicator.get_style_context()
            if n == self.active_tool:
                ctx.add_class("lane-active-indicator")
            else:
                ctx.remove_class("lane-active-indicator")

    def _update_print_buttons(self):
        sensitive = not self._is_printing
        for btn in self._unload_btns.values():
            btn.set_sensitive(sensitive)
        for btn in self._load_btns.values():
            btn.set_sensitive(sensitive)

    # ------------------------------------------------------------------ #
    # KlipperScreen subscription callbacks                                 #
    # ------------------------------------------------------------------ #

    def process_update(self, action, data):
        if action != "notify_status_update":
            return

        if "toolchanger" in data:
            active = data["toolchanger"].get("tool_number")
            if active is not None:
                self.active_tool = active
                self._update_active_indicator()

        if "print_stats" in data:
            state = data["print_stats"].get("state")
            if state is not None:
                self._is_printing = state == "printing"
                self._update_print_buttons()

        # Re-fetch Spoolman data when spool assignments change in save_variables.
        if "save_variables" in data:
            self._fetch_data()
            return

        for n in range(self.tool_count):
            key = f"filament_switch_sensor filament_sensor_at_tool{n}"
            if key in data:
                detected = data[key].get("filament_detected")
                if detected is not None:
                    self.sensor_states[n] = detected
                    self._update_lane(n)

    # ------------------------------------------------------------------ #
    # Panel lifecycle                                                      #
    # ------------------------------------------------------------------ #

    def activate(self):
        # Refresh every time the panel comes to the foreground, including
        # returning from the assign sub-panel after a spool change.
        self._fetch_data()

    # ------------------------------------------------------------------ #
    # Button handlers                                                      #
    # ------------------------------------------------------------------ #

    def _on_spool_clicked(self, widget, n):
        self._screen._send_action(widget, "printer.gcode.script",
                                  {"script": f"T{n}"})

    def _on_assign_clicked(self, widget, n):
        self._screen.show_panel(
            "filament_lanes_spoolman",
            title=_(f"Assign Spool — T{n}"),
            lane=n,
            current_name=self.lane_data.get(str(n), {}).get("name", ""),
        )

    def _on_unload_clicked(self, widget, n):
        self._screen._send_action(widget, "printer.gcode.script",
                                  {"script": f"UNLOAD_ANY_TOOL T={n} D=1400 S=30"})

    def _on_load_clicked(self, widget, n):
        self._screen._send_action(widget, "printer.gcode.script",
                                  {"script": f"LOAD_ANY_TOOL_DIST T={n} S=30 D=1400"})
