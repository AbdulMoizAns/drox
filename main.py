"""
Drox Screen Studio - Ultimate Interactive Screen Drawing & Teaching Tool
Features:
- Transparent Desktop Annotation (draw over any PPT, PDF, Video, Browser)
- One-Click Mouse Pass-Through Mode (F2 / Mouse button) to interact with desktop
- Instant Whiteboard, Blackboard, and Math Grid Modes
- Audience Spotlight & Laser Pointer with fading trails
- Smart Shapes (Arrows, Lines, Boxes, Circles)
- Numbered Step Stamp Badges (1, 2, 3...)
- In-Place Rich Text Annotations
- Floating, Draggable, and Minimizable Glassmorphic Toolbar
- High-Performance Screen Recording + Microphone Audio into MP4 [F9 / Ctrl+R]
- High-Speed Undo/Redo & Instant Screenshot Capture to Disk & Clipboard [Ctrl+S]
- Floating Interactive Toast Notification with 1-click video playback & folder opening
"""

import sys
import os
import json
import datetime
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout,
    QVBoxLayout, QLabel, QPushButton, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QKeySequence, QShortcut, QPixmap, QIcon

from canvas import OverlayCanvas
from toolbar import FloatingToolbar
from hotkeys import GlobalHotkeyManager
from recorder import ScreenRecorder

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


def load_settings() -> dict:
    """Loads persistent user configuration from settings.json."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_settings(data: dict):
    """Saves user configuration to settings.json."""
    try:
        settings = load_settings()
        settings.update(data)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
    except Exception:
        pass



def open_in_file_manager(target_path: str):
    """
    Opens Windows File Explorer highlighting the file or opening the exact folder.
    Avoids Windows Explorer command-line parsing bug with spaces where it defaults to Documents.
    """
    if not target_path:
        return

    norm_path = os.path.normpath(os.path.abspath(target_path))
    folder = os.path.dirname(norm_path) if os.path.isfile(norm_path) else norm_path

    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

    # 1. If pointing to a valid file, launch explorer /select,"path" as single string command
    if os.path.isfile(norm_path):
        try:
            subprocess.Popen(f'explorer /select,"{norm_path}"')
            return
        except Exception:
            pass

    # 2. Open folder directly via ShellExecute (always opens exact target folder, NEVER Documents)
    try:
        os.startfile(folder)
    except Exception:
        try:
            subprocess.Popen(f'explorer "{folder}"')
        except Exception:
            pass


class ToastNotification(QWidget):
    """
    Floating Glassmorphic notification banner for screenshots and recorded lecture videos.
    Includes direct action buttons: Open Folder, Play Video, Dismiss.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.SubWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.container = QWidget(self)
        self.container.setObjectName("ToastContainer")
        self.setStyleSheet("""
            QWidget#ToastContainer {
                background-color: rgba(15, 23, 42, 0.95);
                border: 1px solid rgba(59, 130, 246, 0.6);
                border-radius: 10px;
            }
            QLabel#ToastTitle {
                color: #FFFFFF;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 11px;
                font-weight: bold;
            }
            QLabel#ToastSub {
                color: #94A3B8;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 10px;
            }
            QPushButton {
                background-color: rgba(59, 130, 246, 0.25);
                color: #FFFFFF;
                border: 1px solid rgba(59, 130, 246, 0.5);
                border-radius: 5px;
                padding: 4px 8px;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton#CloseBtn {
                background: transparent;
                border: none;
                color: #94A3B8;
                font-size: 13px;
                font-weight: bold;
                padding: 2px 6px;
            }
            QPushButton#CloseBtn:hover {
                color: #EF4444;
            }
        """)

        c_layout = QHBoxLayout(self.container)
        c_layout.setContentsMargins(12, 8, 12, 8)
        c_layout.setSpacing(10)

        self.icon_label = QLabel("🎬", self.container)
        self.icon_label.setStyleSheet("font-size: 18px;")
        c_layout.addWidget(self.icon_label)

        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(1)
        self.title_label = QLabel("Lecture Recording Saved!", self.container)
        self.title_label.setObjectName("ToastTitle")
        self.sub_label = QLabel("", self.container)
        self.sub_label.setObjectName("ToastSub")
        text_vbox.addWidget(self.title_label)
        text_vbox.addWidget(self.sub_label)
        c_layout.addLayout(text_vbox)

        self.play_btn = QPushButton("▶️ Play", self.container)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.clicked.connect(self._play_file)
        c_layout.addWidget(self.play_btn)

        self.folder_btn = QPushButton("📁 Folder", self.container)
        self.folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_btn.clicked.connect(self._open_folder)
        c_layout.addWidget(self.folder_btn)

        self.close_btn = QPushButton("✕", self.container)
        self.close_btn.setObjectName("CloseBtn")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.hide_toast)
        c_layout.addWidget(self.close_btn)

        layout.addWidget(self.container)

        self.current_filepath = ""
        self.auto_hide_timer = QTimer(self)
        self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.timeout.connect(self.hide_toast)

    def show_message(self, title: str, filepath: str, is_video: bool = True):
        self.current_filepath = filepath
        if os.path.isdir(filepath):
            self.icon_label.setText("📁")
            self.title_label.setText(title)
            self.sub_label.setText(filepath)
            self.play_btn.setVisible(False)
        else:
            self.icon_label.setText("🎬" if is_video else "📸")
            self.title_label.setText(title)
            self.sub_label.setText(os.path.basename(filepath))
            self.play_btn.setVisible(is_video)
        self.adjustSize()

        parent = self.parentWidget()
        if parent:
            pw, ph = parent.width(), parent.height()
            self.move(max(10, pw - self.width() - 30), max(10, ph - self.height() - 40))

        self.show()
        self.raise_()
        if parent and hasattr(parent, 'update_mask'):
            parent.update_mask()
        self.auto_hide_timer.start(8000)

    def hide_toast(self):
        self.hide()
        parent = self.parentWidget()
        if parent and hasattr(parent, 'update_mask'):
            parent.update_mask()

    def _play_file(self):
        if self.current_filepath and os.path.exists(self.current_filepath):
            try:
                os.startfile(self.current_filepath)
            except Exception:
                pass
        self.hide_toast()

    def _open_folder(self):
        if self.current_filepath:
            open_in_file_manager(self.current_filepath)
        self.hide_toast()


class ScreenStudioApp(QMainWindow):
    def __init__(self):
        super().__init__()

        # 1. Initialize Fullscreen Transparent Canvas
        self.canvas = OverlayCanvas()
        self.canvas.parent_app = self

        # 2. Initialize Floating Toolbar as direct child of Canvas
        self.toolbar = FloatingToolbar(parent=self.canvas)
        self.canvas.toolbar = self.toolbar

        # Position toolbar at top center of primary screen
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.geometry()
            tb_x = (geom.width() - self.toolbar.sizeHint().width()) // 2
            tb_y = 20
            self.toolbar.move(max(10, tb_x), tb_y)

        # 3. Floating Notification Toast for Recordings and Screenshots
        self.toast = ToastNotification(parent=self.canvas)
        self.canvas.toast = self.toast

        # 4. Load Persistent Settings & Initialize Screen & Mic Recorder
        settings = load_settings()
        saved_rec_dir = settings.get("recording_dir")
        if saved_rec_dir and os.path.isdir(saved_rec_dir):
            self.recordings_dir = os.path.normpath(saved_rec_dir)
        else:
            self.recordings_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")
        os.makedirs(self.recordings_dir, exist_ok=True)

        self.recorder = ScreenRecorder(output_dir=self.recordings_dir, fps=25)
        self.toolbar.set_recording_folder_tooltip(self.recordings_dir)

        self.rec_timer = QTimer(self)
        self.rec_timer.setInterval(1000)
        self.rec_timer.timeout.connect(self._on_rec_timer_tick)

        # 5. Connect Signals & Slots
        self._connect_signals()

        # 6. Setup Global System-Wide Hotkeys & Local Shortcuts
        self._setup_global_hotkeys()
        self._setup_shortcuts()

        # 7. Show canvas (toolbar is child so it displays natively on top)
        self.canvas.showFullScreen()
        self.toolbar.show()
        self.toolbar.raise_()

    def _connect_signals(self):
        # Toolbar -> Canvas
        self.toolbar.tool_selected.connect(self._on_tool_selected)
        self.toolbar.color_selected.connect(self.canvas.set_color)
        self.toolbar.width_changed.connect(self.canvas.set_width)
        self.toolbar.board_changed.connect(self.canvas.set_board_mode)
        self.toolbar.undo_requested.connect(self.canvas.undo)
        self.toolbar.redo_requested.connect(self.canvas.redo)
        self.toolbar.clear_requested.connect(self.canvas.clear_canvas)
        self.toolbar.screenshot_requested.connect(self.take_screenshot)
        self.toolbar.close_requested.connect(self.close_app)

        # Recording Signals
        self.toolbar.record_start_requested.connect(self._handle_record_start)
        self.toolbar.record_pause_requested.connect(self._handle_record_pause)
        self.toolbar.record_resume_requested.connect(self._handle_record_resume)
        self.toolbar.record_stop_requested.connect(self._handle_record_stop)
        self.toolbar.open_recordings_requested.connect(self._open_recordings_folder)
        self.toolbar.change_folder_requested.connect(self._change_recordings_folder)

        # Canvas -> Toolbar (e.g. right-click to switch to mouse cursor)
        self.canvas.mode_changed.connect(self.toolbar.select_tool)

    def _on_tool_selected(self, tool_id: str):
        self.canvas.set_tool(tool_id)
        if hasattr(self, 'hotkey_mgr'):
            self.hotkey_mgr.set_drawing_mode(tool_id != "CURSOR")

    def _setup_global_hotkeys(self):
        """Global system-wide hotkeys that work from any app (PowerPoint, Zoom, Chrome)."""
        self.hotkey_mgr = GlobalHotkeyManager(self)
        self.hotkey_mgr.hotkey_triggered.connect(self._handle_global_hotkey)

    def _handle_global_hotkey(self, action: str):
        if action == "TOGGLE_CURSOR":
            self._toggle_cursor_mode()
        elif action == "ESCAPE":
            self._on_escape()
        elif action == "UNDO":
            self.canvas.undo()
        elif action == "REDO":
            self.canvas.redo()
        elif action == "CLEAR":
            self.canvas.clear_canvas()
        elif action == "SCREENSHOT":
            self.take_screenshot()
        elif action == "TOGGLE_RECORD":
            self._toggle_recording()
        elif action == "TOGGLE_PAUSE":
            self._toggle_pause()
        elif action == "QUIT":
            self.close_app()
        elif action.startswith("TOOL_"):
            tool_name = action.replace("TOOL_", "")
            self.toolbar.select_tool(tool_name)

    def set_typing_mode(self, is_typing: bool):
        """Pauses hotkeys so user can type freely without triggering tools."""
        if hasattr(self, 'hotkey_mgr'):
            self.hotkey_mgr.set_typing_mode(is_typing)

    def _setup_shortcuts(self):
        """Local Qt application shortcuts fallback."""
        ctx = Qt.ShortcutContext.ApplicationShortcut

        # Toggle Pass-Through Mouse Mode (F2 or Ctrl+Space)
        s1 = QShortcut(QKeySequence("F2"), self.canvas, self._toggle_cursor_mode)
        s1.setContext(ctx)
        s2 = QShortcut(QKeySequence("Ctrl+Space"), self.canvas, self._toggle_cursor_mode)
        s2.setContext(ctx)

        # Tool shortcuts on toolbar/canvas
        shortcuts = [
            ("P", "PEN"),
            ("H", "HIGHLIGHTER"),
            ("L", "LASER"),
            ("S", "SPOTLIGHT"),
            ("A", "ARROW"),
            ("I", "LINE"),
            ("R", "RECT"),
            ("C", "ELLIPSE"),
            ("O", "ELLIPSE"),
            ("B", "BADGE"),
            ("T", "TEXT"),
            ("E", "ERASER"),
        ]
        for key, tool_id in shortcuts:
            sc = QShortcut(QKeySequence(key), self.canvas, lambda tid=tool_id: self.toolbar.select_tool(tid))
            sc.setContext(ctx)

        # Undo / Redo / Clear / Screenshot / Record
        sc_z = QShortcut(QKeySequence("Ctrl+Z"), self.canvas, self.canvas.undo)
        sc_z.setContext(ctx)
        sc_y = QShortcut(QKeySequence("Ctrl+Y"), self.canvas, self.canvas.redo)
        sc_y.setContext(ctx)

        sc_del = QShortcut(QKeySequence("Delete"), self.canvas, self.canvas.clear_canvas)
        sc_del.setContext(ctx)

        sc_s = QShortcut(QKeySequence("Ctrl+S"), self.canvas, self.take_screenshot)
        sc_s.setContext(ctx)

        # Record shortcuts (F9 or Ctrl+R for Start/Stop, F8 for Pause/Resume)
        sc_rec1 = QShortcut(QKeySequence("F9"), self.canvas, self._toggle_recording)
        sc_rec1.setContext(ctx)
        sc_rec2 = QShortcut(QKeySequence("Ctrl+R"), self.canvas, self._toggle_recording)
        sc_rec2.setContext(ctx)
        sc_pause = QShortcut(QKeySequence("F8"), self.canvas, self._toggle_pause)
        sc_pause.setContext(ctx)

        # Escape key
        sc_esc = QShortcut(QKeySequence("Escape"), self.canvas, self._on_escape)
        sc_esc.setContext(ctx)

        # Close Application Shortcuts (Ctrl+Q, Ctrl+W, Alt+F4)
        sc_q = QShortcut(QKeySequence("Ctrl+Q"), self.canvas, self.close_app)
        sc_q.setContext(ctx)
        sc_w = QShortcut(QKeySequence("Ctrl+W"), self.canvas, self.close_app)
        sc_w.setContext(ctx)
        sc_f4 = QShortcut(QKeySequence("Alt+F4"), self.canvas, self.close_app)
        sc_f4.setContext(ctx)

    def close_app(self):
        """Cleanly exit and close the application."""
        if hasattr(self, 'recorder') and self.recorder.is_recording:
            try:
                self.recorder.stop_recording()
            except Exception:
                pass

        if hasattr(self, 'hotkey_mgr') and hasattr(self.hotkey_mgr, 'stop'):
            self.hotkey_mgr.stop()
        QApplication.quit()

    def _toggle_cursor_mode(self):
        """Toggle between Pass-Through Mouse mode and drawing Pen mode."""
        if self.canvas.current_tool == "CURSOR":
            self.toolbar.select_tool("PEN")
        else:
            self.toolbar.select_tool("CURSOR")

    def _on_escape(self):
        """When Escape is pressed, quickly switch to Mouse mode."""
        if self.canvas.current_tool != "CURSOR":
            self.toolbar.select_tool("CURSOR")

    # --- Recording Handlers ---

    def _toggle_recording(self):
        """Called by F9 / Ctrl+R shortcut."""
        if self.recorder.is_recording:
            self._handle_record_stop()
        else:
            self._handle_record_start()

    def _toggle_pause(self):
        """Called by F8 shortcut to toggle Pause/Resume."""
        if not self.recorder.is_recording:
            return
        if self.recorder.is_paused:
            self._handle_record_resume()
        else:
            self._handle_record_pause()

    def _handle_record_start(self):
        """Starts recording screen + mic."""
        out_file = self.recorder.start_recording(with_mic=self.toolbar.mic_enabled)
        self.rec_timer.start()
        self.toolbar.set_recording_state(True, paused=False)

    def _handle_record_pause(self):
        """Pauses recording."""
        self.recorder.pause_recording()
        self.toolbar.set_recording_state(True, paused=True)

    def _handle_record_resume(self):
        """Resumes recording."""
        self.recorder.resume_recording()
        self.toolbar.set_recording_state(True, paused=False)

    def _handle_record_stop(self):
        """Stops recording, finalizes MP4, and AUTOMATICALLY opens folder with video selected."""
        self.rec_timer.stop()
        saved_file = self.recorder.stop_recording()
        self.toolbar.set_recording_state(False, paused=False)

        if saved_file and os.path.exists(saved_file):
            # 1. Automatically open the recordings folder and highlight the saved video!
            open_in_file_manager(saved_file)

            # 2. Show floating interactive toast
            self.toast.show_message("🎬 Lecture Recording Saved!", saved_file, is_video=True)

    def _on_rec_timer_tick(self):
        dur = int(self.recorder.get_duration())
        self.toolbar.update_rec_timer(dur)

    def _open_recordings_folder(self):
        target = self.recorder.output_dir if hasattr(self, 'recorder') and self.recorder.output_dir else self.recordings_dir
        open_in_file_manager(target)

    def _change_recordings_folder(self):
        """Allows user to select and change the destination folder for recordings."""
        prev_tool = self.canvas.current_tool
        if prev_tool != "CURSOR":
            self.canvas.set_click_through(True)

        curr_dir = self.recorder.output_dir if hasattr(self, 'recorder') and self.recorder.output_dir else self.recordings_dir

        selected_dir = QFileDialog.getExistingDirectory(
            self.canvas,
            "Select Video Recording Folder (Drox Screen Studio)",
            curr_dir,
            QFileDialog.Option.ShowDirsOnly
        )

        if prev_tool != "CURSOR":
            self.canvas.set_click_through(False)

        if selected_dir:
            norm_dir = os.path.normpath(selected_dir)
            os.makedirs(norm_dir, exist_ok=True)
            self.recordings_dir = norm_dir
            self.recorder.output_dir = norm_dir
            save_settings({"recording_dir": norm_dir})
            self.toolbar.set_recording_folder_tooltip(norm_dir)
            self.toast.show_message("📁 Recording Folder Updated!", norm_dir, is_video=False)

    # --- Screenshot Handler ---

    def take_screenshot(self):
        """
        Captures full screen with annotations, copies it to Clipboard,
        and saves it to the Screenshots folder.
        """
        # Hide toolbar and toast briefly so they don't appear in the captured slide
        self.toolbar.hide()
        if self.toast.isVisible():
            self.toast.hide()
        QApplication.processEvents()

        screen = QApplication.primaryScreen()
        if not screen:
            self.toolbar.show()
            return

        # Grab entire desktop screen with drawing overlay
        pixmap = screen.grabWindow(0)

        # Restore toolbar
        self.toolbar.show()

        # Copy to Clipboard
        clipboard = QApplication.clipboard()
        clipboard.setPixmap(pixmap)

        # Save to disk in screenshots folder
        screenshots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)

        filename = f"Lecture_Note_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = os.path.join(screenshots_dir, filename)
        pixmap.save(filepath, "PNG")

        # Visual feedback on toolbar snap button
        orig_text = self.toolbar.snap_btn.text()
        self.toolbar.snap_btn.setText("✅")
        self.toolbar.snap_btn.setToolTip(f"Copied to Clipboard & Saved to: {filename}")
        QTimer.singleShot(1800, lambda: self._reset_snap_btn(orig_text))

        # Show interactive toast
        self.toast.show_message("📸 Screenshot Saved & Copied!", filepath, is_video=False)

    def _reset_snap_btn(self, orig_text: str):
        self.toolbar.snap_btn.setText(orig_text)
        self.toolbar.snap_btn.setToolTip("Save Screenshot & Copy to Clipboard [Ctrl+S]")


def main():
    # Set Windows AppUserModelID for taskbar icon display
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("drox.screenstudio.v1")
    except Exception:
        pass

    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Drox Screen Studio")

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    studio = ScreenStudioApp()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
