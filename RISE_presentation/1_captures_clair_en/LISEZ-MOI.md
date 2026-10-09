# RISE : écrans en anglais

Les écrans de `1_captures_clair` dont la vidéo a besoin, traduits pour sa version anglaise
(`python3 tools/build.py --apple --lang en`, qui les prend via `tools/localize.py`).
Mêmes membres fictifs, même mise en page : seul le texte change. Versets en King James (domaine public).

| Écrans | Comment ils ont été traduits |
|---|---|
| 02, 03, 04, 06, 07, 09, 10, 11, 12, 14 | Retouche IA (Nano Banana Pro, via FLORA), recalée sur la capture d'origine. Les photos et avatars d'origine ont été remis par-dessus : aucun visage retouché par l'IA. Sur 02, le post sous la barre d'onglets avait perdu son fondu : il a été refait à la main. |
| 15, 17, 18, `extraits/` | Retypés à la main dans les polices de l'appli (Inter, Newsreader) : `videos/rise-presentation/tools/retext.py`. Tout ce qui n'est pas du texte est resté au pixel près. `extraits/` : le post verset et la première réponse du quiz, tirés des clips. |

Petits défauts connus, hors des morceaux que la vidéo utilise : sur 07, le bouton « Encourager »
n'est pas traduit et le « 2 » après « Updates » a disparu ; sur 09, la puce « Other » déborde à droite
(on la voit coupée au bord de la feuille, comme une rangée qui défile).
