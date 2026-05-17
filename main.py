"""
Prompt-Live — Prompteur musical pour groupes live.
Affiche paroles et accords depuis des fichiers PDF/DOCX numérotés.
Écran externe si branché, sinon plein écran sur l'écran principal.
"""
import sys
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QLabel, QFileDialog, QFrame, QTextBrowser,
    QComboBox, QSlider, QCheckBox,
)
from PyQt6.QtCore import Qt, QSettings, QFileSystemWatcher, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QObject, QEvent
from PyQt6.QtGui import QKeySequence, QShortcut, QWheelEvent, QMouseEvent

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

    def _at_bottom(self, view) -> bool:
        sb = view.verticalScrollBar()
        return sb.maximum() == 0 or sb.value() >= sb.maximum() - self.BOTTOM_MARGIN

    def _at_top(self, view) -> bool:
        return view.verticalScrollBar().value() <= self.BOTTOM_MARGIN

    def eventFilter(self, _obj, event):
        if not self.enabled:
            return False
        if event.type() != QEvent.Type.KeyPress or event.isAutoRepeat():
            return False

        key = event.key()
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

    def __init__(self, on_prev, on_next, on_scroll=None):
        super().__init__()
        self._on_prev   = on_prev
        self._on_next   = on_next
        self._on_scroll = on_scroll  # callable(ratio: float)
        self._scroll_px    = _SPEED_PX[3]
        self._emit_enabled = True
        self._anim = QPropertyAnimation(self.verticalScrollBar(), b"value")
        self._anim.setDuration(_ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuint)
        self.verticalScrollBar().valueChanged.connect(self._on_value_changed)
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


# ─── Fenêtre du prompteur ─────────────────────────────────────────────────────

class PrompterWindow(QMainWindow):

    ZOOM_STEP = 0.1
    ZOOM_MIN = 0.3
    ZOOM_MAX = 3.0

    def __init__(self, songs: list[Song], start_index: int = 0, on_navigate=None, on_scroll=None, on_display=None,
                 font_family: str = "'Courier New',Courier,monospace", scroll_speed: int = 3):
        super().__init__()
        self.songs = songs
        self.current_index = start_index
        self._zoom = 1.0
        self._show_chords: bool | None = None
        self._on_navigate  = on_navigate
        self._on_scroll    = on_scroll
        self._on_display   = on_display
        self._scroll_speed = scroll_speed
        self._font_family  = font_family

        self._watcher = QFileSystemWatcher()
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._reload_timer = QTimer()
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(150)
        self._reload_timer.timeout.connect(self._reload_current)

        # Empêche la mise en veille écran pendant le show
        self._caffeinate = subprocess.Popen(["caffeinate", "-d"])

        self.setWindowTitle("Prompt-Live")
        self.setStyleSheet("background-color: black;")

        root = QWidget()
        root.setStyleSheet("background-color: black;")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(50, 30, 50, 20)
        layout.setSpacing(6)

        # En-tête : titre + compteur
        header = QHBoxLayout()
        self.title_label = QLabel()
        self.title_label.setStyleSheet(
            "color: #666666; font-size: 15px; font-weight: bold;"
        )
        header.addWidget(self.title_label, 1)

        self.counter_label = QLabel()
        self.counter_label.setStyleSheet("color: #444444; font-size: 13px;")
        header.addWidget(self.counter_label)
        layout.addLayout(header)

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
        )
        self.view._scroll_px = _SPEED_PX.get(scroll_speed, 160)
        layout.addWidget(self.view, 1)

        # Pied de page
        hint = QLabel(
            "← / clic gauche : chanson précédente   |   ↑↓ / molette : défilement   |   → / clic droit : chanson suivante"
        )
        hint.setStyleSheet("color: #2a2a2a; font-size: 10px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # Raccourcis clavier
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.close)
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out)
        QShortcut(QKeySequence("A"),      self, self._toggle_chords)

        self._display(self.current_index)

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
        self._caffeinate.terminate()
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
        # Premier appui : on bascule depuis la valeur du fichier
        current = song.show_chords if self._show_chords is None else self._show_chords
        self._show_chords = not current
        self._display(self.current_index)

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

    def _display(self, index: int):
        if not self.songs or index >= len(self.songs):
            return
        song = self.songs[index]
        self._watch(song.file_path)
        self.title_label.setText(song.title.upper())
        self.counter_label.setText(f"{index + 1} / {len(self.songs)}")
        show_chords = song.show_chords if self._show_chords is None else self._show_chords
        html = render_html(song, zoom=self._zoom, show_chords=show_chords, font_family=self._font_family)
        self.view.setHtml(html)
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
        self._web_scroll_timer = QTimer()
        self._web_scroll_timer.setSingleShot(True)
        self._web_scroll_timer.setInterval(80)
        self._web_scroll_source: "PrompterWindow | None" = None
        self._web_scroll_timer.timeout.connect(self._flush_web_scroll)

        settings = QSettings("Prompt-Live", "Prompt-Live")
        self._last_dir: str = settings.value("last_dir", "")
        self._font_family: str = settings.value("font_family", "Menlo")
        self._scroll_speed: int = int(settings.value("scroll_speed", 3))

        self.setWindowTitle("Prompt-Live — Contrôle")
        self.setMinimumSize(460, 580)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Titre
        lbl = QLabel("Prompt-Live  —  Prompteur musical")
        lbl.setStyleSheet("font-size: 17px; font-weight: bold;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        # Sélection du répertoire
        dir_row = QHBoxLayout()
        self.dir_label = QLabel(self._last_dir or "Aucun répertoire sélectionné")
        self.dir_label.setStyleSheet("color: #555; font-size: 11px;")
        self.dir_label.setWordWrap(True)
        dir_row.addWidget(self.dir_label, 1)
        btn_dir = QPushButton("Choisir…")
        btn_dir.setFixedWidth(80)
        btn_dir.clicked.connect(self._choose_dir)
        dir_row.addWidget(btn_dir)
        layout.addLayout(dir_row)

        # Boutons Recharger + Éditer
        reload_row = QHBoxLayout()
        btn_reload = QPushButton("↺  Recharger")
        btn_reload.clicked.connect(self._reload)
        reload_row.addWidget(btn_reload)
        btn_edit = QPushButton("✏  Éditer les chansons")
        btn_edit.clicked.connect(self._open_editor)
        reload_row.addWidget(btn_edit)
        layout.addLayout(reload_row)

        # Liste des chansons
        lbl2 = QLabel("Chansons (double-clic pour lancer depuis cette chanson) :")
        lbl2.setStyleSheet("font-size: 11px; color: #666;")
        layout.addWidget(lbl2)

        self.song_list = QListWidget()
        self.song_list.setStyleSheet("font-size: 13px;")
        self.song_list.itemDoubleClicked.connect(self._double_click)
        layout.addWidget(self.song_list, 1)

        # ── Police ────────────────────────────────────────────────────────────
        sep0 = QFrame(); sep0.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep0)

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Police :"))
        self._font_combo = QComboBox()
        for name in ["Courier New", "Menlo", "Monaco", "Andale Mono", "PT Mono"]:
            self._font_combo.addItem(name)
        idx = self._font_combo.findText(self._font_family)
        if idx >= 0:
            self._font_combo.setCurrentIndex(idx)
        self._font_combo.currentTextChanged.connect(self._on_font_changed)
        font_row.addWidget(self._font_combo, 1)
        layout.addLayout(font_row)

        # ── Vitesse de défilement ──────────────────────────────────────────────
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Défilement :"))
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(1, 5)
        self._speed_slider.setValue(self._scroll_speed)
        self._speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._speed_slider.setTickInterval(1)
        self._speed_slider.valueChanged.connect(self._on_speed_changed)
        speed_row.addWidget(self._speed_slider, 1)
        lbl_slow = QLabel("Lent"); lbl_slow.setStyleSheet("font-size:10px;color:#888;")
        lbl_fast = QLabel("Rapide"); lbl_fast.setStyleSheet("font-size:10px;color:#888;")
        speed_row.insertWidget(1, lbl_slow)
        speed_row.addWidget(lbl_fast)
        layout.addLayout(speed_row)

        # ── Sélection des écrans ───────────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        screen_header = QHBoxLayout()
        screen_header.addWidget(QLabel("Diffusion sur :"))
        btn_refresh = QPushButton("↺")
        btn_refresh.setFixedWidth(30)
        btn_refresh.setFixedHeight(22)
        btn_refresh.setToolTip("Actualiser les écrans")
        btn_refresh.clicked.connect(self._build_screen_buttons)
        screen_header.addWidget(btn_refresh)
        screen_header.addStretch()
        layout.addLayout(screen_header)

        self.screens_row = QHBoxLayout()
        self.screens_row.setSpacing(6)
        layout.addLayout(self.screens_row)

        # ── Accès web (iPad / navigateur) ─────────────────────────────────────
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep2)

        web_row = QHBoxLayout()
        lbl_web = QLabel("iPad / web :")
        lbl_web.setStyleSheet("font-size: 11px;")
        web_row.addWidget(lbl_web)
        self._url_label = QLabel("démarrage…")
        self._url_label.setStyleSheet(
            "color: #1a6ee0; font-size: 12px; font-family: 'Menlo', monospace;"
        )
        self._url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._url_label.setCursor(Qt.CursorShape.IBeamCursor)
        web_row.addWidget(self._url_label, 1)
        layout.addLayout(web_row)

        # Bouton Lancer
        self.btn_launch = QPushButton("▶   Lancer le prompteur")
        self.btn_launch.setEnabled(False)
        self.btn_launch.setFixedHeight(44)
        self.btn_launch.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                border-radius: 6px;
                border: none;
                background-color: #cccccc;
                color: #888888;
            }
            QPushButton:enabled {
                background-color: #1a1a2e;
                color: #ffffff;
            }
            QPushButton:enabled:hover {
                background-color: #2a2a5e;
            }
        """)
        self.btn_launch.clicked.connect(lambda: self._launch(0))

        self.btn_stop = QPushButton("■   Arrêter le prompteur")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setFixedHeight(44)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                border-radius: 6px;
                border: none;
                background-color: #cccccc;
                color: #888888;
            }
            QPushButton:enabled {
                background-color: #5a0000;
                color: #ffffff;
            }
            QPushButton:enabled:hover {
                background-color: #8a0000;
            }
        """)
        self.btn_stop.clicked.connect(self._stop)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_launch)
        btn_row.addWidget(self.btn_stop)
        layout.addLayout(btn_row)

        self._build_screen_buttons()

        # ── Pédale Bluetooth ──────────────────────────────────────────────────
        sep3 = QFrame(); sep3.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep3)

        settings = QSettings("Prompt-Live", "Prompt-Live")
        pedal_enabled = bool(settings.value("pedal_enabled", True, type=bool))
        pedal_speed   = int(settings.value("pedal_speed", 3))

        pedal_row = QHBoxLayout()
        self._pedal_cb = QCheckBox("Pédale BT")
        self._pedal_cb.setChecked(pedal_enabled)
        self._pedal_cb.toggled.connect(self._on_pedal_toggled)
        pedal_row.addWidget(self._pedal_cb)

        pedal_row.addSpacing(12)
        pedal_row.addWidget(QLabel("Vitesse :"))
        self._pedal_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._pedal_speed_slider.setRange(1, 5)
        self._pedal_speed_slider.setValue(pedal_speed)
        self._pedal_speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._pedal_speed_slider.setTickInterval(1)
        self._pedal_speed_slider.valueChanged.connect(self._on_pedal_speed_changed)
        pedal_row.addWidget(self._pedal_speed_slider, 1)
        lbl_ps = QLabel("Lent"); lbl_ps.setStyleSheet("font-size:10px;color:#888;")
        lbl_pf = QLabel("Rapide"); lbl_pf.setStyleSheet("font-size:10px;color:#888;")
        pedal_row.insertWidget(pedal_row.count() - 1, lbl_ps)
        pedal_row.addWidget(lbl_pf)
        layout.addLayout(pedal_row)

        pedal_hint = QLabel("↓ / Espace  défilement     2× ↓ en bas de page → chanson suivante")
        pedal_hint.setStyleSheet("font-size: 10px; color: #888;")
        layout.addWidget(pedal_hint)

        self._pedal_filter = _PedalFilter(lambda: self._prompters)
        self._pedal_filter.enabled    = pedal_enabled
        self._pedal_filter._scroll_px = _SPEED_PX.get(pedal_speed, 160)
        QApplication.instance().installEventFilter(self._pedal_filter)

        # Serveur web — démarre immédiatement, affiche l'URL
        self._web_server = PromptWebServer()
        try:
            url = self._web_server.start()
            self._url_label.setText(url)
        except OSError as e:
            self._url_label.setText(f"Erreur port : {e.strerror}")

        # Écoute les branchements/débranchements d'écrans
        QApplication.instance().screenAdded.connect(lambda _: self._build_screen_buttons())
        QApplication.instance().screenRemoved.connect(lambda _: self._build_screen_buttons())

        QTimer.singleShot(0, self._ask_directory)

    # ── Pédale ────────────────────────────────────────────────────────────────

    def _on_pedal_toggled(self, checked: bool):
        self._pedal_filter.enabled = checked
        QSettings("Prompt-Live", "Prompt-Live").setValue("pedal_enabled", checked)

    def _on_pedal_speed_changed(self, value: int):
        self._pedal_filter._scroll_px = _SPEED_PX.get(value, 160)
        QSettings("Prompt-Live", "Prompt-Live").setValue("pedal_speed", value)

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
            label = f"{'★ ' if is_primary else ''}Écran {i + 1}\n{geo.width()}×{geo.height()}"
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
            flash_label = f"Écran {i + 1}"
            btn.setToolTip("Clic gauche : sélectionner\nClic droit : identifier l'écran")
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
            self, "Choisir le répertoire des chansons", self._last_dir,
            QFileDialog.Option.DontUseNativeDialog,
        )
        if d:
            self._set_dir(d)
        elif self._last_dir:
            self._reload()

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Choisir le répertoire des chansons", self._last_dir,
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
            self.song_list.addItem(f"Erreur : {e}")
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
                               scroll_speed=self._scroll_speed)
            p.setGeometry(scr.geometry())
            p.showFullScreen()
            self._prompters.append(p)

        self.btn_launch.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def _stop(self):
        for p in self._prompters:
            p.close()
        self._prompters.clear()
        self.btn_stop.setEnabled(False)
        self.btn_launch.setEnabled(bool(self.songs))
        self._web_server.push_setlist([s.title for s in self.songs])

    def closeEvent(self, event):
        for p in self._prompters:
            p.close()
        self._prompters.clear()
        self._web_server.stop()
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
