# Témoignage de Tony — le style de dessin (validé par Tony : « je kiffe le style de dessins, il faut garder ça »)

Le style du film, c'est **son tout premier dessin** (`tools/draw_test.py`, rendu `tools/still.png`), redessiné
**en noir sur fond blanc** par `tools/sketch.py`. **Le dessin validé** (« OUAIIIS franchement ça c'est top ») est gardé
tel quel dans `reference/tony_valide.png` ; `python3 tools/sketch.py` le refait à l'identique dans
`renders/tony_sketch.png`. Toute nouvelle image du film se dessine avec ce script et sa plume `Hand`, et se compare à
cette référence.

## À garder

- **Fond blanc papier** (250, 248, 243), **encre noire** (24, 22, 22). Une seule couleur : l'orange RISE
  (255, 109, 0), pour la flamme du logo.
- **Trait à main levée, « sans retouche, sans outils »** (ni règle ni compas) : le trait ondule un peu, s'épaissit
  là où le feutre se pose et s'affine quand il se lève, dépasse un peu à ses bouts, est parfois fait en deux fois ou
  repassé à côté de lui-même ; un cercle ne se referme jamais parfaitement ; les hachures sont parallèles et
  s'arrêtent près du bord, pas dessus ; le feutre accroche un peu sur le grain du papier.
- **Un dessin simple, comme le premier** : Tony de face à sa table, la tête un peu penchée ; la table (son bord,
  les planches en perspective, quelques tirets de bois) ; le téléphone posé, allumé, avec ses rayons ; des bulles de
  pensée (?, bulle de message, croix). Pas de décor chargé.
- **Tony** : visage rond de face ; lunettes rondes fines ; yeux fatigués, paupières lourdes, cernes ; sourcils
  épais ; le nez du premier dessin ; bouche plate ; tee-shirt à col rond côtelé, plis, hachures sur une épaule ; cou
  hachuré sous le menton.
- **Cheveux** : ondulés façon coréenne et **tirés vers l'arrière** (« mes cheveux partent en arrière ») : ils
  montent du front et repartent en vagues par-dessus la tête, un peu de volume sur le devant mais **le crâne pas trop
  long** (« un tout petit peu moins long »), le front dégagé, deux mèches libres qui retombent sur le front — demandé
  par Tony (« ça me ressemblerait plus »). Pas de frange.
- **Barbe** : courte, en petits traits, la moustache aussi en petits traits — **choisie par Tony** (la version rasée
  existe encore : `drawing(beard=False)`).

- **Les autres personnes** : dessinées comme Tony (visage rond, traits simples, même plume), chacune avec ses
  cheveux à elle ; toujours vues du buste, derrière une table qui cache le reste (jamais de mains).
- **Les images du film** : une par phrase de `SCRIPT.md`, dans `SCENES` de `tools/sketch.py` (rendus
  `renders/scene_01.png`…). La 1 est le dessin validé, inchangé.

## À ne pas faire (ses retours)

- **Pas de mains**, nulle part dans le film (« ça fait peur ») : les bras descendent sous la table.
- Pas de fond noir (« on reste sur du fond blanc »).
- Pas de rendu 3D ou gravé (« ça fait vachement 3D »).
- Pas de tête réaliste de trois-quarts (« y a rien à voir » avec son dessin).
- Rien d'enfantin : pas d'yeux mignons avec reflet, de grand sourire, de coucou de la main, de prénom avec une
  flèche.
- Pas de gros trait entre le nez et la bouche (« bizarre ») : la moustache est faite de petits traits.
- Pas de décor chargé (fenêtre, étagère, plante, tasse : « ça fait trop »).
- Ne pas reprendre l'accroche d'un autre (le faux écran « contenu sensible » du reel de référence, sa phrase) :
  « ça va faire copieur ». On garde le principe — une image qui intrigue dès la première seconde — mais avec son
  histoire à lui et la niche de RISE (« dans notre contexte ou peut-être notre niche »).

## Le texte

Le texte du film est dans `SCRIPT.md` (version de Tony ; « Depuis tout jeune » retiré à sa demande). Il remplace les
listes `SCRIPT` des anciens `tools/episode1_v*.py`.

## Animation

`tools/film.py` → `renders/film_v2.mp4` (il s'ouvre sur l'alerte qu'il a dans la tête, voir `SCRIPT.md` ; la v1
s'ouvrait sur le premier dessin et ses bulles) : les dessins de `sketch.py` animés comme le reel qu'il a envoyé — douze
dessins par seconde, chacun tenu deux images, l'encre qui « vibre » un peu (la main repasse les traits ; ce qui est
aléatoire — les poils, les rayons, le gribouillis — reste en place d'un dessin à l'autre) ; peu de choses bougent à
la fois ; les scènes s'enchaînent par des mouvements de caméra, pas par des coupes. Tant que sa voix n'est pas
enregistrée, la phrase s'écrit en haut mot à mot (petites capitales, coupée à ses pauses) ; tout se recale ensuite
sur sa voix. On reprend la technique du reel, jamais les motifs propres à cet artiste.
