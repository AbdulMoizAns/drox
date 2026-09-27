"""
Global System-Wide Hotkey Listener for Drox Screen Studio using pynput.
Enables instant hotkey response even when PowerPoint, Chrome, or other apps are focused.
Includes typing detection so hotkeys are cleanly disabled while typing notes.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from pynput import keyboard


class GlobalHotkeyManager(QObject):
    """
    Listens for system-wide hotkeys and dispatches them safely to PyQt GUI thread.
    """
    hotkey_triggered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctrl_pressed = False
        self.shift_pressed = False
        self.is_active_drawing = True  # Controls whether single-letter keys are active
        self.is_typing = False          # When user is typing text notes, hotkeys are disabled!
        self._start_listener()

    def set_drawing_mode(self, is_drawing: bool):
        """When True, single-letter shortcuts (P, H, L, etc.) are active."""
        self.is_active_drawing = is_drawing

    def set_typing_mode(self, is_typing: bool):
        """When True, completely disables hotkeys so letters type into text box."""
        self.is_typing = is_typing

    def _start_listener(self):
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.daemon = True
        self.listener.start()

    def _on_press(self, key):
        try:
            # If user is currently typing in the Text annotation box, DO NOT intercept any keys!
            if self.is_typing:
                return

            # Track modifiers
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self.ctrl_pressed = True
                return
            if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
                self.shift_pressed = True
                return

            # Always active global toggle hotkeys: F2 or Ctrl+Space (Mouse mode), F9 (Recording)
            if key == keyboard.Key.f2:
                self.hotkey_triggered.emit("TOGGLE_CURSOR")
                return

            if key == keyboard.Key.f8:
                self.hotkey_triggered.emit("TOGGLE_PAUSE")
                return

            if key == keyboard.Key.f9:
                self.hotkey_triggered.emit("TOGGLE_RECORD")
                return

            if self.ctrl_pressed and key == keyboard.Key.space:
                self.hotkey_triggered.emit("TOGGLE_CURSOR")
                return

            # If Ctrl is held:
            if self.ctrl_pressed:
                if hasattr(key, 'char') and key.char:
                    char_lower = key.char.lower()
                    if char_lower == 'z':
                        self.hotkey_triggered.emit("UNDO")
                        return
                    elif char_lower == 'y':
                        self.hotkey_triggered.emit("REDO")
                        return
                    elif char_lower == 's':
                        self.hotkey_triggered.emit("SCREENSHOT")
                        return
                    elif char_lower == 'r':
                        self.hotkey_triggered.emit("TOGGLE_RECORD")
                        return
                    elif char_lower == 'q':
                        self.hotkey_triggered.emit("QUIT")
                        return

            # Single-key shortcuts (Active when drawing mode is ON)
            if self.is_active_drawing:
                if key == keyboard.Key.esc:
                    self.hotkey_triggered.emit("ESCAPE")
                    return
                elif key == keyboard.Key.delete:
                    self.hotkey_triggered.emit("CLEAR")
                    return

                if hasattr(key, 'char') and key.char:
                    ch = key.char.lower()
                    shortcuts = {
                        'p': "TOOL_PEN",
                        'h': "TOOL_HIGHLIGHTER",
                        'l': "TOOL_LASER",
                        's': "TOOL_SPOTLIGHT",
                        'a': "TOOL_ARROW",
                        'i': "TOOL_LINE",
                        'r': "TOOL_RECT",
                        'c': "TOOL_ELLIPSE",  # C for Circle!
                        'o': "TOOL_ELLIPSE",  # O also for Circle
                        'b': "TOOL_BADGE",
                        't': "TOOL_TEXT",     # T for Text
                        'e': "TOOL_ERASER",
                    }
                    if ch in shortcuts:
                        self.hotkey_triggered.emit(shortcuts[ch])
                        return

        except Exception as e:
            pass

    def _on_release(self, key):
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressed = False
        elif key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            self.shift_pressed = False

    def stop(self):
        """Stop background listener thread."""
        try:
            self.listener.stop()
        except Exception:
            pass
