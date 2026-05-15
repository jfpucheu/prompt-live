# Promt — Prompteur musical

Application Mac PyQt6 pour afficher paroles et accords en live sur scène.
Diffuse également en temps réel sur iPad/navigateur via un serveur SSE local.

## Lancer l'application

```bash
cd /Users/jeff/Developpement/prompt
python main.py
```

## Architecture

| Fichier | Rôle |
|---------|------|
| `main.py` | Fenêtre de contrôle (`ControlWindow`), fenêtre prompteur (`PrompterWindow`), flash d'écran |
| `editor.py` | Éditeur WYSIWYG des fichiers `.prompt` |
| `renderer.py` | Génération HTML depuis un objet `Song` — utilisé par le prompteur desktop ET l'iPad |
| `parsers.py` | Parsing des fichiers `.prompt` → objets `Song`, `Section`, `PromptLine` |
| `web_server.py` | Serveur HTTP + SSE (port 8765) pour la diffusion iPad |

## Flux de données

```
fichiers .prompt
    → parsers.load_songs()       → list[Song]
    → renderer.render_html()     → HTML string
    → PrompterView.setHtml()     → affichage desktop
    → web_server.push_song()     → SSE → iPad/navigateur
```

## Classes principales

### `Song` (parsers.py)
Objet central passé partout.
- `font_lyrics`, `font_chords`, `font_section` : tailles en px
- `chord_color`, `section_color` : couleurs hex
- `show_chords` : bool
- `tags` : `{lower: hex}`, `tag_names` : `{lower: original_case}`
- `sections` : list[Section]

### `Section` / `PromptLine` (parsers.py)
- `Section.singer` : prénom affiché après `▸` sur la section
- `PromptLine.is_chord` : détecté automatiquement par `is_chord_line()`
- `PromptLine.color` / `PromptLine.singer` : issu des balises `@Tag` en fin de ligne

### `EditorWindow` (editor.py)
- `_BD(QTextBlockUserData)` : métadonnées par bloc — `tag`, `is_section`, `is_chord`
- `_ins()` : insère un bloc avec format fixe (`FixedHeight = lyrics_size * 1.45`)
- `_render_section_block()` : réécrit texte + format d'un bloc section (via `insertText`)
- `_reformat_section_block()` : met à jour couleurs/taille d'un bloc section (via `mergeCharFormat` — visuellement fiable)
- **IMPORTANT** : `mergeCharFormat` fonctionne visuellement dans `beginEditBlock` ; `insertText` ne repeint pas. Utiliser `_reformat_section_block` pour les changements de couleur/taille, `_render_section_block` pour les changements de texte.

### `render_html()` (renderer.py)
- Paramètres : `song`, `zoom`, `show_chords`, `font_family`
- Les lignes d'accords utilisent `_chord_spans()` : les noms d'accords sont rendus à `fs_chords`, les **espaces à `fs_lyrics`** → alignement parfait quelle que soit la taille
- `font-size:{fs_lyrics}px` sur chaque `<p>` force QTextBrowser à utiliser la bonne hauteur de bloc
- Police actuelle : `'Courier New',Courier,monospace` (monospace obligatoire pour l'alignement)

### `PromptWebServer` (web_server.py)
- SSE sur `/events` : messages JSON `{type: "song"|"setlist"|"scroll", ...}`
- `push_song(html)` : envoie le HTML complet d'une chanson
- `push_setlist(titles)` : envoie la liste des chansons (état repos)
- `push_scroll(ratio)` : synchronise le défilement (0.0–1.0)

## Format des fichiers .prompt

Voir `FORMAT.md` pour la syntaxe complète.

Points importants :
- Fichiers numérotés (`01_...prompt`) pour l'ordre de passage
- Lignes d'accords détectées automatiquement si tous les tokens matchent `[A-G][#b]?...`
- Les espaces dans les lignes d'accords doivent être calibrés en **Courier New** — c'est la seule police qui garantit l'alignement avec le rendu

## Réglages persistants (`QSettings "Promt"/"Promt"`)

| Clé | Valeur |
|-----|--------|
| `last_dir` | Dernier répertoire de chansons |
| `font_family` | Police monospace choisie |

## Pièges connus

- **Ne jamais appeler `blockSignals(True)` sur une scrollbar Qt** — ça bloque le signal `valueChanged` de façon permanente
- **Enum PyQt6** : `QTextBlockFormat.LineHeightTypes.FixedHeight.value` — le `.value` est obligatoire (Python < 3.10)
- **Alignement accords** : les espaces entre les accords sont rendus à `fs_lyrics` (pas `fs_chords`) dans `_chord_spans()`. Ne jamais rendre les espaces à `fs_chords` sinon l'alignement dérive
- **Couleur de section en live** : utiliser `_reformat_section_block` (mergeCharFormat), pas `_render_section_block` (insertText ne repeint pas dans beginEditBlock)
- **Police monospace obligatoire** : avec une police proportionnelle (Helvetica), les espaces dérivent selon les largeurs de caractères. Seule une police monospace garantit l'alignement
