# Témoignage de Tony — le texte (version de Tony, retouchée ensemble)

Toute l'histoire en une vidéo, de l'accroche à RISE : environ 1 min 10 à 1 min 20 à voix posée. Tony l'enregistre
lui-même ; les images se calent ensuite sur sa voix. Les « paroles » qu'il a entendues se montrent écrites à la main
à l'image (comme le commentaire du bulletin « Tony se complaît dans sa médiocrité »), elles ne se disent pas.

L'accroche se voit avant de s'entendre : la première image, en grand (« c'est bien d'avoir le truc en grand »), est ce
qu'il a dans la tête, dessiné comme une alerte de téléphone — ⚠ « Demander de la prière ? » et, en gros, « Tu risques
de déranger. » [Annuler] [Demander]. La voix dit la même chose (« peur de déranger ») pour qu'on comprenne tout de
suite ; « Annuler » s'entoure sur « Moi, tout le temps », la caméra recule et c'est une pensée au-dessus de lui ; son
téléphone, éteint, s'allume en orange sur « réseau social ». C'est notre idée à nous, dans notre niche : on ne reprend
ni l'écran ni la phrase du reel de référence (« ça va faire copieur »). Si « demander de la prière » n'est pas vrai
pour Tony, l'alerte dit « Envoyer le message ? » (`ALERTS` dans `tools/sketch.py`).

> Toi aussi, t'as peur de déranger ? Moi, tout le temps.
>
> Et pourtant… j'ai créé un réseau social.
>
> Moi c'est Tony.
>
> Pendant longtemps, j'ai été quelqu'un de renfermé. Le genre de personne qui n'osait pas poser de questions.
> Peut-être par peur de dire n'importe quoi… ou par peur de déranger.
>
> J'ai souvent été rabaissé. Par des amis, par des proches, même par des profs…
>
> À force d'entendre ce genre de paroles, j'ai fini par me créer des barrières. J'avais peur du jugement, du regard
> des autres. Aller vers les gens était devenu difficile.
>
> Même en grandissant dans ma foi, j'avais du mal à faire le premier pas pour échanger avec d'autres chrétiens.
>
> Pourtant, j'avais besoin de cet entourage pour apprendre, partager et avancer avec Dieu.
>
> C'est justement pour ça que j'ai créé RISE.
>
> Pour offrir une communauté à ceux qui, comme moi, n'osent pas toujours aller vers les autres. Un endroit où partager
> leurs témoignages, poser leurs questions, demander de la prière et rejoindre des groupes.
>
> Parce que je voulais créer l'espace dont j'aurais moi-même eu besoin pour grandir dans ma foi.

## Version pour ElevenLabs (modèle Eleven v3), avec les émotions

Ton voulu par Tony : **ennuyé** (« bored »), sombre et **linéaire** — la même voix du début à la fin, sans montée ni
changement d'émotion, comme le reel de référence. Une seule indication, la même en tête de chaque paragraphe pour que
la voix ne dérive pas ; pas d'autres consignes ; la ponctuation du texte telle quelle. Les indications entre crochets
sont en anglais (le modèle les lit comme des consignes, il ne les prononce pas). Réglage conseillé : Stability sur
« Natural » ; « Creative » si ce n'est pas assez triste, « Robust » si la voix varie trop. Si la voix prononce mal « RISE », l'écrire comme il se dit.

```
[bored] Toi aussi, t'as peur de déranger ? Moi, tout le temps.

[bored] Et pourtant… j'ai créé un réseau social.

[bored] Moi c'est Tony.

[bored] Pendant longtemps, j'ai été quelqu'un de renfermé. Le genre de personne qui n'osait pas poser de questions. Peut-être par peur de dire n'importe quoi… ou par peur de déranger.

[bored] J'ai souvent été rabaissé. Par des amis, par des proches, même par des profs…

[bored] À force d'entendre ce genre de paroles, j'ai fini par me créer des barrières. J'avais peur du jugement, du regard des autres. Aller vers les gens était devenu difficile.

[bored] Même en grandissant dans ma foi, j'avais du mal à faire le premier pas pour échanger avec d'autres chrétiens.

[bored] Pourtant, j'avais besoin de cet entourage pour apprendre, partager et avancer avec Dieu.

[bored] C'est justement pour ça que j'ai créé RISE.

[bored] Pour offrir une communauté à ceux qui, comme moi, n'osent pas toujours aller vers les autres. Un endroit où partager leurs témoignages, poser leurs questions, demander de la prière et rejoindre des groupes.

[bored] Parce que je voulais créer l'espace dont j'aurais moi-même eu besoin pour grandir dans ma foi.
```
