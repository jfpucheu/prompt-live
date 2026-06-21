"""
Serveur HTTP léger pour diffuser le prompteur sur un appareil distant (iPad…).
Utilise Server-Sent Events (SSE).
Annonce le nom prompt-live.local via mDNS (zeroconf) si la lib est disponible.
"""
import json
import queue
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

try:
    from zeroconf import ServiceInfo, Zeroconf as _Zeroconf
    _ZEROCONF_OK = True
except ImportError:
    _ZEROCONF_OK = False


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
  padding: 24px 32px 104px;
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
  display: flex; flex-direction: column; align-items: stretch;
  background: rgba(0,0,0,.90);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
  border-top: 1px solid #1c1c1c;
  z-index: 200;
}
.ctrl-btn-row {
  height: 64px;
  display: flex; align-items: center; justify-content: space-around;
}
body.follower .ctrl-btn-row { display: none; }
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
/* ── Barre de mode (toujours visible) ────────────────────────────────────── */
#ctrl-mode-row {
  height: 40px;
  display: flex; align-items: center; justify-content: flex-end;
  padding: 0 14px 6px;
  border-top: 1px solid #111;
}
body.follower #ctrl-mode-row { border-top: none; padding-bottom: 8px; }
#btn-mode {
  background: none; border: 1px solid #222; color: #444;
  font-size: 12px; letter-spacing: 1px; text-transform: uppercase;
  padding: 5px 14px; border-radius: 20px;
  cursor: pointer; touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  user-select: none; -webkit-user-select: none;
  transition: color .1s, border-color .1s, background .1s;
}
#btn-mode:active { background: #1a1a1a; color: #aaa; border-color: #444; }
/* ── Sélection du mode ───────────────────────────────────────────────────── */
#mode-overlay {
  display: none; position: fixed; inset: 0;
  background: #000; z-index: 400;
  flex-direction: column; align-items: center; justify-content: center;
  gap: 28px;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
}
#mode-overlay.open { display: flex; }
.mo-title {
  color: #444; font-size: 11px; letter-spacing: 3px; text-transform: uppercase;
}
.mo-cards {
  display: flex; gap: 20px; flex-wrap: wrap; justify-content: center;
  padding: 0 24px;
}
.mo-card {
  background: #0d0d0d; border: 1px solid #222; border-radius: 16px;
  padding: 32px 28px; min-width: 140px; text-align: center;
  cursor: pointer; touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  user-select: none; -webkit-user-select: none;
  transition: border-color .15s, background .15s;
}
.mo-card:active { background: #1a1a1a; border-color: #555; }
.mo-icon { font-size: 42px; line-height: 1; margin-bottom: 14px; }
.mo-name { color: #fff; font-size: 20px; font-weight: 600; margin-bottom: 6px; }
.mo-desc { color: #555; font-size: 13px; line-height: 1.5; }
.mo-hint { color: #222; font-size: 12px; text-align: center; padding: 0 32px; }
body.follower { padding-bottom: 40px; }
/* ── Overlay setlist ─────────────────────────────────────────────────────── */
#list-overlay {
  display: none; position: fixed; inset: 0;
  background: #000; z-index: 300;
  flex-direction: column; overflow: hidden;
}
#list-overlay.open { display: flex; }
#list-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 20px 24px 12px; border-bottom: 1px solid #1a1a1a;
  flex-shrink: 0;
}
#list-head span {
  color: #555; font-family: -apple-system, sans-serif;
  font-size: 11px; letter-spacing: 3px; text-transform: uppercase;
}
#list-close {
  background: none; border: none; color: #666;
  font-size: 26px; line-height: 1; cursor: pointer; padding: 4px 10px;
  touch-action: manipulation; -webkit-tap-highlight-color: transparent;
}
#list-close:active { color: #fff; }
#list-items {
  flex: 1; overflow-y: auto; list-style: none;
  padding: 0 0 20px; -webkit-overflow-scrolling: touch;
}
.li-row {
  display: flex; align-items: center; gap: 16px;
  padding: 20px 24px; border-bottom: 1px solid #0f0f0f;
  font-family: -apple-system, 'Helvetica Neue', sans-serif;
  font-size: 22px; color: #888;
  cursor: pointer; touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
  user-select: none; -webkit-user-select: none;
}
.li-row:active { background: #111; color: #fff; }
.li-row.cur { color: #fff; }
.li-row.cur .li-n { color: #0c9; }
.li-n {
  color: #333; font-size: 13px; min-width: 30px;
  text-align: right; flex-shrink: 0; font-family: monospace;
}
</style>
</head>
<body>
<div id="dot"></div>
<div id="content"><p class="wait" data-i18n="wait">En attente&#x2026;</p></div>
<div id="mode-overlay">
  <p class="mo-title">Prompt-Live</p>
  <div class="mo-cards">
    <div class="mo-card" onclick="setMode('follower')">
      <div class="mo-icon">&#x1F441;&#xFE0F;</div>
      <div class="mo-name" data-i18n="moFollower">Suiveur</div>
      <div class="mo-desc" data-i18n="moFollDesc">Affichage synchronis&#233;<br>sans contr&#244;le</div>
    </div>
    <div class="mo-card" onclick="setMode('commands')">
      <div class="mo-icon">&#x1F3A4;</div>
      <div class="mo-name" data-i18n="moCommands">Commandes</div>
      <div class="mo-desc" data-i18n="moCommDesc">Pilotage du<br>prompteur</div>
    </div>
  </div>
  <p class="mo-hint" data-i18n="moHint">Appuie sur le bouton <em>Mode</em> en bas pour changer</p>
</div>
<div id="list-overlay">
  <div id="list-head">
    <span>Setlist</span>
    <button id="list-close" onclick="closeList()">&#x2715;</button>
  </div>
  <ol id="list-items"></ol>
</div>
<div id="controls">
  <div id="ctrl-btn-row" class="ctrl-btn-row">
    <button class="cb" onclick="sendCmd({cmd:'prev'})">&#x2B05;</button>
    <button class="cb" onclick="sendCmd({cmd:'scroll',d:'up'})">&#x25B2;</button>
    <button class="cb" id="btn-auto" onclick="sendCmd({cmd:'autoscroll'})">&#x25B6;&#x25B6;</button>
    <button class="cb" onclick="sendCmd({cmd:'scroll',d:'down'})">&#x25BC;</button>
    <button class="cb" onclick="sendCmd({cmd:'next'})">&#x27A1;</button>
    <button class="cb" onclick="openList()">&#x2630;</button>
  </div>
  <div id="ctrl-mode-row">
    <button id="btn-mode" onclick="openModeOverlay()">Mode</button>
  </div>
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

// ── i18n ───────────────────────────────────────────────────────────────────
const _en = (navigator.language || '').toLowerCase().startsWith('en');
const _t = {
  wait:       _en ? 'Waiting…'                        : 'En attente…',
  noSongs:    _en ? 'No songs loaded'                      : 'Aucune chanson chargée',
  moFollower: _en ? 'Follower'                             : 'Suiveur',
  moFollDesc: _en ? 'Synchronized display<br>no control'   : 'Affichage synchronisé<br>sans contrôle',
  moCommands: _en ? 'Commands'                             : 'Commandes',
  moCommDesc: _en ? 'Prompter<br>control'                  : 'Pilotage du<br>prompteur',
  moHint:     _en ? 'Tap the <em>Mode</em> button below to change' : 'Appuie sur le bouton <em>Mode</em> en bas pour changer',
  modeLabel:  _en ? 'Mode'     : 'Mode',
};
document.querySelectorAll('[data-i18n]').forEach(el => {
  const v = _t[el.dataset.i18n];
  if (v !== undefined) el.innerHTML = v;
});

// ── Mode suiveur / commandes ───────────────────────────────────────────────
function applyMode(mode) {
  document.body.classList.toggle('follower', mode === 'follower');
  const btn = document.getElementById('btn-mode');
  if (btn) btn.textContent = mode === 'follower'
    ? (_en ? 'Follower' : 'Suiveur')
    : (_en ? 'Commands' : 'Commandes');
}

function setMode(mode) {
  localStorage.setItem('pl-mode', mode);
  applyMode(mode);
  document.getElementById('mode-overlay').classList.remove('open');
}

function openModeOverlay() {
  document.getElementById('mode-overlay').classList.add('open');
}

(function initMode() {
  const saved = localStorage.getItem('pl-mode') || 'follower';
  if (!localStorage.getItem('pl-mode')) localStorage.setItem('pl-mode', 'follower');
  applyMode(saved);
})();

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

// ── Scroll piloté par le serveur ───────────────────────────────────────────
// Le serveur envoie scroll_line à 60 fps ; on positionne directement la page.
// Les deltas sont de 10-20 px par frame et suivent la courbe du serveur —
// aucune interpolation JS nécessaire.
function scrollToTarget(y) {
  window.scrollTo(0, y);
}

// ── Setlist ───────────────────────────────────────────────────────────────
function renderSetlist(songs) {
  if (!songs.length) {
    box.innerHTML = '<p class="wait">' + _t.noSongs + '</p>';
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
// Méthode 1 : API native Screen Wake Lock (HTTPS uniquement)
let _wakeLock = null;
async function requestWakeLock() {
  if (!('wakeLock' in navigator)) return;
  try { _wakeLock = await navigator.wakeLock.request('screen'); } catch (_) {}
}

// Méthode 2 : vidéo canvas 1×1 px en boucle (fonctionne en HTTP sur iOS).
// Nécessite un geste utilisateur pour démarrer, puis se maintient seule.
// Un timer de 25 s relance la vidéo si iOS la met en pause silencieusement.
let _wakeVideo = null;
let _wakeTimer = null;

function _keepVideoAlive() {
  clearTimeout(_wakeTimer);
  if (_wakeVideo && _wakeVideo.paused) _wakeVideo.play().catch(() => {});
  _wakeTimer = setTimeout(_keepVideoAlive, 25000);
}

function startVideoWakeLock() {
  if (_wakeVideo) {
    if (_wakeVideo.paused) _wakeVideo.play().catch(() => {});
    return;
  }
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
    _keepVideoAlive();
  } catch (_) {}
}

requestWakeLock();
// Pas de { once } : chaque toucher peut relancer la vidéo si elle a été stoppée
document.addEventListener('touchstart', () => {
  requestWakeLock();
  startVideoWakeLock();
}, { passive: true });
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState !== 'visible') return;
  requestWakeLock();
  startVideoWakeLock();
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

// ── Overlay setlist ────────────────────────────────────────────────────────
let _titles = [];
let _curIdx  = -1;

function openList() {
  _renderList();
  document.getElementById('list-overlay').classList.add('open');
}
function closeList() {
  document.getElementById('list-overlay').classList.remove('open');
}
function _renderList() {
  const ol = document.getElementById('list-items');
  ol.innerHTML = '';
  _titles.forEach((t, i) => {
    const li = document.createElement('li');
    li.className = 'li-row' + (i === _curIdx ? ' cur' : '');
    const n = document.createElement('span');
    n.className = 'li-n';
    n.textContent = String(i + 1).padStart(2, '0');
    li.appendChild(n);
    li.appendChild(document.createTextNode(t));
    li.addEventListener('click', () => { sendCmd({cmd:'goto',index:i}); closeList(); });
    ol.appendChild(li);
  });
  setTimeout(() => {
    const cur = ol.querySelector('.cur');
    if (cur) cur.scrollIntoView({block:'center',behavior:'smooth'});
  }, 50);
}

// ── Scroll tactile (mode commandes) ───────────────────────────────────────
// Le scroll natif iOS reste actif (feedback 1:1 immédiat sur la tablette).
// On relaie l'index du premier bloc visible (zoom-indépendant) ; on ignore
// les scroll_line entrants du serveur pendant et juste après le toucher.
let _userScrolling    = false;
let _scrollDecayTimer = null;
let _scrollRelayTimer = null;

function _getTopBlockIdx() {
  for (const el of document.querySelectorAll('#content p[data-block]')) {
    if (el.getBoundingClientRect().bottom > 4) return parseInt(el.dataset.block);
  }
  return -1;
}

window.addEventListener('scroll', () => {
  if (localStorage.getItem('pl-mode') !== 'commands' || !_userScrolling) return;
  if (_scrollRelayTimer) return;
  _scrollRelayTimer = setTimeout(() => {
    _scrollRelayTimer = null;
    const idx = _getTopBlockIdx();
    if (idx >= 0) sendCmd({cmd: 'scroll_block', index: idx});
  }, 33);
}, {passive: true});

box.addEventListener('touchstart', () => {
  _userScrolling = true;
  clearTimeout(_scrollDecayTimer);
}, {passive: true});

box.addEventListener('touchend', () => {
  clearTimeout(_scrollDecayTimer);
  // 800 ms : laisse le momentum scroll iOS se terminer avant de ré-accepter
  // les mises à jour du serveur
  _scrollDecayTimer = setTimeout(() => { _userScrolling = false; }, 800);
}, {passive: true});

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
      _titles = d.songs;
      renderSetlist(d.songs);
    } else if (d.type === 'navigate') {
      _curIdx = d.index;
      if (d.titles && d.titles.length) _titles = d.titles;
    } else if (d.type === 'scroll_line') {
      if (!_userScrolling) {
        const el = document.querySelector('#content p[data-block="' + d.index + '"]');
        if (el) scrollToTarget(el.getBoundingClientRect().top + window.pageYOffset);
      }
    } else if (d.type === 'autoscroll') {
      updateAutoBtn(d.active);
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
        self._titles: list[str] = []        # titres courants (pour overlay iPad)
        self._current_index: int = -1       # index chanson courante
        self._command_queue: list = []      # commandes reçues depuis l'iPad
        self._zeroconf: "_Zeroconf | None" = None
        self._mdns_info = None

    # ── API publique ─────────────────────────────────────────────────────────

    def start(self) -> str:
        """Démarre le serveur ; retourne l'URL locale (ex. http://192.168.1.5:8765)."""
        self._server = _ThreadingHTTPServer(("", self._port), self._make_handler())
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self._start_mdns()
        return f"http://{_local_ip()}:{self._port}"

    def mdns_url(self) -> "str | None":
        """Retourne l'URL mDNS si l'annonce .local est active, sinon None."""
        if self._zeroconf and self._mdns_info:
            return f"http://prompt-live.local:{self._port}"
        return None

    def _start_mdns(self):
        if not _ZEROCONF_OK:
            return
        try:
            ip = _local_ip()
            self._zeroconf = _Zeroconf()
            self._mdns_info = ServiceInfo(
                "_http._tcp.local.",
                "Prompt-Live._http._tcp.local.",
                addresses=[socket.inet_aton(ip)],
                port=self._port,
                properties={"path": "/"},
                server="prompt-live.local.",
            )
            self._zeroconf.register_service(self._mdns_info)
        except Exception:
            if self._zeroconf:
                self._zeroconf.close()
            self._zeroconf = None
            self._mdns_info = None

    def stop(self):
        if self._zeroconf:
            try:
                if self._mdns_info:
                    self._zeroconf.unregister_service(self._mdns_info)
                self._zeroconf.close()
            except Exception:
                pass
            self._zeroconf = None
            self._mdns_info = None
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

    def set_titles(self, titles: list[str]):
        """Mémorise la liste des titres pour l'overlay iPad."""
        self._titles = titles

    def push_navigate(self, index: int):
        """Synchronise l'index de la chanson courante sur les clients web."""
        self._current_index = index
        self._broadcast(json.dumps({
            "type": "navigate", "index": index, "titles": self._titles
        }))

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

    def _initial_state(self) -> "list[str]":
        """Retourne les messages SSE à envoyer à un nouveau client selon l'état courant."""
        msgs = []
        if self._last_html:
            msgs.append(json.dumps({"type": "song", "html": self._last_html}))
            if self._current_index >= 0:
                msgs.append(json.dumps({
                    "type": "navigate",
                    "index": self._current_index,
                    "titles": self._titles,
                }))
        elif self._last_setlist:
            msgs.append(json.dumps({"type": "setlist", "songs": self._last_setlist}))
        return msgs

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
                elif self.path == "/setlist":
                    b = json.dumps({
                        "titles": srv._titles,
                        "current": srv._current_index,
                    }).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
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
                        first = True
                        for msg in init:
                            prefix = "retry: 2000\n" if first else ""
                            self.wfile.write(f"{prefix}data: {msg}\n\n".encode())
                            first = False
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
