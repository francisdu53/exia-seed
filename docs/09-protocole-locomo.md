# 09 — Protocole LoCoMo : la thèse d'EXIA SEED à l'échelle

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Version :** 0.6 — protocole **pré-enregistré** ; banc construit (§11) ; pilote fait le 01/10 (§12) ; **protocole de juge aligné sur la référence (Mem0) après étude des concurrents (§13)** ; **pilote rejoué en 0.9.1 et banc complet le 18/10 (§14) : H1 échoue, H4 tient**, accord de Francis ; **0.6 (18/10 au soir) : diagnostic, saturation corrigée, `speaker` lu — égalité avec les embeddings à l'échelle fusionnée sur 2 conversations neuves, confirmé sur les 8 au seuil de H1, de justesse et avec une réserve de méthode (§14.5-14.10)**
**Date :** 1er octobre 2026
**Statut :** Banc mené (§12-14). H1 tient de justesse en 0.9.2, H2 échoue, H4 tient (§14.10). Prochain levier : l'écart sur conv-43/49, puis la consolidation.
**Référence :** `SPEC-EXIA-SEED.md` (§0, décision du 29/09) · `08-banc-fcm-embeddings.md` (§11 : parité à 185 faits ;
§12 : 0.8.0) · spec EXIA GHOST `05c_MODULE_MEMOIRE_WIKI.md` §1.2 (le mur de Karpathy) et §2 (langues déclarées)
**Origine :** Francis, 01/10 — *« voyons comment faire le protocole LoCoMo afin de valider ma thèse pour EXIA SEED »*.

---

## 1 — La thèse, et ce que LoCoMo peut en dire

**Thèse** : *un wiki à la Karpathy (le modèle lit son index et ses pages) bute sur un mur quand il grandit, et
l'industrie retombe alors sur les embeddings. FCM EXIA franchit ce mur **sans embeddings** : aussi bien qu'eux,
sans modèle d'embedding, en millisecondes, en expliquant chaque résultat.*

**Ce que nos bancs ont déjà montré** (docs/08 §11) : à 185 faits, FCM, embeddings et plein texte sont **à
égalité**. On n'a donc encore rien appris sur la **croissance** — c'est le cœur de la thèse.

**LoCoMo** (Maharana et al., ACL 2024, `snap-research/locomo`) : 10 longues conversations entre deux personnes
(≈ 600 tours, jusqu'à 32 sessions datées, chacune ≈ 16-26 k tokens), **1 986 questions** : multi-sauts (282),
temporelles (321), connaissance du monde (96), simples (841), pièges sans réponse (446, catégorie 5). C'est le
banc public de Mem0, Zep, MemMachine…

**Le piège à éviter** : une conversation LoCoMo donne ≈ 150-300 faits — **la taille de la mémoire de Nexa
aujourd'hui**, là où tout le monde est à égalité. LoCoMo tel quel ne teste donc pas la croissance. D'où l'échelle
du §4 : on **fusionne** les 10 conversations dans une seule mémoire (≈ 10×), et on mesure qui se dégrade.

## 2 — Ce qui varie, ce qui est fixe

**Une seule variable : le moteur qui retrouve.** Tout le reste est identique pour tous :
- **les mêmes pages** : une seule consolidation par conversation, partagée par tous les moteurs ;
- **le même modèle** pour répondre et pour juger ; **la même consigne** de réponse ; **le même budget** de
  contexte (12 faits ou ≈ 600 tokens, le plus petit des deux) ;
- **la même requête** : la question elle-même (pas de reformulation — aucun appel de modèle en plus, aucune
  variance ajoutée).

| Moteur | Ce qu'il donne au modèle | Rôle dans la démonstration |
|---|---|---|
| **A — FCM EXIA** (0.8.0 figée) | `memoire_chercher` : faits classés + pistes | **la thèse** |
| **B — Embeddings** (bge-m3, cosinus) | les 12 faits les plus proches | ce que l'industrie fait au mur |
| **C — Plein texte** (BM25) | les 12 meilleurs faits BM25 | le « script de recherche naïf » de Karpathy |
| **D — Karpathy pur** | le modèle lit INDEX.md, choisit 1-3 pages, les lit, répond | **le mur** : il doit se dégrader à l'échelle |
| **E — Tout le contexte** | la conversation entière | l'étalon (impossible à l'échelle fusionnée : 200 k+ tokens) |

## 3 — Les adaptations, déclarées

EXIA SEED a été construit pour Nexa : français, un utilisateur et un assistant. LoCoMo est en anglais, entre deux
personnes. **Résolu par les masques de langue (docs/10, plugin 0.9.0)** — un seul code, une copie configurée :
1. **`langue: en`** — tout passe par le masque anglais : faits écrits en anglais, mots vides, dates relatives
   (« yesterday », « last Saturday »), nombres, « 38,512 », intitulés, index. **Le masque anglais est générique
   (liste NLTK) : les ajouts « propres au banc » du masque d'EXIA GHOST sont exclus**, pour ne pas régler EXIA SEED
   sur l'examen (docs/10 D3). Aucune traduction nulle part : conversation, faits, questions, réponses et juge en anglais.
2. **`interlocuteurs: [a, b]`, `nom_agent: ""`** — pas d'agent ; la règle 4 devient « tous sont des personnes » ; les
   deux noms sont implicites dans ce qu'ils disent (docs/10 D9).
3. **Dates de session** — chaque session LoCoMo a sa date (« 1:56 pm on 8 May, 2023 ») : elle devient l'en-tête du
   fichier brut, comme un jour de conversation de Nexa ; `dit_le` et `event_time` (R2) s'y rattachent.

**Non-régression prouvée** : le masque français reproduit la 0.8.0 au caractère près (docs/10 §5 ; dans la version publique, hors noms d'exemple des consignes, fictifs) — le banc ne teste
pas une autre version que celle de Nexa, seulement une autre langue.

## 4 — L'échelle

| Niveau | Mémoire | Questions notées | Taille attendue |
|---|---|---|---|
| **S — séparée** | une mémoire par conversation | toutes | ≈ 150-300 faits (= Nexa aujourd'hui) |
| **F — fusionnée** | les 10 conversations dans **une** mémoire | toutes | ≈ 2 000-3 000 faits, ≈ 10× |

En fusionné, chaque question doit retrouver la bonne personne parmi 20 : les 9 autres conversations sont des
**distracteurs**. Les pages des 10 conversations sont réunies telles quelles (même code, aucune étiquette de
conversation) ; un nom de nœud en collision est suffixé, et c'est compté.

## 5 — Hypothèses et critères, fixés avant la mesure

Mesure principale : **score J** (juge LoCoMo standard, celui du protocole de Mem0, pour rester
comparable aux chiffres publiés), catégories 1-4 ; la catégorie 5 (savoir dire « je ne sais pas ») à part.

| # | Hypothèse | Critère de réussite |
|---|---|---|
| **H1** | **À l'échelle fusionnée, A vaut B** | J(A, F) ≥ J(B, F) − 2 points |
| H2 | A se dégrade moins que B en passant de S à F | perte(A) ≤ perte(B) |
| H3 | Karpathy pur (D) bute sur le mur | perte(D) > perte(A) |
| H4 | A sans modèle d'embedding, en millisecondes | p95(A) < 20 ms en F ; B : modèle 1,3 Go, ≈ 250 ms |
| H5 | *Honnêteté* : en S, tout le contexte (E) bat tout le monde (comme dans le papier Mem0) | — (on le publie quel qu'il soit) |

**La thèse est validée sur LoCoMo si H1 tient** (H2-H4 la renforcent). **Si H1 échoue, c'est écrit et publié
tel quel**, avec le diagnostic.

**Contre l'auto-illusion** (même règle qu'au banc 8, D8) : le **pilote** se fait sur 2 conversations ; tout ce qui
est corrigé après le pilote est déclaré, et ces 2 conversations sont alors rapportées **à part**. Les chiffres
annoncés portent sur les **8 autres**, jamais regardées. **Aucun réglage d'EXIA SEED sur LoCoMo** pendant la mesure.

## 6 — Le modèle

**GPT-4o-mini pour toute la chaîne** (consolider, répondre, juger) :
- **comparable** : c'est le modèle des publications Mem0 / Zep et de notre juge d'avril ;
- **crédible** : avec un petit modèle, c'est la mémoire qui fait le travail — avec GPT-6, toute mémoire paraît bonne ;
- **réserve** : la consolidation d'EXIA SEED est exigeante (citations, dates, concepts). Si le pilote montre trop
  de rejets au contrôle de citation, la consolidation seule passe sur GPT-4.1-mini (comme EXIA GHOST V2.7.2), et
  c'est déclaré.
- Disponibilité et prix **vérifiés le jour du lancement** ; si GPT-4o-mini n'existe plus, le plus proche, déclaré.

**Pas GPT-6 Astra par l'abonnement de Nexa** : quota de Nexa, non comparable, raisonnement coûteux.

## 7 — Coût estimé (prix connus, à revérifier)

Bases : consolidation réelle de Nexa (2-7 k tokens en entrée, 0,2-1 k en sortie) ; ≈ 1,2 k tokens par réponse
avec 12 faits ; ≈ 0,4 k par jugement.

| Volet | Tokens (entrée) | Coût GPT-4o-mini |
|---|---|---|
| Consolidation (272 sessions) | ≈ 1,5 M | ≈ 0,40 $ |
| A, B, C × (S + F) — 6 × 1 986 réponses + jugements | ≈ 19 M | ≈ 3,50 $ |
| D Karpathy (index + pages ; l'index grossit en F) | ≈ 50 M | ≈ 7,50 $ |
| E tout le contexte (S seulement ; le cache d'OpenAI réduit le préfixe répété) | ≈ 40 M | ≈ 3-6 $ |
| **Total** | **≈ 110 M** | **≈ 15-18 $** |
| **Cœur seul (A, B, C)** | **≈ 21 M** | **≈ 4-5 $** |
| **Pilote (2 conversations, S, tous moteurs)** | | **≈ 2 $** |

**Garde-fou** : Francis crée la clé API avec un **plafond de dépense** fixé dans le tableau de bord d'OpenAI (25 $
proposés) — le banc ne peut pas dépasser, quoi qu'il arrive. Clé saisie par Francis lui-même (fichier 600), jamais
affichée.

## 8 — Mise en œuvre

1. **Données** : `locomo10.json` (dépôt public). Licence à vérifier avant publication (CC BY-NC probable) : on
   publie les **résultats et le code**, pas le jeu de données — on y renvoie.
2. **Code** (dans `exia-seed/banc/locomo/`, rien dans la production de Nexa) :
   chargeur LoCoMo → fichiers bruts datés ; appel de modèle compatible OpenAI (clé, compte des tokens) ;
   paramètres `langue` et `interlocuteurs` dans le plugin (défauts inchangés, tests) ; les 5 moteurs ; consigne de
   réponse et juge **standards de LoCoMo** ; rapport par catégorie, par échelle, tokens, latences.
3. **Lieu** : conteneur jetable (image de Nexa, avec réseau pour l'API), données dans un dossier de banc ; bge-m3
   sur l'hôte comme au banc 8. **La mémoire de Nexa n'est jamais touchée.**
4. **Ordre** : tests → pilote (2 conversations) → bilan au pilote, décision de Francis → banc complet → doc 09 §
   résultats → publication.

## 9 — Ce que ce banc ne dira pas

- **Le français** : LoCoMo est anglais. Nos bancs 8-10 restent la preuve en français, sur données réelles.
- **La très grande échelle** : 10× (≈ 3 000 faits) n'est pas 100×. Une extension possible ensuite : ajouter des
  distracteurs (conversations synthétiques) pour aller à 30 000 faits — à décider après.
- **Le mode agent** : la question sert de requête, en un coup. Nexa, elle, reformule et peut chercher plusieurs
  fois — ce qui ne peut que l'aider ; c'est volontairement exclu pour garder une seule variable.

## 10 — Références publiées (à revérifier avant comparaison)

Papier Mem0 (avril 2025, GPT-4o-mini, juge J) : Mem0 ≈ 67 %, Mem0 graphe ≈ 68 %, **tout le contexte ≈ 73 %**, Zep ≈ 66 %
(Zep revendique davantage). Les scores d'EXIA GHOST, autre système de mémoire du même auteur, ne sont pas repris ici
(décision de Francis, 28/10/2026 : deux systèmes, deux dépôts).

---

## 11 — Le banc construit (01/10/2026) — éprouvé à blanc, rien dépensé

**Code** : `banc/locomo/` — une étape par fichier (`preparer`, `fusionner`, `recuperer`, `embeddings` sur l'hôte,
`repondre`, `juger`, `bilan`), `commun.py` (réglages fixés), `modele.py` (l'appel), `lancer.sh` (chaque étape dans
un conteneur JETABLE de l'image de Nexa ; données dans `$HOME/banc-locomo`, hors du volume de Nexa ; plugin 0.9.0 en
lecture seule). **Jamais dans le conteneur de Nexa.**

### 11.1 Choix de mise en œuvre, déclarés avant la mesure
1. **Une session = un lot**, consolidé aussitôt, dans l'ordre (comme une journée de Nexa). Toutes les lignes d'une
   session portent l'heure de la session (LoCoMo ne date pas les tours).
2. **Photos partagées** : le texte du tour + « [shares a photo: <légende>] » (1 226 tours concernés).
3. **Contexte de A, B, C** : 12 faits au plus, une ligne par fait, précédée de la date où il a été dit
   (« - [8 May 2023] … ») — **identique pour les trois**.
4. **Consigne de réponse et juge : ceux d'EXIA GHOST, mot pour mot** (`eval_locomo.py`), à une adaptation près : les
   deux listes « mémoires de A / mémoires de B » deviennent une seule liste. Juge permissif (standard). Catégorie 5 :
   réponse attendue « Not mentioned ».
5. **C = BM25 pur sur le texte des faits** (colonne `t`), sans le champ lexical des concepts — qui est un apport
   d'EXIA SEED (aux bancs 8-10, le « plein texte » le lisait aussi).
6. **D, Karpathy pur** : 1) INDEX.md + la question → au plus 3 pages ; 2) leurs faits datés (sans plafond : c'est la
   lecture de pages de Karpathy) → réponse. Deux appels ; ses tokens sont comptés à part.
7. **E** : la conversation entière, datée — échelle S seulement.
8. **Question posée après la dernière session** de sa conversation. En F, aucun fait n'est écarté comme « dit après » :
   les conversations n'ont pas les mêmes dates.
9. **Fusion** : pages de même nom fusionnées (les distracteurs s'y mêlent) ; **interlocuteurs homonymes séparés** —
   « John » parle dans conv-41, conv-43 et conv-47 : trois personnes, trois pages (`john_conv_41`…, alias « John »).
   Les fusionner n'aurait faussé que la FCM (qui raisonne sur les pages). Références au brut préfixées par la
   conversation (sinon deux lignes de même numéro créeraient de fausses arêtes « vécu ensemble »).
10. **Tranches** : pilote = conv-26 et conv-30 (304 questions) ; vérification = les 8 autres (1 682 questions).

### 11.2 Éprouvé à blanc
Modèle factice, conteneur **sans réseau** (`--network none` : aucun appel ne peut partir), sur un mini-jeu écrit
pour l'épreuve (`banc/locomo/locomo_blanc*.json`, jamais LoCoMo) : les 7 étapes, les 5 moteurs, les 2 échelles,
le bilan et les critères H1-H4 sortent. Interlocuteurs homonymes séparés (vérifié). **Reprise sans repayer** :
une relance ne refait aucun appel (99 avant, 99 après). **Plafond** : à 0 $, le banc s'arrête AVANT tout appel.
Le vrai jeu se lit entièrement (272 sessions, toutes les dates, 1 986 questions) — structure et tailles seulement,
aucune question lue.

### 11.3 Coût réestimé sur les tailles réelles (GPT-4o-mini, prix à revérifier)

| Volet | Entrée | Coût |
|---|---|---|
| Consolidation (272 sessions) | ≈ 1,0 M | ≈ 0,30 $ |
| A, B, C × S, F | ≈ 11 M | ≈ 1,75 $ |
| D Karpathy × S, F | ≈ 22 M | ≈ 3,40 $ |
| E tout le contexte (S) — avant le rabais du cache d'OpenAI | ≈ 42 M | ≈ 3,50-6,35 $ |
| Juge (9 séries) | ≈ 4,5 M | ≈ 0,80 $ |
| **Total** | **≈ 80 M** | **≈ 10-13 $** |
| **Pilote (2 conversations, 304 questions)** | | **≈ 1,5-2 $** |

Double garde-fou : plafond fixé par Francis chez OpenAI (25 $ proposés) + arrêt local à 20 $ (`LOCOMO_PLAFOND_USD`).

### 11.4 Pour lancer le pilote
1. Francis crée une clé API OpenAI, avec un plafond de dépense dans les réglages du compte, puis la saisit
   lui-même, masquée : `sh $HOME/banc-locomo/saisir-cle.sh` (fichier 600 ; Claude ne la lit jamais).
2. Vérifier ce jour-là : GPT-4o-mini disponible, prix réels (`commun.PRIX`).
3. `RUN=pilote sh lancer.sh preparer conv-26 conv-30`, puis `fusionner`, `recuperer`, `embeddings`, `repondre`,
   `juger`, `bilan`. Au pilote, la fusion ne réunit que 2 conversations : l'échelle F y est seulement éprouvée.
4. Bilan du pilote à Francis (taux de rejet de la consolidation avec GPT-4o-mini, coût réel, résultats à part),
   **décision de Francis**, puis le banc complet.

---

## 12 — Le pilote (01/10/2026) : conv-26 et conv-30, 304 questions, 0,92 $

**Clé** : celle d'EXIA GHOST (`EXIA_OPENAI_API_KEY`, 24 $ prépayés — un plafond naturel), autorisée par Francis.
Prix vérifiés le jour même (GPT-4o-mini : 0,15 / 0,075 en cache / 0,60 $ par million). Ces 304 questions sont
désormais VUES : elles restent rapportées à part.

### 12.1 Consolidation par GPT-4o-mini
38 sessions, **156 faits retenus, 6 rejetés (3,7 %)** — rejets sains (un nombre inventé « 18 », deux sections
inventées, deux noms absents des sources) ; 18 dates retirées ; 139/156 faits rattachés à des concepts ; 0,03 $.
**Défaut du modèle** : 32 faits sur 156 (20 %) restent à la première personne (« I'm thrilled to make a family… »),
contre la règle 1 (fait autonome) — la même mémoire pour tous les moteurs, donc la comparaison reste loyale.

### 12.2 DÉFAUT DU JUGE — et il touche EXIA GHOST
Le juge d'EXIA GHOST (repris mot pour mot, §11.1) contient : *« If the gold answer indicates the information is not
available and the generated answer also says unknown/not mentioned, mark as CORRECT. »* GPT-4o-mini l'applique à
**toutes** les questions : au pilote, **124 à 135 réponses « Unknown » sur 233 jugées justes** en catégories 1-4
(« attendu : amazing — réponse : Unknown → CORRECT »). Scores affichés 91-94 % ; réels 34-41 %.

Ce défaut venait du juge d'EXIA GHOST, repris tel quel ; il touche aussi ses résultats publiés. La correction est
portée dans le dépôt d'EXIA GHOST (https://github.com/francisdu53/exia-ghost-benchmarks ; décision de Francis, 28/10/2026) ; les scores d'EXIA GHOST ne sont pas repris ici.

**Juge v2 (déclaré, appliqué au pilote et au banc complet)** : une abstention est jugée par RÈGLE — fausse en
catégories 1-4, juste en catégorie 5 ; une réponse affirmative en catégorie 5 est fausse ; le modèle ne juge que
les vraies réponses des catégories 1-4, avec la consigne permissive MOINS la phrase fautive. Jugements v1 gardés.

### 12.3 Diagnostic ajouté : M, toute la mémoire
Tous les faits de la conversation donnés au modèle : **le plafond de ce que la consolidation a gardé.**

### 12.4 Résultats (juge v2) — catégories 1-4, 233 questions ; catégorie 5 à part (71)

| Moteur | S | F (2 conv.) | cat. 1 | cat. 2 | cat. 4 | cat. 5 |
|---|---|---|---|---|---|---|
| **A — FCM EXIA** | **41,2 %** | **41,2 %** | 51,2 | 39,7 | 37,7 | 91,6 |
| B — embeddings | 35,2 % | 35,2 % | 41,9 | 30,2 | 35,1 | 90,1 |
| C — plein texte | 37,3 % | 36,9 % | 37,2 | 33,3 | 40,4 | 91,6 |
| D — Karpathy pur | 34,8 % | 34,3 % | 37,2 | 30,2 | 36,0 | 87,3 |
| *M — toute la mémoire* | *42,1 %* | — | 44,2 | 38,1 | 43,9 | 78,9 |
| E — conversation entière | 80,3 % | — | 79,1 | 60,3 | 96,5 | 50,7 |

Tests appariés (McNemar exact) : **A contre B : 28 questions que seule A réussit, 14 que seule B réussit, p = 0,044**
(en F : 26 contre 12, p = 0,034) ; A contre C : 20 contre 11, p = 0,15 (non significatif) ; A contre M : p = 0,84.
Latence de A : 2,2 ms (p95) ; B : 270-340 ms, 2,4 Go.

### 12.5 Ce que dit le pilote
1. **La FCM retrouve presque tout ce que la mémoire contient** (A 41,2 % contre M 42,1 %, non distinguables) ; les
   embeddings en retrouvent moins (35,2 %, significatif sur 233 questions). H1 tient au pilote.
2. **La limite n'est pas la recherche, c'est la consolidation** : la mémoire entière plafonne à 42 % quand la
   conversation entière donne 80 %. Environ 4 faits par session (règle 3 : « ne retiens que ce qui sera UTILE PLUS
   TARD », pensée pour un assistant) : LoCoMo pose des questions de détail que la mémoire n'a pas gardées.
3. **L'échelle n'est pas encore testée** : 2 conversations fusionnées, ce n'est pas 10 ; le banc complet le dira.
4. Les moteurs à mémoire s'abstiennent beaucoup (≈ 55 % de « Unknown ») : excellents en catégorie 5, mauvais en 1-4.

---

## 13 — Le juge aligné sur le protocole de référence (01/10/2026)

**Question de Francis** : *« est-ce que tu as utilisé le protocole correct pour le juge ? … voir quels étaient leurs
processus, pas faire du copier-coller. »* Réponse : **non** — v1 était le juge d'EXIA GHOST (phrase ajoutée fautive),
v2 ma propre correction. Étude des concurrents (agent, code des dépôts lu, 01/10) :

- **Papier LoCoMo** : pas de juge — F1 de tokens (Porter) ; catégorie 5 par chaîne (« not mentioned »).
- **Mem0 (2025) a fixé le protocole « de fait »** : consigne `ACCURACY_PROMPT` (permissive, **sans clause d'abstention**),
  GPT-4o-mini, T = 0, sortie JSON, **catégorie 5 exclue**, J + F1 + BLEU-1, 10 exécutions dans le papier.
  **Repris tel quel par Zep, MemOS, MemMachine, EverMemOS.** Mem0 : 66,88 % ; **tout le contexte : 72,90 %**.
- Bonnes pratiques relevées : plusieurs passes du juge (MemOS, EverMemOS : 3), F1 à côté de J, cat. 5 à part (Supermemory :
  un juge d'abstention séparé), réponses brutes publiées, bruit d'exécution mesuré.
- Controverses : numérotation des catégories confondue dans plusieurs papiers (seul le global est robuste) ; audit Penfield
  Labs (avril 2026) — 6,4 % de réponses de référence fausses (plafond ≈ 93,6 %), juge Mem0 trop clément sur les réponses
  vagues ; Zep avait d'abord compté la cat. 5 (84 % → 75,14 %).
- **Aucune** source n'ajoute « unknown = correct » au juge général : la phrase d'EXIA GHOST lui était propre.

**Juge v3 = protocole de référence** (`banc/locomo/juger.py`) : consigne Mem0 extraite **par programme** de leur dépôt
(commit `aae5989e`, 8 juillet 2025), vérifiée identique octet pour octet (1 657 caractères) ; GPT-4o-mini, T = 0, JSON ;
**3 passes**, étiquette à la majorité ; catégorie 5 hors de J, notée par règle d'abstention ; **F1 du papier LoCoMo**
(fonctions recopiées de `task_eval/evaluation.py`, `banc/locomo/f1.py`, sur l'hôte). Jugements v1 et v2 archivés.

### 13.1 Le pilote sous le protocole de référence (catégories 1-4, 233 questions)

| Moteur | J (v3) | F1 | bruit du juge (3 passes) |
|---|---|---|---|
| **A — FCM EXIA** | **33,0 % (S) · 33,5 % (F)** | **21,8 · 22,1** | ≤ 0,2 pt |
| C — plein texte | 32,6 · 31,3 | 21,6 · 19,6 | 0 |
| B — embeddings | 28,3 · 28,3 | 17,8 · 17,8 | 0 |
| D — Karpathy pur | 28,8 · 27,0 | 19,9 · 18,7 | 0 |
| *M — toute la mémoire* | *33,5* | *22,2* | 0,35 |
| E — conversation entière | 67,8 | 48,7 | 0,2 |

- **Point d'ancrage** : E (tout le contexte, GPT-4o-mini) = 67,8 %, contre 72,9 % publié par Mem0 avec le même modèle —
  même ordre de grandeur (une exécution, consigne de réponse différente) : le protocole est sain.
- **Classement identique sous les trois juges et sous le F1 (sans juge)** : A ≈ M ≥ C > B ≈ D.
- A contre B : 27 questions que seule A réussit, 16 que seule B réussit (p = 0,13) — la tendance tient, la
  significativité attend les 1 682 questions du banc complet.
- **La limite reste la consolidation** : toute la mémoire plafonne à 33,5 % (Mem0 garde bien plus de souvenirs, top-k 30).
  Les scores absolus d'EXIA SEED sur LoCoMo ne sont donc pas comparables à ceux de Mem0 : on compare des MOTEURS sur une
  même mémoire, pas des systèmes complets.
- Pilote : 1,05 $ en tout.

---

## 14 — 18/10/2026 : EXIA SEED 0.9.1 (accord de Francis : « vas-y tu peux y aller avec E »)

### 14.1 État des lieux avant de lancer
- **Modèles** : gpt-4o-mini (réponses et juge, protocole de référence) et gpt-4.1-mini (réserve) RÉPONDENT (appel réel de
  quelques tokens, aucun en-tête de fin de vie). OpenAI a annoncé à Francis le **retrait de gpt-4o et gpt-4.1 le 14 janvier
  2027** : après cette date, ce banc ne se rejoue plus à l'identique (les réponses et jugements bruts restent archivés dans
  `runs/`). Pas de changement de modèle : il rendrait les chiffres incomparables avec le pilote et la littérature.
- Clé : `$HOME/banc-locomo/.cle-openai` (600), jamais affichée ; solde vu par Francis : 22 $ (la clé ne permet pas de le lire).
- Moteur B : bge-m3 toujours présent sur le VPS. Plugin : la 0.9.1 du dépôt (masque anglais).
- Ce que la 0.9.1 change pour LoCoMo : seuls les **mots distinctifs** touchent le moteur A (`memoire_chercher`) ; la fiche
  entre dans INDEX.md, donc dans le moteur D (Karpathy) ; enveloppes, avis, amorçage : sans objet. La consolidation (la
  limite mesurée au pilote) ne change pas : **pas de saut attendu**, annoncé avant la mesure.

### 14.2 Le pilote rejoué en 0.9.1 (run `pilote-091`, cache d'appels du pilote recopié) — 0,20 $
Consolidation : **les mêmes 156 faits au caractère près** (servie par le cache) ; fiches et mots : 38 appels, < 0,01 $.

| Moteur (233 questions, cat. 1-4, juge v3) | 0.9.0 | 0.9.1 | gagnées / perdues |
|---|---|---|---|
| A — FCM, échelle S | 77 (33,0 %) | 78 (33,5 %) | 2 / 1 |
| A — FCM, échelle F | 78 (33,5 %) | 76 (32,6 %) | 0 / 2 |
| C — plein texte, M — toute la mémoire | identiques | identiques | 0 / 0 |
| D — Karpathy pur, S | 67 | 66 | 12 / 13 |

**Jeu égal** : la 0.9.1 ne gagne ni ne perd sur LoCoMo (± 2 questions, dans le bruit). Les fiches dans l'index font
choisir d'autres pages au moteur D pour 25 questions, au même total.

### 14.3 Le banc complet (run `complet-091`)
10 conversations, 1 986 questions (chiffres annoncés : les 8 conversations de vérification ; pilote à part), moteurs A, B,
C, D, E, M, échelles S et F ; arrêt local à 15 $ ; coût réestimé 7-9 $ (à l'échelle F, D relit l'index des 10
conversations). Résultats : §14.4.


### 14.4 Résultats du banc complet (18/10, 14h19 → 16h03 UTC) — 13,84 $
**Vérification** : 8 conversations jamais vues (pilote à part), 1 307 questions des catégories 1-4, catégorie 5 à part
(375). Juge v3 (gpt-4o-mini, 3 passes, écart-type ≤ 0,17 point : le bruit du juge est négligeable).

| Moteur | S (une conversation) | F (10 fusionnées) | Perte | Cat. 5 (S) | F1 (S) | p95 |
|---|---|---|---|---|---|---|
| A — FCM (`memoire_chercher`) | **38,4 %** (502) | 33,2 % (434) | −5,2 | 91,2 % | 27,6 | 2,4 / 4,8 ms |
| B — embeddings bge-m3 | 38,3 % (501) | **38,3 %** (500) | −0,1 | 92,3 % | 26,3 | 314 / 391 ms |
| C — plein texte BM25 | 35,5 % (464) | 31,3 % (409) | −4,2 | 92,8 % | 26,2 | 0,2 / 0,3 ms |
| D — Karpathy pur | 35,0 % (458) | 30,4 % (397) | −4,7 | 90,4 % | 24,3 | — |
| M — toute la mémoire | 41,6 % (544) | — | | 86,7 % | 28,9 | — |
| E — conversation entière | 71,8 % (938) | — | | 52,3 % | 50,6 | — |

Tests appariés (McNemar, questions où un seul des deux a juste) :
- A_S contre B_S : 89 contre 88, p = 1,0 → **égalité exacte** à l'échelle d'une conversation (confirme docs/08 §11).
- A_S contre C_S : 82 contre 44, p = 0,0009 → la FCM bat nettement le plein texte.
- A_F contre B_F : 67 contre 133, p < 0,001 → **les embeddings battent nettement la FCM à l'échelle fusionnée.**
- A_F contre C_F : 84 contre 59, p = 0,04.

**Critères pré-enregistrés (§1)** : **H1 échoue** (33,2 < 38,3 − 2), H2 échoue (perte 5,2 contre 0,1), H3 échoue
(perte de D 4,7 < perte de A 5,2), H4 tient (4,8 ms, 80 fois plus rapide que B, sans modèle de 1,3 Go).
**La thèse n'est pas validée sur LoCoMo** : la FCM vaut les embeddings à la taille d'une mémoire, pas à dix fois cette
taille. Comme annoncé au §1, c'est écrit tel quel.

**Le pilote avait trompé** : sur 233 questions, H1 et H3 tenaient (A_F 29,2 contre B_F 27,9). Sur 1 307, ils tombent.
Un pilote de 2 conversations ne suffit pas à trancher une différence de quelques points.

**Ce qui tient** :
- Catégorie 5 (pièges sans réponse) : tous les moteurs à mémoire refusent à 90-93 % ; la conversation entière (E) se
  laisse piéger une fois sur deux (52 %). Mémoire consolidée = moins d'invention.
- À l'échelle d'une conversation (la taille de la mémoire de Nexa aujourd'hui), A = B, sans modèle et en 2 ms.
- A atteint 92 % de M (38,4 / 41,6) : le moteur retrouve presque tout ce que la mémoire contient.

**Où est la limite** :
- **La consolidation, d'abord** : donner TOUTE la mémoire (M) ne fait que 41,6 %, contre 71,8 % pour la conversation
  brute (E). 30 points sont perdus à l'écriture des faits, avant toute recherche. C'est le plus gros levier, et il est
  commun à tous les moteurs.
- **La fusion, ensuite — diagnostic local, sans appel de modèle** : dans le contexte donné au modèle, la part de faits
  venant de la bonne conversation tombe à **56 % pour A_F** (contre 77 % pour B_F, 90 % pour A_S). Sur les 146
  questions perdues par A_F et gagnées par B_F (catégorie 5 comprise), cette part n'est que de 49 % (17 contextes
  n'ont aucun fait de la bonne conversation). Sur 7 351 faits étrangers ramenés par A_F, **89 % ne mentionnent aucun des
  deux interlocuteurs de la question** : la question nomme la personne (« What did Caroline… »), mais le moteur suit
  le sujet (peinture, randonnée, travail) vers les faits d'autres personnes. Hypothèse, NON vérifiée : les concepts et
  le champ lexical, communs aux 10 conversations, servent de carrefour ; le nom de la personne ne pèse pas assez pour
  borner la propagation. Seul « john » est un vrai homonyme entre conversations.

**Coût** : 13,84 $ (40 544 appels), au-dessus de mon estimation de 7-9 $. Postes : lectures de pages du moteur D
6,46 $ (l'index fusionné relu à chaque question, D_F seul ≈ 5,7 $), réponses 6,09 $ (dont E ≈ 4 $), juge 1,00 $,
consolidation et fiches 0,29 $. Le plafond local de 15 $ n'a pas été atteint.

Données brutes : `$HOME/banc-locomo/runs/complet-091/` (`bilan.json`, `contextes/`, `reponses/`, `jugements/`).

### 14.5 Pourquoi A décroche en F — diagnostic du 18/10 (local, aucun appel de modèle)
Question de Francis : *« Pourquoi la FCM EXIA décroche quand ça grossit ? cela ne devrait pas… »*. Deux causes, mesurées
sur une copie de la mémoire fusionnée, dans un conteneur sans réseau. Témoin : la même procédure avec les réglages du
banc redonne les contextes d'origine (1 981 sur 1 986 identiques).

**1. Un défaut du banc (le mien).** `fusionner.py` et `recuperer.py` déclarent les **20 interlocuteurs implicites** en F,
comme Francis chez Nexa. Un nœud implicite n'est jamais un point d'entrée (`rappel.py`, alias ignorés) et ne crée
aucun lien « nommé » (`graphe.calculer`) : la FCM ne voit donc pas le nom de la personne dans la question, alors que
les embeddings et BM25 le voient. Chez Nexa, c'est juste (un seul utilisateur, présent partout). En F, c'est faux :
chaque interlocuteur devient un sujet parmi d'autres. Sans implicites, le graphe passe de 1 528 à 2 004 arêtes.

| Part des faits venant de la bonne conversation (cat. 1-4, 1 307 q.) | A_F banc | A_F sans implicites | B_F |
|---|---|---|---|
| Conversations sans homonyme (827 q.) | 62,5 % | **79,0 %** | 83,3 % |
| Les 3 conversations à « John » (480 q.) | 48,9 % | 48,8 % | 67,7 % |

**2. Un vrai défaut du moteur : la saturation du classement.** Le score d'un fait vaut
`cab_pull(activation du sujet, 1, couverture de la question)`. Quand la personne est nommée, son sujet est activé à
≈ 1 et **tous ses faits obtiennent ≈ 1, quel que soit le reste de la question** : le classement devient aveugle au
contenu. Mesuré : sans implicites, **317 questions reçoivent l'un de 86 contextes identiques** (B : 24). Exemple, 22
questions sur Jolene (« les noms de ses serpents », « quand a-t-elle acheté Seraphim », « combien de fois en France »)
reçoivent les mêmes 12 faits, qui commencent par « Jolene's mother passed away last year ».
C'est la même cause racine que le bruit du rappel (docs/12 §1 : le score ne descend jamais sous l'activation).
**Le lien avec la taille** : tant qu'une page tient dans le budget de 12 faits, l'ordre interne ne compte pas ; quand
la mémoire grandit, les pages grandissent, et le choix des 12 faits dans une page saturée se fait par les critères de
départage (activation, BM25, récence), plus par la question. En S, le défaut était masqué : les deux interlocuteurs
étant implicites, leur nom n'activait rien et le contenu de la question menait.
Les homonymes (« John » ×3) aggravent : la question ne dit pas lequel ; seul le contenu peut trancher, et c'est lui que
la saturation efface.

**Conséquence pour le §14.4** : le résultat de H1 en F mélange un défaut du banc et un défaut du moteur. Il reste
publié tel quel, avec ce diagnostic. Mesure à faire, avec l'accord de Francis : réponses et juge de A_F sans implicites
(≈ 0,25 $), puis, séparément, une correction de la saturation éprouvée sur le pilote et vérifiée sur les 8 autres.
Fichiers : `banc/locomo/diag_implicites.py` ; contextes dans `$HOME/banc-locomo/runs/complet-091/diagnostic-implicites/`.

### 14.6 Le banc corrigé, mesuré sur 3 conversations (run `speaker-3`, 18/10) — 0,12 $
Budget limité par Francis : 2-3 conversations. Questions de conv-41 (John/Maria), conv-42 (Joanna/Nate), conv-48
(Deborah/Jolene) : 542 questions cat. 1-4, 150 cat. 5. Mémoire fusionnée = toujours les 10 conversations (sans appel
au modèle). Changements du banc (une seule correction) : aucun interlocuteur implicite (`LOCOMO_IMPLICITES`, défaut 0) ;
`speaker` des trois John renommé comme leur page. B et C repris de `complet-091` (inchangés : C_S, C_F identiques à
100 %). Cache d'appels recopié.

| Mêmes 542 questions | S | F |
|---|---|---|
| A avant (implicites) | 199 (36,7 %) | 181 (33,4 %) |
| **A banc corrigé** | **183 (33,8 %)** | **151 (27,9 %)** |
| B embeddings | 190 (35,1 %) | 191 (35,2 %) |
| C plein texte | 191 (35,2 %) | 174 (32,1 %) |

A corrigé contre A avant : S 17 gagnées / 33 perdues (p = 0,03) ; F 23 / 53 (p < 0,001). **La correction fait PERDRE.**
Ma prédiction du §14.5 (« le banc était biaisé contre la FCM ») était fausse dans son effet : la part de faits de la
bonne conversation montait (79 % hors homonymes), mais la justesse baisse. **La pureté n'est pas l'utilité.**

**Pourquoi : la saturation (§14.5, cause 2) devient dominante.** Quand le nom allume son sujet, tous les faits de ce
sujet montent à ≈ 1 et la question n'ordonne plus rien. Questions dont le contexte est partagé avec au moins une autre :
A_S 114 → **237**, A_F 50 → **200** (B_F : 22). conv-41 (le John le plus fourni) en F : 75 → 50.
Rendre les implicites masquait la saturation : sans nom actif, le contenu de la question menait le classement.

**Conséquence** : la saturation est LA cause à corriger ; elle passe avant la lecture du `speaker` par le moteur (qui
serait une source d'activation de plus, donc la même saturation). Les noms doivent rester actifs (c'est juste en
principe, et nécessaire en multi-utilisateur) — une fois le classement corrigé.

### 14.7 La correction de la saturation (18/10, accord de Francis : « oui vas-y ») — 0,10 $
**Le changement, une ligne** (`requete.py`, note des faits de `memoire_chercher`) : les deux arguments de `cab_pull`
échangent leur rôle.

    avant : cab_pull(activation du sujet, 1, couverture de la question)    → ≈ 1 pour tout fait d'un sujet nommé
    après : cab_pull(couverture de la question, 1, 0,25 × activation)      → la question choisit, le sujet départage

Le sujet dit OÙ chercher, la question dit QUOI prendre. `POIDS_SUJET = None` rend l'ancienne note.
Le rappel (`rappel.py`, phase 2 chez Nexa) n'est PAS touché.

**Réglage sans juge, gratuit** (`banc/locomo/diag_saturation.py`) : mesure « réponse présente » = au moins la moitié des
mots pleins de la réponse attendue figurent dans les 12 faits. Validée contre le juge : juste dans ≈ 60 % des cas quand
elle est présente, ≈ 13 % quand elle est absente. Noms actifs (sans implicites) partout.

| Variante (réponse présente, S / F) | pilote 26+30 (233 q.) | 41+42+48 (542 q.) |
|---|---|---|
| ancienne note | 96 / 97 | 227 / 191 |
| 0,5 × activation | 98 / 95 | 237 / 223 |
| **0,25 × activation (retenue)** | 94 / 93 | **245 / 236** |
| 0,1 × activation | — | 244 / 234 |
| 0 (sujet ignoré) | 76 / 80 | 225 / 221 |

Essayé aussi : retirer du classement les mots qui ont nommé le sujet (« mots dépensés ») — inutile, retiré du code.
Le pilote ne sature presque pas (Caroline/Melanie, Jon/Gina) : il ne départage pas les variantes.

**Vérification, variante figée AVANT** : conv-43 (Tim/John), conv-47 (James/John), conv-49 (Evan/Sam), jamais examinées.
484 questions cat. 1-4. Run `satur-3`.

| Mêmes 484 questions | S | F |
|---|---|---|
| A publié (§14.4 : implicites, ancienne note) | 183 (37,8 %) | 147 (30,4 %) |
| A noms actifs, ancienne note — réponse présente, sans juge | 208 | 185 |
| A noms actifs, nouvelle note — réponse présente, sans juge | 217 | 198 |
| **A noms actifs, nouvelle note — juge** | **177 (36,6 %)** | **155 (32,0 %)** |
| B embeddings | 190 (39,3 %) | 187 (38,6 %) |
| C plein texte | 160 (33,1 %) | 135 (27,9 %) |

- Contre A publié : S 9 gagnées / 15 perdues (p = 0,31) ; F 14 / 6 (p = 0,12). **Pas de différence significative.**
- Contexte partagé avec une autre question (saturation) : S 97 → 69, F 20 → 16 (B : 0).
- Contre B en F : 19 / 51 (p < 0,001). **L'écart avec les embeddings à l'échelle fusionnée reste entier.**

**Lecture** : la correction est nécessaire — elle rend les noms utilisables (sans elle, les activer coûtait 30 questions
en F sur 41+42+48, §14.6) — mais elle ne suffit pas. **Où naît l'écart restant** (traçage local, F, 43+47+49) : sur
2 360 faits étrangers, 1 737 viennent des sujets de rang 2 et plus, rejoints par propagation ou par les pages communes
(« hiking_trail » réunit les randonnées de toutes les conversations). Exemple : « Which geographical locations has Tim
been to? » → premier sujet « hiking_trail » (par le concept « outdoor activities »), des faits de Joanna. La question
nomme Tim ; le moteur ne sait pas que ces faits ont été dits par Joanna. **C'est exactement ce que la lecture du
`speaker` doit corriger** (demande de Francis, 18/10).

Tests du dépôt : 17 suites, toutes réussies. Banc des requêtes sur la mémoire de Nexa (docs/08 §12) : à rejouer avant
tout déploiement.

### 14.8 Le moteur lit le `speaker` (18/10, accord de Francis : « vas-y ») — 0,06 $
Francis : *« il faut faire lire le speaker au moteur, sinon comment l'agent peut savoir qui a parlé ? »* Constat : chaque
fait portait son `speaker` depuis la 0.1.0, mais seule la consolidation l'écrivait ; ni la recherche ni le rappel ne le
lisaient, et `memoire_chercher` ne le montrait pas.

**Deux changements** (`requete.py`) :
1. **Classement** : quand la question nomme une personne qui a parlé (un `speaker` qui a sa page, hors utilisateur et
   agent), un fait dit par QUELQU'UN D'AUTRE et qui ne la nomme pas est tiré vers 0 : `cab_pull(note, 0, 0,5)`.
2. **Affichage** : chaque fait rendu porte `dit_par` quand son auteur est une telle personne. Chez Nexa aujourd'hui,
   presque tout est dit par Francis (implicite) : **0 token de plus**. Le rappel (phase 2) n'est pas touché.
   Reste à faire (accord séparé, touche la mémoire réelle) : l'annuaire « ID de canal → personne » et le demandeur.

**Réglage gratuit** (réponse présente, F ; pureté = part des faits venant de la bonne conversation) : 0,25 / 0,5 / 0,75
/ 1 → effets de ± 5 questions selon le lot ; pureté F 58 % → 64 / 69 / 71 / 71 % (B : 70 %). Retenu 0,5, figé avant la
vérification.

**Vérification** : conv-44 (Audrey/Andrew) et conv-50 (Calvin/Dave), les deux dernières jamais examinées, échelle F,
281 questions cat. 1-4 ; runs `spk-a` (saturation seule) et `spk-b` (+ speaker).

| Mêmes 281 questions, échelle fusionnée | Justes | Pureté |
|---|---|---|
| A publié (§14.4) | 106 (37,7 %) | 69 % |
| A, saturation corrigée | 115 (40,9 %) | 77 % |
| **A, saturation + speaker** | **121 (43,1 %)** | **90 %** |
| B embeddings | 122 (43,4 %) | 88 % |
| C plein texte | 100 (35,6 %) | — |

- A + speaker contre A publié : 21 gagnées / 6 perdues, **p = 0,006**. Contre la saturation seule : 10 / 4 (p = 0,18).
- **A + speaker contre B : 24 / 25, p = 1 — égalité à l'échelle fusionnée sur ces deux conversations.**
- Catégorie 5 : 76/81 pour A comme pour B.

**Prudence** : 281 questions, 2 conversations — le pilote (233 questions) avait déjà trompé (§14.4). Sur conv-43/47/49,
la saturation seule laissait l'écart entier (155 contre 187) ; le speaker n'y a été mesuré que sans juge (+2 à +9). H1 ne
sera tenue pour validée qu'après un banc sur les 8 conversations (≈ 0,6 $ pour A seul en S et F, B et C étant repris).

Tests du dépôt : 17 suites, toutes réussies.

**Sur la mémoire de Nexa** (banc 10, docs/08 §13) : la lecture du speaker est sans effet ; la note anti-saturation
(0,25) coûte 5 souvenirs utiles sur 164 avec la mémoire du 23-29/09. Rien n'est déployé.

### 14.9 Le bilan en clair, et ce que pèse chaque moteur (18/10, Francis : « tu documentes tout »)
**Ce qu'on retient de la journée.** Ce midi, EXIA SEED faisait jeu égal avec les embeddings sur une conversation et
décrochait de 5 points quand dix conversations étaient fusionnées. Trois causes ont été trouvées : un défaut du banc
(tous les interlocuteurs rendus implicites, §14.5), une note qui saturait dès qu'un nom était cité (§14.7), et le
`speaker` écrit mais jamais lu (§14.8). Après les deux corrections, sur deux conversations jamais examinées, à l'échelle
fusionnée : **121 justes contre 122 pour les embeddings, 90 % des faits rendus viennent de la bonne personne.**

**Ce que pèse chaque moteur** (mesuré le 18/10 sur la mémoire fusionnée de `spk-b` : 10 conversations, 1 025 faits,
726 nœuds ; processeur AMD EPYC 9354P, 2 cœurs alloués, Python 3.12, sans carte graphique) :

| | A — EXIA SEED | B — embeddings bge-m3 |
|---|---|---|
| Ce qu'il faut en plus des pages (2,7 Mo, communes aux deux) | graphe 1,5 Mo | vecteurs 4,2 Mo (1 025 × 1 024 × 4 octets) **+ modèle 2,27 Go** |
| Mémoire vive, processus entier | **60 Mo** (dont ≈ 10 Mo pour Python lui-même) | **2 625 Mo** |
| Démarrage | 0,9 s (lecture des pages et du graphe) | 13,8 s (chargement du modèle) |
| Une recherche | 4,2 ms (médiane), 5,0 ms (p95) | 314 ms (médiane), 391 ms (p95), §14.4 |
| Calcul | sommes et `cab_pull`, déterministe | réseau de neurones de 568 M de paramètres |

Soit ≈ 44 fois moins de mémoire vive et ≈ 75 fois plus rapide, pour un score égal sur ce lot. Le coût de fabrication de
la mémoire (la consolidation par un modèle de langage) est **le même pour les deux** : B encode les faits que la
consolidation a écrits. L'écart de prix est donc dans le matériel nécessaire pour chercher, pas dans les appels payés.

**Ce que ces chiffres ne disent pas encore.**
- L'égalité est mesurée sur 281 questions ; elle doit tenir sur les 8 conversations (≈ 0,6 $) avant d'être annoncée.
- La mémoire vive de A est celle d'un programme Python ; elle n'a pas été mesurée sur un processeur embarqué.
- Le plafond reste la consolidation : la conversation entière donne 71,8 %, toute la mémoire 41,6 % (§14.4).

**Perspective : l'embarqué** (Francis, 18/10 : *« je vois un dispositif comme celui-là dans des drones ou des avions,
ou n'importe quel système embarqué »*). Ce qui va dans ce sens : pas de modèle à charger, quelques dizaines de Mo, des
millisecondes, et un calcul **déterministe et explicable** — chaque note est une somme qu'on peut retracer, ce qu'un
réseau de neurones ne permet pas, et c'est ce que demande la certification d'un logiciel embarqué critique. Ce qui reste
à résoudre : la **recherche** est embarquable, l'**écriture** ne l'est pas encore (la consolidation appelle un modèle de
langage : il faudrait la faire au sol, entre deux missions, ou avec un petit modèle à bord) ; la mémoire mesurée ici est
faite de conversations, pas d'événements de mission ou de capteurs ; le vocabulaire passe par les masques de langue, il
en faudrait un pour le domaine ; et le moteur est en Python, pas dans un langage de l'embarqué. Aucune de ces quatre
conditions n'a été mesurée.

### 14.10 La confirmation sur les 8 conversations (18/10, accord de Francis : « vas-y fais ») — 0,17 $
Run `confirm-092` : moteur A de la 0.9.2 (saturation corrigée, `speaker` lu), 8 conversations de vérification, S et F,
1 307 questions cat. 1-4 + 375 cat. 5. Mémoires et cache d'appels repris de `complet-091` et des runs de l'après-midi ;
B, C, D, E, M repris de `complet-091` (inchangés par la correction). Script : `$HOME/banc-locomo/lancer-confirm-092.sh`.

| Cat. 1-4, 1 307 questions | Une conversation (S) | Dix fusionnées (F) | Perte |
|---|---|---|---|
| A publié (0.9.1, §14.4) | 38,4 % (502) | 33,2 % (434) | −5,2 |
| **A corrigé (0.9.2)** | **38,6 % (505)** | **36,8 % (481)** | **−1,8** |
| B embeddings | 38,3 % (501) | 38,3 % (500) | −0,1 |
| C plein texte | 35,5 % (464) | 31,3 % (409) | −4,2 |

- A corrigé contre A publié, F : 75 gagnées / 28 perdues, **p < 0,001** (+47 questions). En S : 48 / 45, p = 0,84 — la
  correction ne coûte rien à la taille d'une mémoire.
- A corrigé contre B, F : 77 / 96, **p = 0,17** — écart de 1,5 point, non significatif. En S : 93 / 89, p = 0,82.
- **H1 (A_F ≥ B_F − 2) tient, de justesse** : 36,8 ≥ 36,3. **H2 (perte de A ≤ perte de B) échoue** : −1,8 (p = 0,02
  entre S et F) contre −0,1. **H4 tient** : 3,9 ms médiane, 7,4 ms p95 en F (4,8 ms avant ; B : 282 / 391 ms).
- Pureté F (part des faits rendus venant de la conversation de la question) : 62,7 % → **85,7 %** ; B : 90,0 %.
- Catégorie 5 : 344/375 en S comme en F (B : 346).
- L'écart restant est concentré sur deux conversations : conv-43 (Tim/John, 58 contre 71) et conv-49 (Evan/Sam, 56
  contre 66) ; ailleurs A égale ou dépasse B (conv-42 : 73 contre 65, conv-48 : 50 contre 45). Par catégorie, en F :
  multi-sauts (1) 94 contre 103, temporel (2) 99 contre 103, ouvert (3) 18 contre 21, simple (4) 270 contre 273. Cause
  de l'écart sur conv-43/49 : **non cherchée**.

**Réserve de méthode, à écrire en face du résultat** : le §5 voulait « aucun réglage sur LoCoMo pendant la mesure ». Le
diagnostic (§14.5) et les réglages (§14.7-14.8) ont été faits sur six de ces huit conversations (41, 42, 48 ; 43, 47,
49) ; seules conv-44 et conv-50 sont restées vierges jusqu'à la vérification (§14.8 : 121 contre 122). Le chiffre propre
est celui-là ; les 8 conversations confirment qu'il ne s'effondre pas ailleurs. Les réglages sont restés grossiers
(deux constantes, 0,25 et 0,5, choisies sur une mesure sans juge), ce qui limite l'ajustement, sans l'exclure.

**Ce que ça dit de la thèse** : sans modèle d'embedding, EXIA SEED reste à 1,5 point des embeddings quand la mémoire est
dix fois plus grosse (5,1 points avant la correction), au seuil fixé avant la mesure, avec 44 fois moins de mémoire vive
et 70 fois moins de temps par recherche (§14.9). Il perd encore un peu en grossissant, ce que les embeddings ne font pas.
