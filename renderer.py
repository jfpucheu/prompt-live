"""Génération HTML du prompteur depuis un objet Song."""
from parsers import Song, transpose_chord


def _rebuild_chord_text(positions: list, col_start: int, col_end: int) -> str:
    """Reconstruit une ligne d'accords pour la plage [col_start, col_end)."""
    chunk = [(p - col_start, n) for p, n in positions if col_start <= p < col_end]
    if not chunk:
        return ""
    size = chunk[-1][0] + len(chunk[-1][1])
    buf = [' '] * size
    for cp, name in chunk:
        for k, ch in enumerate(name):
            if cp + k < size:
                buf[cp + k] = ch
    return ''.join(buf).rstrip()


def _wrap_splits(text: str, cols: int) -> list:
    """Découpe `text` en tranches de max `cols` caractères, en coupant sur les espaces."""
    slices, start = [], 0
    while start < len(text):
        end = start + cols
        if end >= len(text):
            slices.append((start, len(text)))
            break
        # Cherche le dernier espace ≤ end
        bp = end
        for i in range(end, start, -1):
            if text[i - 1] == ' ':
                bp = i
                break
        if bp == start:   # aucun espace → coupe dur
            bp = end
        slices.append((start, bp))
        start = bp
    return slices


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


def _transpose_chord_text(positions: list, semitones: int) -> str:
    """Reconstruit une ligne d'accords en transposant les noms, en préservant les colonnes."""
    if not positions:
        return ""
    tp = [(col, transpose_chord(name, semitones)) for col, name in positions]
    size = max(col + len(name) for col, name in tp)
    buf = [' '] * size
    for col, name in tp:
        for k, c in enumerate(name):
            if col + k < size:
                buf[col + k] = c
    return ''.join(buf).rstrip()


def render_html(song: Song, zoom: float = 1.0, show_chords: "bool | None" = None,
                font_family: str = "'Courier New',Courier,monospace",
                chars_per_line: int = 0, transpose: int = 0) -> str:
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

    block_num = 0
    for section in song.sections:
        if section.label:
            label_color = song.section_color
            singer_html = ""
            if section.singer:
                singer_color = section.color or label_color
                singer_html = (
                    f'<span style="color:{singer_color};font-size:{fs_section}px;'
                    f'font-weight:bold;"> ▸ {esc(section.singer)}</span>'
                )
            parts.append(
                f'<p style="{p_style}white-space:normal;" data-block="{block_num}">'
                f'<span style="color:{label_color};font-size:{fs_section}px;'
                f'font-weight:bold;">[{esc(section.label)}]</span>{singer_html}</p>'
            )
            block_num += 1

        lines = section.lines
        idx = 0
        while idx < len(lines):
            line = lines[idx]

            if line.is_chord and not _show_chords:
                idx += 1
                continue

            if not line.text.strip():
                parts.append(f'<p style="{p_style}" data-block="{block_num}"><span>&nbsp;</span></p>')
                block_num += 1
                idx += 1
                continue

            if line.is_note:
                parts.append(
                    f'<p style="{p_style}" data-block="{block_num}">'
                    f'<span style="color:#666666;font-style:italic;font-size:{fs_lyrics}px;">'
                    f'{esc(line.text)}</span></p>'
                )
                block_num += 1
                idx += 1
                continue

            # Accord suivi d'une parole longue → découpage synchronisé
            if (line.is_chord and chars_per_line > 0
                    and idx + 1 < len(lines)):
                nxt = lines[idx + 1]
                if (not nxt.is_chord and not nxt.is_note
                        and nxt.text.strip()
                        and len(nxt.text) > chars_per_line):
                    tp_pos = [(c, transpose_chord(n, transpose)) for c, n in line.chord_positions] if transpose else line.chord_positions
                    for s_start, s_end in _wrap_splits(nxt.text, chars_per_line):
                        chord_chunk = _rebuild_chord_text(tp_pos, s_start, s_end)
                        if chord_chunk:
                            inner = _chord_spans(chord_chunk, esc, song.chord_color, fs_chords, fs_lyrics)
                            parts.append(f'<p style="{p_style}" data-type="chord" data-block="{block_num}">{inner}</p>')
                            block_num += 1
                        lyric_chunk = nxt.text[s_start:s_end]
                        color = nxt.color or section.color or "#ffffff"
                        parts.append(
                            f'<p style="{p_style}" data-type="lyric" data-block="{block_num}">'
                            f'<span style="color:{color};font-size:{fs_lyrics}px;'
                            f'font-weight:bold;">{esc(lyric_chunk)}</span></p>'
                        )
                        block_num += 1
                    idx += 2
                    continue

            if line.is_chord:
                chord_text = _transpose_chord_text(line.chord_positions, transpose) if transpose else line.text
                inner = _chord_spans(chord_text, esc, song.chord_color, fs_chords, fs_lyrics)
                parts.append(f'<p style="{p_style}" data-type="chord" data-block="{block_num}">{inner}</p>')
            else:
                color = line.color or section.color or "#ffffff"
                parts.append(
                    f'<p style="{p_style}" data-type="lyric" data-block="{block_num}">'
                    f'<span style="color:{color};font-size:{fs_lyrics}px;'
                    f'font-weight:bold;">{esc(line.text)}</span></p>'
                )
            block_num += 1
            idx += 1

    parts.append("</div>")
    return "".join(parts)
