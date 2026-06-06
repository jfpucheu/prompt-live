"""
Prompt-Live — Prompteur musical pour groupes live.
Affiche paroles et accords depuis des fichiers PDF/DOCX numérotés.
Écran externe si branché, sinon plein écran sur l'écran principal.
"""
import sys
import subprocess

_DEFAULT_FONT = "Menlo" if sys.platform == "darwin" else "Courier New"


def _prevent_sleep():
    """Empêche la mise en veille de l'écran. macOS → caffeinate, Windows → SetThreadExecutionState."""
    if sys.platform == "win32":
        import ctypes
        ES_CONTINUOUS       = 0x80000000
        ES_DISPLAY_REQUIRED = 0x00000002
        ES_SYSTEM_REQUIRED  = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
        )
        return None
    return subprocess.Popen(["caffeinate", "-d"])


def _allow_sleep(handle):
    """Annule _prevent_sleep()."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)  # ES_CONTINUOUS seul = reset
    elif handle is not None:
        handle.terminate()


# ─── Internationalisation ─────────────────────────────────────────────────────

_LANG = "fr"

_TR = {
    "fr": {
        "ctrl_title":     "Prompt-Live — Contrôle",
        "app_title":      "Prompt-Live  —  Prompteur musical",
        "no_dir":         "Aucun répertoire sélectionné",
        "browse":         "Choisir…",
        "reload":         "↺  Recharger",
        "edit_songs":     "✏  Éditer les chansons",
        "songs_label":    "Chansons (double-clic pour lancer depuis cette chanson) :",
        "font_label":     "Police :",
        "scroll_label":   "Défilement :",
        "slow":           "Lent",
        "fast":           "Rapide",
        "screens_label":  "Diffusion sur :",
        "refresh_tip":    "Actualiser les écrans",
        "web_label":      "iPad / web :",
        "web_starting":   "démarrage…",
        "port_error":     "Erreur port : ",
        "launch":         "▶   Lancer le prompteur",
        "stop":           "■   Arrêter le prompteur",
        "pedal":          "Pédale BT",
        "speed_label":    "Vitesse :",
        "pedal_hint":     "↓ / Espace  défilement     ↓ en bas de page → chanson suivante",
        "key_received":   "Touche reçue : ",
        "pedal_down_tag": "  ← pédale ↓",
        "pedal_up_tag":   "  ← pédale ↑",
        "clock":          "Horloge",
        "size_label":     "Taille :",
        "screen_n":       "Écran {}",
        "screen_tip":     "Clic gauche : sélectionner\nClic droit : identifier l'écran",
        "choose_dir":     "Choisir le répertoire des chansons",
        "error":          "Erreur : ",
        "autoscroll":     "Défilement auto",
        "transpose":      "Transposition :",
        "reset":          "↺",
        "tab_main":       "Accueil",
        "tab_params":     "Paramètres",
        "prompter_hint":  "← préc   ↑↓ défilement   → suiv   S auto-scroll   T / ⇧T transposer",
    },
    "en": {
        "ctrl_title":     "Prompt-Live — Control",
        "app_title":      "Prompt-Live  —  Live Prompter",
        "no_dir":         "No directory selected",
        "browse":         "Browse…",
        "reload":         "↺  Reload",
        "edit_songs":     "✏  Edit songs",
        "songs_label":    "Songs (double-click to start from this song):",
        "font_label":     "Font:",
        "scroll_label":   "Scroll:",
        "slow":           "Slow",
        "fast":           "Fast",
        "screens_label":  "Display on:",
        "refresh_tip":    "Refresh screens",
        "web_label":      "iPad / web:",
        "web_starting":   "starting…",
        "port_error":     "Port error: ",
        "launch":         "▶   Launch prompter",
        "stop":           "■   Stop prompter",
        "pedal":          "BT Pedal",
        "speed_label":    "Speed:",
        "pedal_hint":     "↓ / Space  scroll     ↓ at bottom → next song",
        "key_received":   "Key received: ",
        "pedal_down_tag": "  ← pedal ↓",
        "pedal_up_tag":   "  ← pedal ↑",
        "clock":          "Clock",
        "size_label":     "Size:",
        "screen_n":       "Screen {}",
        "screen_tip":     "Left click: select\nRight click: identify screen",
        "choose_dir":     "Choose songs directory",
        "error":          "Error: ",
        "autoscroll":     "Auto-scroll",
        "transpose":      "Transpose:",
        "reset":          "↺",
        "tab_main":       "Main",
        "tab_params":     "Settings",
        "prompter_hint":  "← prev   ↑↓ scroll   → next   S auto-scroll   T / ⇧T transpose",
    },
}

def _t(key: str) -> str:
    return _TR.get(_LANG, _TR["fr"]).get(key, key)


from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QLabel, QFileDialog, QFrame, QTextBrowser,
    QComboBox, QSlider, QCheckBox, QSpinBox, QTabWidget,
)
from PyQt6.QtCore import Qt, QSettings, QFileSystemWatcher, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QObject, QEvent
from PyQt6.QtGui import QKeySequence, QShortcut, QWheelEvent, QMouseEvent, QFont, QFontMetrics

import os as _os
import sys as _sys
from PyQt6.QtGui import QFontDatabase as _QFontDatabase

def _load_bundled_fonts():
    base = getattr(_sys, "_MEIPASS", _os.path.dirname(_os.path.abspath(__file__)))
    fonts_dir = _os.path.join(base, "fonts")
    if _os.path.isdir(fonts_dir):
        for f in _os.listdir(fonts_dir):
            if f.lower().endswith((".ttf", ".otf", ".ttc")):
                _QFontDatabase.addApplicationFont(_os.path.join(fonts_dir, f))

from parsers import load_songs, Song

_SPEED_PX = {1: 60, 2: 100, 3: 160, 4: 240, 5: 340}
_ANIM_MS  = 380

_AUTO_SCROLL_SPEEDS      = {1: 20, 2: 40, 3: 60, 4: 90, 5: 130}  # px/seconde
_AUTO_SCROLL_INTERVAL_MS = 50

# ─── Support pédale Bluetooth ─────────────────────────────────────────────────
# Touches interceptées globalement pour la pédale (configurables ici)
_PEDAL_DOWN_KEYS = {Qt.Key.Key_Down, Qt.Key.Key_Space, Qt.Key.Key_F5}
_PEDAL_UP_KEYS   = {Qt.Key.Key_Up, Qt.Key.Key_F6}


class _PedalFilter(QObject):
    """Filtre d'événements global pour la pédale Bluetooth.

    Appui bas  : défilement vers le bas.
    2 appuis consécutifs en bas de page : chanson suivante.
    Appui haut : défilement vers le haut.
    """

    BOTTOM_MARGIN = 8  # px de tolérance pour "en bas"

    def __init__(self, get_prompters):
        super().__init__()
        self._get_prompters = get_prompters
        self.enabled       = True
        self._scroll_px    = _SPEED_PX[3]
        self._bottom_count = 0  # appuis consécutifs en bas de page
        self._top_count    = 0  # appuis consécutifs en haut de page
        self.debug_cb      = None  # optionnel : callback(key_name: str)

    def _at_bottom(self, view) -> bool:
        sb = view.verticalScrollBar()
        return sb.maximum() == 0 or sb.value() >= sb.maximum() - self.BOTTOM_MARGIN

    def _at_top(self, view) -> bool:
        return view.verticalScrollBar().value() <= self.BOTTOM_MARGIN

    def eventFilter(self, _obj, event):
        if event.type() != QEvent.Type.KeyPress or event.isAutoRepeat():
            return False

        key = event.key()

        if self.debug_cb:
            key_name = QKeySequence(key).toString() or f"0x{key:04X}"
            self.debug_cb(key_name)

        if not self.enabled:
            return False

        is_down = key in _PEDAL_DOWN_KEYS
        is_up   = key in _PEDAL_UP_KEYS
        if not (is_down or is_up):
            return False

        prompters = self._get_prompters()
        if not prompters:
            return False

        view = prompters[0].view

        if is_down:
            self._top_count = 0
            if self._at_bottom(view):
                self._bottom_count += 1
                if self._bottom_count >= 2:
                    self._bottom_count = 0
                    prompters[0].next_song()
            else:
                self._bottom_count = 0
                view._smooth_scroll(self._scroll_px)
            return True

        # is_up
        self._bottom_count = 0
        if self._at_top(view):
            self._top_count += 1
            if self._top_count >= 2:
                self._top_count = 0
                prompters[0].prev_song()
        else:
            self._top_count = 0
            view._smooth_scroll(-self._scroll_px)
        return True
from renderer import render_html
from web_server import PromptWebServer
from editor import EditorWindow


# ─── Widget de défilement du prompteur ────────────────────────────────────────

class PrompterView(QTextBrowser):
    """QTextBrowser avec gestion du scroll molette et clics de navigation."""

    def __init__(self, on_prev, on_next, on_scroll=None, on_autoscroll_changed=None):
        super().__init__()
        self._on_prev   = on_prev
        self._on_next   = on_next
        self._on_scroll = on_scroll  # callable(ratio: float)
        self._on_autoscroll_changed = on_autoscroll_changed  # callable(active: bool)
        self._scroll_px    = _SPEED_PX[3]
        self._emit_enabled = True
        self._anim = QPropertyAnimation(self.verticalScrollBar(), b"value")
        self._anim.setDuration(_ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuint)
        self.verticalScrollBar().valueChanged.connect(self._on_value_changed)
        # Auto-scroll
        self._auto_active   = False
        self._auto_accum    = 0.0
        self._auto_px_tick  = _AUTO_SCROLL_SPEEDS[3] * _AUTO_SCROLL_INTERVAL_MS / 1000.0
        self._auto_timer    = QTimer()
        self._auto_timer.setInterval(_AUTO_SCROLL_INTERVAL_MS)
        self._auto_timer.timeout.connect(self._auto_tick)
        self.setReadOnly(True)
        self.setOpenLinks(False)
        self.setStyleSheet("""
            QTextBrowser {
                background-color: #000000;
                border: none;
            }
            QScrollBar:vertical {
                background: #111111;
                width: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #444444;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_PageDown):
            self._on_next()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_PageUp):
            self._on_prev()
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_Space, Qt.Key.Key_F5):
            self._smooth_scroll(self._scroll_px)
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_F6):
            self._smooth_scroll(-self._scroll_px)
        else:
            super().keyPressEvent(event)

    def _smooth_scroll(self, delta: int):
        sb  = self.verticalScrollBar()
        if self._anim.state() == QPropertyAnimation.State.Running:
            # Accumule vers la destination courante sans repartir de zéro
            end = max(0, min(sb.maximum(), int(self._anim.endValue()) + delta))
            self._anim.stop()
            self._anim.setStartValue(int(self._anim.currentValue()))
        else:
            end = max(0, min(sb.maximum(), sb.value() + delta))
            self._anim.setStartValue(sb.value())
        self._anim.setEndValue(end)
        self._anim.start()

    def _on_value_changed(self, value: int):
        if self._emit_enabled and self._on_scroll:
            self._on_scroll(value)

    def wheelEvent(self, event: QWheelEvent):
        ticks = event.angleDelta().y() / 120
        self._smooth_scroll(int(-ticks * self._scroll_px))
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            self._on_next()
        elif event.button() == Qt.MouseButton.LeftButton:
            self._on_prev()

    # ── Auto-scroll ───────────────────────────────────────────────────────────

    def _auto_tick(self):
        sb = self.verticalScrollBar()
        if sb.value() >= sb.maximum():
            self._auto_timer.stop()
            self._auto_active = False
            if self._on_autoscroll_changed:
                self._on_autoscroll_changed(False)
            return
        self._auto_accum += self._auto_px_tick
        if self._auto_accum >= 1.0:
            delta = int(self._auto_accum)
            self._auto_accum -= delta
            sb.setValue(sb.value() + delta)

    def toggle_auto_scroll(self) -> bool:
        self._auto_active = not self._auto_active
        if self._auto_active:
            self._auto_accum = 0.0
            self._auto_timer.start()
        else:
            self._auto_timer.stop()
        if self._on_autoscroll_changed:
            self._on_autoscroll_changed(self._auto_active)
        return self._auto_active

    def set_auto_scroll_active(self, active: bool):
        if active == self._auto_active:
            return
        self.toggle_auto_scroll()

    def set_auto_scroll_speed(self, speed: int):
        self._auto_px_tick = _AUTO_SCROLL_SPEEDS.get(speed, 60) * _AUTO_SCROLL_INTERVAL_MS / 1000.0

    def stop_auto_scroll(self):
        if self._auto_active:
            self._auto_timer.stop()
            self._auto_active = False
            if self._on_autoscroll_changed:
                self._on_autoscroll_changed(False)


# ─── Fenêtre du prompteur ─────────────────────────────────────────────────────

class PrompterWindow(QMainWindow):

    ZOOM_STEP = 0.1
    ZOOM_MIN = 0.3
    ZOOM_MAX = 3.0

    def __init__(self, songs: list[Song], start_index: int = 0, on_navigate=None, on_scroll=None, on_display=None,
                 font_family: str = "'Courier New',Courier,monospace", scroll_speed: int = 3,
                 transpose: int = 0, on_transpose=None, on_autoscroll=None):
        super().__init__()
        self.songs = songs
        self.current_index = start_index
        self._zoom = 1.0
        self._show_chords: bool | None = None
        self._on_navigate   = on_navigate
        self._on_scroll     = on_scroll
        self._on_display    = on_display
        self._on_transpose  = on_transpose   # callable(value: int)
        self._on_autoscroll = on_autoscroll  # callable(active: bool)
        self._scroll_speed  = scroll_speed
        self._font_family   = font_family
        self._transpose     = transpose

        self._watcher = QFileSystemWatcher()
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._reload_timer = QTimer()
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(150)
        self._reload_timer.timeout.connect(self._reload_current)

        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(250)
        self._resize_timer.timeout.connect(self._redisplay)


        self.setWindowTitle("Prompt-Live")
        self.setStyleSheet("background-color: black;")

        root = QWidget()
        root.setStyleSheet("background-color: black;")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(50, 30, 50, 20)
        layout.setSpacing(6)

        # En-tête : horloge + titre + compteur
        settings_r = QSettings("Prompt-Live", "Prompt-Live")
        self._clock_enabled: bool = bool(settings_r.value("clock_enabled", False, type=bool))
        self._clock_size: int = int(settings_r.value("clock_size", 20))

        header = QHBoxLayout()

        self.title_label = QLabel()
        self.title_label.setStyleSheet(
            "color: #666666; font-size: 15px; font-weight: bold;"
        )
        header.addWidget(self.title_label, 1)

        self.transpose_label = QLabel()
        self.transpose_label.setStyleSheet(
            "color: #ff9900; font-size: 13px; font-weight: bold;"
        )
        self.transpose_label.setVisible(False)
        header.addWidget(self.transpose_label)

        self.auto_label = QLabel("▶▶")
        self.auto_label.setStyleSheet("color: #00cc66; font-size: 13px;")
        self.auto_label.setVisible(False)
        header.addWidget(self.auto_label)

        self.counter_label = QLabel()
        self.counter_label.setStyleSheet("color: #444444; font-size: 13px;")
        header.addWidget(self.counter_label)

        self.clock_label = QLabel()
        self._apply_clock_style()
        self.clock_label.setVisible(self._clock_enabled)
        header.addWidget(self.clock_label)
        layout.addLayout(header)

        self._clock_timer = QTimer()
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._tick_clock)
        if self._clock_enabled:
            self._tick_clock()
            self._clock_timer.start()

        # Séparateur
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #222222;")
        layout.addWidget(sep)

        # Zone de texte principale
        self.view = PrompterView(
            on_prev=self.prev_song,
            on_next=self.next_song,
            on_scroll=self._emit_scroll,
            on_autoscroll_changed=self._on_autoscroll_state,
        )
        self.view._scroll_px = _SPEED_PX.get(scroll_speed, 160)
        layout.addWidget(self.view, 1)

        # Pied de page
        hint = QLabel(_t("prompter_hint"))
        hint.setStyleSheet("color: #2a2a2a; font-size: 10px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # Raccourcis clavier
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.close)
        QShortcut(QKeySequence("Ctrl+="),  self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"),  self, self._zoom_out)
        QShortcut(QKeySequence("A"),       self, self._toggle_chords)
        QShortcut(QKeySequence("S"),       self, self._toggle_auto_scroll)
        QShortcut(QKeySequence("T"),       self, self._transpose_up)
        QShortcut(QKeySequence("Shift+T"), self, self._transpose_down)
        QShortcut(QKeySequence("Ctrl+T"),  self, self._transpose_reset)

        self._display(self.current_index)

    # ── Horloge ───────────────────────────────────────────────────────────────

    def _apply_clock_style(self):
        font = QFont("Courier New")
        font.setPixelSize(self._clock_size)
        font.setBold(True)
        w = QFontMetrics(font).horizontalAdvance("00:00:00") + 16
        self.clock_label.setStyleSheet(
            f"color: #ffff00; font-size: {self._clock_size}px;"
            f" font-family: 'Courier New',monospace; font-weight: bold;"
        )
        self.clock_label.setFixedWidth(w)

    def _tick_clock(self):
        from datetime import datetime
        self.clock_label.setText(datetime.now().strftime("%H:%M:%S"))

    def set_clock_enabled(self, enabled: bool):
        self._clock_enabled = enabled
        self.clock_label.setVisible(enabled)
        if enabled:
            self._tick_clock()
            self._clock_timer.start()
        else:
            self._clock_timer.stop()

    def set_clock_size(self, size: int):
        self._clock_size = size
        self._apply_clock_style()

    # ── Navigation ────────────────────────────────────────────────────────────

    def next_song(self):
        if self.current_index < len(self.songs) - 1:
            self._navigate(self.current_index + 1)

    def prev_song(self):
        if self.current_index > 0:
            self._navigate(self.current_index - 1)

    def _navigate(self, index: int):
        """Change de chanson et notifie les autres fenêtres."""
        if self._on_navigate:
            self._on_navigate(index)  # le contrôleur synchro toutes les fenêtres
        else:
            self.go_to(index)

    def _emit_scroll(self, pos: int):
        if self._on_scroll:
            self._on_scroll(self, pos)

    def set_scroll_pos(self, pos: int):
        self.view._emit_enabled = False
        self.view.verticalScrollBar().setValue(pos)
        self.view._emit_enabled = True

    def go_to(self, index: int):
        """Positionne cette fenêtre sur la chanson index sans notifier les autres."""
        if 0 <= index < len(self.songs):
            self.current_index = index
            self._display(index)

    # ── Cycle de vie ──────────────────────────────────────────────────────────

    def closeEvent(self, event):
        super().closeEvent(event)

    # ── Zoom ──────────────────────────────────────────────────────────────────

    def _zoom_in(self):
        self._zoom = min(self.ZOOM_MAX, round(self._zoom + self.ZOOM_STEP, 2))
        self._display(self.current_index)

    def _zoom_out(self):
        self._zoom = max(self.ZOOM_MIN, round(self._zoom - self.ZOOM_STEP, 2))
        self._display(self.current_index)

    def _toggle_chords(self):
        song = self.songs[self.current_index]
        current = song.show_chords if self._show_chords is None else self._show_chords
        self._show_chords = not current
        self._display(self.current_index)

    # ── Auto-scroll ───────────────────────────────────────────────────────────

    def _toggle_auto_scroll(self):
        self.view.toggle_auto_scroll()

    def _on_autoscroll_state(self, active: bool):
        self.auto_label.setVisible(active)
        if self._on_autoscroll:
            self._on_autoscroll(active)

    def set_auto_scroll_active(self, active: bool):
        self.view.set_auto_scroll_active(active)

    def set_auto_scroll_speed(self, speed: int):
        self.view.set_auto_scroll_speed(speed)

    # ── Transposition ─────────────────────────────────────────────────────────

    def _transpose_up(self):
        self.set_transpose(self._transpose + 1)

    def _transpose_down(self):
        self.set_transpose(self._transpose - 1)

    def _transpose_reset(self):
        self.set_transpose(0)

    def set_transpose(self, value: int):
        self._transpose = value
        sign = "+" if value > 0 else ""
        if value == 0:
            self.transpose_label.setVisible(False)
        else:
            self.transpose_label.setText(f"♯{sign}{value}")
            self.transpose_label.setVisible(True)
        self._display(self.current_index)
        if self._on_transpose:
            self._on_transpose(value)

    # ── Affichage ─────────────────────────────────────────────────────────────

    def _watch(self, path: str):
        """Surveille le fichier courant (gère le cas éditeur qui recrée le fichier)."""
        for p in self._watcher.files():
            self._watcher.removePath(p)
        self._watcher.addPath(path)

    def _on_file_changed(self, path: str):
        # Certains éditeurs (VSCode…) sauvegardent en recréant le fichier :
        # on remet la surveillance après un court délai
        QTimer.singleShot(200, lambda: self._watcher.addPath(path))
        self._reload_timer.start()

    def _reload_current(self):
        from parsers import parse_prompt
        song = self.songs[self.current_index]
        try:
            self.songs[self.current_index] = parse_prompt(song.file_path)
        except Exception:
            return
        pos = self.view.verticalScrollBar().value()
        self._display(self.current_index)
        self.set_scroll_pos(pos)

    def _chars_per_line(self, song: Song) -> int:
        font_name = self._font_family.split(",")[0].strip("' ")
        px = max(8, int(song.font_lyrics * self._zoom))
        font = QFont(font_name)
        font.setPixelSize(px)
        char_w = QFontMetrics(font).horizontalAdvance('M')
        if char_w <= 0:
            return 0
        vp_w = self.view.viewport().width()
        return max(0, vp_w // char_w)

    def _redisplay(self):
        pos = self.view.verticalScrollBar().value()
        self._display(self.current_index)
        self.view.verticalScrollBar().setValue(pos)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start()

    def _display(self, index: int):
        if not self.songs or index >= len(self.songs):
            return
        song = self.songs[index]
        self._watch(song.file_path)
        self.title_label.setText(song.title.upper())
        self.counter_label.setText(f"{index + 1} / {len(self.songs)}")
        show_chords = song.show_chords if self._show_chords is None else self._show_chords
        cpl = self._chars_per_line(song)
        html = render_html(song, zoom=self._zoom, show_chords=show_chords,
                           font_family=self._font_family, chars_per_line=cpl,
                           transpose=self._transpose)
        self.view.setHtml(html)
        self.view.stop_auto_scroll()
        self.view.verticalScrollBar().setValue(0)
        if self._on_display:
            self._on_display(html)


# ─── Flash d'identification d'écran ──────────────────────────────────────────

class ScreenFlash(QMainWindow):
    """Overlay plein écran affiché 2 secondes pour identifier un écran."""

    def __init__(self, screen, label: str):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet("background-color: #000000;")

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel(label)
        lbl.setStyleSheet("color: #ffffff; font-size: 96px; font-weight: bold;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        self.setGeometry(screen.geometry())
        self.showFullScreen()

        QTimer.singleShot(2000, self.close)


# ─── Fenêtre de contrôle ──────────────────────────────────────────────────────

class ControlWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.songs: list[Song] = []
        self._prompters: list[PrompterWindow] = []
        self._screen_btns: list[QPushButton] = []
        self._editor: EditorWindow | None = None
        self._caffeinate = _prevent_sleep()

        self._web_scroll_timer = QTimer()
        self._web_scroll_timer.setSingleShot(True)
        self._web_scroll_timer.setInterval(80)
        self._web_scroll_source: "PrompterWindow | None" = None
        self._web_scroll_timer.timeout.connect(self._flush_web_scroll)

        settings = QSettings("Prompt-Live", "Prompt-Live")
        self._last_dir: str = settings.value("last_dir", "")
        self._font_family: str = settings.value("font_family", _DEFAULT_FONT)
        self._scroll_speed: int = int(settings.value("scroll_speed", 3))
        self._clock_enabled: bool = bool(settings.value("clock_enabled", False, type=bool))
        self._clock_size: int = int(settings.value("clock_size", 20))
        self._transpose: int = 0
        self._autoscroll_speed: int = 3

        global _LANG
        _LANG = settings.value("lang", "fr")

        pedal_enabled = bool(settings.value("pedal_enabled", True, type=bool))
        pedal_speed   = int(settings.value("pedal_speed", 3))

        self.setWindowTitle(_t("ctrl_title"))
        self.setMinimumSize(460, 520)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Titre + sélecteur de langue (toujours visible)
        title_row = QHBoxLayout()
        self._lbl_title = QLabel(_t("app_title"))
        self._lbl_title.setStyleSheet("font-size: 17px; font-weight: bold;")
        self._lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addWidget(self._lbl_title, 1)
        self._lang_btn = QPushButton()
        self._lang_btn.setFixedWidth(52)
        self._lang_btn.setFixedHeight(24)
        self._lang_btn.setStyleSheet(
            "font-size: 11px; font-weight: bold; border-radius: 4px; border: 1px solid #aaa;"
        )
        self._lang_btn.clicked.connect(self._toggle_lang)
        self._update_lang_btn()
        title_row.addWidget(self._lang_btn)
        layout.addLayout(title_row)

        # ── Onglets ───────────────────────────────────────────────────────────
        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget, 1)

        # ─────────────────────────────────────────────────────────────────────
        # Onglet Accueil
        # ─────────────────────────────────────────────────────────────────────
        tab_main = QWidget()
        lay_m = QVBoxLayout(tab_main)
        lay_m.setContentsMargins(8, 10, 8, 8)
        lay_m.setSpacing(8)

        dir_row = QHBoxLayout()
        self.dir_label = QLabel(self._last_dir or _t("no_dir"))
        self.dir_label.setStyleSheet("color: #555; font-size: 11px;")
        self.dir_label.setWordWrap(True)
        dir_row.addWidget(self.dir_label, 1)
        self._btn_dir = QPushButton(_t("browse"))
        self._btn_dir.setFixedWidth(80)
        self._btn_dir.clicked.connect(self._choose_dir)
        dir_row.addWidget(self._btn_dir)
        lay_m.addLayout(dir_row)

        reload_row = QHBoxLayout()
        self._btn_reload = QPushButton(_t("reload"))
        self._btn_reload.clicked.connect(self._reload)
        reload_row.addWidget(self._btn_reload)
        self._btn_edit = QPushButton(_t("edit_songs"))
        self._btn_edit.clicked.connect(self._open_editor)
        reload_row.addWidget(self._btn_edit)
        lay_m.addLayout(reload_row)

        self._lbl_songs = QLabel(_t("songs_label"))
        self._lbl_songs.setStyleSheet("font-size: 11px; color: #666;")
        lay_m.addWidget(self._lbl_songs)

        self.song_list = QListWidget()
        self.song_list.setStyleSheet("font-size: 13px;")
        self.song_list.itemDoubleClicked.connect(self._double_click)
        lay_m.addWidget(self.song_list, 1)

        sep_scr = QFrame(); sep_scr.setFrameShape(QFrame.Shape.HLine)
        lay_m.addWidget(sep_scr)

        screen_header = QHBoxLayout()
        self._lbl_screens = QLabel(_t("screens_label"))
        screen_header.addWidget(self._lbl_screens)
        self._btn_refresh = QPushButton("↺")
        self._btn_refresh.setFixedWidth(30)
        self._btn_refresh.setFixedHeight(22)
        self._btn_refresh.setToolTip(_t("refresh_tip"))
        self._btn_refresh.clicked.connect(self._build_screen_buttons)
        screen_header.addWidget(self._btn_refresh)
        screen_header.addStretch()
        lay_m.addLayout(screen_header)

        self.screens_row = QHBoxLayout()
        self.screens_row.setSpacing(6)
        lay_m.addLayout(self.screens_row)

        sep_web = QFrame(); sep_web.setFrameShape(QFrame.Shape.HLine)
        lay_m.addWidget(sep_web)

        web_row = QHBoxLayout()
        self._lbl_web = QLabel(_t("web_label"))
        self._lbl_web.setStyleSheet("font-size: 11px;")
        web_row.addWidget(self._lbl_web)
        self._url_label = QLabel(_t("web_starting"))
        self._url_label.setStyleSheet(
            "color: #1a6ee0; font-size: 12px; font-family: 'Menlo', monospace;"
        )
        self._url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._url_label.setCursor(Qt.CursorShape.IBeamCursor)
        web_row.addWidget(self._url_label, 1)
        lay_m.addLayout(web_row)

        sep_btn = QFrame(); sep_btn.setFrameShape(QFrame.Shape.HLine)
        lay_m.addWidget(sep_btn)

        self.btn_launch = QPushButton(_t("launch"))
        self.btn_launch.setEnabled(False)
        self.btn_launch.setFixedHeight(44)
        self.btn_launch.setStyleSheet("""
            QPushButton {
                font-size: 14px; border-radius: 6px; border: none;
                background-color: #cccccc; color: #888888;
            }
            QPushButton:enabled { background-color: #1a1a2e; color: #ffffff; }
            QPushButton:enabled:hover { background-color: #2a2a5e; }
        """)
        self.btn_launch.clicked.connect(lambda: self._launch(0))

        self.btn_stop = QPushButton(_t("stop"))
        self.btn_stop.setEnabled(False)
        self.btn_stop.setFixedHeight(44)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                font-size: 14px; border-radius: 6px; border: none;
                background-color: #cccccc; color: #888888;
            }
            QPushButton:enabled { background-color: #5a0000; color: #ffffff; }
            QPushButton:enabled:hover { background-color: #8a0000; }
        """)
        self.btn_stop.clicked.connect(self._stop)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_launch)
        btn_row.addWidget(self.btn_stop)
        lay_m.addLayout(btn_row)

        self._tab_widget.addTab(tab_main, _t("tab_main"))
        self._build_screen_buttons()

        # ─────────────────────────────────────────────────────────────────────
        # Onglet Paramètres
        # ─────────────────────────────────────────────────────────────────────
        tab_params = QWidget()
        lay_p = QVBoxLayout(tab_params)
        lay_p.setContentsMargins(8, 10, 8, 8)
        lay_p.setSpacing(8)

        font_row = QHBoxLayout()
        self._lbl_font = QLabel(_t("font_label"))
        font_row.addWidget(self._lbl_font)
        self._font_combo = QComboBox()
        for name in ["Courier New", "Menlo", "Monaco", "Andale Mono", "PT Mono"]:
            self._font_combo.addItem(name)
        idx = self._font_combo.findText(self._font_family)
        if idx >= 0:
            self._font_combo.setCurrentIndex(idx)
        self._font_combo.currentTextChanged.connect(self._on_font_changed)
        font_row.addWidget(self._font_combo, 1)
        lay_p.addLayout(font_row)

        speed_row = QHBoxLayout()
        self._lbl_scroll = QLabel(_t("scroll_label"))
        speed_row.addWidget(self._lbl_scroll)
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(1, 5)
        self._speed_slider.setValue(self._scroll_speed)
        self._speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._speed_slider.setTickInterval(1)
        self._speed_slider.valueChanged.connect(self._on_speed_changed)
        speed_row.addWidget(self._speed_slider, 1)
        self._lbl_slow = QLabel(_t("slow")); self._lbl_slow.setStyleSheet("font-size:10px;color:#888;")
        self._lbl_fast = QLabel(_t("fast")); self._lbl_fast.setStyleSheet("font-size:10px;color:#888;")
        speed_row.insertWidget(1, self._lbl_slow)
        speed_row.addWidget(self._lbl_fast)
        lay_p.addLayout(speed_row)

        sep_tp = QFrame(); sep_tp.setFrameShape(QFrame.Shape.HLine)
        lay_p.addWidget(sep_tp)

        tp_row = QHBoxLayout()
        self._lbl_transpose = QLabel(_t("transpose"))
        self._lbl_transpose.setStyleSheet("font-size: 11px;")
        tp_row.addWidget(self._lbl_transpose)
        self._btn_tp_down = QPushButton("▼")
        self._btn_tp_down.setFixedWidth(28); self._btn_tp_down.setFixedHeight(22)
        self._btn_tp_down.clicked.connect(self._transpose_down)
        tp_row.addWidget(self._btn_tp_down)
        self._lbl_tp_val = QLabel("0")
        self._lbl_tp_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_tp_val.setFixedWidth(36)
        self._lbl_tp_val.setStyleSheet("font-weight: bold; color: #888888;")
        tp_row.addWidget(self._lbl_tp_val)
        self._btn_tp_up = QPushButton("▲")
        self._btn_tp_up.setFixedWidth(28); self._btn_tp_up.setFixedHeight(22)
        self._btn_tp_up.clicked.connect(self._transpose_up)
        tp_row.addWidget(self._btn_tp_up)
        self._btn_tp_reset = QPushButton(_t("reset"))
        self._btn_tp_reset.setFixedWidth(28); self._btn_tp_reset.setFixedHeight(22)
        self._btn_tp_reset.clicked.connect(self._transpose_reset)
        tp_row.addWidget(self._btn_tp_reset)
        tp_row.addStretch()
        lay_p.addLayout(tp_row)

        as_row = QHBoxLayout()
        self._autoscroll_cb = QCheckBox(_t("autoscroll"))
        self._autoscroll_cb.toggled.connect(self._on_autoscroll_toggled)
        as_row.addWidget(self._autoscroll_cb)
        as_row.addSpacing(12)
        self._lbl_as_slow = QLabel(_t("slow")); self._lbl_as_slow.setStyleSheet("font-size:10px;color:#888;")
        as_row.addWidget(self._lbl_as_slow)
        self._as_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._as_speed_slider.setRange(1, 5)
        self._as_speed_slider.setValue(self._autoscroll_speed)
        self._as_speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._as_speed_slider.setTickInterval(1)
        self._as_speed_slider.valueChanged.connect(self._on_autoscroll_speed_changed)
        as_row.addWidget(self._as_speed_slider, 1)
        self._lbl_as_fast = QLabel(_t("fast")); self._lbl_as_fast.setStyleSheet("font-size:10px;color:#888;")
        as_row.addWidget(self._lbl_as_fast)
        lay_p.addLayout(as_row)

        sep_ped = QFrame(); sep_ped.setFrameShape(QFrame.Shape.HLine)
        lay_p.addWidget(sep_ped)

        pedal_row = QHBoxLayout()
        self._pedal_cb = QCheckBox(_t("pedal"))
        self._pedal_cb.setChecked(pedal_enabled)
        self._pedal_cb.toggled.connect(self._on_pedal_toggled)
        pedal_row.addWidget(self._pedal_cb)
        pedal_row.addSpacing(12)
        self._lbl_pedal_speed = QLabel(_t("speed_label"))
        pedal_row.addWidget(self._lbl_pedal_speed)
        self._pedal_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._pedal_speed_slider.setRange(1, 5)
        self._pedal_speed_slider.setValue(pedal_speed)
        self._pedal_speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._pedal_speed_slider.setTickInterval(1)
        self._pedal_speed_slider.valueChanged.connect(self._on_pedal_speed_changed)
        pedal_row.addWidget(self._pedal_speed_slider, 1)
        self._lbl_pedal_slow = QLabel(_t("slow")); self._lbl_pedal_slow.setStyleSheet("font-size:10px;color:#888;")
        self._lbl_pedal_fast = QLabel(_t("fast")); self._lbl_pedal_fast.setStyleSheet("font-size:10px;color:#888;")
        pedal_row.insertWidget(pedal_row.count() - 1, self._lbl_pedal_slow)
        pedal_row.addWidget(self._lbl_pedal_fast)
        lay_p.addLayout(pedal_row)

        self._pedal_hint_label = QLabel(_t("pedal_hint"))
        self._pedal_hint_label.setStyleSheet("font-size: 10px; color: #888;")
        lay_p.addWidget(self._pedal_hint_label)

        self._pedal_debug_label = QLabel(_t("key_received") + "—")
        self._pedal_debug_label.setStyleSheet("font-size: 10px; color: #f90;")
        lay_p.addWidget(self._pedal_debug_label)

        sep_clk = QFrame(); sep_clk.setFrameShape(QFrame.Shape.HLine)
        lay_p.addWidget(sep_clk)

        clock_row = QHBoxLayout()
        self._clock_cb = QCheckBox(_t("clock"))
        self._clock_cb.setChecked(self._clock_enabled)
        self._clock_cb.toggled.connect(self._on_clock_toggled)
        clock_row.addWidget(self._clock_cb)
        clock_row.addSpacing(12)
        self._lbl_clock_size = QLabel(_t("size_label"))
        clock_row.addWidget(self._lbl_clock_size)
        self._clock_spin = QSpinBox()
        self._clock_spin.setRange(8, 120)
        self._clock_spin.setValue(self._clock_size)
        self._clock_spin.setSuffix(" px")
        self._clock_spin.setFixedWidth(72)
        self._clock_spin.valueChanged.connect(self._on_clock_size)
        clock_row.addWidget(self._clock_spin)
        clock_row.addStretch()
        lay_p.addLayout(clock_row)

        lay_p.addStretch()
        self._tab_widget.addTab(tab_params, _t("tab_params"))

        # ── Infrastructure ────────────────────────────────────────────────────
        self._pedal_filter = _PedalFilter(lambda: self._prompters)
        self._pedal_filter.enabled    = pedal_enabled
        self._pedal_filter._scroll_px = _SPEED_PX.get(pedal_speed, 160)
        self._pedal_filter.debug_cb   = self._on_pedal_debug
        QApplication.instance().installEventFilter(self._pedal_filter)

        self._web_server = PromptWebServer()
        try:
            url = self._web_server.start()
            self._url_label.setText(url)
        except OSError as e:
            self._url_label.setText(_t("port_error") + e.strerror)

        self._cmd_timer = QTimer()
        self._cmd_timer.setInterval(80)
        self._cmd_timer.timeout.connect(self._process_web_commands)
        self._cmd_timer.start()

        QApplication.instance().screenAdded.connect(lambda _: self._build_screen_buttons())
        QApplication.instance().screenRemoved.connect(lambda _: self._build_screen_buttons())

        QTimer.singleShot(0, self._ask_directory)

    # ── Langue ────────────────────────────────────────────────────────────────

    def _toggle_lang(self):
        global _LANG
        _LANG = "en" if _LANG == "fr" else "fr"
        QSettings("Prompt-Live", "Prompt-Live").setValue("lang", _LANG)
        self._retranslate_ui()
        self._build_screen_buttons()

    def _update_lang_btn(self):
        other = "EN" if _LANG == "fr" else "FR"
        self._lang_btn.setText(f"→ {other}")

    def _retranslate_ui(self):
        self.setWindowTitle(_t("ctrl_title"))
        self._lbl_title.setText(_t("app_title"))
        if not self._last_dir:
            self.dir_label.setText(_t("no_dir"))
        self._btn_dir.setText(_t("browse"))
        self._btn_reload.setText(_t("reload"))
        self._btn_edit.setText(_t("edit_songs"))
        self._lbl_songs.setText(_t("songs_label"))
        self._lbl_font.setText(_t("font_label"))
        self._lbl_scroll.setText(_t("scroll_label"))
        self._lbl_slow.setText(_t("slow"))
        self._lbl_fast.setText(_t("fast"))
        self._lbl_screens.setText(_t("screens_label"))
        self._btn_refresh.setToolTip(_t("refresh_tip"))
        self._lbl_web.setText(_t("web_label"))
        self.btn_launch.setText(_t("launch"))
        self.btn_stop.setText(_t("stop"))
        self._pedal_cb.setText(_t("pedal"))
        self._lbl_pedal_speed.setText(_t("speed_label"))
        self._lbl_pedal_slow.setText(_t("slow"))
        self._lbl_pedal_fast.setText(_t("fast"))
        self._pedal_hint_label.setText(_t("pedal_hint"))
        self._pedal_debug_label.setText(_t("key_received") + "—")
        self._clock_cb.setText(_t("clock"))
        self._lbl_clock_size.setText(_t("size_label"))
        self._lbl_transpose.setText(_t("transpose"))
        self._btn_tp_reset.setText(_t("reset"))
        self._autoscroll_cb.setText(_t("autoscroll"))
        self._lbl_as_slow.setText(_t("slow"))
        self._lbl_as_fast.setText(_t("fast"))
        self._tab_widget.setTabText(0, _t("tab_main"))
        self._tab_widget.setTabText(1, _t("tab_params"))
        self._update_lang_btn()

    # ── Pédale ────────────────────────────────────────────────────────────────

    def _on_pedal_toggled(self, checked: bool):
        self._pedal_filter.enabled = checked
        QSettings("Prompt-Live", "Prompt-Live").setValue("pedal_enabled", checked)

    def _on_pedal_speed_changed(self, value: int):
        self._pedal_filter._scroll_px = _SPEED_PX.get(value, 160)
        QSettings("Prompt-Live", "Prompt-Live").setValue("pedal_speed", value)

    def _on_pedal_debug(self, key_name: str):
        down = "✓" if key_name in {QKeySequence(k).toString() for k in _PEDAL_DOWN_KEYS} else ""
        up   = "✓" if key_name in {QKeySequence(k).toString() for k in _PEDAL_UP_KEYS}   else ""
        tag  = _t("pedal_down_tag") if down else (_t("pedal_up_tag") if up else "")
        self._pedal_debug_label.setText(_t("key_received") + f"{key_name}{tag}")

    # ── Horloge ───────────────────────────────────────────────────────────────

    def _on_clock_toggled(self, enabled: bool):
        self._clock_enabled = enabled
        QSettings("Prompt-Live", "Prompt-Live").setValue("clock_enabled", enabled)
        for p in self._prompters:
            p.set_clock_enabled(enabled)

    def _on_clock_size(self, size: int):
        self._clock_size = size
        QSettings("Prompt-Live", "Prompt-Live").setValue("clock_size", size)
        for p in self._prompters:
            p.set_clock_size(size)

    # ── Transposition ─────────────────────────────────────────────────────────

    def _transpose_up(self):
        self._set_transpose(self._transpose + 1)

    def _transpose_down(self):
        self._set_transpose(self._transpose - 1)

    def _transpose_reset(self):
        self._set_transpose(0)

    def _set_transpose(self, value: int):
        self._transpose = value
        sign = "+" if value > 0 else ""
        self._lbl_tp_val.setText(f"{sign}{value}" if value != 0 else "0")
        self._lbl_tp_val.setStyleSheet(
            f"font-weight: bold; color: {'#ff9900' if value != 0 else '#888888'};"
        )
        for p in self._prompters:
            p.set_transpose(value)
        self._web_server.push_transpose(value)

    # ── Auto-scroll ───────────────────────────────────────────────────────────

    def _on_autoscroll_toggled(self, checked: bool):
        for p in self._prompters:
            p.set_auto_scroll_active(checked)
        self._web_server.push_autoscroll(checked)

    def _on_autoscroll_speed_changed(self, value: int):
        self._autoscroll_speed = value
        for p in self._prompters:
            p.set_auto_scroll_speed(value)

    def _on_autoscroll_state(self, active: bool):
        """Callback quand le prompteur change l'état auto-scroll (touche S)."""
        self._autoscroll_cb.setChecked(active)
        self._web_server.push_autoscroll(active)

    # ── Commandes iPad ────────────────────────────────────────────────────────

    def _process_web_commands(self):
        for cmd in self._web_server.poll_commands():
            c = cmd.get("cmd", "")
            if not self._prompters:
                continue
            p = self._prompters[0]
            if c == "next":
                self._on_navigate(min(p.current_index + 1, len(self.songs) - 1))
            elif c == "prev":
                self._on_navigate(max(p.current_index - 1, 0))
            elif c == "scroll":
                px = _SPEED_PX.get(self._scroll_speed, 160)
                p.view._smooth_scroll(px if cmd.get("d") == "down" else -px)
            elif c == "autoscroll":
                active = p.view.toggle_auto_scroll()
                self._autoscroll_cb.setChecked(active)
                self._web_server.push_autoscroll(active)
            elif c == "transpose":
                self._set_transpose(self._transpose + int(cmd.get("delta", 0)))

    # ── Police ────────────────────────────────────────────────────────────────

    def _on_speed_changed(self, value: int):
        self._scroll_speed = value
        QSettings("Prompt-Live", "Prompt-Live").setValue("scroll_speed", value)
        for p in self._prompters:
            p.view._scroll_px = _SPEED_PX.get(value, 160)

    def _on_font_changed(self, name: str):
        self._font_family = name
        QSettings("Prompt-Live", "Prompt-Live").setValue("font_family", name)
        for p in self._prompters:
            p._font_family = f"'{name}',monospace"
            p._display(p.current_index)

    def _css_font(self) -> str:
        return f"'{self._font_family}','Courier New',Courier"

    # ── Gestion des écrans ────────────────────────────────────────────────────

    def _build_screen_buttons(self):
        """Reconstruit les boutons d'écrans selon les écrans détectés."""
        # Nettoie les anciens boutons
        while self.screens_row.count():
            w = self.screens_row.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._screen_btns.clear()

        screens = QApplication.screens()
        primary = QApplication.primaryScreen()

        for i, screen in enumerate(screens):
            geo = screen.geometry()
            is_primary = screen == primary
            label = f"{'★ ' if is_primary else ''}{_t('screen_n').format(i + 1)}\n{geo.width()}×{geo.height()}"
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(len(screens) == 1 or not is_primary)
            btn.setFixedHeight(48)
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 11px; border-radius: 5px;
                    border: 1px solid #aaa; background: #f0f0f0;
                }
                QPushButton:checked {
                    background: #1a1a2e; color: white; border-color: #1a1a2e;
                }
            """)
            # Clic droit → flash d'identification sur cet écran
            flash_label = _t("screen_n").format(i + 1)
            btn.setToolTip(_t("screen_tip"))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda _, s=screen, fl=flash_label: ScreenFlash(s, fl)
            )
            self.screens_row.addWidget(btn)
            self._screen_btns.append(btn)

    def _selected_screens(self) -> list:
        screens = QApplication.screens()
        return [s for s, btn in zip(screens, self._screen_btns) if btn.isChecked()]

    # ── Répertoire ────────────────────────────────────────────────────────────

    def _ask_directory(self):
        d = QFileDialog.getExistingDirectory(
            self, _t("choose_dir"), self._last_dir,
            QFileDialog.Option.DontUseNativeDialog,
        )
        if d:
            self._set_dir(d)
        elif self._last_dir:
            self._reload()

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, _t("choose_dir"), self._last_dir,
            QFileDialog.Option.DontUseNativeDialog,
        )
        if d:
            self._set_dir(d)

    def _set_dir(self, d: str):
        self._last_dir = d
        self.dir_label.setText(d)
        QSettings("Prompt-Live", "Prompt-Live").setValue("last_dir", d)
        self._reload()
        if self._editor and self._editor.isVisible():
            self._editor.set_directory(d)

    def _open_editor(self):
        if self._editor is None or not self._editor.isVisible():
            self._editor = EditorWindow(
                directory=self._last_dir,
                on_save=self._reload,
                font_family=self._font_family,
            )
            self._editor.show()
        else:
            self._editor.raise_()
            self._editor.activateWindow()

    def _reload(self):
        if not self._last_dir:
            return
        self.song_list.clear()
        try:
            self.songs = load_songs(self._last_dir)
        except Exception as e:
            self.song_list.addItem(_t("error") + str(e))
            self.btn_launch.setEnabled(False)
            return

        for i, song in enumerate(self.songs):
            self.song_list.addItem(f"{i + 1:02d}.  {song.title}")

        self.btn_launch.setEnabled(bool(self.songs))
        if self.songs:
            self.song_list.setCurrentRow(0)

        self._web_server.push_setlist([s.title for s in self.songs])

        for p in self._prompters:
            if not p.isHidden():
                p.songs = self.songs
                p.go_to(0)

    # ── Synchronisation navigation + scroll ──────────────────────────────────

    def _on_navigate(self, index: int):
        for p in self._prompters:
            p.go_to(index)
        self.song_list.setCurrentRow(index)

    def _flush_web_scroll(self):
        if self._web_scroll_source and not self._web_scroll_source.isHidden():
            cursor = self._web_scroll_source.view.cursorForPosition(QPoint(0, 1))
            self._web_server.push_scroll_line(cursor.block().blockNumber())
        self._web_scroll_source = None

    def _on_scroll(self, source: PrompterWindow, pos: int):
        for p in self._prompters:
            if p is not source:
                p.set_scroll_pos(pos)
        self._web_scroll_source = source
        if not self._web_scroll_timer.isActive():
            self._web_scroll_timer.start()

    # ── Lancement ─────────────────────────────────────────────────────────────

    def _double_click(self, item):
        self._launch(self.song_list.row(item))

    def _launch(self, start_index: int = 0):
        if not self.songs:
            return

        selected = self._selected_screens()
        if not selected:
            return

        # Ferme les fenêtres précédentes
        for p in self._prompters:
            p.close()
        self._prompters.clear()

        for i, scr in enumerate(selected):
            p = PrompterWindow(self.songs, start_index,
                               on_navigate=self._on_navigate,
                               on_scroll=self._on_scroll,
                               on_display=self._web_server.push_song if i == 0 else None,
                               font_family=self._css_font(),
                               scroll_speed=self._scroll_speed,
                               transpose=self._transpose,
                               on_transpose=self._set_transpose if i == 0 else None,
                               on_autoscroll=self._on_autoscroll_state if i == 0 else None)
            p.view.set_auto_scroll_speed(self._autoscroll_speed)
            p.setGeometry(scr.geometry())
            p.showFullScreen()
            self._prompters.append(p)

        self.btn_launch.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def _stop(self):
        for p in self._prompters:
            p.close()
        self._prompters.clear()
        self._autoscroll_cb.setChecked(False)
        self.btn_stop.setEnabled(False)
        self.btn_launch.setEnabled(bool(self.songs))
        self._web_server.push_setlist([s.title for s in self.songs])

    def closeEvent(self, event):
        for p in self._prompters:
            p.close()
        self._prompters.clear()
        self._web_server.stop()
        _allow_sleep(self._caffeinate)
        event.accept()


# ─── Point d'entrée ───────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Prompt-Live")
    app.setOrganizationName("Prompt-Live")

    _load_bundled_fonts()
    window = ControlWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
