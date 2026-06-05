import sys
import os
import math
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QSizePolicy, QFrame, QCheckBox,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPainter, QPen, QColor

from osdagbridge.core.utils.common import *
from osdagbridge.core.bridge_types.plate_girder.ui_fields_additional_input import CROSS_BRACING_DETAILS_SCHEMA
from osdagbridge.desktop.ui.utils.cad_palette import CAD_DIMENSION
from osdagbridge.desktop.ui.widgets.section_viewer import SectionPreviewWidget, SectionCatalog
from osdagbridge.desktop.ui.widgets.placeholder_section_preview import PlaceholderSectionPreviewWidget


class CrossBracingDetailsTab(QWidget):
    """
    Cross-Bracing Details logic/state widget.

    All Qt widgets are built by UIBuilder and located at runtime via
    self.findChild() using KEY_* constants as objectNames.
    finish_init() seeds default state — it must be called exactly once
    after UIBuilder has finished constructing child widgets.
    """

    def __init__(self, parent=None, additional_input_instance=None):
        super().__init__(parent)
        self.additional_input_instance = additional_input_instance
        self.catalog = SectionCatalog()
        self._girder_details_tab = None
        self._global_design_mode = "Optimized"

        self._combo_width  = 190
        self._label_col_width = 260

        self._state_by_member_key: dict[str, dict] = {}
        self._active_member_key: str | None = None
        self._selection_sync_guard  = False
        self._updating_chord_rules  = False

        # Hidden compatibility combo (no UIBuilder parity needed)
        self.member_id_combo = QComboBox()
        self.member_id_combo.setVisible(False)

    # ── findChild shorthand ────────────────────────────────────────────────────

    def _w(self, widget_type, key):
        """Return the first child widget of *widget_type* whose objectName == *key*."""
        return self.findChild(widget_type, key)

    # ── Convenience properties (read-only, via findChild) ─────────────────────

    @property
    def _select_girders_combo(self) -> QComboBox | None:
        return self._w(QComboBox, KEY_MP_CB_SELECT_GIRDERS)

    @property
    def _no_of_cross_bracing_input(self) -> QLineEdit | None:
        return self._w(QLineEdit, KEY_MP_CB_COUNT)

    @property
    def _member_id_display(self) -> QLineEdit | None:
        return self._w(QLineEdit, KEY_MP_CB_MEMBER_ID)

    @property
    def _spacing_input(self) -> QLineEdit | None:
        return self._w(QLineEdit, KEY_MP_CB_SPACING)

    @property
    def _bracing_type_combo(self) -> QComboBox | None:
        return self._w(QComboBox, KEY_MP_CB_TYPE)

    @property
    def _connection_type_combo(self) -> QComboBox | None:
        return self._w(QComboBox, KEY_MP_CB_CONNECTION_TYPE)

    @property
    def _bracing_section_type_combo(self) -> QComboBox | None:
        return self._w(QComboBox, KEY_MP_CB_SECTION_TYPE)

    @property
    def _bracing_section_combo(self) -> QComboBox | None:
        return self._w(QComboBox, KEY_MP_CB_SECTION_DESIGNATION)

    @property
    def _top_chord_checkbox(self) -> QCheckBox | None:
        return self._w(QCheckBox, KEY_MP_CB_TOP_CHORD_ENABLED)

    @property
    def _top_chord_type_combo(self) -> QComboBox | None:
        return self._w(QComboBox, KEY_MP_CB_TOP_CHORD_SECTION_TYPE)

    @property
    def _top_chord_size_combo(self) -> QComboBox | None:
        return self._w(QComboBox, KEY_MP_CB_TOP_CHORD_SECTION_DESIG)

    @property
    def _bottom_chord_checkbox(self) -> QCheckBox | None:
        return self._w(QCheckBox, KEY_MP_CB_BOTTOM_CHORD_ENABLED)

    @property
    def _bottom_chord_type_combo(self) -> QComboBox | None:
        return self._w(QComboBox, KEY_MP_CB_BOTTOM_CHORD_SECTION_TYPE)

    @property
    def _bottom_chord_size_combo(self) -> QComboBox | None:
        return self._w(QComboBox, KEY_MP_CB_BOTTOM_CHORD_SECTION_DESIG)

    @property
    def _bracing_layout_widget(self):
        return self._w(QWidget, KEY_MP_CB_LAYOUT_CAD)

    @property
    def _bracing_preview_label(self) -> PlaceholderSectionPreviewWidget | None:
        return self._w(PlaceholderSectionPreviewWidget, KEY_MP_CB_SECTION_PREVIEW_CAD)

    @property
    def _top_chord_preview_label(self) -> PlaceholderSectionPreviewWidget | None:
        return self._w(PlaceholderSectionPreviewWidget, KEY_MP_CB_TOP_CHORD_PREVIEW_CAD)

    @property
    def _bottom_chord_preview_label(self) -> PlaceholderSectionPreviewWidget | None:
        return self._w(PlaceholderSectionPreviewWidget, KEY_MP_CB_BOTTOM_CHORD_PREVIEW_CAD)

    @property
    def _top_chord_preview_box(self) -> QWidget | None:
        return self._w(QWidget, "top_chord_preview_box")

    @property
    def _bottom_chord_preview_box(self) -> QWidget | None:
        return self._w(QWidget, "bottom_chord_preview_box")

    def finish_init(self) -> None:
        """
        Seed initial state after UIBuilder has finished constructing children.
        Signal connections are handled by the schema's on_change / on_text_changed
        keys — no manual .connect() calls are needed here.
        """
        self._populate_designations()
        self._on_design_changed(self._global_design_mode)
        self.refresh_girder_options()
        self._load_state_for_current_member()
        self._on_bracing_layout_changed()

    # ── Schema-wired signal wrappers ───────────────────────────────────────────
    # These thin wrappers satisfy the single on_change entry in the schema while
    # still fanning out to the multiple internal handlers they need to trigger.

    def _on_bracing_type_combo_changed(self, *_args) -> None:
        """Called by schema on_change for KEY_MP_CB_TYPE."""
        self._update_previews()
        self._on_bracing_layout_changed()

    def _on_bracing_section_type_changed(self, *_args) -> None:
        """Called by schema on_change for KEY_MP_CB_SECTION_TYPE."""
        label = self._bracing_section_type_combo.currentText() if self._bracing_section_type_combo else ""
        self._on_bracing_type_changed(label)

    # ── Count / Spacing auto-calculation ──────────────────────────────────────

    def _on_count_changed(self, *_args) -> None:
        self._sync_span_to_additional_input()
        self._recalculate_spacing()
        try:
            self._refresh_member_id_display()
        except Exception:
            pass

    def _on_field_editing(self, current_text: str, key: str) -> None:
        self._sync_span_to_additional_input()
        ai = getattr(self, "additional_input_instance", None)
        if ai is not None and hasattr(ai, "_on_field_editing"):
            ai._on_field_editing(current_text, key)

    def _on_field_edited(self, key: str, widget) -> None:
        self._sync_span_to_additional_input()
        ai = getattr(self, "additional_input_instance", None)
        if ai is not None and hasattr(ai, "_on_field_edited"):
            ai._on_field_edited(key, widget)
        if key == KEY_MP_CB_COUNT:
            self._recalculate_spacing()
            self._refresh_member_id_display()

    def _recalculate_spacing(self) -> None:
        ai = getattr(self, "additional_input_instance", None)
        span_m = ai.working_input_dict.get(KEY_SPAN) if ai else None
        try:
            span_m = float(span_m)
        except (ValueError, TypeError):
            span_m = None

        count_input = self._no_of_cross_bracing_input
        if count_input is None:
            return

        count_text = (count_input.text() or "").strip()
        if not count_text or span_m is None:
            self._clear_spacing()
            return
        try:
            count = int(count_text)
        except (ValueError, TypeError):
            self._clear_spacing()
            return
        if count <= 0:
            self._clear_spacing()
            return
        spacing = span_m / (count + 1)
        spacing_w = self._spacing_input
        if spacing_w is not None:
            spacing_w.blockSignals(True)
            spacing_w.setText(f"{spacing:.2f}")
            spacing_w.blockSignals(False)

    def _clear_spacing(self) -> None:
        spacing_w = self._spacing_input
        if spacing_w is not None:
            spacing_w.blockSignals(True)
            spacing_w.setText("")
            spacing_w.blockSignals(False)

    def _on_span_or_spacing_changed(self, *_args) -> None:
        self._sync_span_to_additional_input()
        self._recalculate_spacing()
        try:
            self._refresh_member_id_display()
        except Exception:
            pass

    def _sync_span_to_additional_input(self) -> None:
        ai = getattr(self, "additional_input_instance", None)
        if ai is None or not hasattr(ai, "working_input_dict"):
            return
        if KEY_SPAN not in ai.working_input_dict:
            return
        try:
            ai.working_input_dict[KEY_SPAN] = float(ai.working_input_dict[KEY_SPAN])
        except (ValueError, TypeError):
            pass

    # ── Member ID helpers ──────────────────────────────────────────────────────

    def _current_member_id(self) -> str:
        return f"B{self._pair_index()}M1"

    def _current_member_key(self) -> str:
        sg = self._select_girders_combo
        pair   = (sg.currentText() or "").strip() if sg else ""
        member = self._current_member_id()
        return f"{pair}::{member}".strip("::")

    @staticmethod
    def _normalize_member_id(text: str, pair_index: int | None = None) -> str:
        raw   = (text or "").strip().replace(" ", "")
        if not raw:
            return ""
        upper = raw.upper()
        if "M" in upper and upper.startswith("B"):
            return upper
        if upper.startswith("B") and "TO" in upper:
            if pair_index is not None:
                return f"B{pair_index}M1"
            try:
                after_b  = upper[1:]
                pair_num = int("".join(ch for ch in after_b if ch.isdigit()) or 0)
            except Exception:
                pair_num = 0
            return f"B{pair_num}M1" if pair_num > 0 else ""
        if upper.startswith("B") and "-" in upper:
            try:
                b_part, m_part = upper.split("-", 1)
                pair_num = int(b_part[1:])
                mem_num  = int("".join(ch for ch in m_part if ch.isdigit()))
                return f"B{pair_num}M{mem_num}"
            except Exception:
                return ""
        if pair_index is not None:
            try:
                mem_num = int("".join(ch for ch in upper if ch.isdigit()))
                if mem_num > 0:
                    return f"B{pair_index}M{mem_num}"
            except Exception:
                pass
        return ""

    @staticmethod
    def _member_number(text: str) -> int | None:
        text = (text or "").strip().upper().replace(" ", "")
        if not text:
            return None
        if text.startswith("B") and "M" in text:
            try:
                _b, m = text.split("M", 1)
                return int("".join(ch for ch in m if ch.isdigit()) or 0) or None
            except Exception:
                return None
        if text.startswith("B") and "-" in text:
            try:
                _b, m = text.split("-", 1)
                return int("".join(ch for ch in m if ch.isdigit()) or 0) or None
            except Exception:
                return None
        return None

    def _pair_index(self) -> int:
        sg = self._select_girders_combo
        idx = sg.currentIndex() if sg else -1
        return max(0, int(idx)) + 1

    def _get_total_span_m(self) -> float | None:
        tab = self._girder_details_tab
        if tab is None:
            return None
        getter = getattr(tab, "_get_total_span", None)
        if getter is None or not callable(getter):
            return None
        try:
            span = getter()
        except Exception:
            return None
        try:
            span = float(span)
        except Exception:
            return None
        return span if span > 0 else None

    def _get_cross_bracing_spacing_m(self) -> float | None:
        spacing_w = self._spacing_input
        if spacing_w is None:
            return None
        text = (spacing_w.text() or "").strip()
        if not text:
            return None
        try:
            spacing_m = float(text)
        except Exception:
            return None
        return spacing_m if spacing_m > 0 else None

    def _cross_bracing_member_count(self) -> int:
        count_w = self._no_of_cross_bracing_input
        if count_w is None:
            return 1
        count_text = (count_w.text() or "").strip()
        try:
            return max(1, int(count_text))
        except (ValueError, TypeError):
            return 1

    def _member_ids_for_pair(self, pair_index: int) -> list[str]:
        count = self._cross_bracing_member_count()
        return [f"B{pair_index}M{i}" for i in range(1, count + 1)]

    def _refresh_member_id_display(self) -> None:
        pair_index = self._pair_index()
        count      = self._cross_bracing_member_count()
        member_id  = f"B{pair_index}M1"
        display_text = member_id if count <= 1 else f"B{pair_index}M1 to B{pair_index}M{count}"

        mid_w = self._member_id_display
        if mid_w is not None:
            prev = mid_w.blockSignals(True)
            try:
                mid_w.setText(display_text)
            finally:
                mid_w.blockSignals(prev)

        block = self.member_id_combo.blockSignals(True)
        try:
            self.member_id_combo.clear()
            self.member_id_combo.addItems([member_id])
            self.member_id_combo.setCurrentIndex(0)
        finally:
            self.member_id_combo.blockSignals(block)

    # ── Schema introspection helpers ──────────────────────────────────────────
    # These iterate CROSS_BRACING_DETAILS_SCHEMA for state management and
    # collect/restore — they are NOT involved in building UI widgets.

    def _default_member_state(self) -> dict:
        state: dict[str, object] = {}
        for field in self._schema_fields("section_inputs"):
            field_id  = str(field.get("id")   or "").strip()
            if not field_id:
                continue
            field_type = str(field.get("type") or "line").strip().lower()
            if field_type in {"combo", "combo_dynamic"}:
                choices  = self._schema_choices(field_id, [])
                fallback = choices[0] if choices else ""
                state[field_id] = str(self._schema_default(field_id, fallback))
            elif field_type == "checkbox":
                state[field_id] = bool(self._schema_default(field_id, False))
            else:
                state[field_id] = str(self._schema_default(field_id, ""))

        for field in self._schema_fields("overview"):
            field_id = str(field.get("id") or "").strip()
            if not field_id or field_id in ("select_girders", "member_id"):
                continue
            state[field_id] = str(self._schema_default(field_id, ""))

        state["bracing_section_data"]  = None
        state["bracing_section_text"]  = ""
        state["top_chord_data"]        = None
        state["top_chord_text"]        = ""
        state["bottom_chord_data"]     = None
        state["bottom_chord_text"]     = ""
        return state

    def _schema_fields(self, section: str) -> list[dict]:
        direct = CROSS_BRACING_DETAILS_SCHEMA.get(section, [])
        if isinstance(direct, list):
            return [dict(f) for f in direct if isinstance(f, dict)]

        title_map = {
            "overview":       "Overview",
            "section_inputs": "Section Inputs",
        }
        wanted_title = title_map.get(section, "")
        for sec in CROSS_BRACING_DETAILS_SCHEMA.get("sections", []):
            if not isinstance(sec, dict):
                continue
            if str(sec.get("title") or "").strip() != wanted_title:
                continue
            out: list[dict] = []
            for row in sec.get("rows", []) or []:
                if not isinstance(row, dict):
                    continue
                for field in row.get("fields", []) or []:
                    if isinstance(field, dict):
                        out.append(dict(field))
            return out
        return []

    def _schema_field_def(self, field_id: str) -> dict:
        target = str(field_id or "").strip()
        if not target:
            return {}
        for section in ("overview", "section_inputs"):
            for field in self._schema_fields(section):
                if str(field.get("id") or "").strip() == target:
                    return field
        return {}

    def _schema_label(self, field_id: str, fallback: str) -> str:
        field = self._schema_field_def(field_id)
        label = field.get("label")
        return str(label if label is not None else fallback)

    def _schema_choices(self, field_id: str, fallback: list[str]) -> list[str]:
        field   = self._schema_field_def(field_id)
        choices = field.get("choices") or fallback
        return [str(c) for c in choices]

    def _schema_default(self, field_id: str, fallback):
        field = self._schema_field_def(field_id)
        return field.get("default", fallback)

    def _widget_for_field(self, field_id: str):
        """Resolve a schema field widget by its objectName (== field id)."""
        key = str(field_id or "").strip()
        if key:
            from PySide6.QtWidgets import QWidget as _QW
            return self.findChild(_QW, key)
        return None

    # ── State snapshot / restore ───────────────────────────────────────────────

    def _snapshot_current_state(self) -> dict:
        from PySide6.QtWidgets import QCheckBox as _CB, QComboBox as _Combo, QLineEdit as _LE

        state: dict[str, object] = {}
        for field in self._schema_fields("section_inputs"):
            field_id = str(field.get("id") or "").strip()
            if not field_id:
                continue
            widget = self._widget_for_field(field_id)
            if isinstance(widget, _CB):
                state[field_id] = widget.isChecked()
            elif isinstance(widget, _Combo):
                state[field_id] = widget.currentText()
            elif isinstance(widget, _LE):
                state[field_id] = widget.text()

        for field in self._schema_fields("overview"):
            field_id = str(field.get("id") or "").strip()
            if not field_id or field_id in ("select_girders", "member_id"):
                continue
            widget = self._widget_for_field(field_id)
            if isinstance(widget, _LE):
                state[field_id] = widget.text()
            elif isinstance(widget, _Combo):
                state[field_id] = widget.currentText()

        bsc = self._bracing_section_combo
        tcs = self._top_chord_size_combo
        bcs = self._bottom_chord_size_combo

        state["design"]               = self._global_design_mode
        state["bracing_section_data"] = bsc.currentData() if bsc else None
        state["bracing_section_text"] = bsc.currentText() if bsc else ""
        state["top_chord_data"]       = tcs.currentData()   if tcs   else None
        state["top_chord_text"]       = tcs.currentText()   if tcs   else ""
        state["bottom_chord_data"]    = bcs.currentData() if bcs else None
        state["bottom_chord_text"]    = bcs.currentText() if bcs else ""
        return state

    def _store_current_member_state(self) -> None:
        if self._select_girders_combo is None:
            return
        key = self._active_member_key or self._current_member_key()
        if not key:
            return
        self._state_by_member_key[key] = self._snapshot_current_state()
        self._active_member_key = key

    def _set_combo_to_data_or_text(self, combo: QComboBox, desired_data, desired_text: str) -> None:
        if desired_data is not None:
            idx = combo.findData(desired_data)
            if idx >= 0:
                combo.setCurrentIndex(idx)
                return
        if desired_text:
            idx = combo.findText(desired_text)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _apply_state(self, state: dict) -> None:
        def _get(full_key, short_key, default=None):
            return state.get(full_key, state.get(short_key, default))

        bt = self._bracing_type_combo
        if bt:
            bt.setCurrentText(
                _get(KEY_MP_CB_TYPE, "bracing_type") or bt.currentText()
            )

        ct = self._connection_type_combo
        if ct is not None:
            ct.setCurrentText(
                _get(KEY_MP_CB_CONNECTION_TYPE, "connection_type")
                or ct.currentText()
            )

        bst = self._bracing_section_type_combo
        if bst:
            bst.setCurrentText(
                _get(KEY_MP_CB_SECTION_TYPE, "bracing_section_type")
                or bst.currentText()
            )
        bsc = self._bracing_section_combo
        if bst and bsc:
            self._update_designations_for(bsc, bst.currentText())
            self._set_combo_to_data_or_text(
                bsc,
                state.get("bracing_section_data"),
                state.get("bracing_section_text") or "",
            )

        tcc = self._top_chord_checkbox
        if tcc:
            tcc.setChecked(
                bool(_get(KEY_MP_CB_TOP_CHORD_ENABLED, "top_chord_enabled", False))
            )
        tct = self._top_chord_type_combo
        if tct:
            tct.setCurrentText(
                _get(KEY_MP_CB_TOP_CHORD_SECTION_TYPE, "top_chord_type")
                or tct.currentText()
            )
        tcs = self._top_chord_size_combo
        if tct and tcs:
            self._update_designations_for(tcs, tct.currentText())
            self._set_combo_to_data_or_text(
                tcs,
                state.get("top_chord_data"),
                state.get("top_chord_text") or "",
            )

        bt_text = (
            _get(KEY_MP_CB_TYPE, "bracing_type") or (bt.currentText() if bt else "") or ""
        ).strip()
        bcc = self._bottom_chord_checkbox
        if bcc:
            if bt_text == "K-Bracing":
                bcc.setChecked(True)
            else:
                bcc.setChecked(
                    bool(_get(KEY_MP_CB_BOTTOM_CHORD_ENABLED, "bottom_chord_enabled", True))
                )

        bct = self._bottom_chord_type_combo
        if bct:
            bct.setCurrentText(
                _get(KEY_MP_CB_BOTTOM_CHORD_SECTION_TYPE, "bottom_chord_type")
                or bct.currentText()
            )
        bcs = self._bottom_chord_size_combo
        if bct and bcs:
            self._update_designations_for(bcs, bct.currentText())
            self._set_combo_to_data_or_text(
                bcs,
                state.get("bottom_chord_data"),
                state.get("bottom_chord_text") or "",
            )

        count_w = self._no_of_cross_bracing_input
        if count_w is not None:
            count_w.blockSignals(True)
            count_w.setText(
                _get(KEY_MP_CB_COUNT, "no_of_cross_bracing") or ""
            )
            count_w.blockSignals(False)

        self._recalculate_spacing()
        self._on_bracing_layout_changed()
        self._on_design_changed(self._global_design_mode)

    def _load_state_for_current_member(self) -> None:
        key = self._current_member_key()
        if not key:
            return
        self._active_member_key = key
        state = self._state_by_member_key.get(key) or self._default_member_state()

        # Collect live widget references for signal blocking
        widgets_to_block = [
            self._bracing_type_combo, self._bracing_section_type_combo,
            self._bracing_section_combo, self._top_chord_checkbox,
            self._top_chord_type_combo, self._top_chord_size_combo,
            self._bottom_chord_checkbox, self._bottom_chord_type_combo,
            self._bottom_chord_size_combo,
        ]
        ct = self._connection_type_combo
        if ct is not None:
            widgets_to_block.append(ct)

        guards = [w.blockSignals(True) for w in widgets_to_block if w is not None]
        try:
            self._apply_state(state)
        finally:
            for w, g in zip([w for w in widgets_to_block if w is not None], guards):
                w.blockSignals(g)

        self._update_previews()

    # ── Selection change handler ───────────────────────────────────────────────

    def _on_select_girders_index_changed(self, *_args) -> None:
        if self._selection_sync_guard:
            return
        self._store_current_member_state()
        self._selection_sync_guard = True
        try:
            self._refresh_member_id_display()
        finally:
            self._selection_sync_guard = False
        self._load_state_for_current_member()

    # ── Girder Details binding ─────────────────────────────────────────────────

    def bind_girder_details_tab(self, girder_details_tab) -> None:
        self._girder_details_tab = girder_details_tab
        try:
            length_input = getattr(girder_details_tab, "length_input", None)
            if length_input is not None and hasattr(length_input, "textChanged"):
                length_input.textChanged.connect(self._on_span_or_spacing_changed)
        except Exception:
            pass
        self._sync_span_to_additional_input()
        self.refresh_girder_options()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.refresh_girder_options()

    def _girder_pairs(self) -> list[str]:
        girders = []
        if self._girder_details_tab is not None and hasattr(self._girder_details_tab, "available_girders"):
            try:
                girders = list(getattr(self._girder_details_tab, "available_girders") or [])
            except Exception:
                girders = []
        if not girders:
            girders = ["G1", "G2"]
        pairs = [f"{girders[i]} to {girders[i + 1]}" for i in range(len(girders) - 1)]
        return pairs or ["G1 to G2"]

    def refresh_girder_options(self) -> None:
        try:
            self._store_current_member_state()
        except Exception:
            pass

        sg = self._select_girders_combo
        if sg is None:
            return

        pairs     = self._girder_pairs()
        prev_pair = sg.currentText().strip()

        block_a = sg.blockSignals(True)
        try:
            sg.clear()
            sg.addItems(pairs)
            if prev_pair in pairs:
                sg.setCurrentText(prev_pair)
            else:
                sg.setCurrentIndex(0)
        finally:
            sg.blockSignals(block_a)

        self._refresh_member_id_display()
        self._load_state_for_current_member()

    # ── Design mode ───────────────────────────────────────────────────────────

    def _apply_custom_mode(self, is_custom: bool) -> None:
        for widget in [
            self._bracing_section_type_combo, self._bracing_section_combo,
            self._top_chord_type_combo,        self._top_chord_size_combo,
            self._bottom_chord_type_combo,     self._bottom_chord_size_combo,
        ]:
            if widget is not None:
                widget.setEnabled(is_custom)
        self._on_bracing_layout_changed()

    def _on_design_changed(self, label: str) -> None:
        is_custom = label == "Custom"
        self._apply_custom_mode(is_custom)
        self._update_previews()

    def set_design_mode(self, mode_str: str) -> None:
        mode = "Custom" if str(mode_str or "").strip().lower() in {"custom", "customized"} else "Optimized"
        self._global_design_mode = mode
        self._on_design_changed(mode)

    # ── Section designation helpers ────────────────────────────────────────────

    def _display_name_for(self, designation: str, section_type: str) -> str:
        name = (designation or "").strip()
        if section_type in ("angle", "double_angle_long", "double_angle_short"):
            name = name.lstrip("∠⌒⟡⟠").strip()
            if not name.upper().startswith("IS"):
                name = f"IS {name}"
        return name

    def _fill_combo(self, combo: QComboBox, items, section_type: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        for des in items:
            combo.addItem(self._display_name_for(des, section_type), des)
        combo.blockSignals(False)

    def _set_preview(
        self,
        widget: SectionPreviewWidget,
        type_combo: QComboBox,
        size_combo:  QComboBox,
    ) -> None:
        stype       = self._map_section_type(type_combo.currentText())
        designation = size_combo.currentData() or size_combo.currentText()
        show_double_total = stype not in ("double_angle_long", "double_angle_short")
        widget.set_section(stype, designation, show_double_total)

    def _populate_designations(self) -> None:
        angles = self.catalog.list_angles()
        for combo in [
            self._bracing_section_combo,
            self._top_chord_size_combo,
            self._bottom_chord_size_combo,
        ]:
            if combo is not None:
                self._fill_combo(combo, angles, "angle")

    def _map_section_type(self, label: str) -> str:
        return {
            "Angle":                        "angle",
            "Double Angle (Long Leg)":      "double_angle_long",
            "Double Angle (Short Leg)":     "double_angle_short",
            "Channel":                      "channel",
            "Double Channel":               "double_channel",
        }.get(label, "angle")

    def _update_designations_for(self, combo: QComboBox | None, type_label: str) -> None:
        if combo is None:
            return
        stype = self._map_section_type(type_label)
        items = self.catalog.list_angles() if stype in ("angle", "double_angle_long", "double_angle_short") else self.catalog.list_channels()
        self._fill_combo(combo, items, stype)

    # ── Type-change callbacks ──────────────────────────────────────────────────

    def _on_bracing_type_changed(self, *_args) -> None:
        label = self._bracing_section_type_combo.currentText() if self._bracing_section_type_combo else ""
        self._update_designations_for(self._bracing_section_combo, label)
        self._update_previews()

    def _on_top_chord_type_changed(self, *_args) -> None:
        label = self._top_chord_type_combo.currentText() if self._top_chord_type_combo else ""
        self._update_designations_for(self._top_chord_size_combo, label)
        self._update_previews()

    def _on_bottom_chord_type_changed(self, *_args) -> None:
        label = self._bottom_chord_type_combo.currentText() if self._bottom_chord_type_combo else ""
        self._update_designations_for(self._bottom_chord_size_combo, label)
        self._update_previews()

    # ── Preview update ─────────────────────────────────────────────────────────

    def _update_previews(self, *_args) -> None:
        bpl = self._bracing_preview_label
        tcp = self._top_chord_preview_label
        bcp = self._bottom_chord_preview_label

        if self._global_design_mode != "Custom":
            for w in [bpl, tcp, bcp]:
                if w is not None:
                    w.set_section("", "")
            return

        bst = self._bracing_section_type_combo
        bsc = self._bracing_section_combo
        if bpl and bst and bsc:
            self._set_preview(bpl, bst, bsc)

        tcc = self._top_chord_checkbox
        tct = self._top_chord_type_combo
        tcs = self._top_chord_size_combo
        if tcc and tcc.isChecked():
            if tcp and tct and tcs:
                self._set_preview(tcp, tct, tcs)
        elif tcp:
            tcp.set_section("", "")

        bcc = self._bottom_chord_checkbox
        bct = self._bottom_chord_type_combo
        bcs = self._bottom_chord_size_combo
        if bcc and bcc.isChecked():
            if bcp and bct and bcs:
                self._set_preview(bcp, bct, bcs)
        elif bcp:
            bcp.set_section("", "")

    # ── Layout change (chord visibility + CAD widget) ─────────────────────────

    def _on_bracing_layout_changed(self, *_args) -> None:
        if self._updating_chord_rules:
            return
        self._updating_chord_rules = True
        try:
            bt = self._bracing_type_combo
            bracing   = (bt.currentText() or "").strip() if bt else ""
            is_custom = self._global_design_mode == "Custom"

            tcc = self._top_chord_checkbox
            bcc = self._bottom_chord_checkbox

            if bracing == "K-Bracing":
                if bcc is not None:
                    bcc.setChecked(True)
                    bcc.setEnabled(True)
                if tcc is not None:
                    tcc.setEnabled(True)
            else:
                for cb in [bcc, tcc]:
                    if cb is not None:
                        cb.setEnabled(True)

            top_enabled    = is_custom and (tcc.isChecked() if tcc else False)
            bottom_enabled = is_custom and (bcc.isChecked() if bcc else False)

            tct = self._top_chord_type_combo
            tcs = self._top_chord_size_combo
            for w in [tct, tcs]:
                if w is not None:
                    w.setEnabled(top_enabled)

            bct = self._bottom_chord_type_combo
            bcs = self._bottom_chord_size_combo
            for w in [bct, bcs]:
                if w is not None:
                    w.setEnabled(bottom_enabled)

            tcpb = self._top_chord_preview_box
            if tcpb is not None:
                tcpb.setVisible(tcc.isChecked() if tcc else False)

            show_bottom = (
                (bcc.isChecked() if bcc else False)
                or bracing == "K-Bracing"
            )
            if show_bottom and bcc is not None and not bcc.isChecked():
                bcc.setChecked(True)
            bcpb = self._bottom_chord_preview_box
            if bcpb is not None:
                bcpb.setVisible(show_bottom)

            blw = self._bracing_layout_widget
            mid_w = self._member_id_display
            sg    = self._select_girders_combo
            if blw is not None:
                blw.set_layout(
                    bracing,
                    tcc.isChecked() if tcc else False,
                    bcc.isChecked() if bcc else False,
                    mid_w.text() if mid_w else "",
                    sg.currentText() if sg else "",
                )
        finally:
            self._updating_chord_rules = False

        self._update_previews()

    # ── External API ──────────────────────────────────────────────────────────

    def reset_defaults(self) -> None:
        self._state_by_member_key.clear()
        self._active_member_key = None
        try:
            self.refresh_girder_options()
        except Exception:
            pass
        self._state_by_member_key.clear()
        self._active_member_key = None

        self._selection_sync_guard = True
        try:
            sg = self._select_girders_combo
            if sg is not None and sg.count() > 0:
                sg.setCurrentIndex(0)
            if self.member_id_combo.count() > 0:
                self.member_id_combo.setCurrentIndex(0)
        finally:
            self._selection_sync_guard = False

        self._load_state_for_current_member()

    def collect_data(self) -> dict:
        from PySide6.QtWidgets import QCheckBox as _CB, QComboBox as _Combo, QLineEdit as _LE
        self._store_current_member_state()

        pairs = self._girder_pairs()
        by_member: dict[str, dict] = {}
        for pair_idx, pair_label in enumerate(pairs, start=1):
            base_member = f"B{pair_idx}M1"
            base_key    = f"{pair_label}::{base_member}"
            base_state  = self._state_by_member_key.get(base_key)
            if base_state is None:
                base_state = dict(self._default_member_state())
                self._state_by_member_key[base_key] = dict(base_state)
            for member_id in self._member_ids_for_pair(pair_idx):
                payload = dict(base_state)
                payload["select_girders"] = pair_label
                payload["member_id"]      = member_id
                by_member[member_id]      = payload

        sg = self._select_girders_combo
        current_pair   = (sg.currentText() or "").strip() if sg else ""
        current_member = self._current_member_id().strip().upper()

        result: dict[str, object] = {
            "select_girders":          current_pair,
            "member_id":               current_member,
            "cross_bracing_by_member": by_member,
        }

        for field in self._schema_fields("section_inputs"):
            field_id = str(field.get("id") or "").strip()
            if not field_id:
                continue
            widget = self._widget_for_field(field_id)
            if isinstance(widget, _CB):
                result[field_id] = widget.isChecked()
            elif isinstance(widget, _Combo):
                result[field_id] = widget.currentText()
            elif isinstance(widget, _LE):
                result[field_id] = widget.text()

        for field in self._schema_fields("overview"):
            field_id = str(field.get("id") or "").strip()
            if not field_id or field_id in ("select_girders", "member_id"):
                continue
            widget = self._widget_for_field(field_id)
            if isinstance(widget, _LE):
                result[field_id] = widget.text()

        result["design"] = self._global_design_mode
        return result

    def restore_data(self, data: dict) -> None:
        if not isinstance(data, dict):
            return

        restored = data.get("cross_bracing_by_member")
        if isinstance(restored, dict):
            rebuilt: dict[str, dict] = {}
            for _member_id, payload in restored.items():
                if not isinstance(payload, dict):
                    continue
                pair_label = str(payload.get("select_girders") or "").strip()
                member_id  = str(payload.get("member_id") or _member_id or "").strip().upper()
                if not pair_label or not member_id.endswith("M1"):
                    continue
                state = dict(payload)
                state.pop("select_girders", None)
                state.pop("member_id", None)
                rebuilt[f"{pair_label}::{member_id}"] = state
            if rebuilt:
                self._state_by_member_key = rebuilt

        try:
            self.refresh_girder_options()
        except Exception:
            pass

        target_pair = str(data.get("select_girders") or "").strip()
        sg = self._select_girders_combo
        if target_pair and sg is not None:
            try:
                sg.setCurrentText(target_pair)
            except Exception:
                pass

        try:
            self._refresh_member_id_display()
        except Exception:
            pass
        try:
            self._load_state_for_current_member()
        except Exception:
            pass