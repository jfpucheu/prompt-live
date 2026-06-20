<p align="center">
  <img src="logo/prompt-live.svg" width="120" alt="Prompt-Live logo"/>
</p>

<h1 align="center">Prompt-Live</h1>
<p align="center"><em>Free open-source stage prompter for live bands — lyrics, chords & iPad sync</em></p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-macOS-lightgrey?logo=apple"/>
  <img src="https://img.shields.io/badge/platform-Windows-0078d4?logo=windows"/>
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python"/>
  <img src="https://img.shields.io/badge/license-MIT%20%2B%20Commons%20Clause-orange"/>
  <img src="https://github.com/jfpucheu/prompt-live/actions/workflows/pr-build.yml/badge.svg" alt="CI"/>
</p>

<p align="center">
  <a href="https://jfpucheu.github.io/prompt-live/index.en.html">🌐 Website — jfpucheu.github.io/prompt-live</a>
</p>

> **Free alternative to ProPresenter, OnSong and SongShow Plus** — display lyrics and chords on stage screens with real-time iPad sync and Bluetooth pedal support.

---

## Screenshots

| Control window | Prompter | Editor |
|---|---|---|
| ![Control](docs/screen-control.png) | ![Prompter](docs/screen-prompter.png) | ![Editor](docs/screen-editor.png) |

---

## Overview

Prompt-Live is a **macOS and Windows** app for displaying lyrics and chords live on stage. Built for bands with multiple singers: each vocalist can be color-coded, chords are displayed above lyrics, and everything scrolls smoothly from the sound desk.

**Key features**

- Load a folder of numbered `.prompt` files — setlist order is automatic
- Full-screen display on any external monitor or projector
- Smooth auto-scroll with 5 speed levels, adjustable per song
- Keyboard navigation: ↑↓ scroll, ←→ previous/next song
- Bluetooth HID pedal support (↓ scrolls, 2× bottom = next song, 2× top = previous song)
- Real-time iPad/tablet sync via built-in SSE web server — no app install needed
- Multi-screen support — all displays stay in sync
- Built-in editor with live preview
- Per-singer and per-section color coding
- Embedded monospace fonts (PT Mono) for perfect chord/lyric alignment

---

## Installation (development)

**macOS**
```bash
git clone https://github.com/jfpucheu/prompt-live.git
cd prompt-live
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

**Windows**
```powershell
git clone https://github.com/jfpucheu/prompt-live.git
cd prompt-live
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## Download

Head to the [**Releases**](https://github.com/jfpucheu/prompt-live/releases) page to download the latest build:

| Platform | File |
|----------|------|
| macOS Intel (x86_64) | `Prompt-Live-apple-intel.zip` |
| macOS Apple Silicon (M1/M2/M3) | `Prompt-Live-apple-silicon.zip` |
| Windows 10/11 (x64) | `Prompt-Live-windows-x64.zip` |

**macOS** — Unzip and drag `Prompt-Live.app` to your Applications folder.

> **macOS security**: the app is not notarized by Apple. On first launch, macOS may silently block it. Open a Terminal and run:
> ```bash
> xattr -dr com.apple.quarantine /Applications/Prompt-Live.app
> ```
> Then launch the app normally.

**Windows** — Unzip `Prompt-Live-windows-x64.zip` anywhere and run `Prompt-Live.exe`.

> **Windows security**: SmartScreen may show a warning on first launch. Click **More info** then **Run anyway**. This only happens once.

---

## `.prompt` file format

Song files are plain text with a lightweight syntax.

### Header

```
Titre: Amazing Grace
TailleParoles: 32
TailleAccords: 18
CouleurSection: jaune
CouleurAccords: gris
Vitesse: 2

@Vanessa: Rouge
@Guillaume: Bleu
@Armelle: Violet
```

| Key | Description | Default |
|-----|-------------|---------|
| `Titre:` | Song title | filename |
| `TailleParoles:` | Lyrics font size | `28` |
| `TailleAccords:` | Chord font size | `18` |
| `TailleSection:` | Section label font size | `16` |
| `CouleurSection:` | Section label color | `#AAAAAA` |
| `CouleurAccords:` | Chord color | `#888888` |
| `AfficherAccords:` | Show chords: `oui` / `non` | `oui` |
| `Vitesse:` | Auto-scroll speed for this song (1–5) | _(global speed)_ |
| `@Name: color` | Defines a singer's color | — |

### Content

```
[Intro]
(Acoustic guitar — capo 2)
G         Cmaj7/E
Amazing grace, how sweet the sound

[Verse 1]@Vanessa
D          G
That saved a wretch like me @Guillaume
```

| Syntax | Effect |
|--------|--------|
| `[Section]` | Section label |
| `[Section]@Name` | Entire section in that singer's color |
| `Line @Name` | Individual line in that singer's color |
| `(text in parentheses)` | Stage note / direction (italic grey) |
| Short line above lyrics | Chord line (smaller font) |

### Available colors

`rouge` `bleu` `vert` `orange` `jaune` `violet` `cyan` `rose` `blanc` `gris`

Or any hex code: `#FF8800`

### Setlist order

Prefix files with a number to define the order:

```
01_Amazing Grace.prompt
02_Hallelujah.prompt
03_Le Reve du Pecheur.prompt
```

---

## Usage

### Running a show

1. Open Prompt-Live and select your songs folder
2. Connect your projector or stage TV — it appears automatically in full screen
3. Use the control window to navigate and adjust speed
4. Click **Launch** to start

### Keyboard shortcuts (prompter mode)

| Key | Action |
|-----|--------|
| `↑` / `↓` | Scroll |
| `→` / `Page Down` | Next song |
| `←` / `Page Up` | Previous song |

### Bluetooth pedal

Any Bluetooth pedal recognized as an HID keyboard is supported natively. The key filter works regardless of which window is focused — no need to keep the prompter in the foreground.

| Gesture | Action |
|---------|--------|
| Pedal down (`↓`) | Scroll down |
| 2 presses at bottom of page | Next song |
| Pedal up (`↑`) | Scroll up |
| 2 presses at top of page | Previous song |

The pedal can be **enabled/disabled** and its **scroll speed** set independently in the control window (*BT Pedal* section).

Recognized keys: `↓`, `Space`, `F5` (down) — `↑`, `F6` (up). If your pedal sends different keys, edit `_PEDAL_DOWN_KEYS` / `_PEDAL_UP_KEYS` in `main.py`.

### iPad sync

On the same Wi-Fi network, open a browser on your iPad and go to:

```
http://<computer IP>:8765
```

The IP address is shown in the control window. The tablet follows the scroll in real time.

---

## Build & Release

**macOS**
```bash
# Regenerate icon (if changed)
python logo/make_icns.py

# Build the app
./build.sh
# → dist/Prompt-Live.app
```

**Windows**
```powershell
.venv\Scripts\pip install pyinstaller pillow
.venv\Scripts\pyinstaller prompt-live.spec --clean --noconfirm
# → dist\Prompt-Live\Prompt-Live.exe
```

GitHub Actions runs the tests and automatically produces macOS (Intel + Apple Silicon) and Windows binaries on any `v*` tag push:

```bash
git tag v1.0.0
git push origin v1.0.0
```

---

## FAQ

**App doesn't start (no window, no error) — macOS**
> macOS silently blocks unsigned downloaded apps. Open a Terminal and run:
> ```bash
> xattr -dr com.apple.quarantine /Applications/Prompt-Live.app
> ```
> Then relaunch normally.

**Windows SmartScreen blocks the launch**
> Click **More info** in the warning window, then **Run anyway**. This only happens on first launch for unsigned executables.

**macOS says "unidentified developer"**
> Right-click → **Open** on `Prompt-Live.app`. Confirm in the dialog. Only needed once.

**External screen doesn't go full screen**
> Make sure the external display is detected by macOS (System Settings → Displays). Prompt-Live automatically uses the second screen when the prompter is launched. If you plugged it in after startup, relaunch the prompter.

**iPad won't connect**
> - Make sure the computer and iPad are on the **same Wi-Fi network**
> - The IP address is shown in the control window (e.g. `http://192.168.1.10:8765`)
> - Temporarily disable the macOS firewall if the connection fails (System Settings → Network → Firewall)
> - Some corporate networks block local device-to-device connections

**iPad scroll is out of sync with the main screen**
> Sync is line-number based. If font sizes differ significantly between the screen and the iPad, the displayed line may be slightly off — this is expected.

**Chords are misaligned with lyrics**
> Use only **monospace** fonts (PT Mono is embedded and selected by default). Helvetica, Arial and other proportional fonts cause alignment drift.

**A song doesn't appear in the list**
> Files must have the `.prompt` extension and be in the selected folder. Files without a numeric prefix are shown last.

**App won't close when an iPad is connected**
> Close the control window (red button). All windows and the web server close together. If the app stays in the background, force-quit with `Cmd+Q`.

**Editing a `.prompt` file in an external editor**
> Prompt-Live watches the folder automatically. Any change saved in an external editor is reloaded live without restarting the app.

---

## License

[MIT + Commons Clause](LICENSE) — free to use and modify, but reselling the software is not permitted.
