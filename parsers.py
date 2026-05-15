import os
import re
from dataclasses import dataclass, field
from typing import Optional


NAMED_COLORS: dict[str, str] = {
    "rouge": "#FF5555", "red": "#FF5555",
    "bleu": "#5599FF",  "blue": "#5599FF",
    "vert": "#55CC55",  "green": "#55CC55",
    "orange": "#FF9933",
    "jaune": "#FFE055", "yellow": "#FFE055",
    "violet": "#CC66FF","purple": "#CC66FF",
    "cyan": "#44DDDD",
    "rose": "#FF88CC",  "pink": "#FF88CC",
    "blanc": "#FFFFFF", "white": "#FFFFFF",
    "gris": "#AAAAAA",  "gray": "#AAAAAA", "grey": "#AAAAAA",
}

DEFAULT_FONT_LYRICS    = 28
DEFAULT_FONT_CHORDS    = 18
DEFAULT_FONT_SECTION   = 16
DEFAULT_SECTION_COLOR  = "#AAAAAA"

# Accord valide : racine A-G, altération optionnelle, qualité, chiffres, basse optionnelle
_CHORD_TOKEN_RE = re.compile(
    r'^[A-G][#b]?(maj|Maj|min|m|M|dim|aug|sus|add)?[0-9]*(/[A-G][#b]?)?$'
)


def is_chord_line(text: str) -> bool:
    """True si tous les tokens de la ligne sont des accords de guitare."""
    tokens = text.split()
    if not tokens:
        return False
    return all(_CHORD_TOKEN_RE.match(t) for t in tokens)


def resolve_color(value: str) -> str:
    v = value.strip().lower()
    if v in NAMED_COLORS:
        return NAMED_COLORS[v]
    if re.match(r'^#?[0-9a-fA-F]{3,8}$', v):
        return f"#{v.lstrip('#').upper()}"
    return "#FFFFFF"


@dataclass
class PromptLine:
    text: str
    color: Optional[str] = None   # None = hérite de la section ou blanc
    singer: Optional[str] = None  # prénom à afficher si balise sur la ligne
    is_chord: bool = False
    is_note: bool = False


@dataclass
class Section:
    label: str
    color: Optional[str] = None
    singer: Optional[str] = None  # prénom à afficher sur la section
    lines: list[PromptLine] = field(default_factory=list)


DEFAULT_CHORD_COLOR = "#888888"

@dataclass
class Song:
    title: str
    file_path: str
    order: int
    notes: str = ""
    tags: dict[str, str] = field(default_factory=dict)       # {lower: hex}
    tag_names: dict[str, str] = field(default_factory=dict)  # {lower: original_case}
    sections: list[Section] = field(default_factory=list)
    font_lyrics:    int = DEFAULT_FONT_LYRICS
    font_chords:    int = DEFAULT_FONT_CHORDS
    font_section:   int = DEFAULT_FONT_SECTION
    chord_color:    str  = DEFAULT_CHORD_COLOR
    section_color:  str  = DEFAULT_SECTION_COLOR
    show_chords:    bool = True


# [Label]  ou  [Label]@Tag
_SECTION_RE = re.compile(r'^\[([^\]]+)\]\s*(?:@(\w+))?\s*$')
# @Tag en fin de ligne
_TRAILING_TAG_RE = re.compile(r'\s+@(\w+)\s*$')
# Définition en en-tête : @Tag: couleur
_DEF_RE = re.compile(r'^@(\w+)\s*:\s*(.+)')


def parse_prompt(file_path: str) -> Song:
    with open(file_path, encoding="utf-8") as f:
        lines = [l.rstrip('\n') for l in f]
    return _parse_lines(lines, file_path)


def parse_prompt_text(text: str, file_path: str = "") -> Song:
    """Parse depuis un string (pour la prévisualisation en direct)."""
    lines = [l.rstrip('\r') for l in text.split('\n')]
    return _parse_lines(lines, file_path)


def _parse_lines(lines: list, file_path: str) -> Song:
    title = os.path.basename(file_path).rsplit('.', 1)[0] if file_path else "Sans titre"
    notes = ""
    tags: dict[str, str] = {}
    tag_names: dict[str, str] = {}  # {nom_lower: nom_original}
    sections: list[Section] = []
    font_lyrics   = DEFAULT_FONT_LYRICS
    font_chords   = DEFAULT_FONT_CHORDS
    font_section  = DEFAULT_FONT_SECTION
    chord_color   = DEFAULT_CHORD_COLOR
    section_color = DEFAULT_SECTION_COLOR
    show_chords   = True

    # ── En-tête ───────────────────────────────────────────────────────────────
    i = 0
    header_notes: list[str] = []
    while i < len(lines):
        line = lines[i]
        if _SECTION_RE.match(line.strip()):
            break
        stripped = line.strip()
        sl = stripped.lower()
        if stripped.startswith('('):
            header_notes.append(stripped)
            i += 1
            continue
        if sl.startswith("titre:"):
            title = stripped.split(":", 1)[1].strip()
        elif sl.startswith("notes:"):
            notes = stripped.split(":", 1)[1].strip()
        elif sl.startswith("tailleparoles:"):
            try:
                font_lyrics = int(stripped.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif sl.startswith("tailleaccords:"):
            try:
                font_chords = int(stripped.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif sl.startswith("taillesection:"):
            try:
                font_section = int(stripped.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif sl.startswith("afficheraccords:"):
            val = stripped.split(":", 1)[1].strip().lower()
            show_chords = val not in ("non", "no", "false", "0")
        elif sl.startswith("couleursection:"):
            section_color = resolve_color(stripped.split(":", 1)[1].strip())
        elif sl.startswith("couleuraccords:"):
            chord_color = resolve_color(stripped.split(":", 1)[1].strip())
        elif m := _DEF_RE.match(stripped):
            original = m.group(1)
            tags[original.lower()] = resolve_color(m.group(2))
            tag_names[original.lower()] = original  # préserve la casse du prénom
        i += 1

    # ── Contenu ───────────────────────────────────────────────────────────────
    current: Optional[Section] = None

    def flush():
        nonlocal current
        if current is not None:
            sections.append(current)
            current = None

    while i < len(lines):
        line = lines[i]
        i += 1
        stripped = line.strip()

        # Marqueur de section → seul déclencheur de flush
        if m := _SECTION_RE.match(stripped):
            flush()
            tag_key    = m.group(2).lower() if m.group(2) else None
            tag_color  = tags.get(tag_key) if tag_key else None
            tag_singer = tag_names.get(tag_key) if tag_key else None
            current = Section(label=m.group(1), color=tag_color, singer=tag_singer)
            continue

        # Ligne vide avant la première section : on ignore
        if current is None:
            if stripped == "":
                continue
            current = Section(label="")

        # Ligne vide dans une section : on la conserve comme saut de ligne
        if stripped == "":
            current.lines.append(PromptLine(text=""))
            continue

        tm = _TRAILING_TAG_RE.search(line)
        if tm:
            tag_key    = tm.group(1).lower()
            line_color  = tags.get(tag_key)
            line_singer = tag_names.get(tag_key)
            text = line[:tm.start()].rstrip()
        else:
            line_color  = None
            line_singer = None
            text = line

        is_note = text.strip().startswith('(')
        current.lines.append(PromptLine(
            text=text,
            color=line_color,
            singer=line_singer,
            is_chord=False if is_note else is_chord_line(text),
            is_note=is_note,
        ))

    flush()

    if header_notes and sections:
        for note in reversed(header_notes):
            sections[0].lines.insert(0, PromptLine(text=note, is_note=True))

    return Song(
        title=title,
        file_path=file_path,
        order=_extract_order(os.path.basename(file_path)) if file_path else 9999,
        notes=notes,
        tags=tags,
        tag_names=tag_names,
        sections=sections,
        font_lyrics=font_lyrics,
        font_chords=font_chords,
        font_section=font_section,
        chord_color=chord_color,
        section_color=section_color,
        show_chords=show_chords,
    )


def _extract_order(filename: str) -> int:
    num = ""
    for ch in filename:
        if ch.isdigit():
            num += ch
        else:
            break
    return int(num) if num else 9999


def load_songs(directory: str) -> list[Song]:
    songs = []
    for filename in sorted(os.listdir(directory)):
        if not filename.lower().endswith(".prompt"):
            continue
        try:
            songs.append(parse_prompt(os.path.join(directory, filename)))
        except Exception as e:
            print(f"[Prompt-Live] Erreur '{filename}': {e}")
    songs.sort(key=lambda s: s.order)
    return songs
