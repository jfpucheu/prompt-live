<p align="center">
  <img src="logo/prompt-live.svg" width="120" alt="Prompt-Live logo"/>
</p>

<h1 align="center">Prompt-Live</h1>
<p align="center"><em>Prompteur musical pour groupes live — paroles & accords sur grand écran</em></p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-macOS-lightgrey?logo=apple"/>
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python"/>
  <img src="https://img.shields.io/badge/license-MIT%20%2B%20Commons%20Clause-orange"/>
</p>

---

## Présentation

Prompt-Live est une application macOS pour afficher paroles et accords en temps réel sur scène. Elle est pensée pour les groupes avec plusieurs chanteurs : chaque interprète peut être coloré différemment, les accords sont affichés au-dessus des paroles, et tout défile en douceur depuis la table de régie.

**Fonctionnalités principales**

- Chargement d'un dossier de fichiers `.prompt` numérotés (ordre de passage automatique)
- Affichage plein écran sur l'écran externe (retro-projecteur, TV scène…)
- Défilement fluide avec animation, vitesse réglable (5 niveaux)
- Navigation au clavier : ↑↓ défilement, ←→ chanson précédente/suivante
- Synchronisation iPad/tablette via navigateur web (serveur SSE intégré)
- Support multi-écrans : même ligne en haut sur tous les écrans
- Éditeur intégré avec prévisualisation en direct
- Coloration par chanteur / section
- Polices monospace embarquées (PT Mono) pour un alignement parfait accords/paroles
- Import PDF et DOCX

---

## Installation (développement)

```bash
git clone https://github.com/jfpucheu/prompt-live.git
cd prompt-live
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

---

## Télécharger l'application

Rendez-vous sur la page [**Releases**](https://github.com/jfpucheu/prompt-live/releases) pour télécharger la dernière version compilée pour macOS :

| Version | Intel (x86_64) | Apple Silicon (M1/M2/M3) |
|---------|---------------|--------------------------|
| Dernière | `Prompt-Live-intel.zip` | `Prompt-Live-apple-silicon.zip` |

Dézipper et glisser `Prompt-Live.app` dans votre dossier Applications.

> **Sécurité macOS** : au premier lancement, faire clic droit → Ouvrir si macOS bloque l'application (non notarisée).

---

## Format des fichiers `.prompt`

Les fichiers sont de simples fichiers texte avec une syntaxe légère.

### En-tête

```
Titre: Amazing Grace
TailleParoles: 32
TailleAccords: 18
CouleurSection: jaune
CouleurAccords: gris

@Vanessa: Rouge
@Guillaume: Bleu
@Armelle: Violet
```

| Balise | Description | Défaut |
|--------|-------------|--------|
| `Titre:` | Titre affiché | nom du fichier |
| `TailleParoles:` | Taille de police des paroles | `28` |
| `TailleAccords:` | Taille de police des accords | `18` |
| `TailleSection:` | Taille des titres de section | `16` |
| `CouleurSection:` | Couleur des titres de section | `#AAAAAA` |
| `CouleurAccords:` | Couleur des accords | `#888888` |
| `AfficherAccords:` | `oui` / `non` | `oui` |
| `@Prenom: couleur` | Définit la couleur d'un chanteur | — |

### Contenu

```
[Intro]
(Guitare acoustique — capo 2)
G         Cmaj7/E
Amazing grace, how sweet the sound

[Couplet 1]@Vanessa
D          G
That saved a wretch like me @Guillaume
```

| Syntaxe | Effet |
|---------|-------|
| `[Section]` | Titre de section |
| `[Section]@Prenom` | Section entière colorée |
| `Ligne @Prenom` | Ligne individuelle colorée |
| `(note entre parenthèses)` | Note / indication de jeu (italique gris) |
| Ligne courte au-dessus des paroles | Accord (police plus petite) |

### Couleurs disponibles

`rouge` `bleu` `vert` `orange` `jaune` `violet` `cyan` `rose` `blanc` `gris`
Ou code hexadécimal : `#FF8800`

### Ordre de passage

Préfixer les fichiers par un numéro pour définir l'ordre :

```
01_Amazing Grace.prompt
02_Hallelujah.prompt
03_Le Reve du Pecheur.prompt
```

---

## Utilisation

### Lancer un concert

1. Ouvrir Prompt-Live et sélectionner le dossier de chansons
2. Brancher le retro-projecteur / TV scène — il s'affiche automatiquement en plein écran
3. Utiliser la fenêtre de contrôle pour naviguer et régler la vitesse
4. Appuyer sur **Prompter** pour démarrer

### Contrôles clavier (en mode prompteur)

| Touche | Action |
|--------|--------|
| `↑` / `↓` | Défilement |
| `→` / `Page Bas` | Chanson suivante |
| `←` / `Page Haut` | Chanson précédente |

### Synchronisation iPad

Sur le même réseau Wi-Fi, ouvrir un navigateur sur l'iPad et aller sur :

```
http://<IP de l'ordinateur>:8765
```

L'adresse IP est affichée dans la fenêtre de contrôle. La tablette suit le défilement en temps réel.

---

## Build & Release

```bash
# Générer l'icône (si modifiée)
python logo/make_icns.py

# Compiler l'application
./build.sh
# → dist/Prompt-Live.app
```

La CI GitHub Actions produit automatiquement les binaires Intel et Apple Silicon lors d'un push de tag `v*` :

```bash
git tag v1.0.0
git push origin v1.0.0
```

---

## Licence

[MIT + Commons Clause](LICENSE) — libre d'utilisation et de modification, mais la revente du logiciel est interdite.
