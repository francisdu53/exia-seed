# 17 — Quel modèle pour consolider ? Banc sur six journées réelles (protocole)

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Statut : protocole PRÉ-ENREGISTRÉ — rien n'est mesuré.** Écrit et publié le 5 novembre 2026, AVANT tout appel.
Les seuils (§6) sont fixés ici, avant de voir le moindre résultat, et ne bougeront pas. Les résultats seront ajoutés ensuite, échecs compris.
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

**Copies uniquement** : la mémoire vivante de Nexa n'est jamais écrite. Le brut est envoyé tel quel aux fournisseurs (§8).

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
  Mistral traite en Europe par défaut (ses pages se contredisent sur l'entraînement).
- **Ce qui est publié** : ce protocole, puis **uniquement les résultats des modèles**, agrégés — scores, taux, coûts,
  par profil de journée. Aucune donnée mémorielle, aucun extrait du brut, aucun fait, aucun exemple précis ; le contexte
  est décrit de façon abstraite. Le contrôle humain est rapporté en nombres (vrais, faux, mal attribués), sans les faits.

## 9 — Résultats (5 novembre 2026)

Exécution complète le 5/11 : 6 modèles × 2 passages × 6 journées, puis 71 questions par mémoire (de 1 à 28 selon la
journée), lecteur et juge Terra. **Dépense réelle de tout le banc : 2,04 $** (analyse complémentaire comprise ; Astra
passe par l'abonnement de production). Seuils du §6 appliqués tels quels ; moyenne des deux passages.

### 9.1 Le verdict pré-enregistré

| Modèle | Bonnes réponses | Couverture | Lots perdus (sur 12 journées-passages) | Verdict |
|---|---|---|---|---|
| **GPT-6 Astra** (référence) | **62,7 %** | **69,7 %** | 0 | — |
| GPT-6.1 Terra | 59,2 % ✓ | 58,8 % ✗ (seuil 64,7 %) | 0 ✓ | **non qualifié**, sur la couverture |
| GPT-6 Luna | 33,1 % ✗ | 31,6 % ✗ | 0 ✓ | non qualifié |
| Claude Haiku 5.5 | 27,5 % ✗ | 14,5 % ✗ | 16 ✗ | non qualifié |
| Mistral Small 4 | 27,5 % ✗ | 23,2 % ✗ | 16 ✗ | non qualifié |
| Mistral Large 4 | 28,2 % ✗ | 24,1 % ✗ | 6 ✗ | non qualifié |

- **Aucun modèle n'est qualifié.** Terra est le seul proche : à égalité apparente sur les questions (11 questions
  gagnées, 6 perdues face à Astra sur le premier passage, McNemar p = 0,33 — pas de différence visible, ce qui n'est pas
  une preuve d'équivalence), mais il cite environ 11 points de messages de moins. Il retient en moyenne 76 faits sur les
  six journées, contre 105 pour Astra, et varie davantage d'un passage à l'autre (83 puis 69 faits).
- Les quatre autres perdent nettement sur les questions (McNemar p ≤ 0,013) et retiennent trois à quatre fois et demie moins de
  faits qu'Astra. La perte se concentre sur les journées intensives.
- **Contrôle humain (Q3)** : en attente de la relecture à l'aveugle par Francis ; il ne peut plus changer aucun verdict
  (tous les modèles échouent déjà sur Q1 ou Q2).

### 9.2 Le coût réel, compté par les fournisseurs

| Modèle | Coût réel d'un passage sur les six journées | Mois estimé (une consolidation par jour) |
|---|---|---|
| Astra (prix API équivalent) | 2,14 $ | ≈ 7,3 $ |
| Terra | 0,11 à 0,20 $ | ≈ 0,5 $ |
| Mistral Large 4 | 0,09 à 0,16 $ | ≈ 0,4 $ |
| Haiku 5.5 | 0,04 $ | ≈ 0,13 $ |
| Mistral Small 4 | 0,02 à 0,03 $ | ≈ 0,08 $ |
| Luna | 0,01 à 0,02 $ | ≈ 0,05 $ |

Le mois est extrapolé du volume des 42 jours connus ; il suppose le même mélange de journées.

- **Les estimations du code (caractères ÷ 4) sous-estiment** : chez Astra, 101 700 tokens d'entrée estimés pour
  111 900 réels (+10 %), 17 900 de sortie pour 20 400 (+14 %).
- **Le raisonnement** : à l'effort « low », Terra n'a compté que 209 tokens de raisonnement sur un passage, Luna 3 293 ;
  les autres fournisseurs ne le détaillent pas (il est compris dans la sortie). L'abonnement d'Astra ne le détaille pas
  non plus.
- **Le nombre de passages par jour pèse autant que le modèle.** En production, la consolidation tourne à chaque fin de
  session (environ quatre fois par jour) et renvoie chaque fois la consigne et le catalogue des pages ; sur les mêmes
  journées, une consolidation unique a demandé environ 40 % d'entrée en moins. C'est un levier sans perte connue, à
  mesurer avant de l'adopter.

### 9.3 Un défaut des conditions, et l'analyse complémentaire

La réponse maximale de 8 000 tokens (§3) venait d'un banc précédent ; la consolidation de production n'en impose pas.
Pour la référence, l'écart est resté sans effet (sa plus longue réponse : 5 873 tokens). Mais Haiku 5.5 et les deux
Mistral écrivent plus long : leurs réponses tronquées étaient refusées et, parce que le cache du banc renvoyait la même
réponse au nouvel essai au lieu de rappeler le modèle comme le ferait la production, le lot était perdu.

**Analyse complémentaire, hors verdict** : les trois modèles relancés avec une sortie de 32 000 tokens et de vrais
nouveaux essais.

| Complémentaire | Bonnes réponses | Couverture | Lots perdus |
|---|---|---|---|
| Haiku 5.5 | 34,5 % | 29,4 % | 0 |
| Mistral Large 4 | 30,3 % | 26,3 % | 0 |
| Mistral Small 4 | 23,9 % | 15,8 % | 21 (JSON invalide même au nouvel essai) |

Avec de la place, Haiku et Mistral Large ne perdent plus de lots, mais restent très loin d'Astra : la troncature
n'expliquait pas leur retard. **Correction pour les bancs suivants** : pas de limite de sortie plus basse que celle de
la production, et un nouvel essai doit être un nouvel appel.

### 9.4 Ce que ça veut dire

- **Pour un assistant personnel comme Nexa** : la consigne de consolidation actuelle, écrite et éprouvée avec Astra, ne
  se transporte pas telle quelle vers un modèle bon marché. Le seul candidat sérieux est Terra, environ quatorze fois moins
  cher, qui perd sur la couverture.
- **La question suivante n'est pas « quel modèle », mais « quelle consigne pour quel modèle »** : le banc a testé la
  consigne d'Astra sur tous (§7). Un banc suivant pourrait adapter la consigne à Terra, sur d'autres journées que ces
  six, qui ont désormais servi.
- **Les journées intensives font la différence** : sur les journées calmes, les écarts sont faibles ; c'est quand la
  matière abonde que les petits modèles en laissent tomber.

## 10 — Une consigne adaptée à Terra (pré-enregistré le 5/11, avant exécution)

**Décision de Francis** : rejouer Terra sur **le même panel**, avec une consigne écrite pour lui, afin de comparer sur
les mêmes faits. **Biais connu, écrit d'avance** : ces six journées ont déjà servi ; le résultat sera donc optimiste
pour Terra. Pour le limiter :

- la consigne s'appuie sur deux sources seulement : le guide officiel de la famille GPT-6 (OpenAI n'en publie pas pour
  Terra seul : consignes précises dites une fois, sans insistance typographique, but final explicite, travail
  décomposé puis vérifié ; effort « medium » recommandé par défaut) et le **diagnostic agrégé** du §9 — Terra propose
  environ 22 % de fragments de moins qu'Astra sur les mêmes lignes, et ses rejets « nombre absent des sources » sont
  neuf fois plus nombreux (18 contre 2) : il calcule ou convertit au lieu de recopier ;
- elle est écrite **une seule fois** (`banc/modeles/consigne_terra.txt`) et lancée **une seule fois**, sans aucun
  aller-retour sur les résultats ; même contrat de sortie, même message utilisateur, même contrôle de citation ;
- ce qu'elle change : le but et le critère de fin explicites (chaque message à détail concret couvert), une méthode
  message par message avec vérification finale, la consigne de recopier nombres, dates et noms sans rien calculer dans
  le fait ; le reste des règles de production, dit une fois chacune.

**Deux variantes, deux passages chacune** : **T** — consigne adaptée, effort « low » (celui de la production : isole
l'effet de la consigne) ; **U** — consigne adaptée, effort « medium » (la recommandation d'OpenAI). Mêmes mesures, mêmes
questions, même lecteur et même juge ; mêmes seuils du §6, appliqués à chacune face aux deux passages d'Astra déjà
faits. Budget : moins de 2 $.

### 10.1 Résultats (5 novembre 2026)

| Variante | Bonnes réponses | Couverture | Faits retenus (moy.) | Lots perdus | Face à Astra, premier passage |
|---|---|---|---|---|---|
| Astra, consigne de production (référence) | 62,7 % | 69,7 % | 105 | 0 | — |
| Terra, consigne de production (§9) | 59,2 % | 58,8 % | 76 | 0 | 11 gagnées, 6 perdues, p = 0,33 |
| **Terra T — consigne adaptée, effort « low »** | **69,7 %** ✓ | **79,4 %** ✓ | **127,5** | **0** ✓ | **13 gagnées, 3 perdues, p = 0,02** |
| Terra U — consigne adaptée, effort « medium » | 44,4 % ✗ | 50,9 % ✗ | 104 | 12 ✗ | 7 gagnées, 15 perdues, p = 0,13 |

- **T est qualifiée sur Q1, Q2 et Q4** ; Q3 attend la relecture à l'aveugle. Elle fait mieux qu'Astra et sa consigne
  de production : +7 points de bonnes réponses, +10 points de couverture, environ 20 % de faits en plus, aux deux
  passages (129 puis 126 faits : plus stable que Terra avec la consigne de production). Les rejets « nombre absent des
  sources » tombent de 18 à 0 ; les rejets « nom propre absent » montent (37, contre 19), si bien que le total des
  rejets reste au niveau d'avant (19 en moyenne).
- **Coût réel** : 0,14 à 0,23 $ par passage sur les six journées, contre 2,14 $ au prix API équivalent pour Astra —
  environ dix fois moins ; de l'ordre de 0,6 $ par mois à une consolidation par jour.
- **U échoue, et c'est d'abord un défaut du banc** : à l'effort « medium », Terra raisonne davantage (environ 10 500
  tokens de raisonnement sur un passage, contre 174 en « low »), et le raisonnement compte dans la sortie maximale de
  8 000 tokens ; les réponses tronquées sont refusées. La correction notée au §9.3 (ne pas imposer de limite plus basse
  que la production) n'a pas été appliquée à cette variante : c'est une erreur de conduite du banc, pas un verdict sur
  l'effort « medium ». La partie de U qui n'a pas été tronquée (journées calmes et moyennes) est au niveau de T.

**Réserves, dites sans les atténuer :**
- **Mêmes journées** : le diagnostic qui a guidé la consigne venait de ces six jours ; le gain est donc à confirmer sur
  d'autres journées avant toute décision de production.
- **Juge et questions par Terra** : les questions, le lecteur et le juge sont ceux de tout le banc (Terra, effort
  « none »), les mêmes pour Astra ; un biais de préférence pour sa propre façon d'écrire ne peut pas être exclu. La
  couverture, elle, ne dépend d'aucun modèle — et c'est sur elle que l'écart est le plus net.
- **La consigne adaptée n'a rien de propre à Terra** : rien ne dit qu'elle n'améliorerait pas Astra aussi. La
  comparaison juste suivante est Astra avec la même consigne.

## 11 — Confirmation sur six nouvelles journées (pré-enregistré le 5/11, avant exécution)

**Question de décision** : remplacer la consolidation de production (Astra, consigne actuelle) par Terra avec la
consigne adaptée du §10 vaut-il le coup ? Le §10 a tourné sur des journées déjà vues ; on confirme ici sur **six
journées jamais utilisées** (C3, C4, M3, M4, I3, I4 : deux par profil, mêmes tiers de volume), la consigne
`consigne_terra.txt` **inchangée** (aucune retouche depuis le §10).

- Bras : **Astra, consigne de production** (la référence d'aujourd'hui) contre **Terra, consigne adaptée, effort
  « low »** (la proposition) ; deux passages chacun.
- Conditions corrigées selon le §9.3 pour les deux bras : sortie jusqu'à 32 000 tokens côté API (la production n'a
  pas de limite), et un nouvel essai est un vrai nouvel appel.
- Mêmes mesures, mêmes seuils du §6. **Décision** : si Terra est qualifiée ici aussi (Q1, Q2, Q4, puis Q3 après
  relecture), son passage en production est proposé à Francis ; sinon, on garde la production telle quelle.

### 11.1 Résultats (5 novembre 2026)

| Six journées jamais utilisées, deux passages | Bonnes réponses | Couverture | Faits retenus (moy.) | Lots perdus | Coût réel par passage |
|---|---|---|---|---|---|
| Astra, consigne de production (référence) | 65,3 % | 84,1 % | 93 | 0 | 1,91 $ (prix API équivalent) |
| **Terra, consigne adaptée, effort « low »** | **73,4 %** ✓ | **85,2 %** ✓ | **96** | **0** ✓ | **0,11 à 0,19 $** |

- **Terra est qualifiée sur Q1, Q2 et Q4 sur des journées qu'aucun réglage n'a vues** ; Q3 attend la relecture à
  l'aveugle. Face à Astra sur le premier passage : 9 questions gagnées, 3 perdues (McNemar p = 0,15) — pas de différence
  significative, l'écart va dans le sens de Terra. Elle est stable (95 puis 97 faits) et coûte environ dix fois moins.
- **Le gain du §10.1 était en partie optimiste**, comme annoncé : sur ces journées, Terra fait jeu égal avec Astra en
  faits et en couverture (+1 point), au lieu de +20 % de faits et +10 points. Le résultat qui compte pour une décision
  est celui-ci : **même qualité, environ dix fois moins cher.**
- **Dépense totale du banc 17 : 3,65 $.**
