"""
Éditeur .prompt WYSIWYG — édition directe sur le rendu.
Panneau latéral pour tous les paramètres + gestion des acteurs.
"""
import os
import re
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QScrollArea, QLabel, QPushButton, QComboBox,
    QLineEdit, QSpinBox, QCheckBox, QInputDialog, QMessageBox, QFrame,
    QColorDialog,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QFontMetrics, QTextCharFormat, QKeySequence, QShortcut,
    QTextCursor, QTextBlockUserData, QTextBlockFormat,
)
from parsers import parse_prompt_text
from renderer import _wrap_splits, _rebuild_chord_text


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _recolor(block, color: str):
    bc = QTextCursor(block)
    bc.movePosition(QTextCursor.MoveOperation.StartOfBlock)
    bc.movePosition(QTextCursor.MoveOperation.EndOfBlock,
                    QTextCursor.MoveMode.KeepAnchor)
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    bc.mergeCharFormat(fmt)

def _resize_block(block, size: float):
    bc = QTextCursor(block)
    bc.movePosition(QTextCursor.MoveOperation.StartOfBlock)
    bc.movePosition(QTextCursor.MoveOperation.EndOfBlock,
                    QTextCursor.MoveMode.KeepAnchor)
    fmt = QTextCharFormat()
    fmt.setFontPointSize(size)
    bc.mergeCharFormat(fmt)

def _extract_header(content: str) -> str:
    m = re.search(r'^\[', content, re.MULTILINE)
    return content[:m.start()].rstrip('\n') if m else content


# ── Métadonnées par bloc ──────────────────────────────────────────────────────

class _BD(QTextBlockUserData):
    def __init__(self, tag='', is_section=False, is_chord=False, is_note=False,
                 is_split=False, full_text=''):
        super().__init__()
        self.tag        = tag
        self.is_section = is_section
        self.is_chord   = is_chord
        self.is_note    = is_note
        self.is_split   = is_split    # True = bloc de continuation (display only)
        self.full_text  = full_text   # texte original complet sur le 1er bloc d'une paire scindée


# ── Bouton couleur ────────────────────────────────────────────────────────────

class ColorButton(QPushButton):
    color_changed = pyqtSignal(str)

    def __init__(self, color='#888888', parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self._color = color.upper() if color.startswith('#') else color.upper()
        self._apply()

    def _apply(self):
        self.setStyleSheet(
            f"background:{self._color}; border:1px solid #aaa; border-radius:3px;"
        )

    @property
    def color(self): return self._color

    def set_color(self, c: str, emit=True):
        self._color = c.upper()
        self._apply()
        if emit:
            self.color_changed.emit(self._color)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            c = QColorDialog.getColor(QColor(self._color), self, "Couleur")
            if c.isValid():
                self.set_color(c.name().upper())
        else:
            super().mousePressEvent(event)


# ── QTextEdit éditable ────────────────────────────────────────────────────────

class _SongEdit(QTextEdit):
    def __init__(self):
        super().__init__()
        self._lyrics_size: float = 28.0
        self._font_family: str = "Courier New"
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#ffffff"))
            fmt.setFontPointSize(self._lyrics_size)
            fmt.setFontWeight(700)
            fmt.setFontFamilies([self._font_family])
            self.textCursor().insertBlock(QTextBlockFormat(), fmt)
        else:
            super().keyPressEvent(event)


# ── Panneau latéral de paramètres ─────────────────────────────────────────────

class _SettingsPanel(QScrollArea):

    # Signaux émis quand l'utilisateur change un réglage
    chord_color_changed   = pyqtSignal(str)
    section_color_changed = pyqtSignal(str)
    font_lyrics_changed   = pyqtSignal(int)
    font_chords_changed   = pyqtSignal(int)
    font_section_changed  = pyqtSignal(int)
    tag_color_changed     = pyqtSignal(str, str)  # (name, color)
    tag_added             = pyqtSignal(str, str)  # (name, color)
    tag_renamed           = pyqtSignal(str, str)  # (old, new)
    tag_deleted           = pyqtSignal(str)        # (name)
    show_chords_changed   = pyqtSignal(bool)
    meta_changed          = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(230)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        self._vbox = QVBoxLayout(inner)
        self._vbox.setContentsMargins(10, 14, 10, 14)
        self._vbox.setSpacing(8)
        self._vbox.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ── Métadonnées ───────────────────────────────────────────────────────
        self._vbox.addWidget(self._sep_label("MÉTADONNÉES"))

        self._titre = QLineEdit()
        self._titre.textChanged.connect(self.meta_changed)
        self._add_row("Titre", self._titre)

        # ── Tailles ───────────────────────────────────────────────────────────
        self._vbox.addWidget(self._sep_label("TAILLES (px)"))

        self._sz_lyrics = self._spinbox(8, 144)
        self._sz_lyrics.valueChanged.connect(self.font_lyrics_changed)
        self._add_row("Paroles", self._sz_lyrics)

        self._sz_chords = self._spinbox(8, 144)
        self._sz_chords.valueChanged.connect(self.font_chords_changed)
        self._add_row("Accords", self._sz_chords)

        self._sz_section = self._spinbox(8, 144)
        self._sz_section.valueChanged.connect(self.font_section_changed)
        self._add_row("Sections", self._sz_section)

        # ── Couleurs ──────────────────────────────────────────────────────────
        self._vbox.addWidget(self._sep_label("COULEURS"))

        self._col_chords = ColorButton()
        self._col_chords.color_changed.connect(self.chord_color_changed)
        self._add_row("Accords", self._col_chords)

        self._col_section = ColorButton()
        self._col_section.color_changed.connect(self.section_color_changed)
        self._add_row("Sections", self._col_section)

        self._show_chords = QCheckBox("Afficher les accords")
        self._show_chords.toggled.connect(self.show_chords_changed)
        self._show_chords.toggled.connect(lambda _: self.meta_changed.emit())
        self._vbox.addWidget(self._show_chords)

        # ── Acteurs ───────────────────────────────────────────────────────────
        self._vbox.addWidget(self._sep_label("ACTEURS"))

        self._tags_box = QVBoxLayout()
        self._tags_box.setSpacing(4)
        self._vbox.addLayout(self._tags_box)

        btn_add = QPushButton("+ Ajouter un acteur")
        btn_add.setFixedHeight(26)
        btn_add.clicked.connect(self._add_tag_dialog)
        self._vbox.addWidget(btn_add)

        self._vbox.addStretch()
        self.setWidget(inner)

        self._current_tags: list[str] = []  # noms dans l'ordre courant

    # ── Chargement ────────────────────────────────────────────────────────────

    def load(self, song):
        for w, sig, val in [
            (self._titre,      'textChanged', song.title),
            (self._sz_lyrics,  'valueChanged', song.font_lyrics),
            (self._sz_chords,  'valueChanged', song.font_chords),
            (self._sz_section, 'valueChanged', song.font_section),
        ]:
            w.blockSignals(True)
            (w.setText if isinstance(w, QLineEdit) else w.setValue)(val)
            w.blockSignals(False)

        self._col_chords.set_color(song.chord_color, emit=False)
        self._col_section.set_color(song.section_color, emit=False)

        self._show_chords.blockSignals(True)
        self._show_chords.setChecked(song.show_chords)
        self._show_chords.blockSignals(False)

        self.rebuild_tags(song)

    def rebuild_tags(self, song):
        """Recrée les lignes d'acteurs depuis les données de la chanson."""
        while self._tags_box.count():
            w = self._tags_box.takeAt(0).widget()
            if w: w.deleteLater()
        self._current_tags.clear()
        for key in song.tags:
            name  = song.tag_names.get(key, key.capitalize())
            color = song.tags[key]
            self._insert_tag_row(name, color)

    def _insert_tag_row(self, name: str, color: str):
        row = QWidget()
        row.setStyleSheet("background:transparent;")
        rh = QHBoxLayout(row)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.setSpacing(4)

        cb = ColorButton(color)
        cb.color_changed.connect(lambda c, n=name: self.tag_color_changed.emit(n, c))
        rh.addWidget(cb)

        lbl = QLabel(name)
        lbl.setStyleSheet("color:#ccc; font-size:12px;")
        rh.addWidget(lbl, 1)

        btn_ren = self._icon_btn("✏")
        btn_ren.setToolTip("Renommer")
        btn_ren.clicked.connect(lambda _, n=name, l=lbl, c=cb: self._rename_tag(n, l, c))
        rh.addWidget(btn_ren)

        btn_del = self._icon_btn("−", hover_color="#f55")
        btn_del.setToolTip("Supprimer")
        btn_del.clicked.connect(lambda _, n=name, r=row: self._delete_tag(n, r))
        rh.addWidget(btn_del)

        self._tags_box.addWidget(row)
        self._current_tags.append(name)

    def _add_tag_dialog(self):
        name, ok = QInputDialog.getText(self, "Nouvel acteur", "Prénom :")
        if not ok or not name.strip():
            return
        c = QColorDialog.getColor(QColor("#FF5555"), self, "Couleur de l'acteur")
        color = c.name().upper() if c.isValid() else "#FF5555"
        self._insert_tag_row(name.strip(), color)
        self.tag_added.emit(name.strip(), color)

    def _rename_tag(self, old_name: str, lbl: QLabel, cb: ColorButton):
        new_name, ok = QInputDialog.getText(
            self, "Renommer l'acteur", "Nouveau prénom :", text=old_name
        )
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        # Met à jour le label et reconnecte le bouton couleur
        lbl.setText(new_name.strip())
        cb.color_changed.disconnect()
        cb.color_changed.connect(
            lambda c, n=new_name.strip(): self.tag_color_changed.emit(n, c)
        )
        self.tag_renamed.emit(old_name, new_name.strip())

    def _delete_tag(self, name: str, row: QWidget):
        row.deleteLater()
        if name in self._current_tags:
            self._current_tags.remove(name)
        self.tag_deleted.emit(name)

    # ── Getters pour la sauvegarde ────────────────────────────────────────────

    def titre(self):       return self._titre.text().strip()
    def show_chords(self): return self._show_chords.isChecked()

    # ── Helpers UI ────────────────────────────────────────────────────────────

    def _sep_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size:9px; letter-spacing:1px; color:#888;"
            "border-top:1px solid #ccc; padding-top:8px; margin-top:4px;"
        )
        return lbl

    def _add_row(self, label, widget):
        row = QHBoxLayout()
        row.setSpacing(6)
        lbl = QLabel(label)
        lbl.setStyleSheet("font-size:11px;")
        lbl.setFixedWidth(60)
        row.addWidget(lbl)
        row.addWidget(widget)
        self._vbox.addLayout(row)

    def _spinbox(self, lo, hi):
        sb = QSpinBox()
        sb.setRange(lo, hi)
        sb.setFixedHeight(24)
        return sb

    def _icon_btn(self, icon, hover_color="#000"):
        btn = QPushButton(icon)
        btn.setFixedSize(22, 22)
        btn.setStyleSheet("font-size:11px;")
        return btn


# ── Fenêtre éditeur ───────────────────────────────────────────────────────────

class EditorWindow(QMainWindow):

    def __init__(self, directory: str = "", on_save=None, font_family: str = "Courier New", parent=None):
        super().__init__(parent)
        self._directory    = directory
        self._on_save      = on_save
        self._font_family  = font_family
        self._current_path = ""
        self._modified     = False
        self._song         = None

        self.setWindowTitle("Prompt-Live — Éditeur")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        root = QWidget()
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # ── Barre d'outils ────────────────────────────────────────────────────
        bar = QWidget()
        bar.setFixedHeight(46)
        bh = QHBoxLayout(bar)
        bh.setContentsMargins(8, 0, 8, 0)
        bh.setSpacing(6)

        self._combo = QComboBox()
        self._combo.setFixedWidth(240)
        self._combo.currentIndexChanged.connect(self._on_combo_changed)
        bh.addWidget(self._combo)
        bh.addWidget(self._mkbtn("+ Nouveau", self._new_file))

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color:#333;"); bh.addWidget(sep)

        self._tag_zone = QHBoxLayout()
        self._tag_zone.setSpacing(4)
        bh.addLayout(self._tag_zone)

        bh.addStretch()
        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("font-size:11px;")
        bh.addWidget(self._lbl_status)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet("color:#333;"); bh.addWidget(sep2)

        self._btn_save = self._mkbtn("Sauvegarder  ⌘S", self._save,
                                     enabled=False, active_bg="#1a1a2e")
        bh.addWidget(self._btn_save)
        vbox.addWidget(bar)

        # ── Splitter éditeur | paramètres ─────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._edit = _SongEdit()
        self._edit.setStyleSheet("""
            QTextEdit {
                background:#000000; border:none; padding:30px 50px;
            }
            QScrollBar:vertical { background:#111; width:6px; }
            QScrollBar::handle:vertical { background:#333; border-radius:3px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
            QScrollBar:horizontal { background:#111; height:6px; }
            QScrollBar::handle:horizontal { background:#333; border-radius:3px; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
        """)
        self._edit.textChanged.connect(self._on_changed)
        splitter.addWidget(self._edit)

        self._rebuild_timer = QTimer()
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.setInterval(300)
        self._rebuild_timer.timeout.connect(self._rebuild_splits)

        self._panel = _SettingsPanel()
        self._panel.chord_color_changed.connect(self._on_chord_color)
        self._panel.section_color_changed.connect(self._on_section_color)
        self._panel.font_lyrics_changed.connect(
            lambda v: self._on_font_change('lyrics', v))
        self._panel.font_chords_changed.connect(
            lambda v: self._on_font_change('chords', v))
        self._panel.font_section_changed.connect(
            lambda v: self._on_font_change('section', v))
        self._panel.tag_color_changed.connect(self._on_tag_color)
        self._panel.tag_added.connect(self._on_tag_add)
        self._panel.tag_renamed.connect(self._on_tag_rename)
        self._panel.tag_deleted.connect(self._on_tag_delete)
        self._panel.show_chords_changed.connect(self._on_show_chords)
        self._panel.meta_changed.connect(self._mark_modified)
        splitter.addWidget(self._panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        vbox.addWidget(splitter, 1)

        # ── Pied de page ──────────────────────────────────────────────────────
        foot = QWidget()
        fh = QHBoxLayout(foot)
        fh.setContentsMargins(12, 3, 12, 3)
        self._lbl_pos = QLabel("Ln 1, Col 1")
        self._lbl_pos.setStyleSheet("font-size:10px; color:#888;")
        fh.addStretch()
        fh.addWidget(self._lbl_pos)
        vbox.addWidget(foot)

        self._edit.cursorPositionChanged.connect(self._update_pos)
        QShortcut(QKeySequence.StandardKey.Save, self, self._save)

        if directory:
            self._refresh_combo()

    # ── Helpers UI ────────────────────────────────────────────────────────────

    def _mkbtn(self, label, slot, enabled=True, active_bg="#2e2e2e"):
        btn = QPushButton(label)
        btn.setFixedHeight(28)
        btn.setEnabled(enabled)
        btn.clicked.connect(slot)
        return btn

    # ── Fichiers ──────────────────────────────────────────────────────────────

    def set_directory(self, d: str):
        self._directory = d
        self._refresh_combo()

    def _refresh_combo(self):
        self._combo.blockSignals(True)
        self._combo.clear()
        cur = 0
        if self._directory and os.path.isdir(self._directory):
            for i, name in enumerate(sorted(
                f for f in os.listdir(self._directory)
                if f.lower().endswith(".prompt")
            )):
                path = os.path.join(self._directory, name)
                self._combo.addItem(name, userData=path)
                if path == self._current_path:
                    cur = i
        self._combo.blockSignals(False)
        if self._combo.count():
            self._combo.setCurrentIndex(cur)
            if not self._current_path:
                self._load(self._combo.itemData(0))

    def _on_combo_changed(self, idx):
        if idx < 0: return
        path = self._combo.itemData(idx)
        if path == self._current_path: return
        if not self._confirm_discard():
            self._combo.blockSignals(True)
            for i in range(self._combo.count()):
                if self._combo.itemData(i) == self._current_path:
                    self._combo.setCurrentIndex(i); break
            self._combo.blockSignals(False)
            return
        self._load(path)

    def _load(self, path: str):
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
        except Exception as e:
            self._set_status(f"Erreur : {e}"); return
        self._current_path = path
        try:
            song = parse_prompt_text(raw, path)
        except Exception as e:
            self._set_status(f"Parse : {e}"); return
        self._song = song
        self._edit._lyrics_size = float(song.font_lyrics)
        self._edit._font_family = self._font_family
        self._edit.setFont(QFont(self._font_family))
        self._build_document(song)
        self._panel.load(song)
        self._rebuild_tag_buttons(song)
        self._set_modified(False)
        self._set_status(os.path.basename(path))

    def _save(self):
        if not self._current_path or not self._song: return
        header = self._build_header()
        content = self._extract_content()
        try:
            with open(self._current_path, "w", encoding="utf-8") as f:
                f.write(header + "\n\n" + content)
        except Exception as e:
            self._set_status(f"Erreur : {e}"); return
        self._set_modified(False)
        self._set_status(f"{os.path.basename(self._current_path)}  ✓")
        if self._on_save:
            self._on_save()

    def _new_file(self):
        if not self._directory or not self._confirm_discard(): return
        existing = [n for n in os.listdir(self._directory)
                    if n.lower().endswith(".prompt")]
        default = f"{len(existing)+1:02d}_Nouvelle chanson.prompt"
        name, ok = QInputDialog.getText(self, "Nouveau fichier", "Nom :", text=default)
        if not ok or not name.strip(): return
        if not name.lower().endswith(".prompt"):
            name += ".prompt"
        path = os.path.join(self._directory, name.strip())
        if os.path.exists(path):
            self._set_status("Existe déjà."); return
        base = re.sub(r'^[\d_ -]+', '', os.path.splitext(name.strip())[0])
        tpl = f"Titre: {base}\nTailleParoles: 28\n\n[Intro]\n"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(tpl)
        except Exception as e:
            self._set_status(f"Erreur : {e}"); return
        self._refresh_combo()
        for i in range(self._combo.count()):
            if self._combo.itemData(i) == path:
                self._combo.setCurrentIndex(i); break

    # ── Document ──────────────────────────────────────────────────────────────

    def _build_document(self, song):
        self._edit.blockSignals(True)
        self._edit.clear()
        cursor = self._edit.textCursor()
        first = True

        lh = self._edit._lyrics_size * 1.45

        for section in song.sections:
            if section.label:
                bf = QTextBlockFormat()
                bf.setLineHeight(lh, QTextBlockFormat.LineHeightTypes.FixedHeight.value)
                if not first:
                    cursor.insertBlock(bf)
                else:
                    cursor.setBlockFormat(bf)
                first = False

                fmt_lbl = QTextCharFormat()
                fmt_lbl.setForeground(QColor(song.section_color))
                fmt_lbl.setFontPointSize(float(song.font_section))
                fmt_lbl.setFontWeight(700)
                fmt_lbl.setFontFamilies([self._font_family])
                cursor.insertText(f"[{section.label}]", fmt_lbl)

                if section.singer:
                    tag_color = song.tags.get(section.singer.lower(), song.section_color)
                    fmt_sg = QTextCharFormat()
                    fmt_sg.setForeground(QColor(tag_color))
                    fmt_sg.setFontPointSize(float(song.font_section))
                    fmt_sg.setFontWeight(700)
                    fmt_sg.setFontFamilies([self._font_family])
                    cursor.insertText(f" ▸ {section.singer}", fmt_sg)

                cursor.block().setUserData(_BD(tag=section.singer or "", is_section=True))

            lines = section.lines
            idx = 0
            while idx < len(lines):
                line = lines[idx]

                if line.is_note:
                    self._ins(cursor, line.text, "#666666", song.font_lyrics,
                              italic=True, bd=_BD(is_note=True), first=first)
                    first = False
                    idx += 1
                    continue

                # Accord + parole longue → découpage synchronisé
                if line.is_chord and idx + 1 < len(lines):
                    nxt = lines[idx + 1]
                    cpl = self._chars_per_line()
                    if (cpl > 0 and not nxt.is_chord and not nxt.is_note
                            and nxt.text.strip() and len(nxt.text) > cpl):
                        color = nxt.color or section.color or "#ffffff"
                        tag   = nxt.singer or ("" if nxt.color else (section.singer or ""))
                        slices = _wrap_splits(nxt.text, cpl)
                        for i, (s0, s1) in enumerate(slices):
                            chord_chunk = _rebuild_chord_text(line.chord_positions, s0, s1)
                            lyric_chunk = nxt.text[s0:s1]
                            is_cont = (i > 0)
                            # Bloc accord (seulement s'il y a des accords sur cette tranche)
                            if chord_chunk:
                                self._ins(cursor, chord_chunk, song.chord_color, song.font_chords,
                                          bd=_BD(is_chord=True,
                                                 is_split=is_cont,
                                                 full_text=line.text if i == 0 else ''),
                                          first=first)
                                first = False
                            # Bloc parole
                            self._ins(cursor, lyric_chunk, color, song.font_lyrics,
                                      bd=_BD(tag=tag,
                                             is_split=is_cont,
                                             full_text=nxt.text if i == 0 else ''),
                                      first=first)
                            first = False
                        idx += 2
                        continue

                # Cas normal
                if line.is_chord:
                    self._ins(cursor, line.text, song.chord_color, song.font_chords,
                              bd=_BD(is_chord=True), first=first)
                else:
                    color = line.color or section.color or "#ffffff"
                    effective_tag = line.singer or ("" if line.color else (section.singer or ""))
                    self._ins(cursor, line.text, color, song.font_lyrics,
                              bd=_BD(tag=effective_tag), first=first)
                first = False
                idx += 1

        self._edit.blockSignals(False)
        self._edit.verticalScrollBar().setValue(0)

    def _ins(self, cursor, text, color, size, bold=False, italic=False, bd=None, first=False):
        lh = self._edit._lyrics_size * 1.45
        bf = QTextBlockFormat()
        bf.setLineHeight(lh, QTextBlockFormat.LineHeightTypes.FixedHeight.value)
        if not first:
            cursor.insertBlock(bf)
        else:
            cursor.setBlockFormat(bf)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        fmt.setFontPointSize(float(size))
        fmt.setFontWeight(400 if italic else 700)
        fmt.setFontItalic(italic)
        fmt.setFontFamilies([self._font_family])
        cursor.insertText(text, fmt)
        if bd:
            cursor.block().setUserData(bd)

    def _render_section_block(self, block, bd):
        """Réécrit le texte ET le formatage d'un bloc section (quand le texte change)."""
        text = block.text()
        label = re.sub(r'\s*▸.*$', '', text).strip()
        sec_color = self._song.section_color if self._song else "#AAAAAA"
        sec_size  = float(self._song.font_section) if self._song else 16.0

        bc = QTextCursor(block)
        bc.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        bc.movePosition(QTextCursor.MoveOperation.EndOfBlock,
                        QTextCursor.MoveMode.KeepAnchor)

        fmt_lbl = QTextCharFormat()
        fmt_lbl.setForeground(QColor(sec_color))
        fmt_lbl.setFontPointSize(sec_size)
        fmt_lbl.setFontWeight(700)
        bc.insertText(label, fmt_lbl)

        if bd.tag:
            tag_color = (self._song.tags.get(bd.tag.lower(), sec_color)
                         if self._song else sec_color)
            fmt_sg = QTextCharFormat()
            fmt_sg.setForeground(QColor(tag_color))
            fmt_sg.setFontPointSize(sec_size)
            fmt_sg.setFontWeight(400)
            bc.insertText(f" ▸ {bd.tag}", fmt_sg)

    def _reformat_section_block(self, block, bd):
        """Met à jour couleurs et taille d'un bloc section via mergeCharFormat (pas de changement de texte)."""
        text = block.text()
        arrow_pos = text.find(' ▸ ')
        label_end = arrow_pos if arrow_pos >= 0 else len(text)
        base      = block.position()

        sec_color = self._song.section_color if self._song else "#AAAAAA"
        sec_size  = float(self._song.font_section) if self._song else 16.0

        doc = self._edit.document()

        # Label [...]
        bc = QTextCursor(doc)
        bc.setPosition(base)
        bc.setPosition(base + label_end, QTextCursor.MoveMode.KeepAnchor)
        fmt_lbl = QTextCharFormat()
        fmt_lbl.setForeground(QColor(sec_color))
        fmt_lbl.setFontPointSize(sec_size)
        fmt_lbl.setFontWeight(700)
        bc.mergeCharFormat(fmt_lbl)

        # ▸ Nom
        if arrow_pos >= 0 and bd.tag:
            tag_color = (self._song.tags.get(bd.tag.lower(), sec_color)
                         if self._song else sec_color)
            bc.setPosition(base + arrow_pos)
            bc.setPosition(base + len(text), QTextCursor.MoveMode.KeepAnchor)
            fmt_sg = QTextCharFormat()
            fmt_sg.setForeground(QColor(tag_color))
            fmt_sg.setFontPointSize(sec_size)
            fmt_sg.setFontWeight(400)
            bc.mergeCharFormat(fmt_sg)

    # ── Boutons @Tag ──────────────────────────────────────────────────────────

    def _rebuild_tag_buttons(self, song):
        while self._tag_zone.count():
            w = self._tag_zone.takeAt(0).widget()
            if w: w.deleteLater()

        for key, color in song.tags.items():
            name = song.tag_names.get(key, key.capitalize())
            btn = QPushButton(name)
            btn.setFixedHeight(26)
            btn.setToolTip(f"Colorer la sélection avec @{name}")
            btn.setStyleSheet(f"""
                QPushButton {{
                    font-size:11px; font-weight:bold; border-radius:4px;
                    border:2px solid {color}; background:transparent;
                    color:{color}; padding:0 10px;
                }}
                QPushButton:hover {{ background:{color}; color:#fff; }}
            """)
            btn.clicked.connect(lambda _c, n=name, c=color: self._apply_tag(n, c))
            self._tag_zone.addWidget(btn)

        if song.tags:
            btn_rm = QPushButton("✕")
            btn_rm.setFixedSize(26, 26)
            btn_rm.setToolTip("Retirer le tag")
            btn_rm.clicked.connect(self._remove_tag)
            self._tag_zone.addWidget(btn_rm)

    # ── Application des tags (lyrics uniquement) ──────────────────────────────

    def _apply_tag(self, name: str, color: str):
        def toggle(block, bd):
            if bd.is_chord:
                return
            if bd.is_section:
                if bd.tag and bd.tag.lower() == name.lower():
                    bd.tag = ""
                    self._recolor_section_lines(block, "", "#ffffff")
                else:
                    bd.tag = name
                    self._recolor_section_lines(block, name, color)
                self._render_section_block(block, bd)
            else:
                if bd.tag and bd.tag.lower() == name.lower():
                    bd.tag = ""
                    _recolor(block, "#ffffff")
                else:
                    bd.tag = name
                    _recolor(block, color)

        self._on_selection(toggle)

    def _section_singer_for(self, block) -> str:
        """Remonte le document pour trouver le chanteur de la section parente."""
        b = block.previous()
        while b.isValid():
            bd = b.userData()
            if bd and bd.is_section:
                return bd.tag or ""
            b = b.previous()
        return ""

    def _remove_tag(self):
        def clear(block, bd):
            if bd.is_chord:
                return
            if bd.is_section:
                if bd.tag:
                    bd.tag = ""
                    self._render_section_block(block, bd)
            else:
                section_singer = self._section_singer_for(block)
                if section_singer and self._song:
                    bd.tag = section_singer
                    color = self._song.tags.get(section_singer.lower(), "#ffffff")
                else:
                    bd.tag = ""
                    color = "#ffffff"
                _recolor(block, color)

        self._on_selection(clear)

    def _recolor_section_lines(self, section_block, singer: str, color: str):
        """Recolore toutes les lignes de la section avec la couleur du chanteur (ou blanc)."""
        block = section_block.next()
        while block.isValid():
            bd = block.userData()
            if bd is None:
                bd = _BD(); block.setUserData(bd)
            if bd.is_section:
                break
            if not bd.is_chord and not bd.is_note:
                bd.tag = singer
                _recolor(block, color)
            block = block.next()

    def _on_selection(self, fn):
        cursor = self._edit.textCursor()
        s = min(cursor.anchor(), cursor.position())
        e = max(cursor.anchor(), cursor.position())
        doc = self._edit.document()
        first_block = doc.findBlock(s)
        last_block  = doc.findBlock(max(s, e - 1))
        cursor.beginEditBlock()
        block = first_block
        while block.isValid():
            bd = block.userData()
            if bd is None:
                bd = _BD(); block.setUserData(bd)
            fn(block, bd)
            if block == last_block: break
            block = block.next()
        cursor.endEditBlock()

    # ── Réactions aux changements de paramètres ───────────────────────────────

    def _on_show_chords(self, show: bool):
        if self._song:
            self._song.show_chords = show
        chord_color  = self._song.chord_color  if self._song else "#888888"
        chord_size   = float(self._song.font_chords) if self._song else 18.0

        def apply(b, bd):
            bc = QTextCursor(b)
            bc.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            bc.movePosition(QTextCursor.MoveOperation.EndOfBlock,
                            QTextCursor.MoveMode.KeepAnchor)
            fmt = QTextCharFormat()
            if show:
                fmt.setForeground(QColor(chord_color))
                fmt.setFontPointSize(chord_size)
            else:
                fmt.setForeground(QColor("#000000"))  # fond noir = invisible
                fmt.setFontPointSize(0.1)
            bc.mergeCharFormat(fmt)

        self._iter_blocks(lambda b, bd: bd.is_chord, apply)
        self._mark_modified()

    def _on_chord_color(self, color: str):
        if self._song: self._song.chord_color = color
        if self._song and self._song.show_chords:
            self._iter_blocks(lambda b, bd: bd.is_chord, lambda b, _: _recolor(b, color))
        self._mark_modified()

    def _on_section_color(self, color: str):
        if self._song: self._song.section_color = color
        self._iter_blocks(
            lambda b, bd: bd.is_section,
            lambda b, bd: self._reformat_section_block(b, bd),
        )
        self._mark_modified()

    def _on_font_change(self, kind: str, size: int):
        if self._song:
            if   kind == 'lyrics':  self._song.font_lyrics  = size
            elif kind == 'chords':  self._song.font_chords  = size
            elif kind == 'section': self._song.font_section = size
            self._edit._lyrics_size = float(self._song.font_lyrics)

        lh_lyrics = self._edit._lyrics_size * 1.45

        def apply(b, bd):
            if kind == 'lyrics':
                bc = QTextCursor(b)
                bf = QTextBlockFormat()
                bf.setLineHeight(lh_lyrics, QTextBlockFormat.LineHeightTypes.FixedHeight.value)
                bc.setBlockFormat(bf)
                if not bd.is_section and not bd.is_chord:
                    _resize_block(b, float(size))
            elif kind == 'chords' and bd.is_chord:
                _resize_block(b, float(size))
            elif kind == 'section' and bd.is_section:
                self._reformat_section_block(b, bd)

        self._iter_blocks(lambda b, bd: True, apply)
        self._mark_modified()
        # La taille de police modifie chars_per_line → recalculer les découpes
        if kind == 'lyrics':
            self._rebuild_timer.start()

    def _on_tag_color(self, name: str, color: str):
        if self._song:
            key = name.lower()
            self._song.tags[key] = color
            def apply(b, bd):
                if bd.tag.lower() == key:
                    if bd.is_section:
                        self._reformat_section_block(b, bd)
                    else:
                        _recolor(b, color)
            self._iter_blocks(lambda b, bd: bool(bd.tag), apply)
            self._rebuild_tag_buttons(self._song)
        self._mark_modified()

    def _on_tag_add(self, name: str, color: str):
        if self._song:
            key = name.lower()
            self._song.tags[key] = color
            self._song.tag_names[key] = name
            self._rebuild_tag_buttons(self._song)
        self._mark_modified()

    def _on_tag_rename(self, old_name: str, new_name: str):
        if self._song:
            old_key, new_key = old_name.lower(), new_name.lower()
            color = self._song.tags.pop(old_key, '#ffffff')
            self._song.tags[new_key] = color
            self._song.tag_names.pop(old_key, None)
            self._song.tag_names[new_key] = new_name
        block = self._edit.document().begin()
        while block.isValid():
            bd = block.userData()
            if bd and bd.tag.lower() == old_name.lower():
                bd.tag = new_name
                if bd.is_section:
                    self._render_section_block(block, bd)
            block = block.next()
        if self._song:
            self._rebuild_tag_buttons(self._song)
        self._mark_modified()

    def _on_tag_delete(self, name: str):
        if self._song:
            key = name.lower()
            self._song.tags.pop(key, None)
            self._song.tag_names.pop(key, None)
        def clear(b, bd):
            if bd.tag.lower() == name.lower():
                bd.tag = ""
                if bd.is_section:
                    self._render_section_block(b, bd)
                else:
                    _recolor(b, "#ffffff")
        self._iter_blocks(lambda b, bd: bool(bd.tag), clear)
        if self._song:
            self._rebuild_tag_buttons(self._song)
        self._mark_modified()

    def _iter_blocks(self, predicate, action):
        doc = self._edit.document()
        cursor = self._edit.textCursor()
        cursor.beginEditBlock()
        block = doc.begin()
        while block.isValid():
            bd = block.userData()
            if bd is None:
                bd = _BD(); block.setUserData(bd)
            if predicate(block, bd):
                action(block, bd)
            block = block.next()
        cursor.endEditBlock()

    # ── Reconstruction de l'en-tête ───────────────────────────────────────────

    def _build_header(self) -> str:
        s = self._song
        p = self._panel
        lines = [f"Titre: {p.titre() or s.title}"]
        lines += [
            f"TailleParoles: {s.font_lyrics}",
            f"TailleAccords: {s.font_chords}",
            f"TailleSection: {s.font_section}",
            f"CouleurSection: {s.section_color}",
            f"CouleurAccords: {s.chord_color}",
        ]
        if not p.show_chords():
            lines.append("AfficherAccords: non")
        if s.tag_names:
            lines.append("")
            for key, orig in s.tag_names.items():
                lines.append(f"@{orig}: {s.tags[key]}")
        return '\n'.join(lines)

    def _chars_per_line(self) -> int:
        if not self._song:
            return 0
        px = max(8, self._song.font_lyrics)
        font = QFont(self._font_family)
        font.setPixelSize(px)
        char_w = QFontMetrics(font).horizontalAdvance('M')
        if char_w <= 0:
            return 0
        return max(0, self._edit.viewport().width() // char_w)

    def _rebuild_splits(self):
        """Re-découpe les blocs selon la largeur courante, sans perdre les éditions."""
        if not self._song:
            return
        try:
            header = self._build_header()
            content = self._extract_content()
            song = parse_prompt_text(header + "\n\n" + content, self._current_path)
            self._song = song
        except Exception:
            return
        cursor = self._edit.textCursor()
        bn  = cursor.blockNumber()
        pos = cursor.positionInBlock()
        self._build_document(song)
        doc = self._edit.document()
        target = doc.findBlockByNumber(min(bn, doc.blockCount() - 1))
        nc = QTextCursor(target)
        nc.setPosition(target.position() + min(pos, max(0, target.length() - 1)))
        self._edit.setTextCursor(nc)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild_timer.start()

    def _extract_content(self) -> str:
        lines = []
        block = self._edit.document().begin()
        while block.isValid():
            text = block.text()
            bd   = block.userData()

            # Blocs de continuation : ignorés (leur contenu est dans full_text du 1er bloc)
            if bd and bd.is_split:
                block = block.next()
                continue

            tag    = bd.tag if bd else ""
            is_sec = (bd and bd.is_section) or bool(re.match(r'^\s*\[', text))

            if not text.strip():
                lines.append(" ")
            elif is_sec:
                clean = re.sub(r'\s*▸.*$', '', text).strip()
                lines.append(clean + (f"@{tag}" if tag else ""))
            else:
                # Si ce bloc est le 1er d'une paire scindée, restaurer le texte complet
                # (full_text = texte d'origine avant découpage)
                full = bd.full_text if bd and bd.full_text else text
                lines.append(full + (f" @{tag}" if tag else ""))

            block = block.next()
        return '\n'.join(lines)

    # ── État ─────────────────────────────────────────────────────────────────

    def _on_changed(self):
        if self._current_path:
            self._mark_modified()

    def _mark_modified(self):
        self._set_modified(True)

    def _set_modified(self, v: bool):
        self._modified = v
        self._btn_save.setEnabled(bool(self._current_path))
        name = os.path.basename(self._current_path) if self._current_path else ""
        dot  = " •" if v and name else ""
        self.setWindowTitle(f"Prompt-Live — Éditeur{('  —  ' + name + dot) if name else ''}")

    def _set_status(self, msg: str):
        self._lbl_status.setText(msg)
        if "✓" in msg:
            QTimer.singleShot(2500, lambda: self._lbl_status.setText(
                os.path.basename(self._current_path) if self._current_path else ""
            ))

    def _update_pos(self):
        c = self._edit.textCursor()
        self._lbl_pos.setText(f"Ln {c.blockNumber()+1},  Col {c.columnNumber()+1}")

    def _confirm_discard(self) -> bool:
        if not self._modified: return True
        reply = QMessageBox.question(
            self, "Modifications non sauvegardées",
            f"Sauvegarder « {os.path.basename(self._current_path)} » ?",
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            self._save(); return True
        return reply == QMessageBox.StandardButton.Discard

    def closeEvent(self, event):
        if self._confirm_discard(): event.accept()
        else: event.ignore()
