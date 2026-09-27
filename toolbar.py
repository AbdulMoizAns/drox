"""
Modern Floating Glassmorphic Toolbar for Drox Screen Studio.
Optimized 2-row compact layout that fits cleanly on all screen sizes (including 1280x720).
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider,
    QLabel, QColorDialog, QFrame, QButtonGroup, QMenu
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QColor


TOOLBAR_STYLE = """
QWidget#ToolbarContainer {
    background-color: rgba(18, 24, 38, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 12px;
}

QFrame#Divider {
    background-color: rgba(255, 255, 255, 0.15);
    width: 1px;
    margin: 2px 2px;
}

QPushButton {
    background-color: transparent;
    color: #E2E8F0;
    border: none;
    border-radius: 6px;
    padding: 4px 6px;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 11px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: rgba(255, 255, 255, 0.15);
    color: #FFFFFF;
}

QPushButton:checked {
    background-color: #3B82F6;
    color: #FFFFFF;
}

QPushButton#MiniBtn {
    background-color: rgba(37, 99, 235, 0.95);
    color: #FFFFFF;
    border-radius: 14px;
    font-size: 12px;
    font-weight: bold;
    border: 1px solid rgba(255, 255, 255, 0.3);
}

QPushButton#MiniBtn:hover {
    background-color: #1D4ED8;
}

QSlider::groove:horizontal {
    height: 4px;
    background: rgba(255, 255, 255, 0.2);
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #3B82F6;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #FFFFFF;
    border: 2px solid #3B82F6;
    width: 12px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 6px;
}

QLabel {
    color: #94A3B8;
    font-family: 'Segoe UI', sans-serif;
    font-size: 11px;
    font-weight: 600;
}
"""


class ColorButton(QPushButton):
    """Compact circular color swatch button."""
    def __init__(self, color_hex: str, parent=None):
        super().__init__(parent)
        self.color_hex = color_hex
        self.setFixedSize(18, 18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self._update_style()

    def _update_style(self):
        border = "2px solid #FFFFFF" if self.isChecked() else "1px solid rgba(255,255,255,0.3)"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.color_hex};
                border: {border};
                border-radius: 9px;
            }}
            QPushButton:hover {{
                border: 2px solid #60A5FA;
            }}
        """)

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._update_style()


class FloatingToolbar(QWidget):
    """
    Compact 2-Row Floating Control Bar.
    """
    tool_selected = pyqtSignal(str)
    color_selected = pyqtSignal(QColor)
    width_changed = pyqtSignal(float)
    board_changed = pyqtSignal(str)
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    screenshot_requested = pyqtSignal()
    close_requested = pyqtSignal()
    record_start_requested = pyqtSignal()
    record_pause_requested = pyqtSignal()
    record_resume_requested = pyqtSignal()
    record_stop_requested = pyqtSignal()
    record_toggled = pyqtSignal(bool)
    mic_toggled = pyqtSignal(bool)
    open_recordings_requested = pyqtSignal()
    change_folder_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        if parent is None:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.drag_start_pos = None
        self.is_minimized = False
        self.is_recording = False
        self.is_paused = False
        self.mic_enabled = True

        self._init_ui()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Container Widget for styling
        self.container = QWidget(self)
        self.container.setObjectName("ToolbarContainer")
        self.setStyleSheet(TOOLBAR_STYLE)

        container_vbox = QVBoxLayout(self.container)
        container_vbox.setContentsMargins(8, 4, 8, 4)
        container_vbox.setSpacing(4)

        # ==========================================
        # ROW 1: TOOLS & MINIMIZE BUTTON
        # ==========================================
        row1_layout = QHBoxLayout()
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(3)

        # Drag Grip Handle
        self.grip_label = QLabel("⋮⋮", self.container)
        self.grip_label.setToolTip("Drag to move toolbar anywhere on screen")
        self.grip_label.setStyleSheet("color: #64748B; font-size: 14px; font-weight: bold; padding-right: 2px;")
        self.grip_label.setCursor(Qt.CursorShape.SizeAllCursor)
        row1_layout.addWidget(self.grip_label)

        # Tool Buttons Group
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)

        tools = [
            ("CURSOR", "👆 Mouse", "Mouse Mode (Click slides/desktop) [F2]"),
            ("PEN", "✏️ Pen", "Freehand Pen [P]"),
            ("HIGHLIGHTER", "🖍️ Marker", "Highlighter [H]"),
            ("LASER", "🔴 Laser", "Laser Pointer [L]"),
            ("SPOTLIGHT", "🔦 Focus", "Spotlight [S]"),
            ("ARROW", "↗️ Arrow", "Arrow [A]"),
            ("LINE", "📏 Line", "Straight Line [I]"),
            ("RECT", "▭ Box", "Rectangle Box [R]"),
            ("ELLIPSE", "◯ Circle", "Circle [C]"),
            ("BADGE", "🔢 123", "Step Badges (1, 2, 3...) [B]"),
            ("TEXT", "T Text", "Type Text [T]"),
            ("ERASER", "🧹 Erase", "Eraser [E]"),
        ]

        self.tool_buttons = {}
        for tool_id, label, tip in tools:
            btn = QPushButton(label, self.container)
            btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, tid=tool_id: self._on_tool_clicked(tid))
            self.tool_group.addButton(btn)
            row1_layout.addWidget(btn)
            self.tool_buttons[tool_id] = btn

        self.tool_buttons["PEN"].setChecked(True)

        row1_layout.addStretch()

        # Minimize Button
        self.min_btn = QPushButton("─", self.container)
        self.min_btn.setToolTip("Collapse toolbar to mini floating pill")
        self.min_btn.setFixedSize(22, 22)
        self.min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.min_btn.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 13px;")
        self.min_btn.clicked.connect(self.toggle_minimize)
        row1_layout.addWidget(self.min_btn)

        # Close Application Button
        self.close_btn = QPushButton("✕", self.container)
        self.close_btn.setToolTip("Exit / Close Application [Ctrl+Q]")
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton { color: #94A3B8; font-weight: bold; font-size: 12px; }
            QPushButton:hover { background-color: #EF4444; color: #FFFFFF; border-radius: 4px; }
        """)
        self.close_btn.clicked.connect(self.close_requested.emit)
        row1_layout.addWidget(self.close_btn)

        container_vbox.addLayout(row1_layout)

        # ==========================================
        # ROW 2: BOARDS, COLORS, SLIDER, ACTIONS
        # ==========================================
        row2_layout = QHBoxLayout()
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(4)

        # Board Backgrounds
        self.board_group = QButtonGroup(self)
        self.board_group.setExclusive(True)

        boards = [
            ("TRANSPARENT", "🖥️ Screen", "Transparent Desktop Mode"),
            ("WHITEBOARD", "📄 White", "Whiteboard Canvas"),
            ("BLACKBOARD", "⬛ Black", "Dark Blackboard Canvas"),
            ("GRID_DARK", "📐 Grid", "Math Grid Canvas"),
        ]

        self.board_buttons = {}
        for board_id, label, tip in boards:
            btn = QPushButton(label, self.container)
            btn.setCheckable(True)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton { font-size: 10px; padding: 3px 5px; color: #CBD5E1; }
                QPushButton:checked { background-color: #475569; color: #FFFFFF; }
            """)
            btn.clicked.connect(lambda checked, bid=board_id: self.board_changed.emit(bid))
            self.board_group.addButton(btn)
            row2_layout.addWidget(btn)
            self.board_buttons[board_id] = btn

        self.board_buttons["TRANSPARENT"].setChecked(True)

        self._add_divider(row2_layout)

        # Colors Swatches
        colors = [
            "#EF4444", "#F97316", "#FACC15", "#10B981",
            "#06B6D4", "#3B82F6", "#A855F7", "#FFFFFF"
        ]

        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        self.color_swatches = []

        for c_hex in colors:
            c_btn = ColorButton(c_hex, self.container)
            c_btn.setToolTip(f"Color: {c_hex}")
            c_btn.clicked.connect(lambda checked, hex_val=c_hex, btn=c_btn: self._on_color_swatch_clicked(hex_val, btn))
            self.color_group.addButton(c_btn)
            row2_layout.addWidget(c_btn)
            self.color_swatches.append(c_btn)

        self.color_swatches[0].setChecked(True)

        # Custom Color Picker button
        self.custom_color_btn = QPushButton("🎨", self.container)
        self.custom_color_btn.setToolTip("Custom Color...")
        self.custom_color_btn.setFixedSize(22, 22)
        self.custom_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_color_btn.setStyleSheet("""
            QPushButton { background-color: rgba(255,255,255,0.1); border-radius: 11px; font-size: 11px; padding: 0px; }
            QPushButton:hover { background-color: rgba(255,255,255,0.25); }
        """)
        self.custom_color_btn.clicked.connect(self._open_color_dialog)
        row2_layout.addWidget(self.custom_color_btn)

        self._add_divider(row2_layout)

        # Stroke Size Slider
        self.size_label = QLabel("4px", self.container)
        self.size_label.setStyleSheet("color: #94A3B8; font-weight: bold; min-width: 22px; font-size: 10px;")

        self.size_slider = QSlider(Qt.Orientation.Horizontal, self.container)
        self.size_slider.setRange(2, 32)
        self.size_slider.setValue(4)
        self.size_slider.setFixedWidth(50)
        self.size_slider.setToolTip("Stroke Thickness (Use mouse wheel anytime)")
        self.size_slider.valueChanged.connect(self._on_size_slider_changed)

        row2_layout.addWidget(self.size_slider)
        row2_layout.addWidget(self.size_label)

        self._add_divider(row2_layout)

        # Action Buttons
        self.undo_btn = QPushButton("↩️", self.container)
        self.undo_btn.setToolTip("Undo [Ctrl+Z]")
        self.undo_btn.setFixedSize(24, 24)
        self.undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_btn.clicked.connect(self.undo_requested.emit)
        row2_layout.addWidget(self.undo_btn)

        self.redo_btn = QPushButton("↪️", self.container)
        self.redo_btn.setToolTip("Redo [Ctrl+Y]")
        self.redo_btn.setFixedSize(24, 24)
        self.redo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.redo_btn.clicked.connect(self.redo_requested.emit)
        row2_layout.addWidget(self.redo_btn)

        self.clear_btn = QPushButton("🗑️", self.container)
        self.clear_btn.setToolTip("Clear Screen [Del]")
        self.clear_btn.setFixedSize(24, 24)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet("QPushButton:hover { background-color: rgba(239, 68, 68, 0.35); }")
        self.clear_btn.clicked.connect(self.clear_requested.emit)
        row2_layout.addWidget(self.clear_btn)

        self.snap_btn = QPushButton("📸", self.container)
        self.snap_btn.setToolTip("Save Screenshot & Copy to Clipboard [Ctrl+S]")
        self.snap_btn.setFixedSize(24, 24)
        self.snap_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.snap_btn.setStyleSheet("QPushButton:hover { background-color: rgba(16, 185, 129, 0.35); }")
        self.snap_btn.clicked.connect(self.screenshot_requested.emit)
        row2_layout.addWidget(self.snap_btn)

        self._add_divider(row2_layout)

        # Microphone Toggle Button
        self.mic_btn = QPushButton("🎙️", self.container)
        self.mic_btn.setToolTip("Microphone: ON (Click to Mute)")
        self.mic_btn.setFixedSize(24, 24)
        self.mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_btn.setStyleSheet("""
            QPushButton { background-color: rgba(255,255,255,0.08); border-radius: 4px; font-size: 11px; padding: 0px; }
            QPushButton:hover { background-color: rgba(255,255,255,0.2); }
        """)
        self.mic_btn.clicked.connect(self._toggle_mic)
        row2_layout.addWidget(self.mic_btn)

        # Record Button (Idle)
        self.rec_btn = QPushButton("🔴 REC", self.container)
        self.rec_btn.setToolTip("Start Screen + Mic Recording [F9]")
        self.rec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rec_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.2);
                color: #EF4444;
                border: 1px solid rgba(239, 68, 68, 0.5);
                border-radius: 4px;
                padding: 3px 6px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.35);
                color: #FFFFFF;
            }
        """)
        self.rec_btn.clicked.connect(self._on_rec_clicked)
        row2_layout.addWidget(self.rec_btn)

        # Pause / Resume Button (Visible during recording)
        self.pause_btn = QPushButton("⏸️ PAUSE", self.container)
        self.pause_btn.setToolTip("Pause Recording [F8]")
        self.pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(59, 130, 246, 0.25);
                color: #60A5FA;
                border: 1px solid rgba(59, 130, 246, 0.5);
                border-radius: 4px;
                padding: 3px 6px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2563EB;
                color: #FFFFFF;
            }
        """)
        self.pause_btn.clicked.connect(self._on_pause_clicked)
        self.pause_btn.setVisible(False)
        row2_layout.addWidget(self.pause_btn)

        # Stop Button (Visible during recording)
        self.stop_btn = QPushButton("⏹️ STOP", self.container)
        self.stop_btn.setToolTip("Stop Recording & Open Folder [F9]")
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: #FFFFFF;
                border: 1px solid #EF4444;
                border-radius: 4px;
                padding: 3px 7px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #B91C1C;
            }
        """)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.stop_btn.setVisible(False)
        row2_layout.addWidget(self.stop_btn)

        # Elapsed Recording Timer Label
        self.rec_timer_label = QLabel("00:00", self.container)
        self.rec_timer_label.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 11px; min-width: 32px;")
        self.rec_timer_label.setVisible(False)
        row2_layout.addWidget(self.rec_timer_label)

        # Open Recordings Folder Button
        self.folder_btn = QPushButton("📁", self.container)
        self.folder_btn.setToolTip("Recordings Folder (Click to Open, or Change Folder)")
        self.folder_btn.setFixedSize(24, 24)
        self.folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_btn.setStyleSheet("""
            QPushButton { background-color: rgba(255,255,255,0.08); border-radius: 4px; font-size: 11px; padding: 0px; }
            QPushButton:hover { background-color: rgba(255,255,255,0.2); }
        """)
        self.folder_btn.clicked.connect(self._show_folder_menu)
        row2_layout.addWidget(self.folder_btn)

        container_vbox.addLayout(row2_layout)

        self.main_layout.addWidget(self.container)

        # Mini collapsed container (shown when folded)
        self.mini_container = QWidget(self)
        self.mini_container.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 41, 59, 0.95);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 14px;
            }
        """)
        mini_layout = QHBoxLayout(self.mini_container)
        mini_layout.setContentsMargins(8, 2, 6, 2)
        mini_layout.setSpacing(4)

        self.mini_expand_btn = QPushButton("✏️ Drox Draw", self.mini_container)
        self.mini_expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mini_expand_btn.setToolTip("Click to expand toolbar")
        self.mini_expand_btn.setStyleSheet("border: none; font-size: 11px; font-weight: bold; color: #FFFFFF; background: transparent;")
        self.mini_expand_btn.clicked.connect(self.toggle_minimize)
        mini_layout.addWidget(self.mini_expand_btn)

        self.mini_rec_label = QLabel("", self.mini_container)
        self.mini_rec_label.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 10px;")
        self.mini_rec_label.setVisible(False)
        mini_layout.addWidget(self.mini_rec_label)

        self.mini_pause_btn = QPushButton("⏸️", self.mini_container)
        self.mini_pause_btn.setToolTip("Pause / Resume [F8]")
        self.mini_pause_btn.setFixedSize(20, 20)
        self.mini_pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mini_pause_btn.setStyleSheet("border: none; font-size: 11px; background: transparent;")
        self.mini_pause_btn.clicked.connect(self._on_pause_clicked)
        self.mini_pause_btn.setVisible(False)
        mini_layout.addWidget(self.mini_pause_btn)

        self.mini_stop_btn = QPushButton("⏹️", self.mini_container)
        self.mini_stop_btn.setToolTip("Stop Recording & Open Folder [F9]")
        self.mini_stop_btn.setFixedSize(20, 20)
        self.mini_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mini_stop_btn.setStyleSheet("border: none; font-size: 11px; background: transparent;")
        self.mini_stop_btn.clicked.connect(self._on_stop_clicked)
        self.mini_stop_btn.setVisible(False)
        mini_layout.addWidget(self.mini_stop_btn)

        self.mini_close_btn = QPushButton("✕", self.mini_container)
        self.mini_close_btn.setToolTip("Exit / Close Program [Ctrl+Q]")
        self.mini_close_btn.setFixedSize(18, 18)
        self.mini_close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mini_close_btn.setStyleSheet("""
            QPushButton { color: #94A3B8; font-weight: bold; font-size: 11px; border: none; background: transparent; }
            QPushButton:hover { background-color: #EF4444; color: #FFFFFF; border-radius: 9px; }
        """)
        self.mini_close_btn.clicked.connect(self.close_requested.emit)
        mini_layout.addWidget(self.mini_close_btn)

        self.mini_container.hide()
        self.main_layout.addWidget(self.mini_container)

        self.adjustSize()

    def _add_divider(self, layout: QHBoxLayout):
        divider = QFrame(self.container)
        divider.setObjectName("Divider")
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(divider)

    def _on_tool_clicked(self, tool_id: str):
        self.tool_selected.emit(tool_id)

    def _on_color_swatch_clicked(self, hex_val: str, button: ColorButton):
        for btn in self.color_swatches:
            btn.setChecked(btn == button)
        self.color_selected.emit(QColor(hex_val))

    def _open_color_dialog(self):
        col = QColorDialog.getColor(QColor("#EF4444"), self, "Select Custom Color")
        if col.isValid():
            for btn in self.color_swatches:
                btn.setChecked(False)
            self.color_selected.emit(col)

    def _on_size_slider_changed(self, val: int):
        self.size_label.setText(f"{val}px")
        self.width_changed.emit(float(val))

    def select_tool(self, tool_id: str):
        """Programmatically switch active tool button."""
        if tool_id in self.tool_buttons:
            self.tool_buttons[tool_id].setChecked(True)
            self.tool_selected.emit(tool_id)

    def _toggle_mic(self):
        """Toggles microphone mute state."""
        self.mic_enabled = not self.mic_enabled
        if self.mic_enabled:
            self.mic_btn.setText("🎙️")
            self.mic_btn.setToolTip("Microphone: ON (Click to Mute)")
            self.mic_btn.setStyleSheet("""
                QPushButton { background-color: rgba(255,255,255,0.08); border-radius: 4px; font-size: 11px; padding: 0px; }
                QPushButton:hover { background-color: rgba(255,255,255,0.2); }
            """)
        else:
            self.mic_btn.setText("🔇")
            self.mic_btn.setToolTip("Microphone: MUTED (Click to Enable)")
            self.mic_btn.setStyleSheet("""
                QPushButton { background-color: rgba(239, 68, 68, 0.3); border-radius: 4px; font-size: 11px; color: #FCA5A5; padding: 0px; }
                QPushButton:hover { background-color: rgba(239, 68, 68, 0.45); }
            """)
        self.mic_toggled.emit(self.mic_enabled)

    def _on_rec_clicked(self):
        """Called when 🔴 REC button is clicked."""
        self.record_start_requested.emit()
        self.record_toggled.emit(True)

    def _on_pause_clicked(self):
        """Called when ⏸️ PAUSE / ▶️ RESUME button is clicked."""
        if self.is_paused:
            self.record_resume_requested.emit()
        else:
            self.record_pause_requested.emit()

    def _on_stop_clicked(self):
        """Called when ⏹️ STOP button is clicked."""
        self.record_stop_requested.emit()
        self.record_toggled.emit(False)

    def _toggle_record(self):
        """Toggles between start and stop (used by hotkeys)."""
        if self.is_recording:
            self._on_stop_clicked()
        else:
            self._on_rec_clicked()

    def set_recording_state(self, recording: bool, paused: bool = False):
        """Updates toolbar visual elements according to recording and paused state."""
        self.is_recording = recording
        self.is_paused = paused

        if not recording:
            # Idle
            self.rec_btn.setVisible(True)
            self.pause_btn.setVisible(False)
            self.stop_btn.setVisible(False)
            self.rec_timer_label.setVisible(False)

            self.mini_rec_label.setVisible(False)
            self.mini_pause_btn.setVisible(False)
            self.mini_stop_btn.setVisible(False)
            if self.is_minimized:
                self.resize(145, 34)
        else:
            # Recording or Paused
            self.rec_btn.setVisible(False)
            self.stop_btn.setVisible(True)
            self.pause_btn.setVisible(True)
            self.rec_timer_label.setVisible(True)

            self.mini_rec_label.setVisible(True)
            self.mini_pause_btn.setVisible(True)
            self.mini_stop_btn.setVisible(True)

            if paused:
                self.pause_btn.setText("▶️ RESUME")
                self.pause_btn.setToolTip("Resume Recording [F8]")
                self.pause_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #D97706;
                        color: #FFFFFF;
                        border: 1px solid #F59E0B;
                        border-radius: 4px;
                        padding: 3px 6px;
                        font-weight: bold;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #B45309;
                    }
                """)
                self.rec_timer_label.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 11px; min-width: 32px;")
                self.mini_pause_btn.setText("▶️")
                self.mini_rec_label.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 10px;")
            else:
                self.pause_btn.setText("⏸️ PAUSE")
                self.pause_btn.setToolTip("Pause Recording [F8]")
                self.pause_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(59, 130, 246, 0.25);
                        color: #60A5FA;
                        border: 1px solid rgba(59, 130, 246, 0.5);
                        border-radius: 4px;
                        padding: 3px 6px;
                        font-weight: bold;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #2563EB;
                        color: #FFFFFF;
                    }
                """)
                self.rec_timer_label.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 11px; min-width: 32px;")
                self.mini_pause_btn.setText("⏸️")
                self.mini_rec_label.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 10px;")

            if self.is_minimized:
                self.resize(230, 34)

        self.adjustSize()
        parent = self.parentWidget()
        if parent and hasattr(parent, 'update_mask'):
            parent.update_mask()

    def update_rec_timer(self, seconds: int):
        """Updates timer display during recording."""
        mins = seconds // 60
        secs = seconds % 60
        tag = " ⏸️" if self.is_paused else ""
        text = f"{mins:02d}:{secs:02d}{tag}"
        self.rec_timer_label.setText(text)
        icon = "⏸️" if self.is_paused else "🔴"
        self.mini_rec_label.setText(f"{icon} {mins:02d}:{secs:02d}")

    def toggle_minimize(self):
        """Fold/unfold toolbar."""
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.container.hide()
            self.mini_container.show()
            self.resize(230 if self.is_recording else 145, 34)
        else:
            self.mini_container.hide()
            self.container.show()
            self.adjustSize()

        parent = self.parentWidget()
        if parent and hasattr(parent, 'update_mask'):
            parent.update_mask()

    # --- Dragging Logic ---

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.MouseButton.LeftButton) and self.drag_start_pos is not None:
            delta = event.position().toPoint() - self.drag_start_pos
            new_pos = self.pos() + delta
            parent = self.parentWidget()
            if parent:
                max_x = max(0, parent.width() - self.width())
                max_y = max(0, parent.height() - self.height())
                new_x = max(0, min(new_pos.x(), max_x))
                new_y = max(0, min(new_pos.y(), max_y))
                self.move(new_x, new_y)
                if hasattr(parent, 'update_mask'):
                    parent.update_mask()
            else:
                self.move(new_pos)
            event.accept()

    def _show_folder_menu(self):
        """Displays menu to open or change the recording directory."""
        menu = QMenu(self)
        menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(18, 24, 38, 0.98);
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 4px;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 11px;
                font-weight: 600;
            }
            QMenu::item {
                padding: 6px 14px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #3B82F6;
                color: #FFFFFF;
            }
        """)

        open_act = menu.addAction("📂 Open Recordings Folder")
        open_act.triggered.connect(self.open_recordings_requested.emit)

        change_act = menu.addAction("⚙️ Change Recording Folder...")
        change_act.triggered.connect(self.change_folder_requested.emit)

        btn_pos = self.folder_btn.mapToGlobal(QPoint(0, self.folder_btn.height() + 4))
        menu.exec(btn_pos)

    def set_recording_folder_tooltip(self, path: str):
        """Updates tooltip to show active folder."""
        self.folder_btn.setToolTip(f"Recordings Folder:\n{path}\n(Click to Open, or Change Folder)")
