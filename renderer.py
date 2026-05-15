"""Génération HTML du prompteur depuis un objet Song."""
from parsers import Song


def _chord_spans(text: str, esc, chord_color: str, fs_chords: int, fs_lyrics: int) -> str:
    """Accords à fs_chords, espaces à fs_lyrics → alignement parfait quelle que soit la taille."""
    out = []
    i = 0
    while i < len(text):
        if text[i] == ' ':
            j = i + 1
            while j < len(text) and text[j] == ' ':
                j += 1
            out.append(f'<span style="font-size:{fs_lyrics}px;">{text[i:j]}</span>')
            i = j
        else:
            j = i + 1
            while j < len(text) and text[j] != ' ':
                j += 1
            out.append(
                f'<span style="color:{chord_color};font-size:{fs_chords}px;font-weight:bold;">'
                f'{esc(text[i:j])}</span>'
            )
            i = j
    return ''.join(out)


def render_html(song: Song, zoom: float = 1.0, show_chords: "bool | None" = None,
                font_family: str = "'Courier New',Courier,monospace") -> str:
    fs_lyrics  = max(8, int(song.font_lyrics  * zoom))
    fs_chords  = max(8, int(song.font_chords  * zoom))
    fs_section = max(8, int(song.font_section * zoom))
    _show_chords = song.show_chords if show_chords is None else show_chords

    def esc(t: str) -> str:
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    parts = [f'<div style="font-family:{font_family};white-space:pre-wrap;">']

    if song.notes:
        parts.append(
            f'<p style="white-space:normal;"><span style="color:#666666;font-style:italic;font-size:{fs_section}px;">'
            f'{esc(song.notes)}</span></p>'
        )

    lh = int(fs_lyrics * 1.45)
    p_style = f'margin:0;line-height:{lh}px;font-size:{fs_lyrics}px;'

    for section in song.sections:
        if section.label:
            label_color = song.section_color
            singer_html = ""
            if section.singer:
                singer_color = section.color or label_color
                singer_html = (
                    f'<span style="color:{singer_color};font-size:{fs_section}px;'
                    f'font-weight:normal;"> ▸ {esc(section.singer)}</span>'
                )
            parts.append(
                f'<p style="{p_style}white-space:normal;">'
                f'<span style="color:{label_color};font-size:{fs_section}px;'
                f'font-weight:bold;">[{esc(section.label)}]</span>{singer_html}</p>'
            )

        for line in section.lines:
            if line.is_chord and not _show_chords:
                continue

            if not line.text.strip():
                parts.append(f'<p style="{p_style}"><span>&nbsp;</span></p>')
                continue

            if line.is_chord:
                inner = _chord_spans(line.text, esc, song.chord_color, fs_chords, fs_lyrics)
                parts.append(f'<p style="{p_style}">{inner}</p>')
            else:
                color = line.color or section.color or "#ffffff"
                parts.append(
                    f'<p style="{p_style}">'
                    f'<span style="color:{color};font-size:{fs_lyrics}px;'
                    f'font-weight:bold;">{esc(line.text)}</span></p>'
                )

    parts.append("</div>")
    return "".join(parts)
