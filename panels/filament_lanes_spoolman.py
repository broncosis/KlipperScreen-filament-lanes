import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GdkPixbuf
import logging

from panels.base_panel import ScreenPanel

logger = logging.getLogger("KlipperScreen")


def create_panel(*args, **kwargs):
    return Panel(*args, **kwargs)


class Panel(ScreenPanel):
    """
    Spoolman spool browser opened from the Filament Lanes panel.
    Lets the user pick a spool to assign to a specific lane, or clear the
    current assignment.  On confirm the lane_data namespace in Moonraker is
    updated and the panel closes.
    """

    def __init__(self, screen, title, lane=0, lane_data=None, **kwargs):
        title = title or _("Assign Spool")
        super().__init__(screen, title)

        self.lane = lane
        self.lane_data = dict(lane_data) if lane_data else {}
        self.spools = []

        self._build_ui()
        self._fetch_spools()

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        # Current assignment info + clear button
        current = self.lane_data.get(str(self.lane), {})
        cur_name = current.get("name") or _("None")
        header = Gtk.Label()
        header.set_markup(
            f"<b>T{self.lane}</b>  —  {GLib.markup_escape_text(cur_name)}"
        )
        header.set_halign(Gtk.Align.START)
        header.set_margin_start(8)
        root.pack_start(header, False, False, 4)

        clear_btn = self._gtk.Button("cancel", _("Clear Assignment"), "color2")
        clear_btn.connect("clicked", self._on_clear)
        root.pack_start(clear_btn, False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        root.pack_start(sep, False, False, 4)

        # Spool list inside a scrolled window
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._listbox.set_activate_on_single_click(True)
        scroll.add(self._listbox)
        root.pack_start(scroll, True, True, 0)

        # Loading spinner shown until fetch completes
        self._spinner_row = Gtk.ListBoxRow()
        self._spinner_row.set_activatable(False)
        spinner_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8
        )
        spinner_box.set_halign(Gtk.Align.CENTER)
        spinner_box.set_valign(Gtk.Align.CENTER)
        spinner_box.set_margin_top(16)
        spinner = Gtk.Spinner()
        spinner.start()
        spinner_box.pack_start(spinner, False, False, 0)
        spinner_box.pack_start(Gtk.Label(label=_("Loading spools…")), False, False, 0)
        self._spinner_row.add(spinner_box)
        self._listbox.add(self._spinner_row)

        self.content.pack_start(root, True, True, 0)
        self.content.show_all()

    # ------------------------------------------------------------------ #
    # Data fetch                                                           #
    # ------------------------------------------------------------------ #

    def _fetch_spools(self):
        # Moonraker proxies Spoolman at /server/spoolman/spools
        self._screen.apiclient.send_request(
            "server/spoolman/spools",
            params={},
            callback=self._on_spools_received
        )

    def _on_spools_received(self, result, **kwargs):
        if not result:
            logger.warning("filament_lanes_spoolman: spool fetch returned nothing")
            GLib.idle_add(self._show_error, _("Could not fetch spool list."))
            return

        # Result shape: {"result": [...spools...]} or just [...spools...]
        if isinstance(result, dict) and "result" in result:
            spools = result["result"]
        elif isinstance(result, list):
            spools = result
        else:
            spools = []

        if not isinstance(spools, list):
            logger.warning(
                "filament_lanes_spoolman: unexpected spools shape: %r", result
            )
            GLib.idle_add(self._show_error, _("Unexpected spool data format."))
            return

        self.spools = spools
        GLib.idle_add(self._populate_list)

    def _populate_list(self):
        # Remove spinner
        self._listbox.remove(self._spinner_row)

        if not self.spools:
            row = Gtk.ListBoxRow()
            row.set_activatable(False)
            lbl = Gtk.Label(label=_("No spools found in Spoolman."))
            lbl.set_margin_top(12)
            row.add(lbl)
            self._listbox.add(row)
            self._listbox.show_all()
            return

        for spool in self.spools:
            row = self._build_spool_row(spool)
            if row:
                self._listbox.add(row)

        self._listbox.show_all()

    def _build_spool_row(self, spool):
        filament = spool.get("filament") or {}
        name = filament.get("name") or _("Unknown")
        material = filament.get("material") or ""
        vendor_obj = filament.get("vendor") or {}
        vendor = vendor_obj.get("name") or ""
        color_hex = filament.get("color_hex") or ""
        spool_id = spool.get("id")

        if spool_id is None:
            return None

        row = Gtk.ListBoxRow()
        row.set_name(f"spool_row_{spool_id}")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.set_margin_top(4)
        box.set_margin_bottom(4)

        # Color swatch
        swatch = Gtk.DrawingArea()
        swatch.set_size_request(28, 28)
        if color_hex:
            try:
                r = int(color_hex[0:2], 16) / 255.0
                g = int(color_hex[2:4], 16) / 255.0
                b = int(color_hex[4:6], 16) / 255.0
                swatch.connect("draw", self._draw_swatch, r, g, b)
            except (ValueError, IndexError):
                swatch.connect("draw", self._draw_swatch, 0.5, 0.5, 0.5)
        else:
            swatch.connect("draw", self._draw_swatch, 0.5, 0.5, 0.5)
        box.pack_start(swatch, False, False, 0)

        # Text: name + material · vendor
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        name_lbl = Gtk.Label()
        name_lbl.set_markup(f"<b>{GLib.markup_escape_text(name)}</b>")
        name_lbl.set_halign(Gtk.Align.START)
        text_box.pack_start(name_lbl, False, False, 0)

        sub_parts = [p for p in [material, vendor] if p]
        if sub_parts:
            sub_lbl = Gtk.Label(
                label=" · ".join(sub_parts)
            )
            sub_lbl.set_halign(Gtk.Align.START)
            ctx = sub_lbl.get_style_context()
            ctx.add_class("dim-label")
            text_box.pack_start(sub_lbl, False, False, 0)

        box.pack_start(text_box, True, True, 0)
        row.add(box)

        # Store spool data on the row so the activate handler can retrieve it
        row._spool_data = {
            "name": name,
            "material": material,
            "vendor": vendor,
            "color": color_hex,
            "spool_id": spool_id,
        }
        row.connect("activate", self._on_row_activate)
        return row

    @staticmethod
    def _draw_swatch(widget, cr, r, g, b):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()
        radius = min(w, h) / 2.0
        cr.arc(w / 2, h / 2, radius - 1, 0, 2 * 3.14159)
        cr.set_source_rgb(r, g, b)
        cr.fill_preserve()
        cr.set_source_rgb(0.2, 0.2, 0.2)
        cr.set_line_width(1.5)
        cr.stroke()

    def _show_error(self, message):
        self._listbox.remove(self._spinner_row)
        row = Gtk.ListBoxRow()
        row.set_activatable(False)
        lbl = Gtk.Label(label=message)
        lbl.set_line_wrap(True)
        lbl.set_margin_top(12)
        row.add(lbl)
        self._listbox.add(row)
        self._listbox.show_all()

    # ------------------------------------------------------------------ #
    # Actions                                                              #
    # ------------------------------------------------------------------ #

    def _on_row_activate(self, row):
        self._assign(row._spool_data)

    def _on_clear(self, widget):
        empty = {"name": "", "material": "", "vendor": "", "color": ""}
        self._assign(empty)

    def _assign(self, spool_data):
        new_tools = dict(self.lane_data)
        new_tools[str(self.lane)] = {
            "name":     spool_data.get("name", ""),
            "material": spool_data.get("material", ""),
            "vendor":   spool_data.get("vendor", ""),
            "color":    spool_data.get("color", ""),
        }
        # Keep spool_id if present (informational only)
        if "spool_id" in spool_data and spool_data["spool_id"] is not None:
            new_tools[str(self.lane)]["spool_id"] = spool_data["spool_id"]

        self._save_and_close(new_tools)

    def _save_and_close(self, tools):
        # Write updated tools dict back to Moonraker's lane_data namespace.
        #
        # KlipperScreen's apiclient wraps moonraker-api; the exact signature for
        # a database write may vary by version.  We try send_request with
        # method="POST" first.  If your version of KlipperScreen doesn't support
        # that, replace this call with:
        #
        #   self._screen._send_action(None, "server.database.post_item", {
        #       "namespace": "lane_data", "key": "tools", "value": tools
        #   })
        #
        # Note: _send_action is fire-and-forget (no callback), which is fine here
        # because spoolman-lane-sync will re-sync Spoolman on its own schedule.
        try:
            self._screen.apiclient.send_request(
                "server/database/item",
                method="POST",
                params={"namespace": "lane_data", "key": "tools", "value": tools},
                callback=self._on_saved,
            )
        except TypeError:
            # Fallback: older apiclient may not accept `method` kwarg
            self._screen._send_action(None, "server.database.post_item", {
                "namespace": "lane_data",
                "key": "tools",
                "value": tools,
            })
            self._close()

    def _on_saved(self, result, **kwargs):
        GLib.idle_add(self._close)

    def _close(self):
        # Return to the filament lanes panel, which calls activate() and
        # re-fetches lane_data automatically.
        self._screen.remove_current_panel()
