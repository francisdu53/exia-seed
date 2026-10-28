# 08 — Le banc : FCM EXIA contre embeddings, au service du modèle

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Version :** 0.7 — vérification propre du 29/09 (§11) : parité ; **optimisation du 29/09 (§12) : +15 % d'utiles, en production (0.8.0, 29/09 22h18)**, vérification propre à faire sur les conversations postérieures
**Date :** 27 septembre 2026 · §11 le 29 septembre 2026
**Statut :** Conception, dans l'ordre validé par Francis le 27/09 (requête ✅ → **banc** → causal).
**Référence :** `SPEC-EXIA-SEED.md` §0 · `06-rappel.md` §8 (le premier banc, sa méthode de rejeu, son
juge, et sa mauvaise question) · `07-requete.md` (les outils testés ici)
**Origine :** Francis, 26-27/09 — *« FCM EXIA, c'est la solution pour éviter de passer du système de
Karpathy à l'embedding vectoriel »* ; *« auditable et certifiable tout en restant simple face à la
boîte noire qu'est un embedding »*.

---

## 1 — La question, cette fois la bonne

> **Quand l'index ne suffit plus, et que le modèle cherche dans son wiki, FCM EXIA lui rend-il des
> souvenirs au moins aussi utiles que des embeddings — sans en être un ?**

Karpathy borne son index à *« ~100 sources, quelques centaines de pages »* ; au-delà, *« you want
proper search »*. Ce banc se place **au-delà** : le modèle ne voit pas l'index, il **cherche**.

---

## 2 — Décisions

### D1 — Le modèle formule la requête, une seule fois, pour tous les concurrents
Pour chaque message rejoué, GPT-6 (effort bas) joue Nexa : *« si ta mémoire longue peut t'aider,
écris une requête courte ; sinon : aucune »*. **La même requête** est ensuite donnée à chaque moteur :
seul le moteur change. Le modèle décide aussi **quand** chercher — la voie active, telle qu'elle vivra.

### D2 — Quatre moteurs, à budget égal
Chacun rend au plus **3 sujets, 3 faits par sujet** (≤ 9 faits), groupés par sujet :

| Moteur | Ce qu'il fait |
|---|---|
| **FCM** | `Lecteur.chercher` (étape 7) : cascade, propagation associative, couverture par rareté |
| **FCM + pistes** | le même, plus les pistes de `memoire_lire` sur le premier sujet (même plafond de 9 faits) |
| **Embeddings** | **bge-m3** (le modèle qu'utilisait EXIA GHOST V2.7.x) : similarité cosinus requête ↔ faits, sujets classés par leur meilleur fait |
| **Plein texte** | BM25 (SQLite FTS5), sujets classés par leur meilleur fait |

**Écarté** : un seuil de similarité pour les embeddings. Un RAG vectoriel classique rend toujours ses
k meilleurs ; c'est son fonctionnement réel, et son défaut réel (il parle même quand rien n'est lié).
La FCM, elle, peut se taire : on le mesure (« parle pour rien »).

### D3 — Rejeu sans triche avec le temps
Même méthode qu'en 06 : chaque message contre l'instantané git de la dernière consolidation antérieure.

### D4 — Juge aveugle, sur l'union
GPT-6 (effort bas) voit le message, la réponse réelle de Nexa (contexte) et l'union des faits des
quatre moteurs, mélangés, sans étiquette → « lesquels auraient été utiles ? ». Même consigne qu'en 06.

### D5 — Ce qui est mesuré
Par moteur : souvenirs utiles trouvés, précision, messages où il parle pour rien, **ce qu'il est seul à
trouver**, latence ; et le coût d'infrastructure (RAM, temps de chargement, dépendances). Plus, pour
chaque requête, si la cascade de la FCM est entrée par un nom, un mot, le plein texte, ou rien.

### D6 — bge-m3 tourne sur l'hôte, pour ce banc seulement
Environnement d'EXIA GHOST (sentence-transformers 5.2.3), modèle en cache. L'instance de Nexa reste
sans embedder. Le banc est découpé en trois temps : requêtes (conteneur, modèle) → embeddings (hôte)
→ moteurs FCM et plein texte + juge (conteneur, modèle).

---

## 3 — Prévisions

| Grandeur | Prévision |
|---|---|
| Messages pour lesquels le modèle choisit de chercher | 40 à 60 % |
| FCM contre embeddings, souvenirs utiles | **au moins égal** (la thèse) ; les embeddings gagnent les synonymes, la FCM les associations |
| « Parle pour rien » | FCM nettement moins que les embeddings (qui rendent toujours leurs 9 faits) |
| FCM + pistes | ≥ FCM seule : l'association à la lecture ajoute des souvenirs que personne d'autre ne trouve |
| Plein texte | derrière les deux |
| Latence | FCM < 10 ms ; embeddings ≈ 10-50 ms par requête **après** 1-2 min de chargement et ≈ 2 Go de RAM |
| Coût GPT-6 du banc | ≈ 200 000 tokens |

Si les embeddings font nettement mieux, **ce sera écrit**, et on cherchera pourquoi avant de conclure.

---

## 4 — Limites connues d'avance

1. 17 à 20 pages : l'échelle est **simulée** par l'absence d'index, pas réelle.
2. Un utilisateur, quatre jours, un juge qui est un modèle.
3. La requête est formulée par GPT-6 dans un banc, pas par Nexa dans sa conversation (elle aura tout
   le contexte ; le banc ne lui donne que le message).

---

## 5 — Premier passage (27/09) — résultats

Rejeu de 117 messages ; **le modèle choisit de chercher pour 88 (75 %)** — au-dessus de la prévision
(40-60 %). 138 souvenirs utiles dans l'union des quatre moteurs. Coût du banc : **86 582 tokens**
(requêtes ≈ 25 500, juge ≈ 61 000). Deux défauts de script corrigés en route (faits pris sous forme de
dictionnaire pour « FCM + pistes » ; relance sans refaire les appels déjà enregistrés).

| Moteur | Utiles trouvés | Précision | Parle | Parle pour rien | Seul à trouver | Tokens | Coût |
|---|---|---|---|---|---|---|---|
| **Embeddings (bge-m3)** | **86 (62 %)** | 14 % | 88 | **41** | 28 | 239 | 235 ms/requête (p95 937) · 1,3 Go RAM · 14,7 s de chargement |
| **Plein texte (BM25)** | 81 (59 %) | **36 %** | 58 | 14 | 26 | 100 | < 1 ms |
| **FCM + pistes** | 75 (54 %) | 25 % | 51 | 14 | **17** | 132 | 12 ms (p95) |
| FCM seule | 58 (42 %) | 27 % | 51 | 18 | 8 | 93 | 12 ms |

Par porte d'entrée de la cascade FCM : **rien** (30 messages, souvent une mémoire encore minuscule) →
FCM 0 utile, embeddings 10 ; **plein texte seul** (26) → FCM 20, embeddings 40 ; **mot d'alias + plein
texte** (19) → FCM 28, embeddings 26 ; **nom + plein texte** (9) → 9 et 9.

### 5.1 Prévisions confrontées

| Prévision (§3) | Mesuré | |
|---|---|---|
| Le modèle cherche pour 40-60 % des messages | 75 % | ✗ (plus) |
| FCM ≥ embeddings | FCM 42 %, FCM + pistes 54 %, embeddings 62 % | ✗ |
| FCM parle moins pour rien que les embeddings | 14-18 contre 41 | ✓ |
| FCM + pistes ≥ FCM seule, et trouve ce que personne ne trouve | 54 % contre 42 % ; 17 souvenirs uniques | ✓ |
| Plein texte derrière les deux | 59 % : **devant** la FCM, presque au niveau des embeddings | ✗ |
| FCM < 10 ms ; embeddings 10-50 ms après 1-2 min et ≈ 2 Go | FCM 12 ms p95 ; embeddings 235 ms, 14,7 s, 1,3 Go | ≈ / ✗ (embeddings plus lents, plus légers) |

### 5.2 Diagnostic

1. **La FCM de l'étape 7 a été réglée pour le rappel à blanc**, où se taire est une qualité (seuils
   stricts, couverture au carré, seuil de nœud). Quand le modèle **demande** une recherche, se taire
   devient un défaut : dès que la cascade n'entre que par le plein texte, elle rend deux fois moins
   que les embeddings.
2. **À cette taille, le plein texte vaut presque les embeddings** (59 % contre 62 %), avec la
   meilleure précision — la remarque de Karpathy (« a naive search script ») se vérifie.
3. **La valeur propre de la FCM est l'association** : les pistes trouvent 17 souvenirs utiles
   qu'aucun moteur lexical ni vectoriel n'a proposés.

**Conséquence de conception (D7, 27/09)** : la FCM n'est pas la porte d'entrée ; elle vient **après**.
`memoire_chercher` v2 = entrée par le plein texte (BM25, sans seuil strict) → propagation et pistes
FCM, au même budget de 9 faits. C'est l'architecture qu'annonçait déjà la spec 05c (étages lexicaux,
puis propagation).

**Protocole contre l'auto-illusion (D8)** : réglage sur les messages du 23 au 25/09 ; **vérification
sur ceux du 26/09**, non regardés pendant le réglage. Les requêtes du modèle et les jugements déjà
faits sont réutilisés (mêmes requêtes pour tous) ; seuls les faits nouveaux sont jugés.

---

## 6 — Passage v2 (27/09) — `memoire_chercher` hybride : plein texte → FCM → pistes

**Biais à déclarer** : la v2 a été conçue à partir du diagnostic **global** du premier passage, 26/09
compris (chiffres agrégés, aucun message examiné un à un). La séparation réglage / vérification (D8)
protège les réglages **suivants**, pas celui-ci ; la vérification du 26/09 n'est donc pas vierge.

Mêmes requêtes, mêmes jugements ; seuls les faits nouveaux de la v2 ont été jugés. Coût total du
banc 8 : **94 129 tokens**. Tests de l'étape 7 : 27/27 inchangés.

| | Tout (88 messages, 139 utiles) | | | Réglage 23-25/09 (48) | Vérification 26/09 (40) |
|---|---|---|---|---|---|
| Moteur | Rappel | Précision | Pour rien | Rappel | Rappel |
| **Embeddings** | **62 %** | 14 % | 41 | 53 % | **79 %** |
| **Plein texte** | 58 % | **36 %** | 14 | **59 %** | 57 % |
| **FCM v2** | 56 % | 23 % | 17 | 55 % | 57 % |
| FCM + pistes (v1) | 54 % | 25 % | 14 | 52 % | 57 % |
| FCM (v1) | 42 % | 27 % | 18 | 34 % | 57 % |

### 6.1 Ce que ce banc établit — et ce qu'il n'établit pas

1. **La v2 corrige le défaut de la v1** (42 → 56 %) mais **ne dépasse pas le plein texte** : à cette taille
   (17 sujets, 21 liens), **le graphe n'apporte pas de gain mesurable à la recherche**.
2. **Les embeddings retrouvent le plus**, surtout le 26/09 (application personnelle : beaucoup d'écarts de
   vocabulaire entre la requête et les faits) — **au prix** de 3 fois plus de réponses pour rien, 2,4 fois
   plus de tokens, 235 ms par requête, 1,3 Go de RAM, et d'une similarité qu'on ne peut pas expliquer.
3. **La thèse d'EXIA SEED n'est ni démontrée ni réfutée** par ce banc : le terrain est trop petit pour
   que l'association fasse la différence, et le verdict est porté par des écarts de vocabulaire — un
   problème de **sens**, pas de **structure**.

### 6.2 Deux leviers fidèles à la thèse (sans embedding, auditables)

- **A — Le modèle reformule** : 2-3 variantes de requête, synonymes compris. « Le modèle apporte le
  sens », à la lettre ; quelques dizaines de tokens par recherche.
- **B — Le sens compilé à l'écriture** : à la consolidation, quelques mots-clés et synonymes par fait,
  dans les métadonnées. La philosophie de Karpathy (compiler une fois) contre celle de l'embedding
  (recalculer à chaque question) ; lisible et vérifiable.

**Décision gelée sur ce banc** : plus de réglage de formule sur ces 88 messages — le risque d'ajuster le
banc plutôt que le système est devenu réel.

## 7 — Décision attendue de Francis

Tester A et B sur ce banc (vérification du 26/09 comme juge de paix) avant le causal, ou passer au
causal et revenir au banc quand la mémoire aura grandi.

**Décision de Francis (27/09)** : *« Je suis plus dans la philosophie B, moins gourmande, et Karpathy n'est pas
un lapin de 6 semaines […] à moins que tu aies mieux à proposer »* → B+ proposé, accepté (*« si tu es sûr de
toi, va pour B+ »* — réponse : sûr du principe, pas du résultat ; le banc tranche).

---

## 8 — B+ : compiler le sens dans le graphe (thésaurus de concepts)

**Principe** (Francis, 27/09) : *« la comparaison des métadonnées avec le sens et le champ lexical. S'il y a
un match fort, cela crée une association qui permet de reconstruire le souvenir et surtout de l'enrichir
pour anticiper un sujet, voire de rebondir dessus pour l'approfondir. »*

| Principe | Mécanisme |
|---|---|
| métadonnées | chaque fait rattaché à 1-3 **concepts** d'un thésaurus partagé (`thesaurus.json`) |
| champ lexical | chaque concept porte ses synonymes **une seule fois** (`entretien` : mécanicien, garagiste, atelier…) |
| match fort | force **graduée** : la part du message (pondérée par la rareté des mots) qui tombe dans le champ ; activation = 0,8 × cette part |
| reconstruire | chaque concept est un **nœud FCM**, relié aux pages de ses faits ; la propagation part de lui |
| enrichir, rebondir | pistes **par concept partagé** : un fait d'une autre page qui partage le concept (le garagiste MOREL → le rendez-vous de Hugo, par `entretien`) |

**Précaution** : le rebond est réservé aux associations fortes ; la mémoire **propose**, Nexa **décide**
(les embeddings parlent pour rien 41 fois sur 88).

Construction du thésaurus (banc) : GPT-6, paquets de 50 faits, concepts existants redonnés à chaque paquet
→ **34 concepts** pour les 104 faits, 0 rattachement sans définition. Le fait est cherchable par son texte
**et** par le champ de ses concepts (FTS5 à deux colonnes, champ pondéré 0,4) ; un fait qui répond par le
sens plutôt que par ses mots compte à 0,8. Graphe : **17 → 51 nœuds, 21 → 118 arêtes**.

**Limite déclarée** : thésaurus construit une fois sur tous les faits — pour un message du 23/09, les
**synonymes** peuvent venir de faits plus tardifs (les faits eux-mêmes restent filtrés par instantané).

Résultat B+ (tout) : 91 utiles (61 % à ce moment du banc), dépasse les embeddings (86) avec 18 réponses pour
rien contre 41 ; **mais** vérification du 26/09 : 62 % contre 71 % aux embeddings.

## 9 — B++ : le budget loyal et le champ lexical vivant

**Diagnostic des 13 souvenirs utiles trouvés par les embeddings et pas par B+ (26/09)** — aucun ne vient
d'un mauvais concept :
- **6 : budget / classement.** Les mots étaient dans le fait ou dans le champ, mais B+ ne proposait que
  **4,9 faits** en moyenne contre **8,3** aux embeddings (qui remplissent toujours leurs 9 places) : « 2 sujets
  × 3 faits + pistes » était **un biais de mon banc**.
- **7 : champ trop pauvre.** « chewing-gums catégories têtes de gondole caisses » : le champ de `courses`,
  écrit une fois en 7 mots, n'avait ni « gondole » ni « caisse » — que les faits de Francis contenaient.

**Corrections (D9, D10)** :
- **D9 — Budget loyal** : `memoire_chercher` classe les **faits** eux-mêmes et remplit son budget
  (`faits_max`, 12 pour l'outil, 9 au banc comme les embeddings), en gardant 2 places pour les pistes.
- **D10 — Champ lexical vivant** : chaque concept **apprend le vocabulaire de ses propres faits** — les 4
  mots les plus rares de chaque fait rattaché, 40 au plus par concept. Calculé avec le graphe, sans
  modèle, justifiable (« `gondole` est dans le champ de `courses` parce que tel fait le contient »). C'est
  « ce qui est vécu ensemble se lie », appliqué aux mots ; un embedding fait de même en boîte noire sur
  des milliards de textes étrangers, nous sur la vie de l'utilisateur, en clair.

**⚠️ Le 26/09 n'est plus une vérification** : ces corrections ont été conçues en regardant ses ratés.

| Tout (88 messages, 174 utiles) | Utiles | Rappel | Précision | Pour rien | Seul à trouver | Tokens |
|---|---|---|---|---|---|---|
| **FCM B++** | **114** | **66 %** | **23 %** | **16** | **38** | 222 |
| FCM B+ | 91 | 52 % | 20 % | 18 | 23 | 203 |
| FCM v2 | 78 | 45 % | 23 % | 17 | 12 | 151 |
| Embeddings (bge-m3) | 86 | 49 % | 14 % | 41 | 19 | 239 |
| Plein texte | 81 | 47 % | 36 % | 14 | 10 | 100 |

Réglage 23-25/09 : B++ 68 utiles, embeddings 49. 26/09 (non vierge) : B++ 46, embeddings 37.
Coût total du banc 8 : **140 668 tokens**.

Note de lecture : à chaque variante, les faits nouveaux sont jugés et rejoignent l'ensemble des utiles
(139 → 174) ; tous les moteurs sont mesurés contre le **même** ensemble final, et **chaque fait proposé par
chaque moteur a été jugé** — les rappels relatifs d'un tableau à l'autre ne sont pas comparables entre eux,
les nombres d'utiles le sont.

### 9.1 Verdict provisoire, et ce qui le rendra définitif

**Sur ce banc, à budget égal, FCM EXIA (B++) trouve 33 % de souvenirs utiles de plus que les embeddings**,
avec 2,5 fois moins de réponses pour rien, deux fois plus de souvenirs que personne d'autre ne trouve,
moins de tokens, sans modèle d'embedding (1,3 Go, 235 ms par requête), et en expliquant chaque résultat.

**Vérification propre prévue le 28/09** : les conversations du **27/09**, consolidées dans la nuit, jamais
vues pendant la conception ; mêmes moteurs, **sans aucun réglage**. Si B++ tient, la thèse de Francis est
vérifiée sur ce banc ; sinon, ce sera écrit.

---

## 10 — Mise en production de B++ — 27/09/2026, 15h10

**Décision de Francis** : mise en production — installé avant la vérification du
28/09, qui n'en est pas faussée : le banc tourne sur des copies, avec le code figé.

### 10.1 Ce qui a changé
| Fichier | Changement |
|---|---|
| `consolidation.py` | **règle 12** du prompt : chaque fragment reçoit 1 à 3 `concepts` ; les concepts existants sont donnés au modèle (« CONCEPTS EXISTANTS », avec le début de leur champ) ; un concept nouveau n'entre que défini (`concepts_nouveaux`, fr ≤ 12, en ≤ 6) **et** effectivement utilisé ; un concept non défini est ignoré ; métadonnée `concepts:` sur le fait |
| `graphe.py` | `charger_thesaurus`, `enregistrer_thesaurus` (écriture atomique, un seul écrivain) ; nœuds `concept:*` avec `champ` et `champ_appris` (D10) ; arêtes page ↔ concept (preuve `concept`, 0,5) |
| `rappel.py` | étage **champ lexical** (force graduée) ; FTS5 à deux colonnes (texte, champ ×0,4) ; `racines_sem` |
| `requete.py` | `memoire_chercher` v2 + B++ : porte BM25, sens × 0,8, classement **par fait**, `faits_max` (12 par défaut), 2 places réservées aux pistes ; pistes **par concept partagé** |
| `outils/concepts.py` | rattrapage des faits existants, depuis une graine ; idempotent ; ne touche jamais le texte d'un fait |

### 10.2 Défaut trouvé au test, corrigé avant la production
L'outil de rattrapage enregistrait un thésaurus limité aux concepts **de la graine** : ceux déjà créés par la
consolidation disparaissaient (vérifié : 1 concept restant sur 5). En production, cela aurait vidé des champs
lexicaux. Correction : tout concept utilisé par **un fait de la mémoire** est gardé, l'existant prime ; test ajouté.

### 10.3 Déploiement
1. 0.6.0 sauvegardée (`staging/exia_seed.v0.6-deploye-20260927`) ; 0.7.0 installée. Tests : **257/257**.
2. Rattrapage : graine = thésaurus du banc 8 (celui validé par les mesures) ; **137 faits** sans concept,
   104 connus de la graine, 33 rattachés par le modèle ; **36 concepts** ; commit `9954cbb`.
3. Graphe : **53 nœuds, 125 arêtes**, 20,8 ms ; commit `6cbbe57`.
4. Passerelle relancée en 11 s (Nexa au repos depuis 5 min ; accord de Francis).
5. **Première consolidation avec concepts** (celle de l'extinction, 15h10:41) : 17 faits, **tous rattachés**,
   vocabulaire réutilisé ; graphe recalculé (53 nœuds, 128 arêtes) ; commit `2b17ea8`. Le processus à part a
   survécu au redémarrage et a fini 1 min 20 plus tard.

### 10.4 Vérifié sur la mémoire réelle
« mécanicien » → le garagiste MOREL **et** Hugo chez Sophie à l'atelier (le mot « mécanicien » n'est dans aucun
des deux faits : c'est le champ de `entretien`) ; « chewing-gum », « Autoplus Valmont facture » : les bons
faits ; « météo Brest » : silence.

### 10.5 Défaut observé, corrigé APRÈS la vérification du 28/09
Quand le premier sujet est la fiche de l'utilisateur (liée à tout), les pistes par concept suivent **tous**
ses concepts (ex. « mécanicien » → des faits de loisirs), au lieu du concept **des faits trouvés** (`entretien`).
Correction simple — mais la vérification du 28/09 a été annoncée « mêmes moteurs, sans aucun réglage » :
le moteur reste figé jusque-là.

---

## 11 — Vérification propre (29/09) : l'avance ne tient pas, la parité si

**Protocole, tel qu'annoncé au §9.1** : conversations du **27/09 00h au 29/09 20h** (39 messages de Francis),
jamais regardées pendant la conception ; moteur **figé** (le plugin 0.7.0 déployé, recopié tel quel ; recherche
identique octet par octet à celle de samedi) ; mêmes requêtes pour tous (même consigne qu'au banc 8), même
budget (9 faits), même juge aveugle. Script : `banc/banc9_verif.py` (réutilise ceux du banc 8, rien de
réécrit). Instantanés : ceux de la production, **avec leur thésaurus** ; pour les 18 messages antérieurs au
27/09 15h10 (mémoire encore sans concepts), les faits reçoivent les concepts que leur a donnés le rattrapage
(`9954cbb`) — une métadonnée sur le fait, aucun fait futur ; comptés à part.

Le modèle cherche pour **24 messages sur 39** ; 53 souvenirs utiles dans l'union. Coût : 33 921 tokens.

| 24 messages, 53 utiles | Utiles | Rappel | Précision | Pour rien | Seul à trouver | Tokens |
|---|---|---|---|---|---|---|
| FCM B++ | 29 | 55 % | 14 % | 9 | 7 | 322 |
| **Embeddings (bge-m3)** | **31** | **58 %** | 15 % | 7 | **11** | 296 |
| Plein texte | 30 | 57 % | **19 %** | 9 | 8 | 230 |
| *dont natifs (13 messages, 24 utiles)* | B++ **14** · emb. 12 · plein texte **14** | | | | | |
| *dont rattrapés (11 messages, 29 utiles)* | B++ 15 · emb. **19** · plein texte 16 | | | | | |

Embeddings : 36 s de chargement, 1,3 Go, 256 ms par requête (p95 437 ms).

### 11.1 Ce que cela dit — sans l'arranger

1. **L'avance de +33 % mesurée samedi ne se reproduit pas.** Sur des données neuves, B++, embeddings et
   plein texte sont à égalité ; un ou deux souvenirs d'écart sur 53 ne sont pas significatifs. C'est ce que la
   séparation réglage / vérification (D8) devait révéler : les corrections B+ et B++ avaient été conçues en
   regardant les ratés du 23 au 26/09, et une partie de leur gain était de l'ajustement à ces jours-là.
2. **Les deux autres avantages disparaissent aussi** : « parle pour rien » 9 contre 7 (samedi 16 contre 41),
   précision 14 % contre 15 % (samedi 23 % contre 14 %).
3. **Ce qui tient** : la parité, sans modèle d'embedding (0 Go contre 1,3 Go, quelques millisecondes contre
   256), et un résultat explicable. La thèse de Francis — *« éviter de passer du système de Karpathy à
   l'embedding vectoriel »* — tient **à parité** sur ce banc ; la supériorité, non.
4. **Les moteurs se complètent** : chacun trouve ≈ 55 % des utiles, deux moteurs réunis 42 à 46 sur 53.
5. **Échantillon petit** (24 requêtes). Il ne tranche pas entre les trois ; il suffit à invalider un écart de
   +33 %.

### 11.2 Deux ratés de B++, observés (diagnostic, aucun réglage)

- **Un mot rare direct passe derrière le sens.** Une requête qui mêle deux besoins : le plein texte
  trouve le fait de la fiche de l'utilisateur qui porte le mot rare (2 utiles sur 3 proposés) ; B++ remplit ses 9 places avec
  des faits de facturation atteints par `grêle` et `chiffre d'affaires` (0 utile). Même forme pour « encadré
  titre couleur » (l'encadré client des factures au lieu de l'encadré de l'application personnelle).
- **Les pistes ramènent du hors-sujet** : factures en fin de liste pour une requête sur un
  sujet personnel — la forme déjà notée au §10.5 (pistes depuis la fiche de l'utilisateur).

Hypothèse à tester, pas une conclusion : un fait qui porte un **mot rare de la requête** devrait passer avant
un fait atteint seulement par le champ d'un concept. Toute correction devra être vérifiée sur des
conversations **postérieures** à la correction — celles du 27 au 29/09 ne sont plus vierges.

---

## 12 — Optimisation du 29/09 : trois défauts, trois corrections, une fausse bonne idée

**Demande de Francis** (29/09) : *« Voyons comment tu optimiserais EXIA SEED pour que les ratés ne le soient
plus, et que tu puisses rendre EXIA SEED plus performante avec les données supplémentaires. »*

### 12.1 Méthode — et sa limite, dite d'avance

Banc 10 (`banc/banc10_optim.py`) : **les 112 recherches déjà jugées** (banc 8 : 88, du 23 au 26/09 ; banc 9 : 24,
du 27 au 29/09), mêmes requêtes, budget 9, même juge aveugle ; seuls les faits jamais jugés passent au juge et
rejoignent l'ensemble des utiles (246 au final). Chaque variante recalcule le graphe de chaque instantané avec son
propre code. Coût : **56 989 tokens**.

**Aucune de ces recherches n'est une vérification** : toutes ont été regardées. Protections prises : (1) une
correction doit être un **principe**, pas un ajustement à une requête ; (2) elle doit tenir **sur chacune des trois
tranches** (23-25, 26, 27-29/09) ; (3) une idée qui perd est retirée, même si elle était élégante ; (4) la
vérification propre se fera sur des conversations **postérieures** à la mise en production.

### 12.2 Diagnostic (instrumenté sur les ratés du §11.2)

1. **L'apostrophe typographique collait les mots.** `graphe._norm` passait le texte en ASCII **avant** de changer la
   ponctuation en espaces : « ’ » (écrite par le modèle — 184 fois dans les pages, contre 3 apostrophes droites)
   disparaissait, « l’encadré » devenait `lencadre`, « l’application » `lapplication`, « d’Amandine » `damandine`.
   Invisibles pour la couverture, les alias et les preuves du graphe. Le contrôle de citation et les noms de
   fichiers ont leur propre normalisation : non touchés.
2. **Le champ d'un concept donnait la même note à tous ses faits.** Couverture = max(texte, 0,8 × sens) : les
   35 faits de `facturation` recevaient tous le même crédit pour « chiffre », « affaires », « grêle » — neuf places
   prises par des ex æquo, devant un fait qui portait un mot de la requête dans son **texte**. (« encadré argent
   comptes » : 0 utile, les faits de l'encadré client des factures.)
3. **Les pistes partaient de toute la page du premier sujet** (§10.5) : depuis la fiche de l'utilisateur, tous
   ses concepts.

### 12.3 Corrections

| # | Correction | Principe |
|---|---|---|
| D11 | `_norm` : seuls les accents sont retirés, tout autre signe devient un espace ; ligatures œ, æ, ß | un signe de ponctuation sépare des mots, quel que soit son code |
| D12 | **Spécificité d'un concept** : spec(c) = log(1 + N/n_c) / log(1 + N). Crédit d'un mot de la requête : **1** s'il est dans le texte du fait ; sinon **0,8 × spec** du concept qui le porte ; additif | l'IDF appliqué aux concepts : un concept qui couvre tout ne dit rien de chacun (théorie de l'information) |
| D13 | Pistes depuis les **concepts des faits trouvés** (le plus partagé, puis le plus spécifique) ; pour chacun, le fait d'une autre page le mieux noté pour la requête ; puis les faits qui créent les liens du premier sujet qui n'est pas l'utilisateur | l'association part de ce qu'on a trouvé, pas de tout ce qu'on sait |

### 12.4 Résultats — chaque étape mesurée

| 112 recherches, 246 utiles | 23-25/09 (48) | 26/09 (40) | 27-29/09 (24) | **Tout** | Précision | Pour rien |
|---|---|---|---|---|---|---|
| 0.7.0 (production) | 68 | 46 | 29 | 143 | 20 % | 25 |
| + apostrophe (D11) | 68 | 45 | 33 | 146 | 21 % | 23 |
| + spécificité (D12) | 78 | 46 | 41 | **165** | 22 % | 21 |
| + pistes des faits trouvés (D13) = **retenu** | 79 | 45 | 40 | **164** | 22 % | 22 |
| *rendement décroissant (essayé, retiré)* | *80* | *41* | *36* | *157* | *21 %* | *19* |
| Embeddings (bge-m3) | 49 | 37 | 31 | 117 | 14 % | 48 |
| Plein texte | 54 | 27 | 30 | 111 | 29 % | 23 |

- **+15 % d'utiles** (143 → 164). Aucune tranche ne recule de plus d'un souvenir ; sur les jours neufs (27-29/09),
  **29 → 40**, 9 recherches améliorées, 2 dégradées.
- **D13 est neutre en nombre** (164 contre 165) : il est gardé parce qu'il corrige un défaut visible (« mécanicien »
  menait aux loisirs), pas pour un gain mesuré.
- **La fausse bonne idée** : une sélection à rendement décroissant (chaque fait retenu « use » les mots qu'il couvre,
  pour couvrir toute la requête). Elle perd sur le 26/09 et le 27-29/09 — le juge préfère la profondeur à la variété.
  Retirée du code.
- **Un raté non corrigé, volontairement** : la requête aux deux besoins (§11.2). Contrairement à mon hypothèse,
  le mot visé n'est **pas** le plus rare de la requête ; le message mêlait deux besoins
  sans rapport. Le forcer serait un réglage sur mesure.
- Latence inchangée : **1,6 ms** (p50, mémoire réelle de 185 faits). Graphe réel : 1 arête de plus
  (application personnelle ↔ application de courses, liées par « du même type que l’application de liste de courses »,
  que l'apostrophe cachait).

⚠️ **Lecture honnête** : ces chiffres sont mesurés sur des recherches regardées pendant l'optimisation. L'écart avec
les embeddings (164 contre 117) est donc un **plafond**, pas une preuve — le §11 a montré qu'un +33 % de ce type pouvait
fondre à la vérification. La vérification propre se fera sur les conversations **postérieures** à la mise en service,
comme au §11.

### 12.5 Code et tests
- `graphe.py` : `_norm` (D11). `rappel.py` : `Memoire.specificite`, `fait["sem_spec"]` (D12). `requete.py` : crédit
  additif, classement, `_pistes_trouves` (D13) ; `_pistes` ne garde que la provenance des arêtes.
- `tests/test_etape_8b_optim.py` : **12/12** (et échoue sur 0.7.0, comme attendu) ; toutes suites : **276/276**.
- Staging sauvegardé avant : `staging/exia_seed.v0.7-R3-avant-optim-20260929`. Le staging contient aussi R3 (citation).

### 12.6 Mise en production — 0.8.0, 29/09/2026, 22h18

**Décision de Francis** : *« Tu implémentes et tu mets en service avec les bonnes modifications. »*
1. Nexa au repos depuis 21h35 ; aucune consolidation en cours.
2. 0.7.0 sauvegardée (`staging/exia_seed.v0.7-deploye-20260929`) ; staging copié (optimisation §12 **+ R3**,
   contrôle de citation) ; copie vérifiée identique ; `plugin.yaml` → 0.8.0.
3. Graphe recalculé sur la mémoire réelle : **59 nœuds, 152 arêtes** (la seule arête nouvelle, prévue au banc) ;
   commit `50a927c`.
4. Passerelle relancée (SIGTERM, s6) en 4 s ; Telegram reconnecté ; 28 avertissements de démarrage, identiques
   en nombre et en nature à ceux du 27/09 (outils optionnels non configurés) — aucune erreur.
5. Essai sur une **copie** de la mémoire réelle (pour ne pas écrire dans le journal des requêtes de Nexa) :
   « encadré titre couleur » rend l'encadré de l'application personnelle (0 utile en 0.7.0) ; « mécanicien » rend
   les rendez-vous d'atelier, pistes vers les autres rendez-vous (plus de loisirs) ; « météo Brest » : silence.

**Vérification propre à venir** : les conversations à partir du 30/09, rejouées avec ce moteur figé, contre les
embeddings et le plein texte, sans aucun réglage (même protocole qu'au §11, script `banc9_verif.py`).


## 13 — 18/10/2026 : la 0.8.2 candidate rejouée sur la mémoire de Nexa (banc 10)

**Demande de Francis** : *« rejoue le banc des requêtes sur la mémoire de Nexa »*, avant tout déploiement des deux
changements de `memoire_chercher` trouvés sur LoCoMo (docs/09 §14.7-14.8). Plugin de production 0.8.1 recopié
(`banc-10/p_081`) ; candidat = la même copie + les deux changements portés (`p_082`, ≈ 15 lignes de `requete.py`).
Mêmes 112 recherches, même budget (9), même juge aveugle. Coût : **3 224 tokens** de juge (seuls les faits jamais jugés).

| 112 recherches, 246 utiles | 23-25/09 | 26/09 | 27-29/09 | **Tout** | Pour rien |
|---|---|---|---|---|---|
| 0.8.1 (production) | 79 | 45 | 40 | **164** | 22 |
| témoin : candidat avec l'ancienne note | 79 | 45 | 40 | 164 | 22 |
| candidat, lecture du speaker seule | 79 | 45 | 40 | 164 | 22 |
| **candidat complet (poids du sujet 0,25)** | 75 | 46 | 38 | **159** | 25 |
| poids du sujet 0,5 | 77 | 46 | 39 | 162 | 23 |
| poids « éventail » (budget / faits du sujet) | 79 | 45 | 38 | 162 | 22 |

- **Le portage est propre** : avec l'ancienne note, le candidat redonne la production au fait près.
- **La lecture du speaker n'a aucun effet chez Nexa**, comme prévu : presque tout est dit par Francis (implicite).
- **La note anti-saturation coûte 5 utiles** : 6 recherches dégradées, 1 améliorée, 90 identiques (signe : p ≈ 0,12).
  Ce qu'elle perd, ce sont des souvenirs **associatifs** : un fait du sujet activé qui ne partage presque aucun mot
  avec la requête (« devis facture débosselage remise » → « le modèle de facture doit tenir sur une feuille A4 »).
  L'ancienne note leur donnait la force du sujet ; la nouvelle ne leur en donne que le quart.
- **La tension** : sur LoCoMo (grandes pages, beaucoup de sujets voisins), la précision gagne ; sur la mémoire de
  Nexa du 23-29/09 (185 faits, petites pages), l'association gagne. L'« éventail » est un compromis : −2 ici, mais
  la moitié seulement du gain sur LoCoMo (réponse présente, F : 207 contre 235 sur conv-41/42/48).

**Limite du banc 10** : il rejoue la mémoire du 23-29/09. La mémoire d'aujourd'hui a **507 faits**, et **9 pages
dépassent le budget de 9 faits** (débosselage 54, application personnelle 52, courses 29, Autoplus Valmont 26) — le
terrain où la saturation apparaît. La vérification propre (docs/08 §12.1 : conversations postérieures à la mise en
production) reste à faire : 386 messages de Francis du 30/09 au 18/10 (méthode du banc 9).
