# 17 — Quel modèle pour consolider ? Banc sur six journées réelles (protocole)

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Statut : protocole PRÉ-ENREGISTRÉ — rien n'est mesuré.** Écrit et publié le 5 novembre 2026, AVANT tout appel.
Francis a délégué le jugement des seuils (§6) : ils sont fixés ici, avant de voir le moindre résultat, et ne bougeront
pas. Les résultats seront ajoutés ensuite, échecs compris.
**Question :** quels modèles consolident la mémoire de Nexa aussi bien que son modèle de production, et à quel coût
**réel** — compté par le fournisseur, raisonnement compris ?
**Référence :** `04` (consolidation, contrôle de citation), `13` §19 (rejeu sur copie, mesures de couverture et
questions), `15` (consolidation sans modèle), `16` (visionneuse).

## 1 — Pourquoi

La consolidation est le seul maillon d'EXIA SEED qui exige un modèle de langage. Aujourd'hui, c'est GPT-6 Astra
(effort de raisonnement « low »). Deux inconnues :

- **Le coût réel.** Le journal des consolidations estime les tokens (caractères ÷ 4) et ne compte pas le
  raisonnement, que tous les fournisseurs facturent comme sortie. Sur 42 jours : entrée médiane ≈ 17 400 tokens par
  jour, sortie ≈ 2 100 — estimations.
- **La dépendance à un seul fournisseur et à un modèle cher.** Un modèle dix ou cent fois moins cher consolide-t-il
  aussi fidèlement ? Le 28/10, un petit modèle avait écrit trop peu de faits (`13` §19) : la question est réelle.

## 2 — Les données : six journées de Nexa, deux par profil

Six journées réelles d'usage de Nexa, entre fin octobre et début novembre 2026, choisies par profil de volume (tiers
du brut sur 43 jours : calme < 4 600 tokens ≤ moyen < 8 500 ≤ intensif). Elles sont désignées par une étiquette ;
leur contenu n'est jamais publié.

| Étiquette | Profil | Brut (ordre de grandeur) | Messages de l'utilisateur |
|---|---|---|---|
| C1, C2 | calme | ≈ 1 600 à 1 800 tokens | 3 à 6 |
| M1, M2 | moyen | ≈ 5 000 à 7 600 tokens | 14 à 20 |
| I1, I2 | intensif | ≈ 14 000 à 21 000 tokens | 35 à 39 |

Les journées calmes servent aussi de piège : peu de matière, le modèle doit savoir ne rien inventer.

**Copies uniquement** : la mémoire vivante de Nexa n'est jamais écrite. Le brut est envoyé tel quel aux fournisseurs,
sur décision de Francis (§8).

## 3 — Le même point de départ pour chaque modèle

Pour un jour J, la mémoire est reconstruite **telle qu'elle était la veille**, sans modèle :

- on garde les pages et, dans chaque page, les seuls faits dont le lot d'origine est antérieur à J ; une page née à J
  ou après disparaît ;
- les fiches d'identité et les mots distinctifs sont retirés de toutes les pages (ils peuvent contenir l'avenir) ; le
  graphe est recalculé ;
- **limite connue** : le thésaurus de concepts n'est pas daté ; il est gardé tel quel, le même pour tous les modèles.

Puis chaque modèle consolide les lots du jour J, avec **le code de production de Nexa**, la même consigne (règle 3
exhaustive), le même budget d'entrée (40 000 tokens par appel), la même réponse maximale (8 000 tokens), les fiches
(second appel), et le même contrôle de citation. **Aucune consigne n'est ajustée** : les six jours servent tous à la
vérification, aucun au réglage.

## 4 — Les modèles

| Modèle (identifiant exact) | Fournisseur | Effort de raisonnement | Accès |
|---|---|---|---|
| `gpt-6-astra` | OpenAI | low (production) | abonnement de Nexa, dans son conteneur, sur copie — **la référence** |
| `gpt-6.1-terra` | OpenAI | low | API |
| `gpt-6-luna` | OpenAI | low | API |
| `claude-haiku-5-5` | Anthropic | low | API |
| `mistral-small-2603` (Small 4) | Mistral | none (seuls « none » et « high » existent ; « high » coûterait bien plus) | API |
| `mistral-large-4-0` (Large 4, préversion) | Mistral | low | API |

Écartés : Mistral Medium 3.5 et Large 3, annoncés en retrait le 30/04/2027. Tarifs officiels relevés le 05/11/2026
(USD par million, entrée / sortie) : Astra 10 / 50 · Terra 1 / 5 · Luna 0,10 / 0,50 · Haiku 5.5 0,10 / 0,50 (appels
≤ 100 000 tokens) · Small 4 0,15 / 0,60 · Large 4 0,70 / 2,10.

**Deux passages par modèle et par jour**, pour mesurer l'instabilité. Plafond de dépense : **10 $** pour tout le banc,
inscrit dans le module d'appel (arrêt automatique).

## 5 — Ce qu'on mesure

### 5.1 Le coût réel

Pour chaque appel, les compteurs **renvoyés par le fournisseur** : entrée, entrée en cache, sortie, dont
raisonnement ; nombre d'appels, reprises, erreurs, durée. Coût calculé avec les tarifs du §4. Les estimations
(caractères ÷ 4) sont relevées à côté, pour savoir enfin ce qu'elles valent. Un compteur absent est noté absent, jamais
reconstitué.

### 5.2 La qualité de la consolidation

- **Faits retenus**, et **rejetés par le contrôle de citation** (taux et raisons) ;
- **couverture** : part des messages de l'utilisateur du jour (au moins 6 mots, hors avis du système) cités par au moins un
  fait — la mesure du 28/10 ;
- **stabilité** : écart entre les deux passages d'un même modèle ;
- **contrôle humain** : 10 faits acceptés tirés au sort par modèle (graine fixe), relus par Francis — vrai, faux,
  mal attribué, mal daté. Le contrôle de citation est lexical : il ne voit pas une phrase fausse écrite avec les mots
  de la source (`04` §5.3) ; seul un humain le voit.

### 5.3 L'utilité : des questions

Comme le 28/10 : pour chaque jour, les messages de Francis qui portent un **détail concret** (un nombre, ou un nom
propre ailleurs qu'en tête de phrase). Pour chacun, `gpt-6.1-terra` écrit, à partir du **seul** message, une question
que Francis pourrait poser plus tard et sa réponse — **une fois**, les mêmes pour tous les modèles. Chaque mémoire
répond avec `memoire_chercher` (12 faits) ; lecteur et juge : `gpt-6.1-terra`, les mêmes pour tous (le lecteur et le
juge des bancs précédents, `gpt-4.1-mini` et `gpt-4o-mini`, seront retirés le 14/01/2027). Le juge vérifie aussi, sur
un échantillon, ses propres décisions contre la réponse attendue.

## 6 — Hypothèses et seuils (fixés avant exécution)

Un modèle est dit **qualifié** pour consolider la mémoire de Nexa s'il satisfait **les quatre** :

| # | Critère | Seuil proposé |
|---|---|---|
| Q1 | Bonnes réponses aux questions | ≥ Astra − 5 points (sur l'ensemble des questions des six jours) |
| Q2 | Couverture des messages de l'utilisateur | ≥ Astra − 5 points |
| Q3 | Contrôle humain | 0 fait faux ou mal attribué sur 10 |
| Q4 | Fiabilité technique | 0 passage perdu (réponse illisible non rattrapée) sur 12 |

Les 5 points sont un choix de compromis, posé d'avance : la perte de qualité acceptée en échange d'un coût de
consolidation dix à cent fois plus bas. Les seuils ne seront pas modifiés après lecture des résultats ; si un autre
compromis paraît meilleur ensuite, il sera écrit comme une analyse supplémentaire, distincte du verdict.

Rapportés sans seuil : rejets, stabilité, faits par message, détail par profil (calme, moyen, intensif), coût par jour
et par mois extrapolé sur les 42 jours connus. Test apparié de McNemar et intervalle de confiance pour chaque écart à
Astra. **Avec si peu de questions par jour, une égalité n'est pas une preuve d'équivalence** : elle sera écrite comme
telle.

**Décision** : parmi les modèles qualifiés, le moins cher. Si aucun n'est qualifié, on le dit, et on publie ce que
chacun perd.

## 7 — Ce que ce banc ne dira pas

- La qualité sur d'autres personnes, d'autres langues, d'autres métiers : six journées d'un seul utilisateur.
- La dérive sur des semaines : chaque jour part de la mémoire de production de la veille, pas de la mémoire que le
  modèle aurait construite lui-même. Un rejeu long viendrait après, pour les modèles qualifiés.
- La meilleure consigne pour chaque modèle : la consigne est celle de production, inchangée. Un modèle pourrait faire
  mieux avec une consigne adaptée ; ce n'est pas la question posée ici.

## 8 — Données et publication

- **Les fournisseurs** (comptes API standard, politiques lues le 05/11/2026) : pas d'entraînement par défaut chez
  OpenAI et Anthropic ; conservation jusqu'à 30 jours pour la surveillance des abus ; Anthropic traite hors d'Europe ;
  Mistral traite en Europe par défaut (ses pages se contredisent sur l'entraînement ; l'option « Anonymous improvement
  data » n'a pas été modifiée, par choix de Francis).
- **Ce qui est publié** : ce protocole, puis **uniquement les résultats des modèles**, agrégés — scores, taux, coûts,
  par profil de journée. Aucune donnée mémorielle, aucun extrait du brut, aucun fait, aucun exemple précis ; le contexte
  est décrit de façon abstraite. Le contrôle humain est rapporté en nombres (vrais, faux, mal attribués), sans les faits.
