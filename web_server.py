"""
Serveur HTTP léger pour diffuser le prompteur sur un appareil distant (iPad…).
Utilise Server-Sent Events (SSE) — aucune dépendance externe.
"""
import json
import queue
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


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
  "name": "Promt",
  "short_name": "Promt",
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
<title>Promt</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html { height: 100%; }
body {
  min-height: 100dvh;
  background: #000; color: #fff;
  overflow-x: hidden;
  padding: 24px 32px 60px;
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
</style>
</head>
<body>
<div id="dot"></div>
<div id="content"><p class="wait">En attente…</p></div>
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
let _wakeLock = null;
async function requestWakeLock() {
  if (!('wakeLock' in navigator)) return;
  try {
    _wakeLock = await navigator.wakeLock.request('screen');
  } catch (_) {}
}
requestWakeLock();
// Re-demande le lock quand on revient sur l'onglet (il se libère automatiquement sinon)
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') requestWakeLock();
});

// ── SSE ───────────────────────────────────────────────────────────────────
function connect() {
  const es = new EventSource('/events');
  es.onopen = () => dot.classList.add('on');
  es.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.type === 'song') {
      box.innerHTML = d.html;
      window.scrollTo(0, 0);
    } else if (d.type === 'setlist') {
      renderSetlist(d.songs);
    } else if (d.type === 'scroll') {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      if (max > 0) window.scrollTo(0, max * d.ratio);
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

    # ── API publique ─────────────────────────────────────────────────────────

    def start(self) -> str:
        """Démarre le serveur ; retourne l'URL locale (ex. http://192.168.1.5:8765)."""
        self._server = HTTPServer(("", self._port), self._make_handler())
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return f"http://{_local_ip()}:{self._port}"

    def stop(self):
        if self._server:
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

    def push_scroll(self, ratio: float):
        """Envoie la position de défilement (0.0 – 1.0)."""
        self._broadcast(json.dumps({"type": "scroll", "ratio": round(ratio, 4)}))

    # ── Interne ──────────────────────────────────────────────────────────────

    def _broadcast(self, data: str):
        msg = f"data: {data}\n\n".encode()
        with self._lock:
            dead = []
            for q in self._clients:
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._clients.remove(q)

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
                # Envoie l'état courant immédiatement au nouveau client
                init = srv._initial_state()
                if init:
                    self.wfile.write(f"data: {init}\n\n".encode())
                    self.wfile.flush()
                q: queue.Queue = queue.Queue(maxsize=20)
                with srv._lock:
                    srv._clients.append(q)
                try:
                    while True:
                        try:
                            self.wfile.write(q.get(timeout=25))
                            self.wfile.flush()
                        except queue.Empty:
                            # Keepalive pour éviter que Safari ferme la connexion
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
