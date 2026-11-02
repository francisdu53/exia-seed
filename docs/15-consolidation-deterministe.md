# 15 — Une consolidation sans modèle, pour l'embarqué (réflexion)

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Statut : réflexion et plan — rien n'est mesuré.** Ce document dit une idée et la façon dont on va l'éprouver ; aucun
chiffre ici n'est un résultat.
**Date :** 2 novembre 2026. **Origine :** Francis — *« un LLM consolidateur dans un système embarqué peut être
compliqué ; l'idée est d'avoir une solution fiable, un algorithme spécifique ou une formule »*. Le même jour, une revue
externe du dépôt proposait de mesurer la précision **à budget de tokens égal** et une consolidation **extractive** (§7).
**Référence :** `04` (consolidation, contrôle de citation), `06` (rappel), `13` (LongMemEval), `14` (après la publication).

## 1 — Le problème

Dans EXIA SEED, un seul maillon exige un modèle de langage : **la consolidation**, qui lit le brut chaque nuit et écrit
les faits dans les pages. La recherche, le graphe et le rappel n'en ont jamais eu besoin (11 ms par recherche, 123 Mo
pour tout le processus, aucun modèle chargé).

Pour un assistant personnel, ce maillon est acceptable : un modèle tourne déjà, la consolidation se fait la nuit. Pour
un système **embarqué** — un drone, un véhicule, un cockpit — il ne l'est pas :

- **coût et matériel** : un modèle capable ne tient pas dans le calculateur, ou pas à côté du reste ;
- **latence** : des secondes là où il faudrait des millisecondes ;
- **non-déterminisme** : deux passages sur le même brut ne donnent pas les mêmes faits — difficile à certifier ;
- **dépendance** : sans liaison réseau, plus de consolidation.

La question : **peut-on consolider sans modèle, avec des règles et des formules, de façon fiable et rejouable ?**

## 2 — La décision : deux consolidateurs, une mémoire

| | Assistant personnel (« Pepper Potts », Nexa) | Système embarqué |
|---|---|---|
| Entrée | la parole humaine : désordonnée, implicite, pleine de « ok vas-y » | des événements : capteur, valeur, heure, mission |
| Consolidateur | **le modèle de langage, inchangé** (docs 04, 13) | **déterministe** : ce document |
| Pages, graphe, recherche, rappel | identiques | identiques |

Le contrat entre la consolidation et le reste est **le format des pages** : chaque fait est une phrase, avec sa source
(fichier et ligne du brut), ses dates, son locuteur. Le graphe, la recherche et le rappel ne savent pas *qui* a écrit
la page. On peut donc changer de consolidateur sans toucher au reste — un module, une fonction (principe UNIX).

**Ce qui ne change pas pour Nexa** : son consolidateur reste le modèle de langage (§8).

## 3 — Ce que fait un consolidateur : cinq gestes

Quand le modèle consolide, il fait en réalité cinq choses à la fois :

1. **Ranger** — à quel sujet (quelle page) appartient cette information ? Faut-il créer un sujet neuf ?
2. **Retenir** — cette information mérite-t-elle d'être gardée ?
3. **Mettre à jour** — contredit-elle, ou remplace-t-elle, un fait déjà connu ?
4. **Comprendre une confirmation** — à quoi répond un « oui », un « ok », un « vas-y » ?
5. **Renforcer ou laisser s'effacer** — quelle force garde un souvenir avec le temps ?

Chacun de ces gestes a un principe établi, déterministe et rapide.

## 4 — Un principe établi pour chaque geste

### 4.1 Ranger → la résonance adaptative

**Principe** (Grossberg, 1976 ; Carpenter et Grossberg, 1987 — *Adaptive Resonance Theory*) : une entrée nouvelle est
comparée aux catégories existantes. Si elle **résonne** assez avec l'une d'elles — au-dessus d'un seuil appelé
**vigilance** — elle s'y range et l'enrichit ; sinon, elle crée une catégorie neuve. C'est la réponse classique au
dilemme **stabilité / plasticité** : apprendre du neuf sans écraser l'ancien.

**Chez EXIA SEED, le moteur existe déjà.** À chaque message, le rappel (`06`, `11`) calcule quelles pages le message
allume dans la carte cognitive floue, et l'écrit dans `memoire/rappel/*.jsonl`. Ce que le rappel fait à la lecture, la
consolidation peut le faire à l'écriture :

```
R(s, p)  = activation de la page p par la phrase s        (propagation FCM, comme le rappel)
p*       = la page de plus forte activation
si R(s, p*) ≥ ρ      → la phrase s complète la page p*      (reconsolidation)
sinon                → nouvelle page, nommée par le nom propre ou le groupe nominal le plus saillant de s
```

ρ (la vigilance) se fixe par mesure, pas à la main (§7).

### 4.2 Retenir → la surprise

**Principe** (Shannon, 1948) : la quantité d'information d'un message est d'autant plus grande qu'il est inattendu. Ce
qui est déjà su n'apporte rien. Le cerveau fait de même : la nouveauté déclenche la mise en mémoire.

**Proposition** :

```
N(s, p)  = part des mots pleins de s absents de la page p       (nouveauté, entre 0 et 1)
σ(s)     = saillance : nombres, dates, noms propres, obligations (« il faut », « toujours », « jamais »),
           futur, phrase qui relie deux sujets existants         (entre 0 et 1, règles des masques de langue)
r(s, p)  = cab_pull(N, 1, σ)                                     (une phrase saillante est retenue même si elle
                                                                   recoupe en partie ce qui est su)
retenir si r ≥ θ
```

`cab_pull` est la primitive de score déjà utilisée par la recherche : une traction linéaire de N vers 1, d'autant plus
forte que σ est grand. Les mêmes seuils, la même primitive, partout.

### 4.3 Mettre à jour → la révision des croyances

**Principe** (Alchourrón, Gärdenfors et Makinson, 1985 — la théorie AGM) : quand une information nouvelle contredit
une croyance, on retire le moins possible pour rester cohérent. En pratique : **même sujet, même attribut, valeur
différente → la plus récente remplace l'ancienne**, et l'ancienne reste dans l'historique de la page, datée.

L'extraction des triplets (sujet, attribut, valeur) se fait par motifs, dans les masques de langue — l'architecture
précédente de l'auteur, EXIA GHOST, le faisait déjà sans modèle. C'est le geste le plus difficile en conversation
(« finalement ce sera jeudi ») et le plus simple en embarqué (« batterie : 23 % » remplace « batterie : 41 % »).

### 4.4 Comprendre une confirmation → les paires de dialogue

**Principe** (Schegloff et Sacks, 1973 — les *paires adjacentes* de l'analyse conversationnelle) : une réponse
appartient au tour qui la précède. Une question appelle une réponse, une proposition appelle un accord ou un refus.

**Règle** : un « oui », « ok », « vas-y », « d'accord » qui suit une proposition de l'agent donne le fait *« l'agent
propose X ; l'utilisateur confirme »*, avec les deux lignes pour source. C'est exactement la règle 4 actuelle — les
paroles de l'agent ne sont retenues que si l'utilisateur les confirme — rendue déterministe.

### 4.5 Renforcer ou laisser s'effacer → l'activation d'ACT-R

**Principe** (Anderson et Schooler, 1991 ; Anderson et Lebiere, 1998 — l'architecture ACT-R), tiré de la courbe
d'Ebbinghaus (1885) :

```
B = ln( Σ t_j^(−d) )        t_j = temps écoulé depuis chaque usage du souvenir (écrit, rappelé, lu)
                             d ≈ 0,5
```

Un souvenir qui revient souvent et récemment est fort ; un souvenir jamais rappelé s'efface doucement. La formule est
déterministe, se calcule en microsecondes, et peut pondérer la recherche sans rien effacer du brut.

### 4.6 L'assemblage : la consolidation par résonance

```
pour chaque nouvelle ligne du brut :
    si confirmation d'une proposition de l'agent   → fait « proposé / confirmé »          (4.4)
    p* = page qui résonne le plus ; vigilance ρ    → ranger, ou créer une page             (4.1)
    r = cab_pull(nouveauté, 1, saillance) ≥ θ ?    → retenir la phrase TELLE QUELLE        (4.2)
    même sujet + même attribut, valeur nouvelle ?  → remplacer, garder l'ancienne datée    (4.3)
    à chaque écriture, rappel ou lecture           → mettre à jour la force B              (4.5)
```

**Le fait retenu est la phrase de la source, mot pour mot.** Le contrôle de citation devient trivial : chaque fait est
une sous-chaîne de sa source. Même brut, même mémoire, octet pour octet.

## 5 — Ce qu'une formule ne fera pas (dit d'avance)

- **Résumer.** Le modèle condense une discussion de vingt messages en un fait ; l'extractif garde des phrases
  entières. Les faits sont plus fidèles, mais plus longs — c'est pourquoi la mesure se fait **à budget de tokens égal**.
- **Inférer l'implicite.** « Je passe chez X demain, ils ont trois véhicules à voir » porte deux faits ; une règle en
  verra peut-être un seul.
- **Se passer des masques de langue.** Marqueurs de confirmation, motifs de triplets, signaux de saillance : à écrire
  pour chaque langue, comme aujourd'hui (`10`).
- **Créer des thèmes abstraits.** Sans modèle, un sujet neuf naît d'un nom propre ou d'un groupe nominal ; un thème que
  personne ne nomme (« organisation de la semaine ») n'apparaîtra pas. Le graphe sera plus pauvre en concepts.

## 6 — Pourquoi l'embarqué est le cas facile

Le modèle de langage est surtout un besoin de la **mémoire conversationnelle** : la parole humaine est ambiguë, elle
sous-entend, elle confirme d'un mot. Un système embarqué reçoit des **événements structurés** :

```
14:02  batterie      23 %        mission M7
14:02  vent          38 km/h     rafales
14:05  batterie      21 %        mission M7
```

Le schéma (quoi, valeur, quand) est connu d'avance : ranger est immédiat, la révision (4.3) remplace une valeur par la
suivante, la surprise (4.2) ne retient que **ce qui change** ou franchit un seuil — le principe des systèmes pilotés par
événements. Le cas difficile, c'est la conversation ; si la consolidation par résonance tient sur la parole de Nexa,
elle tiendra sur un journal de bord.

## 7 — Comment on l'éprouvera

Même règle que les documents 09 et 13 : **hypothèses et seuils écrits avant toute mesure**, dans un protocole à part,
seuils validés par Francis ; échecs publiés tels quels.

### 7.1 D'abord un test gratuit : la résonance range-t-elle comme le modèle ?

Les données existent déjà, en lecture seule :

- les journaux du rappel donnent, pour chaque message de Francis, les pages que la FCM a allumées **avant** la
  consolidation ;
- les pages de Nexa donnent, pour chaque fait, la page choisie par le modèle et la ligne source.

On compare, fait par fait : la page choisie par le modèle est-elle la première (ou parmi les trois premières) de la
résonance ? Et quand le modèle a **créé** une page, la résonance était-elle sous la vigilance ? Coût : nul. Si l'accord
est faible, le geste 4.1 est à revoir avant tout le reste.

### 7.2 Les variantes comparées

| Variante | Consolidation |
|---|---|
| LLM | la consolidation actuelle (règle 3 exhaustive, `13` §19) |
| E1 | extractive naïve : chaque phrase de l'utilisateur, telle quelle, dédupliquée |
| E2 | E1 + les phrases de l'assistant, marquées comme telles, jamais seules sources |
| E3 | **par résonance** : les cinq gestes du §4 |

### 7.3 Le juge : la précision à budget de tokens égal

Au document 13, chaque moteur recevait 12 faits, pas le même nombre de tokens : on ne sait pas combien chacun injectait
vraiment. La mesure se fera **par budget** — le bloc rempli par ordre de rang jusqu'à B tokens, B de 100 à 1 600 — pour
chaque consolidation et chaque moteur de recherche (EXIA SEED, embeddings, plein texte), sur :

- **LongMemEval** (mémoire fusionnée, même lecteur et même juge que le document 13) ;
- **les 80 questions tirées des vrais messages de Francis** (`13` §19), sur des copies de la mémoire de Nexa — parce
  que les bancs ne sont pas la vie réelle, et que la parole réelle (« ok », « vas-y », sorties d'outils) est le terrain
  où l'extractif peut s'effondrer.

Le même balayage répond aussi à une question ouverte depuis le document 13 : à budget de tokens égal, EXIA SEED
vaut-il toujours les embeddings ?

### 7.4 Arbre de décision

- **E3 tient** (à quelques points de la consolidation LLM, à budget égal) → consolidation par résonance proposée pour
  l'embarqué, puis un essai sur un vrai journal d'événements.
- **E3 tient partout sauf sur les mises à jour** → hybride possible : résonance partout, un modèle qui ne fait que
  **désigner** les lignes à réviser, sans jamais écrire, sa désignation enregistrée et rejouable.
- **E3 échoue largement** → le modèle garde un rôle que les formules ne remplacent pas ; on publie la courbe pour montrer
  ce que la reformulation apporte réellement.

## 8 — Ce qui ne change pas pour Nexa

Pour un assistant personnel, le consolidateur reste le **modèle de langage** : il comprend la parole humaine mieux que
des règles, et la mesure du 28/10 l'a montré sur sa vraie mémoire (22 → 36 bonnes réponses sur 80, `13` §19).

Quelques gestes déterministes pourront lui servir **en complément**, et seulement si une mesure le justifie : la
résonance pour **vérifier** le rangement choisi par le modèle ; la force ACT-R pour pondérer la recherche. Pistes, pas
décisions.

## Sources

- S. Grossberg, *Adaptive pattern classification and universal recoding*, Biological Cybernetics, 1976 ;
  G. Carpenter et S. Grossberg, *A massively parallel architecture for a self-organizing neural pattern recognition
  machine* (ART 1), 1987.
- C. E. Shannon, *A Mathematical Theory of Communication*, 1948.
- C. Alchourrón, P. Gärdenfors, D. Makinson, *On the logic of theory change*, Journal of Symbolic Logic, 1985.
- E. Schegloff et H. Sacks, *Opening up closings*, Semiotica, 1973.
- J. R. Anderson et L. Schooler, *Reflections of the environment in memory*, Psychological Science, 1991 ;
  J. R. Anderson et C. Lebiere, *The Atomic Components of Thought*, 1998.
- H. Ebbinghaus, *Über das Gedächtnis*, 1885.
