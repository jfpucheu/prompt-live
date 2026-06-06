"""Tests automatisés — parsers, renderer, web_server."""
import json
import sys
import threading
import time
import unittest
import urllib.request

sys.path.insert(0, ".")

from parsers import (
    Song, parse_prompt_text, transpose_chord, extract_chord_positions,
    is_chord_line, load_songs,
)
from renderer import render_html, _transpose_chord_text


# ─── Transposition ────────────────────────────────────────────────────────────

class TestTransposeChord(unittest.TestCase):

    def _t(self, chord, semi, expected):
        result = transpose_chord(chord, semi)
        self.assertEqual(result, expected, f"transpose_chord({chord!r}, {semi}) = {result!r}, attendu {expected!r}")

    # Accords de base
    def test_c_up2(self):       self._t("C",       +2,  "D")
    def test_g_up5(self):       self._t("G",       +5,  "C")
    def test_a_up2(self):       self._t("A",       +2,  "B")
    def test_e_down1(self):     self._t("E",       -1,  "D#")
    def test_b_up1(self):       self._t("B",       +1,  "C")

    # Dièses / bémols
    def test_csharp_up1(self):  self._t("C#",      +1,  "D")
    def test_bb_down1(self):    self._t("Bb",      -1,  "A")
    def test_db_up2(self):      self._t("Db",      +2,  "Eb")
    def test_gb_down2(self):    self._t("Gb",      -2,  "E")

    # Qualités préservées
    def test_am7_up2(self):     self._t("Am7",     +2,  "Bm7")
    def test_csharp_maj7(self): self._t("C#maj7",  +1,  "Dmaj7")
    def test_gbm_down2(self):   self._t("Gbm",     -2,  "Em")
    def test_dsus4_up1(self):   self._t("Dsus4",   +1,  "D#sus4")
    def test_aaug_up3(self):    self._t("Aaug",    +3,  "Caug")

    # Basse
    def test_f_over_c(self):    self._t("F/C",     +2,  "G/D")
    def test_g_over_b(self):    self._t("G/B",     +2,  "A/C#")
    def test_d7_over_fsharp(self): self._t("D7/F#", +1, "D#7/G")

    # Étoile (marqueur de découpe)
    def test_star(self):        self._t("Am*",     +2,  "Bm*")

    # Zéro → identité
    def test_zero(self):        self._t("G",        0,  "G")
    def test_zero_complex(self):self._t("Cmaj7/E",  0,  "Cmaj7/E")

    # Octave complète → identité
    def test_octave(self):      self._t("F#m7",   +12, "F#m7")
    def test_octave_neg(self):  self._t("Bb",     -12, "Bb")

    # Tokens non-accords → inchangés
    def test_non_chord(self):   self._t("lorem",   +2, "lorem")
    def test_empty(self):       self._t("",         2, "")

    # Dièse mineur avec bémol → préférence bémol conservée
    def test_dsharp_up1(self):  self._t("D#",      +1,  "E")


class TestTransposeChordText(unittest.TestCase):

    def test_basic_line(self):
        positions = extract_chord_positions("Am  C  G")
        result = _transpose_chord_text(positions, +2)
        self.assertIn("Bm", result)
        self.assertIn("D",  result)
        self.assertIn("A",  result)

    def test_alignment_preserved(self):
        """La colonne de départ de chaque accord ne doit pas diminuer."""
        original = "C     G     Am    F"
        positions = extract_chord_positions(original)
        transposed = _transpose_chord_text(positions, +2)
        tp_positions = extract_chord_positions(transposed)
        orig_cols = [c for c, _ in positions]
        tp_cols   = [c for c, _ in tp_positions]
        # Chaque accord doit commencer à la même colonne ou après
        for oc, tc in zip(orig_cols, tp_cols):
            self.assertEqual(oc, tc, f"col {oc} → {tc} : désalignement")

    def test_zero_identity(self):
        line = "Am7  D7  G  Cmaj7"
        positions = extract_chord_positions(line)
        self.assertEqual(_transpose_chord_text(positions, 0), line)


# ─── Parsing Transposition ────────────────────────────────────────────────────

class TestParserTranspose(unittest.TestCase):

    def _parse(self, text):
        return parse_prompt_text(text, "")

    def test_default_zero(self):
        song = self._parse("Titre: Test\n\n[Intro]\nC G Am F\n")
        self.assertEqual(song.transpose, 0)

    def test_positive(self):
        song = self._parse("Titre: Test\nTransposition: 3\n\n[Intro]\nC\n")
        self.assertEqual(song.transpose, 3)

    def test_negative(self):
        song = self._parse("Titre: Test\nTransposition: -2\n\n[Intro]\nC\n")
        self.assertEqual(song.transpose, -2)

    def test_invalid_ignored(self):
        song = self._parse("Titre: Test\nTransposition: abc\n\n[Intro]\nC\n")
        self.assertEqual(song.transpose, 0)

    def test_case_insensitive(self):
        song = self._parse("Titre: Test\ntransposition: 5\n\n[Intro]\nC\n")
        self.assertEqual(song.transpose, 5)


# ─── Parsing général ──────────────────────────────────────────────────────────

class TestParser(unittest.TestCase):

    def _parse(self, text):
        return parse_prompt_text(text, "")

    def test_title(self):
        song = self._parse("Titre: Ma chanson\n\n[Intro]\n")
        self.assertEqual(song.title, "Ma chanson")

    def test_chord_line_detected(self):
        song = self._parse("Titre: T\n\n[Verse]\nAm C G\nParoles ici\n")
        self.assertTrue(song.sections[0].lines[0].is_chord)
        self.assertFalse(song.sections[0].lines[1].is_chord)

    def test_chord_positions(self):
        song = self._parse("Titre: T\n\n[Verse]\nAm   C   G\n")
        line = song.sections[0].lines[0]
        self.assertEqual(len(line.chord_positions), 3)
        names = [n for _, n in line.chord_positions]
        self.assertEqual(names, ["Am", "C", "G"])

    def test_note_line(self):
        song = self._parse("Titre: T\n\n[Verse]\n(note de bas de page)\n")
        self.assertTrue(song.sections[0].lines[0].is_note)

    def test_section_singer(self):
        song = self._parse("@Alice: #ff0000\n\n[Verse]@Alice\n")
        self.assertEqual(song.sections[0].singer, "Alice")

    def test_show_chords_false(self):
        song = self._parse("Titre: T\nAfficherAccords: non\n\n[Verse]\nC\n")
        self.assertFalse(song.show_chords)

    def test_tags_parsed(self):
        song = self._parse("@Marie: rouge\n@Pierre: #0055FF\n\n[Verse]\n")
        self.assertIn("marie", song.tags)
        self.assertIn("pierre", song.tags)
        self.assertEqual(song.tags["pierre"], "#0055FF")

    def test_trailing_tag_on_lyric(self):
        song = self._parse("@Bob: bleu\n\n[Verse]\nParoles @Bob\n")
        line = song.sections[0].lines[0]
        self.assertEqual(line.singer, "Bob")

    def test_font_sizes(self):
        song = self._parse("TailleParoles: 32\nTailleAccords: 20\nTailleSection: 14\n\n[Verse]\n")
        self.assertEqual(song.font_lyrics,  32)
        self.assertEqual(song.font_chords,  20)
        self.assertEqual(song.font_section, 14)

    def test_is_chord_line(self):
        self.assertTrue(is_chord_line("Am C G F"))
        self.assertTrue(is_chord_line("Cmaj7/E D7/F# G"))
        self.assertFalse(is_chord_line(""))
        self.assertFalse(is_chord_line("Hello world"))
        self.assertFalse(is_chord_line("Am et C"))

    def test_load_songs_from_dir(self):
        songs = load_songs("test")
        self.assertGreater(len(songs), 0)
        for s in songs:
            self.assertIsInstance(s, Song)
            self.assertTrue(s.title)


# ─── Rendu HTML ───────────────────────────────────────────────────────────────

class TestRenderer(unittest.TestCase):

    def _song(self, text, transpose=0):
        s = parse_prompt_text(text, "")
        s.transpose = transpose
        return s

    def test_html_contains_title_section(self):
        song = self._song("Titre: T\n\n[Intro]\nC G\nParoles\n")
        html = render_html(song)
        self.assertIn("[Intro]", html)
        self.assertIn("Paroles", html)

    def test_chord_color_applied(self):
        song = self._song("CouleurAccords: #FF0000\n\n[V]\nC G\n")
        html = render_html(song)
        self.assertIn("#FF0000", html)

    def test_transpose_changes_chords(self):
        song = self._song("Titre: T\n\n[V]\nAm  C  G\n", transpose=2)
        html = render_html(song)
        self.assertIn("Bm",  html)
        self.assertIn("D",   html)
        self.assertIn("A",   html)
        self.assertNotIn(">Am<", html)

    def test_transpose_zero_keeps_original(self):
        song = self._song("Titre: T\n\n[V]\nAm  C  G\n", transpose=0)
        html = render_html(song)
        self.assertIn("Am", html)
        self.assertIn(">C<", html) if ">C<" in html else self.assertIn("C", html)

    def test_show_chords_false_hides_chords(self):
        song = self._song("AfficherAccords: non\n\n[V]\nC G\nParoles\n")
        html = render_html(song)
        # Les accords ne doivent pas apparaître en tant que contenu visible
        self.assertNotIn("data-type=\"chord\"", html)

    def test_zoom(self):
        song = self._song("TailleParoles: 30\n\n[V]\nParoles\n")
        html2x = render_html(song, zoom=2.0)
        self.assertIn("60px", html2x)

    def test_note_line_rendered(self):
        song = self._song("Titre: T\n\n[V]\n(une note)\n")
        html = render_html(song)
        self.assertIn("une note", html)
        self.assertIn("font-style:italic", html)

    def test_section_color(self):
        song = self._song("CouleurSection: #AABB00\n\n[Refrain]\n")
        html = render_html(song)
        self.assertIn("#AABB00", html)

    def test_song_notes_rendered(self):
        song = self._song("Notes: tempo 120bpm\n\n[V]\n")
        html = render_html(song)
        self.assertIn("tempo 120bpm", html)

    def test_transpose_with_bass(self):
        song = self._song("Titre: T\n\n[V]\nG/B   D/F#\n", transpose=2)
        html = render_html(song)
        self.assertIn("A/C#", html)
        self.assertIn("E/G#", html)

    def test_transpose_full_song(self):
        """Transposition sur un vrai fichier .prompt."""
        songs = load_songs("test")
        self.assertTrue(songs)
        song = songs[0]
        song.transpose = 1
        html = render_html(song)
        self.assertIsInstance(html, str)
        self.assertGreater(len(html), 100)


# ─── Web server ───────────────────────────────────────────────────────────────

class TestWebServer(unittest.TestCase):

    def setUp(self):
        from web_server import PromptWebServer
        self.server = PromptWebServer(port=18765)
        self.url = self.server.start()
        time.sleep(0.1)

    def tearDown(self):
        self.server.stop()

    def test_index_returns_html(self):
        with urllib.request.urlopen(self.url + "/") as r:
            body = r.read().decode()
        self.assertIn("<!DOCTYPE html>", body)
        self.assertIn("Prompt-Live", body)

    def test_manifest_served(self):
        with urllib.request.urlopen(self.url + "/manifest.json") as r:
            data = json.loads(r.read())
        self.assertEqual(data["name"], "Prompt-Live")

    def test_404(self):
        import urllib.error
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.url + "/nonexistent")
        self.assertEqual(ctx.exception.code, 404)

    def test_post_cmd_queued(self):
        payload = json.dumps({"cmd": "next"}).encode()
        req = urllib.request.Request(
            self.url + "/cmd",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as r:
            self.assertEqual(r.status, 204)
        cmds = self.server.poll_commands()
        self.assertEqual(len(cmds), 1)
        self.assertEqual(cmds[0]["cmd"], "next")

    def test_poll_commands_clears_queue(self):
        for cmd in ("prev", "next", "autoscroll"):
            payload = json.dumps({"cmd": cmd}).encode()
            req = urllib.request.Request(
                self.url + "/cmd", data=payload,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            urllib.request.urlopen(req).close()
        first  = self.server.poll_commands()
        second = self.server.poll_commands()
        self.assertEqual(len(first), 3)
        self.assertEqual(len(second), 0)

    def _wait_client_registered(self, timeout=3.0):
        """Attend qu'au moins un client SSE soit enregistré dans _clients."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.server._lock:
                if self.server._clients:
                    return True
            time.sleep(0.01)
        return False

    def _sse_listen(self, push_fn):
        """Connecte un client SSE via socket brute, attend l'enregistrement
        côté serveur, exécute push_fn, retourne la liste des messages reçus."""
        import socket as _socket
        received = []

        def _listen():
            try:
                sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
                sock.settimeout(6)
                sock.connect(("127.0.0.1", 18765))
                sock.sendall(
                    b"GET /events HTTP/1.1\r\n"
                    b"Host: localhost\r\n"
                    b"Connection: keep-alive\r\n\r\n"
                )
                # Lire les headers HTTP
                buf = b""
                while b"\r\n\r\n" not in buf:
                    buf += sock.recv(4096)
                buf = buf[buf.find(b"\r\n\r\n") + 4:]
                # Lire les lignes SSE
                while True:
                    if b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        line = line.strip()
                        if line.startswith(b"data:"):
                            received.append(json.loads(line[5:].decode()))
                            return
                    else:
                        chunk = sock.recv(4096)
                        if not chunk:
                            return
                        buf += chunk
            except Exception:
                pass

        t = threading.Thread(target=_listen, daemon=True)
        t.start()
        self.assertTrue(self._wait_client_registered(), "client SSE non enregistré")
        time.sleep(0.05)
        push_fn()
        t.join(timeout=6)
        return received

    def test_push_song_broadcast(self):
        """Un client SSE reçoit le contenu poussé."""
        received = self._sse_listen(lambda: self.server.push_song("<p>test</p>"))
        self.assertTrue(any(d.get("type") == "song" for d in received))

    def test_push_setlist(self):
        received = self._sse_listen(lambda: self.server.push_setlist(["Song A", "Song B"]))
        self.assertTrue(any(d.get("type") == "setlist" for d in received))

    def test_push_autoscroll(self):
        received = self._sse_listen(lambda: self.server.push_autoscroll(True))
        match = [d for d in received if d.get("type") == "autoscroll"]
        self.assertTrue(match)
        self.assertTrue(match[0]["active"])

    def test_new_client_gets_initial_song(self):
        """Un client qui se connecte après push_song reçoit l'état initial."""
        self.server.push_song("<p>hello</p>")
        time.sleep(0.1)
        received = []
        def _listen():
            try:
                req = urllib.request.urlopen(self.url + "/events", timeout=3)
                for line in req:
                    line = line.decode().strip()
                    if line.startswith("data:"):
                        received.append(json.loads(line[5:]))
                        break
            except Exception:
                pass

        t = threading.Thread(target=_listen, daemon=True)
        t.start()
        t.join(timeout=4)
        self.assertTrue(any(d.get("type") == "song" for d in received))

    def test_push_navigate_broadcast(self):
        """push_navigate diffuse l'index et les titres."""
        self.server.set_titles(["A", "B", "C"])
        received = self._sse_listen(lambda: self.server.push_navigate(1))
        match = [d for d in received if d.get("type") == "navigate"]
        self.assertTrue(match)
        self.assertEqual(match[0]["index"], 1)
        self.assertEqual(match[0]["titles"], ["A", "B", "C"])

    def test_setlist_endpoint(self):
        """GET /setlist retourne les titres et l'index courant."""
        self.server.set_titles(["Song A", "Song B"])
        self.server._current_index = 0
        with urllib.request.urlopen(self.url + "/setlist") as r:
            data = json.loads(r.read())
        self.assertEqual(data["titles"], ["Song A", "Song B"])
        self.assertEqual(data["current"], 0)

    def test_initial_state_includes_navigate(self):
        """Un nouveau client reçoit song + navigate quand l'index est connu."""
        import socket as _socket
        self.server.set_titles(["A", "B"])
        self.server.push_song("<p>hi</p>")
        self.server._current_index = 1
        time.sleep(0.1)
        msgs = []
        try:
            sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            sock.settimeout(4)
            sock.connect(("127.0.0.1", 18765))
            sock.sendall(
                b"GET /events HTTP/1.1\r\nHost: localhost\r\n"
                b"Connection: keep-alive\r\n\r\n"
            )
            buf = b""
            while b"\r\n\r\n" not in buf:
                buf += sock.recv(4096)
            buf = buf[buf.find(b"\r\n\r\n") + 4:]
            while len(msgs) < 2:
                if b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if line.startswith(b"data:"):
                        msgs.append(json.loads(line[5:].decode()))
                else:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
            sock.close()
        except Exception:
            pass
        types = {m["type"] for m in msgs}
        self.assertIn("song", types)
        self.assertIn("navigate", types)
        nav = next(m for m in msgs if m["type"] == "navigate")
        self.assertEqual(nav["index"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
