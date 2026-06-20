# Format des fichiers .prompt

## En-tête

| Balise | Exemple | Défaut |
|--------|---------|--------|
| `Titre:` | `Titre: Le Reve du Pecheur` | nom du fichier |
| `Notes:` | `Notes: Capo 2` | _(vide)_ |
| `TailleParoles:` | `TailleParoles: 28` | `28` |
| `TailleAccords:` | `TailleAccords: 18` | `18` |
| `TailleSection:` | `TailleSection: 14` | `16` |
| `CouleurSection:` | `CouleurSection: jaune` | `#AAAAAA` |
| `CouleurAccords:` | `CouleurAccords: gris` | `#888888` |
| `AfficherAccords:` | `AfficherAccords: non` | `oui` |
| `Vitesse:` | `Vitesse: 4` | _(vitesse globale)_ |
| `@Prenom: couleur` | `@Vanessa: Rouge` | _(définit une couleur)_ |

## Dans le contenu

| Syntaxe | Effet |
|---------|-------|
| `[Intro]` | Marqueur de section |
| `[Chorus]@Vanessa` | Section entière en couleur de Vanessa |
| `J'ai un rêve @Guillaume` | Ligne individuelle en couleur de Guillaume |

## Couleurs disponibles

`rouge` `bleu` `vert` `orange` `jaune` `violet` `cyan` `rose` `blanc` `gris`

Ou un code hex : `CouleurAccords: #FF8800`

## Exemple complet

```
Titre: Le Reve du Pecheur
Notes: Capo 2
TailleParoles: 28
TailleAccords: 18
TailleSection: 14
CouleurSection: jaune
CouleurAccords: gris
Vitesse: 2

@Vanessa: Rouge
@Guillaume: Bleu
@Armelle: Violet

[Intro]
G
Cmaj7/E  D7/F#  G

[Verse 1]@Vanessa
Cmaj7/E
J'ai un rêve
D7/F#
 Le rêve que j'ai

[Chorus]
Pêcher         pêcher @Guillaume
Ici c'est faire des pêchés
```

## Nommage des fichiers

Les fichiers doivent commencer par un numéro pour définir l'ordre de passage :

```
01_Amazing Grace.prompt
02_Hallelujah.prompt
03_Le Reve du Pecheur.prompt
```
