"""
Serveur HTTP léger pour diffuser le prompteur sur un appareil distant (iPad…).
Utilise Server-Sent Events (SSE) — aucune dépendance externe.
"""
import json
import queue
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


_MANIFEST = """\
{
  "name": "Prompt-Live",
  "short_name": "Prompt-Live",
  "display": "fullscreen",
  "background_color": "#000000",
  "theme_color": "#000000",
  "start_url": "/"
}
"""

_INDEX = """\
<!DOCTYPE html><html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black">
<meta name="theme-color" content="#000000">
<link rel="manifest" href="/manifest.json">
<title>Prompt-Live</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html { height: 100%; }
body {
  min-height: 100dvh;
  background: #000; color: #fff;
  overflow-x: hidden;
  padding: 24px 32px 84px;
}
#dot {
  position: fixed; top: 14px; right: 14px;
  width: 10px; height: 10px; border-radius: 50%;
  background: #500; transition: background .4s;
}
#dot.on { background: #0c0; }
#content p { margin: 0; }
.wait {
  color: #333;
  font-family: -apple-system, sans-serif;
  font-size: 22px;
  text-align: center;
  padding-top: 40vh;
}
.setlist {
  max-width: 640px;
  margin: 48px auto 0;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
}
.setlist-title {
  color: #444;
  font-size: 11px;
  letter-spacing: 3px;
  text-transform: uppercase;
  margin-bottom: 24px;
}
.setlist ol { list-style: none; }
.setlist li {
  display: flex;
  align-items: baseline;
  gap: 14px;
  padding: 14px 0;
  border-bottom: 1px solid #111;
  font-size: 22px;
  color: #ccc;
}
.setlist li .n {
  color: #333;
  font-size: 12px;
  min-width: 28px;
  text-align: right;
  flex-shrink: 0;
}
/* Bannière "Ajouter à l'écran d'accueil" pour iOS hors PWA */
#pwa-hint {
  display: none;
  position: fixed; bottom: 28px; left: 50%;
  transform: translateX(-50%);
  background: rgba(30,30,30,.92);
  backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  color: #ccc;
  font-family: -apple-system, sans-serif;
  font-size: 13px; line-height: 1.5;
  padding: 12px 16px 12px 14px;
  border-radius: 12px;
  border: 1px solid #333;
  max-width: 300px;
  text-align: center;
  z-index: 999;
}
#pwa-hint strong { color: #fff; }
#pwa-close {
  display: block; margin: 8px auto 0;
  background: none; border: none;
  color: #555; font-size: 12px;
  cursor: pointer; padding: 2px 8px;
}
/* ── Barre de contrôle iPad ─────────────────────────────────────────────── */
#controls {
  position: fixed; bottom: 0; left: 0; right: 0;
  height: 64px;
  display: flex; align-items: center; justify-content: space-around;
  background: rgba(0,0,0,.90);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
  border-top: 1px solid #1c1c1c;
  z-index: 200;
}
.cb {
  background: none; border: none; color: #777;
  font-size: 28px; padding: 8px 16px;
  cursor: pointer; border-radius: 10px;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  transition: color .1s, background .1s;
  user-select: none; -webkit-user-select: none;
  min-width: 56px; text-align: center;
}
.cb:active { background: #2a2a2a; color: #fff; }
#btn-auto { color: #444; }
#btn-auto.on { color: #00cc66; }
#tp-bar {
  position: fixed; bottom: 68px; right: 12px;
  display: flex; align-items: center; gap: 4px;
  background: rgba(10,10,10,.85);
  border: 1px solid #2a2a2a; border-radius: 20px;
  padding: 5px 10px; z-index: 201;
}
.tp {
  background: none; border: none; color: #666;
  font-size: 15px; font-weight: bold;
  padding: 3px 8px; cursor: pointer;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  border-radius: 8px;
  user-select: none; -webkit-user-select: none;
}
.tp:active { color: #fff; background: #333; }
#tp-val {
  color: #ff9900; font-size: 12px; font-weight: bold;
  min-width: 24px; text-align: center;
}
</style>
</head>
<body>
<div id="dot"></div>
<div id="content"><p class="wait">En attente…</p></div>
<div id="controls">
  <button class="cb" onclick="sendCmd({cmd:'prev'})">&#x2B05;</button>
  <button class="cb" onclick="sendCmd({cmd:'scroll',d:'up'})">&#x25B2;</button>
  <button class="cb" id="btn-auto" onclick="sendCmd({cmd:'autoscroll'})">&#x25B6;&#x25B6;</button>
  <button class="cb" onclick="sendCmd({cmd:'scroll',d:'down'})">&#x25BC;</button>
  <button class="cb" onclick="sendCmd({cmd:'next'})">&#x27A1;</button>
</div>
<div id="tp-bar">
  <button class="tp" onclick="sendCmd({cmd:'transpose',delta:-1})">&#x266D;</button>
  <span id="tp-val">0</span>
  <button class="tp" onclick="sendCmd({cmd:'transpose',delta:1})">&#x266F;</button>
</div>
<div id="pwa-hint">
  Appuie sur <strong>&#x2191; Partager</strong> puis<br>
  <strong>« Sur l'écran d'accueil »</strong><br>
  pour masquer les barres du navigateur.
  <button id="pwa-close" onclick="dismissHint()">Ne plus afficher</button>
</div>
<script>
const dot = document.getElementById('dot');
const box = document.getElementById('content');

// ── Fullscreen ────────────────────────────────────────────────────────────
const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
              (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
const isStandalone = window.navigator.standalone === true ||
                     window.matchMedia('(display-mode: fullscreen)').matches ||
                     window.matchMedia('(display-mode: standalone)').matches;

if (!isIOS && document.fullscreenEnabled) {
  // Android / Chrome : plein écran au premier tap
  document.addEventListener('click', () => {
    if (!document.fullscreenElement)
      document.documentElement.requestFullscreen().catch(() => {});
  }, { once: true });
} else if (isIOS && !isStandalone) {
  // iOS hors PWA : affiche la bannière d'instruction (sauf si déjà fermée)
  if (!sessionStorage.getItem('pwa-hint-dismissed'))
    document.getElementById('pwa-hint').style.display = 'block';
}

function dismissHint() {
  document.getElementById('pwa-hint').style.display = 'none';
  sessionStorage.setItem('pwa-hint-dismissed', '1');
}

// ── Setlist ───────────────────────────────────────────────────────────────
function renderSetlist(songs) {
  if (!songs.length) {
    box.innerHTML = '<p class="wait">Aucune chanson chargée</p>';
    return;
  }
  let html = '<div class="setlist"><p class="setlist-title">Setlist</p><ol>';
  songs.forEach((t, i) => {
    html += '<li><span class="n">' + String(i + 1).padStart(2, '0') + '</span>' +
            t.replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</li>';
  });
  html += '</ol></div>';
  box.innerHTML = html;
}

// ── Wake Lock (empêche la mise en veille de l'écran) ─────────────────────
// Méthode 1 : API native (fonctionne en HTTPS)
let _wakeLock = null;
async function requestWakeLock() {
  if (!('wakeLock' in navigator)) return;
  try { _wakeLock = await navigator.wakeLock.request('screen'); } catch (_) {}
}

// Méthode 2 : flux vidéo depuis un canvas (fonctionne en HTTP, déclenché au
// premier toucher car iOS exige un geste utilisateur pour jouer une vidéo)
let _wakeVideo = null;
function startVideoWakeLock() {
  if (_wakeVideo) return;
  try {
    const c = document.createElement('canvas');
    c.width = 1; c.height = 1;
    c.getContext('2d').fillRect(0, 0, 1, 1);
    _wakeVideo = document.createElement('video');
    _wakeVideo.srcObject = c.captureStream(1);
    _wakeVideo.muted = true;
    _wakeVideo.loop  = true;
    _wakeVideo.setAttribute('playsinline', '');
    _wakeVideo.style.cssText =
      'position:fixed;top:-1px;left:-1px;width:1px;height:1px;opacity:.01;';
    document.body.appendChild(_wakeVideo);
    _wakeVideo.play().catch(() => {});
  } catch (_) {}
}

requestWakeLock();
document.addEventListener('touchstart', () => {
  requestWakeLock();
  startVideoWakeLock();
}, { once: true, passive: true });
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState !== 'visible') return;
  requestWakeLock();
  if (_wakeVideo && _wakeVideo.paused) _wakeVideo.play().catch(() => {});
});

// ── Interleaving accords / paroles ────────────────────────────────────────

// Coupe les enfants de `el` à `offset` caractères ; retourne un nouvel élément
// (hors DOM) contenant la 2e moitié, modifie `el` en place pour la 1re moitié.
function splitElementAtTextOffset(el, offset) {
  const newEl = el.cloneNode(false);
  let pos = 0;
  for (const child of Array.from(el.childNodes)) {
    const len = child.textContent.length;
    if (pos >= offset) {
      el.removeChild(child);
      newEl.appendChild(child);
    } else if (pos + len > offset) {
      const splitAt = offset - pos;
      const before = child.textContent.substring(0, splitAt);
      const after  = child.textContent.substring(splitAt);
      if (child.nodeType === Node.TEXT_NODE) {
        child.textContent = before;
        if (after) newEl.appendChild(document.createTextNode(after));
      } else {
        child.textContent = before;
        const newChild = child.cloneNode(false);
        newChild.textContent = after;
        newEl.appendChild(newChild);
      }
    }
    pos += len;
  }
  return newEl;
}

function rechunkWrappedLines() {
  const divEl = document.querySelector('#content div');
  if (!divEl) return;

  let changed = true;
  while (changed) {
    changed = false;
    const kids = Array.from(divEl.children);
    for (let i = 0; i < kids.length; i++) {
      if (!kids[i].dataset || kids[i].dataset.type !== 'chord') continue;

      let j = i;
      while (j < kids.length && kids[j].dataset && kids[j].dataset.type === 'chord') j++;
      if (j >= kids.length ||
          !kids[j].dataset || kids[j].dataset.type !== 'lyric') {
        i = j - 1;
        continue;
      }

      const lyricEl = kids[j];
      const lhPx = parseFloat(window.getComputedStyle(lyricEl).lineHeight) || 40;
      const elH = lyricEl.getBoundingClientRect().height;
      const numLines = Math.max(1, Math.round(elH / lhPx));

      if (numLines >= 2) {
        const chords = kids.slice(i, j);
        const breaks = findWordLineBreaks(lyricEl, numLines - 1);
        if (breaks.length > 0) {
          doInterleave(chords, lyricEl, breaks);
          changed = true;
          break;
        }
      }
      i = j;
    }
  }
}

function findWordLineBreaks(lyricEl, maxBreaks) {
  const span = lyricEl.querySelector('span');
  if (!span || !span.firstChild || span.firstChild.nodeType !== Node.TEXT_NODE) return [];
  const textNode = span.firstChild;
  const text = textNode.textContent;
  const words = text.split(' ');
  const breaks = [];
  let charPos = 0;
  let prevTop = null;

  for (let wi = 0; wi < words.length && breaks.length < maxBreaks; wi++) {
    if (!words[wi]) { charPos++; continue; }
    const range = document.createRange();
    range.setStart(textNode, charPos);
    range.setEnd(textNode, charPos + words[wi].length);
    const top = range.getBoundingClientRect().top;
    if (prevTop !== null && top > prevTop + 1) breaks.push(charPos);
    prevTop = top;
    charPos += words[wi].length + 1;
  }
  return breaks;
}

function doInterleave(chords, lyricEl, breaks) {
  const span = lyricEl.querySelector('span');
  const textNode = span.firstChild;
  const text = textNode.textContent;
  const parent = lyricEl.parentNode;

  // Découpe les paroles aux positions de saut de ligne
  const parts = [];
  let last = 0;
  for (const bp of breaks) {
    parts.push(text.substring(last, bp).trimEnd());
    last = bp;
  }
  parts.push(text.substring(last).trimStart());

  textNode.textContent = parts[0];

  // Prépare les éléments d'accords pour chaque partie suivante.
  // - Plusieurs éléments d'accords : on les utilise dans l'ordre.
  // - Un seul élément d'accord : on le découpe aux mêmes positions de saut.
  const extraChords = [];
  if (chords.length > 1) {
    for (let k = 1; k < chords.length; k++) extraChords.push(chords[k]);
  } else if (chords.length === 1) {
    let remainder = chords[0];
    let prevBp = 0;
    for (const bp of breaks) {
      const splitAt = bp - prevBp;
      if (splitAt > 0) {
        const nextPart = splitElementAtTextOffset(remainder, splitAt);
        extraChords.push(nextPart);
        remainder = nextPart;
      } else {
        extraChords.push(null);
      }
      prevBp = bp;
    }
  }

  let anchor = lyricEl;
  for (let k = 1; k < parts.length; k++) {
    const chordEl = k - 1 < extraChords.length ? extraChords[k - 1] : null;
    if (chordEl) {
      parent.insertBefore(chordEl, anchor.nextSibling);
      anchor = chordEl;
    }
    const newLyric = lyricEl.cloneNode(true);
    newLyric.querySelector('span').firstChild.textContent = parts[k];
    parent.insertBefore(newLyric, anchor.nextSibling);
    anchor = newLyric;
  }
}

// ── Commandes iPad ────────────────────────────────────────────────────────
function sendCmd(data) {
  fetch('/cmd', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  }).catch(() => {});
}

function updateAutoBtn(active) {
  const btn = document.getElementById('btn-auto');
  if (active) { btn.classList.add('on'); btn.innerHTML = '&#x23F8;'; }
  else         { btn.classList.remove('on'); btn.innerHTML = '&#x25B6;&#x25B6;'; }
}

function updateTranspose(val) {
  document.getElementById('tp-val').textContent = (val > 0 ? '+' : '') + val;
}

// ── SSE ───────────────────────────────────────────────────────────────────
function connect() {
  const es = new EventSource('/events');
  es.onopen = () => dot.classList.add('on');
  es.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.type === 'song') {
      box.innerHTML = d.html;
      window.scrollTo(0, 0);
      requestAnimationFrame(rechunkWrappedLines);
    } else if (d.type === 'setlist') {
      renderSetlist(d.songs);
    } else if (d.type === 'scroll_line') {
      const el = document.querySelector('#content p[data-block="' + d.index + '"]');
      if (el) window.scrollTo(0, el.getBoundingClientRect().top + window.pageYOffset);
    } else if (d.type === 'autoscroll') {
      updateAutoBtn(d.active);
    } else if (d.type === 'transpose') {
      updateTranspose(d.value);
    }
  };
  es.onerror = () => {
    dot.classList.remove('on');
    es.close();
    setTimeout(connect, 3000);
  };
}
connect();
</script>
</body>
</html>
"""


class PromptWebServer:
    """Diffuse le prompteur en temps réel via HTTP + Server-Sent Events."""

    def __init__(self, port: int = 8765):
        self._port = port
        self._clients: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._server: HTTPServer | None = None
        self._last_html: str = ""           # contenu quand le prompteur est actif
        self._last_setlist: list[str] = []  # titres quand le prompteur est arrêté
        self._command_queue: list = []      # commandes reçues depuis l'iPad

    # ── API publique ─────────────────────────────────────────────────────────

    def start(self) -> str:
        """Démarre le serveur ; retourne l'URL locale (ex. http://192.168.1.5:8765)."""
        self._server = _ThreadingHTTPServer(("", self._port), self._make_handler())
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return f"http://{_local_ip()}:{self._port}"

    def stop(self):
        if self._server:
            with self._lock:
                for q in self._clients:
                    try:
                        q.put_nowait(None)  # débloque les threads SSE
                    except queue.Full:
                        pass
            self._server.shutdown()
            self._server = None

    def push_song(self, html: str):
        """Envoie le contenu d'une nouvelle chanson à tous les clients."""
        self._last_html = html
        self._broadcast(json.dumps({"type": "song", "html": html}))

    def push_setlist(self, titles: list[str]):
        """Affiche la liste des chansons (état repos, prompteur arrêté)."""
        self._last_html = ""
        self._last_setlist = titles
        self._broadcast(json.dumps({"type": "setlist", "songs": titles}))

    def push_scroll_line(self, index: int):
        """Envoie l'index du paragraphe visible en haut du viewport."""
        self._broadcast(json.dumps({"type": "scroll_line", "index": index}))

    def push_autoscroll(self, active: bool):
        """Synchronise l'état auto-scroll sur les clients web."""
        self._broadcast(json.dumps({"type": "autoscroll", "active": active}))

    def push_transpose(self, value: int):
        """Synchronise la valeur de transposition sur les clients web."""
        self._broadcast(json.dumps({"type": "transpose", "value": value}))

    def poll_commands(self) -> list:
        """Retourne et vide la file des commandes reçues depuis l'iPad."""
        with self._lock:
            cmds = self._command_queue[:]
            self._command_queue.clear()
        return cmds

    # ── Interne ──────────────────────────────────────────────────────────────

    def _broadcast(self, data: str):
        msg = f"data: {data}\n\n".encode()
        with self._lock:
            for q in self._clients:
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    # Purge les anciens messages et envoie le nouveau
                    # (on ne déconnecte jamais sur queue pleine)
                    try:
                        while True:
                            q.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        q.put_nowait(msg)
                    except queue.Full:
                        pass

    def _initial_state(self) -> "str | None":
        """Retourne le message SSE à envoyer à un nouveau client selon l'état courant."""
        if self._last_html:
            return json.dumps({"type": "song", "html": self._last_html})
        if self._last_setlist is not None:
            return json.dumps({"type": "setlist", "songs": self._last_setlist})
        return None

    def _make_handler(self):
        srv = self

        class _H(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path == '/cmd':
                    try:
                        n = int(self.headers.get('Content-Length', 0))
                        data = json.loads(self.rfile.read(n)) if n else {}
                        with srv._lock:
                            srv._command_queue.append(data)
                    except Exception:
                        pass
                    self.send_response(204)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_GET(self):
                if self.path in ("/", "/index.html"):
                    b = _INDEX.encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    self.wfile.write(b)
                elif self.path == "/manifest.json":
                    b = _MANIFEST.encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/manifest+json")
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    self.wfile.write(b)
                elif self.path == "/events":
                    self._sse()
                else:
                    self.send_response(404)
                    self.end_headers()

            def _sse(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                # Enregistre le client ET récupère l'état initial sous le même verrou
                # pour éviter de rater un broadcast entre les deux opérations
                q: queue.Queue = queue.Queue(maxsize=50)
                with srv._lock:
                    srv._clients.append(q)
                    init = srv._initial_state()

                # Envoie l'état courant au nouveau client
                if init:
                    try:
                        self.wfile.write(f"retry: 2000\ndata: {init}\n\n".encode())
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        with srv._lock:
                            if q in srv._clients:
                                srv._clients.remove(q)
                        return

                try:
                    while True:
                        try:
                            msg = q.get(timeout=15)
                            if msg is None:  # sentinel d'arrêt
                                break
                            self.wfile.write(msg)
                            self.wfile.flush()
                        except queue.Empty:
                            # Keepalive : évite que Safari / routeur ferme la connexion
                            self.wfile.write(b": ping\n\n")
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    with srv._lock:
                        if q in srv._clients:
                            srv._clients.remove(q)

            def log_message(self, *_):
                pass  # supprime les logs dans le terminal

        return _H
