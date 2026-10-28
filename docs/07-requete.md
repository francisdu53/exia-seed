# 07 — La requête : Nexa lit son wiki, FCM EXIA l'y aide

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Version :** 1.0
**Date :** 27 septembre 2026
**Statut :** **Déployé** (plugin 0.6.0, 27/09 ≈ 13h57) — 27/27 tests de l'étape, 238/238 toutes suites.
Conçu dans le cadre validé par Francis le 26/09 (*« je valide… et on voit ce que
cela donne »*) et le 27/09 (*« go pour cet ordre, je te fais confiance ; tu documentes tout et
chaque décision »*).
**Référence :** `SPEC-EXIA-SEED.md` §0 (recadrage : la base est Karpathy) · `05-graphe.md` ·
`06-rappel.md` §0 et §8 · compétence Hermès `llm-wiki` 2.1.0 (§ Query)
**Changelog 1.0 :** code, tests, essai sur la mémoire réelle, déploiement, schéma dans AGENTS.md,
rattrapage des notes perdues. **Changelog 0.1 :** conception.
**Origine :** Francis, 27/09 — *« EXIA SEED = WIKI EXIA (LLM Wiki de Karpathy adapté ou amélioré) +
FCM EXIA. […] Ma réponse pour éviter l'embedding est FCM EXIA. Cela permet à WIKI EXIA de continuer
à grandir sans être saturé grâce aux métadonnées et au système associatif. […] auditable et
certifiable tout en restant simple face à la boîte noire qu'est un embedding. »*

---

## 1 — Positionnement

L'opération **Query** de Karpathy, dans Hermès : *« the LLM reads the index first to find relevant
pages, then drills into them »*. La compétence `llm-wiki` d'Hermès la décline en cinq temps ; EXIA
SEED les garde tous et insère FCM EXIA **exactement au deuxième**, là où Karpathy et Hermès passent à
une recherche par mots-clés et où d'autres mettent des vecteurs :

| Compétence `llm-wiki` (§ Query) | EXIA SEED |
|---|---|
| ① lire `index.md` | Nexa lit `memoire/INDEX.md` avec ses outils de fichiers |
| ② *« for wikis with 100+ pages, also `search_files` »* | **`memoire_chercher`** : FCM EXIA + plein texte, au lieu d'un grep ou de vecteurs |
| ③ lire les pages | **`memoire_lire`** : la page, plus ses **pistes associatives** (les « trails » du Memex) |
| ④ répondre en citant les pages | inchangé |
| ⑤ ranger les bonnes réponses | `memoire_noter` → registre → consolidation (un seul écrivain) |

**Répartition des rôles** — le point de doctrine : le modèle apporte **le sens** (il comprend que
« mécanicien » et « garagiste » disent la même chose, et il formule sa recherche) ; FCM EXIA apporte **la
structure** (qui est lié à quoi, depuis quand, d'après quelle phrase). Un embedder serait un second
encodeur sémantique, plus faible que le premier et opaque ; la FCM fait ce que le modèle ne sait pas
faire : garder et parcourir les liens de toute une vie, avec leur provenance.

---

## 2 — Le terrain

### 2.1 Défaut trouvé en préparant l'étape : `memoire_noter` n'a jamais fonctionné

Le journal d'Hermès affiche *« Memory provider 'exia_seed' registered (0 tools) »* à chaque
chargement, et les trois appels de Nexa à `memoire_noter` (23/09 14h28, 25/09 08h08, 26/09 18h41)
ont échoué : *« Unknown tool: memoire_noter »*.

**Cause** (lue dans le code d'Hermès 0.21.3) : `agent_init.py:1278` appelle
`MemoryManager.add_provider()`, qui lit `get_tool_schemas()` et remplit la table d'aiguillage
(`_tool_to_provider`) ; **puis** `agent_init.py:1286` appelle `initialize_all()`. Le plugin ne
déclarait son outil qu'une fois initialisé (`return [_SCHEMA_NOTER] if self._registre else []`) : la
table est restée vide. Plus tard, `get_all_tool_schemas()` — appelé après l'initialisation — montrait
bien l'outil au modèle, mais l'appel n'avait aucun destinataire.

**Pourquoi les tests ne l'ont pas vu** : ils appelaient `handle_tool_call` directement sur le plugin,
sans passer par le `MemoryManager` d'Hermès. Le chemin de production n'était pas testé — la leçon de
R1 (« vérifier le chemin de production, pas celui des tests ») n'avait pas été appliquée aux outils.

**Correction** (D5) et **rattrapage** : les trois notes perdues sont retrouvées dans le brut et
proposées à Francis.

### 2.2 Ce que le banc 6b a appris

Le modèle lisant l'index trouve 80 % des souvenirs utiles pour ~940 tokens (docs/06 §8). La cascade
symbolique échoue sur des messages conversationnels longs ; **elle n'a pas été éprouvée sur des
requêtes courtes formulées par le modèle** — le cas de `memoire_chercher`. C'est la première chose
que le banc de l'étape 8 vérifiera.

---

## 3 — Décisions

### D1 — Le schéma, dans AGENTS.md (Karpathy : *« what makes the LLM a disciplined wiki maintainer »*)
Quelques lignes, validées dans leur principe par Francis le 26/09 :

```
## Ta mémoire longue — EXIA SEED
Tes conversations sont rangées chaque jour en pages, dans /opt/data/memoire/ : INDEX.md (le
sommaire, une ligne par sujet) et pages/ (un fichier par sujet, faits datés et sourcés).
Pour t'en servir : lis INDEX.md, ouvre les pages utiles. Si le sommaire ne suffit pas :
memoire_chercher(requête courte) ; pour une page et ses liens : memoire_lire(sujet).
Tu LIS ta mémoire, tu ne l'écris pas : la consolidation la tient (contrôle des sources, historique).
Pour qu'une chose y entre sûrement : memoire_noter. Un fait « personnel » ne sort jamais vers un tiers.
```

**Écarté** : pointer la compétence `llm-wiki` d'Hermès sur `memoire/` (`WIKI_PATH`). Elle pousse
l'agent à **écrire** lui-même ses pages (Ingest) : ce serait casser l'écrivain unique, le contrôle de
citation et l'historique git. Nexa garde la compétence pour d'autres wikis éventuels.

### D2 — L'index se lit comme un fichier
Nexa lit `INDEX.md` avec `read_file`, comme chez Karpathy : toujours à jour, coût seulement quand
elle le lit. **Écartés** : l'index dans `system_prompt_block` (figé pour toute une session, or ses
sessions durent des jours) ; un outil `memoire_index` (un outil de plus pour lire un fichier).

### D3 — `memoire_chercher(requete, nombre=5)`
Entrée : une requête **courte**, formulée par Nexa. Sortie : les sujets les plus pertinents, chacun
avec son titre, **pourquoi** il remonte (nommé · mot · plein texte · lié à X) et ses 2 ou 3 faits les
mieux couverts par la requête, datés. Budget ≈ 400 tokens. Moteur : celui de l'étape 6
(cascade, propagation lue au-dessus du repos, couverture par rareté, `cab_pull`), classé par nœud
plutôt que par fait. Déterministe, < 50 ms, zéro appel au modèle.

### D4 — `memoire_lire(sujet)` : la page et ses pistes
Entrée : un nom de sujet ou un alias (tolérant : même cascade). Sortie : les faits de la page par
section, datés, **sans** les métadonnées techniques ; puis **« Pistes »** : pour chaque sujet voisin
(par poids d'arête), **les faits qui ont créé le lien** — la provenance de l'arête *est* la piste.
Lire « Autoplus Valmont » fait apparaître la règle sur Pascal Ménard parce que c'est elle qui relie
les deux pages. Budget ≈ 1 200 tokens, pistes plafonnées. **C'est la « restitution plus fine »
voulue par Francis, dès maintenant** : la mémoire se reconstruit par association, à la lecture.

### D5 — Les outils sont déclarés dès la création du plugin
`get_tool_schemas()` rend toujours les trois schémas (`memoire_noter`, `memoire_chercher`,
`memoire_lire`), initialisé ou non ; `handle_tool_call` répond proprement si la mémoire n'est pas
prête. Test **par le `MemoryManager` d'Hermès** (le chemin de production).

### D6 — Tout ce que la mémoire contient est montré à Nexa
Y compris les faits `personnel` : c'est sa mémoire. La confidentialité est un filtre de **sortie**
(spec §6.6 : jamais vers un tiers), rappelé dans le schéma (D1).

### D7 — Chaque requête est journalisée
`memoire/requetes/<date>.jsonl` : outil, requête, sujets rendus, tokens, latence. Matière de la
télémétrie (étape suivante) et du banc (étape 8).

### D8 — Le rappel à blanc reste un instrument
Inchangé (docs/06) : il continue de mesurer, sans rien injecter.

---

## 4 — Prévisions

| Grandeur | Prévision |
|---|---|
| Latence `memoire_chercher` / `memoire_lire`, mémoire actuelle | < 10 ms |
| Taille d'une réponse | chercher ≈ 150-400 tokens ; lire ≈ 300-1 200 |
| Liste d'acceptation, requêtes courtes type « Autoplus Valmont destinataires facture » | la cascade trouve le bon sujet en tête ≥ 12/12 questions non silencieuses |
| Nexa s'en sert spontanément, une fois le schéma dans AGENTS.md | dès sa prochaine compression (ses consignes se relisent alors) — **à observer, pas à supposer** |

---

## 5 — Ce qui a été construit

| Fichier | Rôle |
|---|---|
| `requete.py` (≈ 200 l.) | `Lecteur.chercher` et `Lecteur.lire` ; journal `memoire/requetes/<date>.jsonl` |
| `rappel.py` | la cascade et la propagation deviennent `Rappeleur.activer()`, **partagée** par le rappel (06) et la requête (07) ; le cache charge aussi les arêtes et leurs preuves (les pistes) ; titres lisibles |
| `graphe.py` | chaque nœud porte un `titre` : son premier alias **français** (« Tarifs de débosselage » et non « Dent Repair Pricing ») |
| `__init__.py` | trois schémas **toujours** déclarés (D5) ; `_requete()` ; un seul cache partagé par le rappel et les outils |

**Deux défauts trouvés par les tests, corrigés** :
1. *« Pascal »* rendait la règle des destinataires avant la fiche de Pascal Ménard : quand un fait
   contient toute la requête, `cab_pull` sature à 1 et l'ordre alphabétique départageait. Départage
   désormais par l'**activation** : le sujet nommé passe devant celui qui partage des mots.
2. La fiche de l'utilisateur montrait « randonnée » à côté du garagiste : pour les fiches implicites
   (utilisateur, agent), seuls les faits **en écho** à la requête sont rendus.

## 6 — Essai sur la mémoire réelle (copie, 27/09) — requêtes courtes, comme Nexa les formulera

| Requête | Résultat |
|---|---|
| « Autoplus Valmont destinataires facture » | Autoplus Valmont *(nommé)*, puis **la règle « Pascal Ménard en copie »** ✓ |
| « tarif porte » | forfait de base, puis **55 € HT** (Autoplus Valmont) ✓ |
| « Claire rappel » | le rappel daté du 16/10 ✓ |
| « chewing-gum rayon » | têtes de gondole ✓ |
| « météo Brest » | rien — message explicite ✓ |
| « rendez-vous mécanicien » | ✗ le fait dit « garagiste » : synonyme — **à Nexa de reformuler**, c'est son rôle |
| `memoire_lire` « Autoplus Valmont » | 8 faits, 4 pistes (Facturation, Pascal Ménard, débosselage, Autoplus Rocheval) ✓ ; « Valmon » ✓ |

**Premier signal, à confirmer au banc (étape 8)** : sur des requêtes courtes, la cascade trouve ce que
les phrases longues lui cachaient (docs/06 §8). La prévision §4 est tenue sur 5 requêtes sur 6 ; le
synonyme est l'échec attendu.

## 7 — Tests

`tests/test_etape_7_requete.py` — **27/27**. Non-régression : 238/238 (un test de l'étape 3 exigeait
un seul outil exposé : adapté, il en existe trois).

1. **Enregistrement par le `MemoryManager` réel d'Hermès** : `add_provider` puis `initialize_all`,
   puis `handle_tool_call` par le manager — les trois outils répondent (non-régression du défaut §2.1).
2. `memoire_chercher` : sujet nommé, alias, mot approché, plein texte, association (« lié à X »),
   rien trouvé → réponse vide explicite ; déterminisme ; budget.
3. `memoire_lire` : par nom, par alias, faute de frappe ; faits par section, datés, sans métadonnées ;
   pistes = faits de provenance des arêtes ; plafond ; sujet inconnu → suggestions.
4. Journal des requêtes.
5. Mémoire non prête → réponse propre, pas d'exception.
6. Non-régression : toutes suites.

---

## 8 — Déploiement — 27/09/2026 ≈ 13h57

1. 0.5.0 sauvegardée (`staging/exia_seed.v0.5-deploye-20260927`) ; 0.6.0 installée ; graphe recalculé.
2. Passerelle relancée en 11 s (Nexa au repos depuis 20 min).
3. **AGENTS.md** : la section « Ta mémoire longue — EXIA SEED » (texte D1, ≈ 160 tokens) ; l'introduction,
   qui disait EXIA SEED « en cours de construction » et renvoyait son savoir vers `knowledge/`, est mise
   en cohérence (« se remplit seule chaque jour ; tes notes de travail restent dans `knowledge/` »).
4. **Rattrapage** : les notes perdues, retrouvées dans `state.db` (les arguments d'appel y sont gardés ;
   11 traces, 3 notes distinctes à cause des rejeux de compression). La note « site vitrine » était déjà
   en mémoire par la consolidation ; les deux autres (organisation Drive des devis et factures ;
   une routine de veille quotidienne) sont réinscrites au registre (`701d9c93`, `1af467b1`,
   source `rattrapage:memoire_noter_perdu`), acceptées par le garde-fou anti-secrets.

**À observer** : AGENTS.md n'est relu qu'à une nouvelle session ou à une compression (constaté le
26/09) ; les outils, eux, sont visibles dès le redémarrage. D'où un message à Francis pour la prévenir.

## 9 — Question ouverte, pour plus tard

Nexa tient aussi **ses propres notes** dans `knowledge/` (≈ 30 fichiers : facturation, courses…) —
un wiki à la Karpathy **écrit par elle**. EXIA SEED est compilé par la consolidation. Deux mémoires
coexistent : faut-il que la FCM indexe aussi `knowledge/`, que la consolidation les ingère, ou les laisser
distinctes (notes de travail d'un côté, mémoire de vie de l'autre) ? **Décision de Francis**, pas tranchée ici.
