---
workflow: motion-graphics
flow: automation
storyboard: no
message: "RISE, le réseau social chrétien : partage, entraide, prière, quiz, verset. Créé par un chrétien, pour les chrétiens."
aspect: "9:16"
language: fr
length: "12,5 s"
destination: "Reels / TikTok / Shorts"
---

# RISE — « rise. » (typo animée)

## Intent
Une vidéo archi simple dans le style d'un reel de référence envoyé par l'utilisateur (« graphics / transitions / repeat. / we don't just edit »):
un seul mot à la fois au centre, très gros, en minuscules ; le fond bascule à chaque mot ; ça coupe sur le beat ; pas de voix,
juste les mots importants. Texte de départ de l'utilisateur : « RISE le premier réseau social chrétien, partage, entraide,
prière, quiz, verset, créé par un chrétien pour les chrétiens. » L'utilisateur a laissé le choix des mots et du rythme.

## Customizations
- v7 : « le pour les chrétiens est même pas terminé que ça fait déjà la transition ; mettre au début réseau social créé par
  un chrétien pour les chrétiens, puis le reste ». La phrase passe au début, sur les coupes les plus lentes (0 → 4 s) :
  « le réseau / social », « créé par un / chrétien », « pour les / chrétiens. » ; chaque fois les mots suivants se posent
  sous les premiers, dans la même lumière ; « pour les chrétiens. » reste sur deux whooshes (0,93 s) avec un lent zoom.
  Puis 16 mots de plus en plus vite (« sondages » ajouté), puis le logo sur blanc.
- v6 : « mettre le RISE à la fin dans un fond blanc pour casser le truc, virer le truc qui vibre ». Le logo passe sur un blanc
  pur (coupe nette depuis le gris de « pour les chrétiens. ») ; plus de tremblement ni de coup de zoom au boum : à la place,
  une lumière chaude part de la flamme sur le blanc pendant que les lettres jaillissent.
- v5 : « virer le R. I. S. E., laisser que le logo à la fin avec un son de transition genre un boum lourd, et splitter le
  créé par un chrétien pour avoir assez de transitions jusqu'à la fin ».
  - Plus de « r / ri. / ris / rise. » ni de mot grossi : les 23 whooshes portent le texte de l'utilisateur dans son ordre :
    « le réseau / social / chrétien. », puis 15 mots de plus en plus vite (partage, entraide, prière, quiz, verset, groupes,
    messages, louange, témoignage, communauté, foi, espérance, amour, joie, paix), puis « créé / par un / chrétien /
    pour les / chrétiens. » sur les coupes les plus rapides.
  - Fin : dans le silence, la bougie du logo (l'animation démarre à 0,2 s), la flamme s'allume, et un boum lourd quand les
    lettres jaillissent (9,67 s), avec un éclat de lumière, l'image qui frappe et tremble ; puis le slogan et les badges.
- v4 : « il faudrait une animation plus stylée qui fait vraiment motion designer, là c'est que des apparitions » et « à la fin
  sans bruit, le logo RISE en motion design et disponible sur les stores ».
  - Chaque mot bouge, calé sur les whooshes : lettres qui montent depuis leur ligne de base, qui rebondissent, qui tombent
    en tournant, qui se resserrent depuis un interlettrage large ; mots qui arrivent de près (zoom) ou en balayage / poussée
    avec flou de vitesse, ou par mise au point ; le whoosh traverse la coupe (le mot part comme le suivant arrive : zoom,
    balayage, poussée) ; « r / ri. / ris / rise. » tapé (les lettres glissent, la nouvelle rebondit), puis « rise. » grossit
    jusqu'aux bords et se fait grignoter.
  - Fin, dans le silence après le son (9,2 → 12,5 s) : l'animation officielle du logo (RISE_presentation/5_logo_anime, version
    claire faite pour la présentation), « Élève-toi. Ensemble. » qui monte, puis les badges App Store et Google Play.
- v3 : l'utilisateur a envoyé le son de la référence (« ce que t'as fait c'est archeum ») : le reel reprend le montage
  de la référence coupe pour coupe, mesuré sur l'enregistrement d'écran : 24 coupes aux mêmes instants, chacune à la fin
  d'un « whoosh » du son, de plus en plus rapprochées ; boucle de 9,5 s dont la fin est silencieuse, comme la référence.
  - La phrase d'abord : « le réseau / social / chrétien. / créé par un chrétien / pour les / chrétiens. » ; un mot reste
    pendant que le suivant se pose dessous.
  - Puis la liste, de plus en plus vite : partage, entraide, prière, quiz, verset, groupes, louange, témoignage, foi,
    amour, joie, paix.
  - Puis « r / ri. / ris / rise. » tapé, puis le mot grossi d'un bord à l'autre et grignoté sur le dernier whoosh (en v3 c'était
    le logo ; il est passé à la fin en v4).
- v2 : la grammaire de la référence. Police type Helvetica grasse (FreeSans Bold), interlettrage serré (-0,035 em), tous
  les mots à la même taille ; le fond et la couleur du texte basculent à chaque coupe ; chaque mot arrive un peu trop gros
  et se pose, certains avec une mise au point floue ou un filé horizontal sur les premières images.
- DA du site RISE : ciel bleu clair, nuages flous, croix floue derrière.
- Deuxième couleur : le ciel au crépuscule, gris avec une lumière pervenche, comme le deuxième fond de la référence ; mots
  blancs. La croix et les nuages n'y sont qu'une trace.
- « le premier » retiré (difficile à prouver) : « le réseau social chrétien. »

## Assets
- Logo : l'animation officielle du splash (RISE_presentation/5_logo_anime), en version claire (assets/brand/rise_splash_light.webm,
  faite par videos/rise-presentation/tools/prepare_splash.py). Badges officiels FR App Store et Google Play (assets/brand).
- Son : music/son_reel_reference.mp3, le son du reel de référence envoyé par l'utilisateur (9,33 s, -14,2 LUFS) ;
  tools/music.py le complète de silence jusqu'à 12,5 s et y place le boum (music/boom.wav, synthétisé par tools/boom.py). Droits : c'est le son d'un autre créateur ; pour publier, le plus
  sûr est de reprendre ce son dans l'app (« Utiliser l'audio »).
- Police : FreeSans Bold (GNU FreeFont, GPL avec exception pour les polices).

## Notes
Usage HyperFrames : inconnu (`hyperframes usage` → unsupported_auth).
