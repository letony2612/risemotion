# Témoignage de Tony — le style de dessin (validé par Tony : « je kiffe le style de dessins, il faut garder ça »)

Le style du film, c'est **son tout premier dessin** (`tools/draw_test.py`, rendu `tools/still.png`), redessiné
**en noir sur fond blanc** par `tools/sketch.py`. **Le dessin validé** (« OUAIIIS franchement ça c'est top ») est gardé
tel quel dans `reference/tony_valide.png` ; `python3 tools/sketch.py` le refait à l'identique dans
`renders/tony_sketch.png`. Toute nouvelle image du film se dessine avec ce script et sa plume `Hand`, et se compare à
cette référence.

## À garder

- **Fond blanc papier** (250, 248, 243), **encre noire** (24, 22, 22). Une seule couleur : l'orange RISE
  (255, 109, 0), pour la flamme du logo — et le rouge du stylo du prof (206, 32, 38), pour son commentaire sur le
  bulletin (« il faudrait l'écrire en rouge »).
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
  flèche. (Son prénom, il le veut quand même sur « Moi c'est Tony » : écrit en grand à côté de lui, « TONY », et
  « CRÉATEUR DE RISE » dessous, comme dans un documentaire — sans flèche.)
- Pas de gros trait entre le nez et la bouche (« bizarre ») : la moustache est faite de petits traits.
- Pas de décor chargé (fenêtre, étagère, plante, tasse : « ça fait trop »).
- Ne pas reprendre l'accroche d'un autre (le faux écran « contenu sensible » du reel de référence, sa phrase) :
  « ça va faire copieur ». On garde le principe — une image qui intrigue dès la première seconde — mais avec son
  histoire à lui et la niche de RISE (« dans notre contexte ou peut-être notre niche »).

## Le texte

Le texte du film est dans `SCRIPT.md` (version de Tony ; « Depuis tout jeune » retiré à sa demande). Il remplace les
listes `SCRIPT` des anciens `tools/episode1_v*.py`.

## Sa voix

Tony a fait sa voix avec ElevenLabs (le bloc `[bored]` de `SCRIPT.md`), en une prise : `assets/voice/take_elevenlabs.mp3`.
`python3 tools/voice.py assets/voice/take_elevenlabs.mp3` la coupe phrase par phrase (le texte calé sur la prise par
`dtw_align`, repris de `rise-presentation`), raccourcit les silences trop longs (« n'hésite pas à cut si besoin pour
rendre certaines phrases plus impactantes ») sans toucher aux mots ni à leur vitesse, garde un temps avant « C'est
justement pour ça que j'ai créé RISE », et donne `assets/voice/voice.wav` et `assets/voice/take.json` (l'heure de
chaque mot). Les pauses entre les phrases se règlent dans `LINES` de `tools/voice.py` (une pause après « même par des
profs… », le temps de lire le bulletin : « on coupe un peu après qu'on dit par les profs », puis un peu moins ; une
avant la dernière phrase, le temps du câlin collectif).

## Animation

`tools/film.py` → `renders/film_v7.mp4` : tout le film, sur sa voix, chaque mouvement calé sur un de ses mots. Les
dessins de `sketch.py` animés comme le reel qu'il a envoyé — douze dessins par seconde, chacun tenu deux images,
l'encre qui « vibre » un peu (la main repasse les traits ; ce qui est aléatoire — les poils, les rayons, le gribouillis
— reste en place d'un dessin à l'autre) ; peu de choses bougent à la fois ; les scènes s'enchaînent par des mouvements
de caméra, pas par des coupes (un défilement vers la page suivante quand le lieu change). On reprend la technique du
reel, jamais les motifs propres à cet artiste (pas d'yeux qui flottent : « le regard des autres », ce sont des gens
tournés vers lui).

- **Pas de sous-titres** (« pour que les gens soient plus concentrés sur la vidéo ») : des mots clés s'écrivent à la
  main dans l'image, là où ils vont, **bien avant qu'il les dise** (« beaucoup plus tôt avant que je dise le mot
  carrément », `LEAD` dans `film.py` : une seconde avant, écrits vite) : RENFERMÉ, AMIS / PROCHES / PROFS, BARRIÈRES,
  JUGEMENT, DIFFICILE, MA FOI, APPRENDRE / PARTAGER / AVEC DIEU, UNE COMMUNAUTÉ, GRANDIR DANS MA FOI… Ce qui les
  illustre arrive aussi avant le mot (les bulles, les écrans du téléphone, le mur).
- **Un maximum de détails sur chaque parole** (« mettre un maximum de détails sur chaque parole »).
- **Rien d'important sous l'interface de TikTok** : les onglets en haut (200 px), la colonne de boutons à droite (x > 930,
  de 640 à 1560), le nom et la description en bas (les 440 derniers px). `python3 tools/film.py --safe T1 T2…` montre
  ces zones sur les images.
- Son téléphone sur la table affiche **RISE** (le logo entier), pas seulement la flamme.
- **La signature RISE à la fin de chaque vidéo** (« ça sera notre signature en gros à chaque fin de vidéo ») : le logo
  RISE dessiné, sa flamme qui s'allume, « Disponible sur les stores » écrit à la main et les badges App Store et Google
  Play (les vrais, `assets/brand/`, jamais redessinés), sur une page blanche après sa dernière phrase.

Les scènes, dans l'ordre (le storyboard en 16 images validé avec Tony, puis ses retours) : l'alerte dans sa tête
(« Annuler » entouré), le recul, son téléphone qui s'allume ; « Moi c'est Tony » ; renfermé, seul dans un coin ; le
« ? » coincé ; la bulle gribouillée ; le groupe qui parle sans lui ; ces trois-là qui deviennent de grandes silhouettes
au-dessus de lui, leurs noms sur leur banc (amis, proches, profs) ; son bulletin, qui vient en grand, avec « Tony se
complaît dans sa médiocrité » écrit en rouge (sans notes : elles étaient inventées), le temps de le lire (une pause
dans sa voix après « profs ») ; les paroles illisibles qui tombent dans un mur de briques ; « jugement » : une bulle qui
se moque (« Haha, n'importe quoi… », qui reprend sa peur de dire n'importe quoi) ; « regard » : les gens qui rient de
lui ; « difficile » : eux au loin, et un cadenas sur le chemin ; « ça me freine dans ma foi » : l'église autour d'eux,
et des barrières tout le long du chemin ; une table de frères et sœurs avec une chaise vide, qu'ils regardent sur
« autour de nous » ; le grand téléphone RISE ; la communauté autour, lui compris, chacun avec ses « … » ; ce qu'on y
fait (témoignages, questions, l'alerte du début avec cette fois « Demander » entouré, et « groupes » : un câlin
collectif, en entrant dans l'écran) ; lui à sa table qui sourit un peu, sa bulle de foi qui grandit ; la signature RISE.
