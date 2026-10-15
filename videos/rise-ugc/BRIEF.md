---
workflow: general-video
flow: automation
storyboard: no
message: "Tu cherches d'autres chrétiens avec qui parler de ta foi ? Sur RISE tu partages, tu rejoins des groupes, tu parles avec d'autres croyants, on prie les uns pour les autres. Élevons-nous ensemble."
aspect: "9:16"
language: fr
length: "16,8 s"
destination: "TikTok (style UGC)"
---

# RISE — test UGC TikTok

## Intent
L'utilisateur veut des vidéos « humaines », qualité iPhone, pas trop lisses, façon contenu UGC, pour TikTok : des
gens sur leur téléphone et des mises en situation, plus l'appli. Pas de photos (« ça convertit pas sur TikTok »).
La génération IA coûtait trop cher pour un résultat incertain : on part sur des vidéos libres de droits (vraies
personnes) et les vraies vidéos d'écran de l'appli.

## Montage
Coupes sur les temps de la musique RISE (124 BPM), qui démarre sur son drop : pleine énergie dès la première image.
Le texte est celui de TikTok (mots noirs sur blanc, une boîte arrondie par ligne), une phrase qui court sur les plans :

| Temps | Plan | Texte |
|---|---|---|
| 0 → 2,9 s | `seul` : quelqu'un seul sur son téléphone, le soir | Tu cherches d'autres chrétiens avec qui parler de ta foi ? |
| 2,9 → 4,8 s | `fil` : le fil de l'appli qui défile | Sur RISE, tu partages ce que tu vis |
| 4,8 → 6,8 s | `amis` : des amis qui rient devant un téléphone | tu rejoins des groupes |
| 6,8 → 9,7 s | `groupe` : un message tapé et envoyé dans un groupe (« Amen ! On se voit dimanche ») | tu parles avec d'autres croyants |
| 9,7 → 11,6 s | `priere` : « Prier » → « Je prie », le compteur passe de 13 à 14 | et on prie les uns pour les autres |
| 11,6 → 13,5 s | `sourire` : quelqu'un qui sourit à son téléphone | Le réseau social créé par un chrétien, pour les chrétiens |
| 13,5 → 16,8 s | la fin de videos/rise-mots : sur noir, la bougie, le boum, le logo, « Élevons-nous ensemble. », « Disponible sur les stores », les badges | |

Chaque plan avance un peu (×1,06) pendant qu'il passe. Les plans de personnes reçoivent un léger grain, pour le
rendu téléphone.

## Ce qui manque
Les trois plans de personnes (`seul`, `amis`, `sourire`) : les banques de vidéos libres (Pexels, Mixkit, Pixabay)
sont bloquées par le réseau de l'environnement cloud. Soit l'utilisateur ouvre l'accès (mixkit.co, assets.mixkit.co,
www.pexels.com, videos.pexels.com), soit il envoie les clips. Ils vont dans footage/ (seul.mp4, amis.mp4,
sourire.mp4 ; pas dans git, trop lourds), puis : python3 tools/prepare.py, tools/build.py, rendu, tools/master.sh.

## Assets et droits
- Appli : les vidéos d'écran de la vraie appli (RISE_presentation/4_clips), sur une base de démonstration : aucun
  vrai membre n'apparaît.
- Personnes : vidéos Pexels ou Mixkit, licence gratuite avec usage commercial, sans mention obligatoire. Ces licences
  interdisent de faire croire que les personnes filmées recommandent le produit : elles servent d'illustration, on ne
  leur fait rien dire (pas de faux témoignage). Noter ici la source de chaque clip.
- Musique : la piste RISE générée avec Lyria pour la présentation (videos/rise-presentation/assets/audio/music_track.mp3).
- Boum : synthétisé (videos/rise-mots/tools/boom.py). Logo et badges : officiels (voir videos/rise-mots).
- Vraies personnes filmées : pas d'étiquette « contenu IA » à mettre sur TikTok.
