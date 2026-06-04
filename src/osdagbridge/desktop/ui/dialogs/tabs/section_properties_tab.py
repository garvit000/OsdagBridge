"""Auto-generated tab module extracted from additional_inputs."""
import sys
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTabBar, QLabel, QLineEdit,
    QComboBox, QGroupBox, QFormLayout, QPushButton, QScrollArea,
    QCheckBox, QMessageBox, QSizePolicy, QSpacerItem, QStackedWidget,
    QFrame, QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QTextEdit, QDialog, QSizePolicy, QSizeGrip, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QDoubleValidator, QIntValidator, QColor

from osdagbridge.core.utils.common import *
from osdagbridge.core.bridge_types.plate_girder.ui_fields_additional_input import CROSS_BRACING_DETAILS_SCHEMA
from osdagbridge.desktop.ui.utils.custom_titlebar import CustomTitleBar
from osdagbridge.desktop.ui.dialogs.tabs.common import apply_field_style
from osdagbridge.desktop.ui.dialogs.additional_input.ui_builder.common_ui_builder import UIBuilder
from osdagbridge.desktop.ui.dialogs.tabs.sub_tabs.section_properties.girder_details_tab import GirderDetailsTab
from osdagbridge.desktop.ui.dialogs.tabs.sub_tabs.section_properties.stiffener_details_tab import StiffenerDetailsTab
from osdagbridge.desktop.ui.dialogs.tabs.sub_tabs.section_properties.cross_bracing_details_tab import CrossBracingDetailsTab
from osdagbridge.desktop.ui.dialogs.tabs.sub_tabs.section_properties.end_diaphragm_details_tab import EndDiaphragmDetailsTab


class SectionPropertiesTab(QWidget):
    """Sub-tab for Section Properties with QTabWidget navigation like Loading tab."""

    def __init__(self, parent=None, additional_input_instance=None):
        super().__init__(parent)
        self.additional_input_instance = additional_input_instance
        self.init_ui()

    def init_ui(self):
        """Initialize styled tab navigation matching Loading subtabs."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._content_frame = QFrame()
        self._content_frame.setFrameShape(QFrame.NoFrame)
        content_layout = QVBoxLayout(self._content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.section_tabs = QTabWidget()
        self.section_tabs.setDocumentMode(True)
        self.section_tabs.setStyleSheet(
            "QTabWidget::pane { border: none; background: #f5f5f5; }"
            "QTabBar::tab { background: #e8e8e8; color: #4b4b4b; border: 1px solid #cfcfcf;"
            " border-bottom: none; padding: 8px 20px; margin-right: 2px; min-width: 120px;"
            " font-size: 11px; }"
            "QTabBar::tab:selected { background: #90AF13; color: #ffffff; font-weight: bold; }"
            "QTabBar::tab:!selected { margin-top: 2px; }"
        )

        self.girder_details_tab   = GirderDetailsTab()
        self.stiffener_details_tab = StiffenerDetailsTab()
        self.end_diaphragm_tab    = EndDiaphragmDetailsTab()

        # ── Cross Bracing: create logic widget, then build its UI via UIBuilder ──
        self.cross_bracing_tab = CrossBracingDetailsTab(
            additional_input_instance=self.additional_input_instance
        )
        self._build_cross_bracing_ui()
        # ── ──────────────────────────────────────────────────────────────────────

        self.section_tabs.addTab(self.girder_details_tab,    "Girder Details")
        self.section_tabs.addTab(self.stiffener_details_tab, "Stiffener Details")
        self.section_tabs.addTab(self.cross_bracing_tab,     "Cross-Bracing Details")
        self.section_tabs.addTab(self.end_diaphragm_tab,     "End Diaphragm Details")
        self._last_section_tab_index = self.section_tabs.currentIndex()

        content_layout.addWidget(self.section_tabs)
        main_layout.addWidget(self._content_frame)

        # Bind stiffener tab to girder tab for member list + optimized state.
        try:
            self.stiffener_details_tab.bind_girder_details_tab(self.girder_details_tab)
        except Exception:
            pass

        # Bind Cross Bracing + End Diaphragm to Girder Details for dynamic girder options.
        try:
            self.cross_bracing_tab.bind_girder_details_tab(self.girder_details_tab)
        except Exception:
            pass
        try:
            self.end_diaphragm_tab.bind_girder_details_tab(self.girder_details_tab)
        except Exception:
            pass

        # Refresh stiffener members whenever a tab becomes active.
        try:
            self.section_tabs.currentChanged.connect(self._on_section_tab_changed)
        except Exception:
            pass

    # ── Cross-Bracing UI construction ─────────────────────────────────────────

    def _build_cross_bracing_ui(self) -> None:
        """
        Use UIBuilder to build the Cross-Bracing Details UI.

        UIBuilder sets every `bind`-named widget as an attribute directly on
        `cross_bracing_tab` (the `owner` argument).  After that we call
        `finish_init()` so the tab can wire its signals and seed state —
        by which point all required widget attributes already exist.
        """
        schema_widget = UIBuilder(
            owner=self.cross_bracing_tab,
            schema=CROSS_BRACING_DETAILS_SCHEMA,
            card_title="",
            main_widget_object_name="cross_bracing.details.main",
            additional_input_instance=self.cross_bracing_tab,
            with_scroll=True,
        )
        schema_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Slot the UIBuilder widget into the tab's own layout so it renders.
        tab_layout = QVBoxLayout(self.cross_bracing_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)
        tab_layout.addWidget(schema_widget)

        # Keep a reference on the tab for any downstream code that may probe it.
        self.cross_bracing_tab._schema_widget = schema_widget

        # Wire signals and seed state now that all bind-attributes are present.
        self.cross_bracing_tab.finish_init()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_lock_overlay_geometry()

    def _update_lock_overlay_geometry(self):
        return

    def set_editable_mode(self, editable: bool) -> None:
        pass

    def set_design_mode(self, mode_str: str) -> None:
        if hasattr(self, "girder_details_tab") and hasattr(self.girder_details_tab, "set_design_mode"):
            self.girder_details_tab.set_design_mode(mode_str)
        if hasattr(self, "cross_bracing_tab") and hasattr(self.cross_bracing_tab, "set_design_mode"):
            self.cross_bracing_tab.set_design_mode(mode_str)
        if hasattr(self, "end_diaphragm_tab") and hasattr(self.end_diaphragm_tab, "set_design_mode"):
            self.end_diaphragm_tab.set_design_mode(mode_str)

    def has_unsaved_changes(self) -> bool:
        try:
            if hasattr(self, "girder_details_tab") and hasattr(self.girder_details_tab, "has_unsaved_changes"):
                return bool(self.girder_details_tab.has_unsaved_changes())
        except Exception:
            pass
        return False

    def _on_section_tab_changed(self, index: int) -> None:
        previous = getattr(self, "_last_section_tab_index", 0)
        if previous != index:
            try:
                leaving_girder_tab = (
                    previous == self.section_tabs.indexOf(getattr(self, "girder_details_tab", None))
                )
                if leaving_girder_tab and hasattr(self, "girder_details_tab") and hasattr(
                    self.girder_details_tab, "_commit_current_member_state"
                ):
                    self.girder_details_tab._commit_current_member_state()
            except Exception:
                pass

        try:
            widget = self.section_tabs.widget(index)
        except Exception:
            return

        self._last_section_tab_index = index

        if widget is getattr(self, "stiffener_details_tab", None):
            try:
                self.stiffener_details_tab.refresh_girder_members()
            except Exception:
                pass
        elif widget is getattr(self, "cross_bracing_tab", None):
            try:
                self.cross_bracing_tab.refresh_girder_options()
            except Exception:
                pass
        elif widget is getattr(self, "end_diaphragm_tab", None):
            try:
                self.end_diaphragm_tab.refresh_girder_options()
            except Exception:
                pass

    # ── Girder count propagation ───────────────────────────────────────────────

    def set_girder_count(self, count) -> None:
        if hasattr(self, "girder_details_tab") and hasattr(self.girder_details_tab, "set_girder_count"):
            self.girder_details_tab.set_girder_count(count)
        try:
            self.stiffener_details_tab.refresh_girder_members()
        except Exception:
            pass
        try:
            self.cross_bracing_tab.refresh_girder_options()
        except Exception:
            pass
        try:
            self.end_diaphragm_tab.refresh_girder_options()
        except Exception:
            pass

    # ── Reset ─────────────────────────────────────────────────────────────────

    def reset_defaults(self) -> None:
        """Reset the entire Member Properties area back to its initial/default state."""
        if hasattr(self, "girder_details_tab") and hasattr(self.girder_details_tab, "reset_defaults"):
            self.girder_details_tab.reset_defaults()

        try:
            self.stiffener_details_tab.refresh_girder_members()
        except Exception:
            pass
        try:
            self.cross_bracing_tab.refresh_girder_options()
        except Exception:
            pass
        try:
            self.end_diaphragm_tab.refresh_girder_options()
        except Exception:
            pass

        if hasattr(self, "stiffener_details_tab") and hasattr(self.stiffener_details_tab, "reset_defaults"):
            self.stiffener_details_tab.reset_defaults()
        if hasattr(self, "cross_bracing_tab") and hasattr(self.cross_bracing_tab, "reset_defaults"):
            self.cross_bracing_tab.reset_defaults()
        if hasattr(self, "end_diaphragm_tab") and hasattr(self.end_diaphragm_tab, "reset_defaults"):
            self.end_diaphragm_tab.reset_defaults()

        try:
            self.section_tabs.setCurrentIndex(0)
        except Exception:
            pass

    def reset_active_tab_defaults(self) -> None:
        """Reset only the currently active Member Properties sub-tab."""
        try:
            active_widget = self.section_tabs.currentWidget()
        except Exception:
            active_widget = None

        if active_widget is None:
            return

        if active_widget is getattr(self, "girder_details_tab", None):
            try:
                self.girder_details_tab.reset_defaults(preserve_selection=True, preserve_segments=True)
            except TypeError:
                self.girder_details_tab.reset_defaults()
            return

        if active_widget is getattr(self, "stiffener_details_tab", None):
            try:
                self.stiffener_details_tab.refresh_girder_members()
            except Exception:
                pass
        elif active_widget is getattr(self, "cross_bracing_tab", None):
            try:
                self.cross_bracing_tab.refresh_girder_options()
            except Exception:
                pass
        elif active_widget is getattr(self, "end_diaphragm_tab", None):
            try:
                self.end_diaphragm_tab.refresh_girder_options()
            except Exception:
                pass

        if hasattr(active_widget, "reset_defaults"):
            try:
                active_widget.reset_defaults()
            except Exception:
                pass

    # ── Save / restore ────────────────────────────────────────────────────────

    def save_properties(self) -> dict:
        data = {}
        if hasattr(self, "girder_details_tab") and hasattr(self.girder_details_tab, "collect_data"):
            data["girder_details"] = self.girder_details_tab.collect_data()
        if hasattr(self, "stiffener_details_tab"):
            if hasattr(self.stiffener_details_tab, "validate"):
                self.stiffener_details_tab.validate()
            if hasattr(self.stiffener_details_tab, "collect_data"):
                data["stiffener_details"] = self.stiffener_details_tab.collect_data()
        if hasattr(self, "cross_bracing_tab") and hasattr(self.cross_bracing_tab, "collect_data"):
            data["cross_bracing"] = self.cross_bracing_tab.collect_data()
        if hasattr(self, "end_diaphragm_tab") and hasattr(self.end_diaphragm_tab, "collect_data"):
            data["end_diaphragm"] = self.end_diaphragm_tab.collect_data()
        return data

    def restore_properties(self, data: dict) -> None:
        """Restore previously saved properties into the sub-tabs."""
        if not isinstance(data, dict):
            return

        girder_data = data.get("girder_details")
        if isinstance(girder_data, dict) and hasattr(self, "girder_details_tab") and hasattr(
            self.girder_details_tab, "restore_data"
        ):
            try:
                self.girder_details_tab.restore_data(girder_data)
            except Exception:
                pass

        stiffener_data = data.get("stiffener_details")
        if isinstance(stiffener_data, dict) and hasattr(self, "stiffener_details_tab") and hasattr(
            self.stiffener_details_tab, "restore_data"
        ):
            try:
                self.stiffener_details_tab.restore_data(stiffener_data)
            except Exception:
                pass

        cross_data = data.get("cross_bracing")
        if isinstance(cross_data, dict) and hasattr(self, "cross_bracing_tab") and hasattr(
            self.cross_bracing_tab, "restore_data"
        ):
            try:
                self.cross_bracing_tab.restore_data(cross_data)
            except Exception:
                pass

        end_data = data.get("end_diaphragm")
        if isinstance(end_data, dict) and hasattr(self, "end_diaphragm_tab") and hasattr(
            self.end_diaphragm_tab, "restore_data"
        ):
            try:
                self.end_diaphragm_tab.restore_data(end_data)
            except Exception:
                pass

        try:
            if hasattr(self, "stiffener_details_tab") and hasattr(
                self.stiffener_details_tab, "refresh_girder_members"
            ):
                self.stiffener_details_tab.refresh_girder_members()
        except Exception:
            pass

        try:
            if hasattr(self, "cross_bracing_tab") and hasattr(
                self.cross_bracing_tab, "refresh_girder_options"
            ):
                self.cross_bracing_tab.refresh_girder_options()
        except Exception:
            pass
        try:
            if hasattr(self, "end_diaphragm_tab") and hasattr(
                self.end_diaphragm_tab, "refresh_girder_options"
            ):
                self.end_diaphragm_tab.refresh_girder_options()
        except Exception:
            pass