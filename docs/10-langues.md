# 10 — Les masques de langue : aucune donnée linguistique dans le code central

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Version :** 1.1 — construit et testé le 1er octobre 2026 (plugin 0.9.0) ; **0.9.1 le 16 octobre 2026** : les apports de la 0.8.1
(docs/11-12) portés dans les masques (§7) — toujours **dépôt de publication seulement** (Nexa reste en 0.8.1, français)
**Statut :** ✅ Fait. **Pas mis en service chez Nexa**, décision de Francis : *« aucun intérêt de mettre en
service pour Nexa, elle est mon assistante personnelle et je suis natif français. Si un jour je suis amené à être
international, on remettra le sujet sur la table. »* Nexa reste en 0.8.0.
**Référence :** EXIA GHOST V2.7.2 `exia/linguistics/` (l'architecture reprise) · `09-protocole-locomo.md` §3
(pourquoi LoCoMo l'exige) · spec EXIA GHOST `05c` §2 (« langues de déploiement déclarées »)
**Origine :** Francis, 01/10 — *« le souci avec notre solution est le hardcoding en langue… On avait intégré un
système de mask avec les langues qui permettait d'être multilingue »* ; *« transférer le hardcoding linguistique
vers des masques de langue est la solution pour nous et elle est éprouvée. Pour le moment on n'a besoin que de
l'anglais et du français. »*

---

## 1 — Le problème

EXIA SEED a été construit pour Nexa, et le français s'était glissé partout : mots vides, jours, mois, « demain »,
nombres en lettres, séparateur de milliers « 12 345 », mots de rôle, formules de consignes (« ne note pas ça »),
consigne de consolidation (« un fait… **en français** »), intitulés des pages, textes rendus au modèle. Sur un banc
anglais (LoCoMo), des questions anglaises auraient cherché dans des faits **français** — injuste pour la FCM et le
plein texte, pas pour des embeddings multilingues.

## 2 — Décisions

| # | Décision | Pourquoi |
|---|---|---|
| D1 | **L'architecture d'EXIA GHOST** : une interface, un masque par langue, un registre (`langues/`) | éprouvée (V2.5.0 → V2.7.2) ; « changer de langue = enregistrer un masque, zéro changement du cœur » |
| D2 | **Élargie** à tout ce qui dépend d'une langue : dates relatives, nombres en lettres, milliers, rôles, consignes de mémoire, consigne de consolidation, intitulés, textes rendus au modèle, schémas d'outils | EXIA GHOST ne masquait que la recherche |
| D3 | **Masque anglais générique, jamais réglé sur un banc** : mots vides = liste anglaise de NLTK ; les ajouts « propres au banc » et les filtres des formules LoCoMo du masque d'EXIA GHOST sont **exclus** | les reprendre serait régler EXIA SEED sur l'examen avant de le passer (docs/09 §5) |
| D4 | **La langue est une propriété de la mémoire** : fichier `.langue`, inscrit à la création ; une mémoire ne change pas de langue (refus explicite) ; une mémoire sans `.langue` mais avec des pages est française (tout ce qui précède la 0.9) | une mémoire consolidée en anglais relue avec le masque français serait silencieusement fausse |
| D5 | **Langue inconnue = refus net**, jamais de repli silencieux | fail-closed |
| D6 | **La langue des faits = la langue du masque** (Nexa : français ; LoCoMo : anglais). Les mots étrangers d'un message restent tels quels dans le fait | décision de Francis : *« ils font partie du contexte »* |
| D7 | **Traçabilité** : `langue: fr/1` dans chaque passage de consolidation (`telemetrie/`) et dans `graphe/rapport.json` | auditabilité : on sait avec quelles règles une mémoire a été faite |
| D8 | **Garde** : un test échoue si une donnée linguistique réapparaît dans le code central | la dérive se ferait sinon une ligne à la fois |
| D9 | **Interlocuteurs** (`interlocuteurs: [...]`, `nom_agent: ""`) : conversation entre personnes, sans agent ; leurs noms sont implicites dans ce qu'ils disent | LoCoMo (deux personnes) ; aussi la future duplication (couple, famille) |
| D10 | **Une seule langue par mémoire** pour l'instant ; le mélange `[fr, en]` (union des masques) plus tard si besoin | simplicité |

**Différence assumée entre les deux masques** : en anglais, un jour cité seul peut désigner le passé (« I went
hiking on Friday ») ; en français, la règle de Francis demeure (« lundi » = le PROCHAIN lundi). Et « last week »
existe en anglais, pas encore « la semaine dernière » en français (l'ajouter changerait le comportement de Nexa).

## 3 — Ce qui a bougé

| Fichier | Avant | Après |
|---|---|---|
| `langues/` (nouveau) | — | `base.py` (interface), `fr.py` (extrait **tel quel** de la 0.8.0), `en.py`, registre, `.langue` |
| `temps.py` | jours, mois, nombres en lettres, « demain », formats | reçoit le masque `m` |
| `consolidation.py` | mots vides, rôles, milliers, consigne entière, index, journal | masque de la mémoire ; `interlocuteurs` ; télémétrie `langue` |
| `consignes.py` | formules françaises | `re_retrait_precedent`, `re_hors_brut`, `re_annonce` du masque |
| `rappel.py`, `graphe.py` | mots vides français ; titre = alias **fr** | mots vides du masque ; titre = alias dans la langue de la mémoire |
| `pages.py` | intitulés « Sémantique »… | intitulés du masque à l'écriture ; ceux de **toutes** les langues reconnus à la lecture |
| `requete.py`, `registre.py`, `ingestion.py`, `__init__.py` | textes rendus au modèle, repères, schémas d'outils (« quand **Francis** dit ») | masque ; schémas au nom de l'utilisateur configuré |

Signatures publiques gardées (`temps.verifier(v, cite, ancre)`, `consignes.detecter(texte)`…) : le masque y est un
paramètre de plus, par défaut celui d'une mémoire sans `.langue` (le français). Le code central le passe toujours.

## 4 — Exceptions déclarées (restent en français)

- les messages **pour l'opérateur** : journal technique, messages des commits git de la mémoire, alertes du graphe ;
- `outils/concepts.py` : le rattrapage des concepts, qui ne sert qu'aux mémoires françaises antérieures à la 0.7 ;
- le marqueur de structure `## Échanges` des fichiers bruts (format de fichier, comme un nom de champ) ;
- la détection des secrets, **déjà bilingue** (« mot de passe », « password », « est », « is ») : inchangée.

## 5 — Preuves

1. **Les 276 tests existants passent sans en toucher un seul.**
2. **Non-régression stricte du français** (`tests/test_langues.py` §C, avec la 0.8.0 de référence montée à côté) :
   même scénario, même modèle factice, même horloge → **consigne envoyée au modèle identique au caractère près
   (4 616 caractères)** ; pages, INDEX, journal, thésaurus, nœuds et arêtes du graphe **identiques octet pour
   octet** ; 5 recherches et une lecture de page identiques ; schémas d'outils identiques. *(Version publique : les noms d'exemple des consignes sont fictifs, le texte et sa longueur diffèrent donc de quelques mots ; la preuve vaut pour le dépôt de travail.)*
3. **Banc 10 rejoué** avec le code porté : **112 recherches réelles sur 112 rendent exactement les mêmes faits**
   qu'en 0.8.0 (0 token dépensé : rien de nouveau à juger).
4. **Anglais de bout en bout** (§B), sur une conversation écrite pour le test — jamais LoCoMo : dates relatives
   (yesterday, last Saturday, on Friday au passé, next week, last week), nombres en lettres, « 1,200 », consignes,
   consolidation entre deux personnes sans agent (un nombre inventé rejeté), pages, index et thésaurus anglais,
   recherche d'une question anglaise.
5. **Le garde mord** : un « lundi » réintroduit dans `requete.py` fait échouer la suite.

**Total : 333 tests sur 333.**

## 6 — Pour ajouter une langue

Un fichier `langues/xx.py` : une sous-classe de `Masque` qui remplit les champs (mots, temps, consignes, textes,
consigne de consolidation, consigne des fiches, schémas d'outils), puis `enregistrer(...)`. Ajouter `xx` au test du registre, et écrire
pour elle une conversation de test comme au §B. Aucun autre fichier ne change.


## 7 — 0.9.1 : les apports de la 0.8.1 dans les masques (16/10/2026)

Fusion à trois voies (base 0.8.0 ; 0.9.0 = masques ; 0.8.1 = production du 16/10, docs/11-12), puis tout texte lu par le
modèle ou par un humain déplacé dans les masques :

| Ajout dans `Masque` | fr (recopié de la 0.8.1) | en |
|---|---|---|
| `consigne_fiches()` | fiche d'identité + mots distinctifs | *IDENTITY SUMMARY* + *DISTINCTIVE WORDS* |
| `textes["souvenirs_entete"]` | « Souvenirs qui remontent avec ce message… » | “Memories rising with this message…” |
| `textes["fiches_pages"]`, `["fiche_alias"]`, `["fiche_actuelle"]`, `["mots_actuels"]` | étiquettes du bloc envoyé au modèle | idem |
| `textes["index"]` | colonne « Ce que c'est (fiche, ou alias) » | “What it is (summary, or aliases)” |
| règle 4 (avec agent) | + les lignes « systeme » = paroles de l'assistant | + « systeme » lines = the assistant's words |

Restent dans le code, comme données de l'HÔTE et non d'une langue : les formes des enveloppes d'Hermès
(`enveloppes.py` — protocole en anglais d'Hermès 0.21.3, quelle que soit la langue de la mémoire) et l'étiquette de
locuteur `systeme` (une étiquette du brut, comme le nom de l'agent).
Défaut trouvé à la relecture de la fusion : les mots distinctifs courts étaient filtrés par les mots vides FRANÇAIS par
défaut au lieu de ceux du masque de la mémoire — corrigé.

**Preuves** : `tests/test_langues.py` avec `REF` = la 0.8.1 de production → **même consigne de consolidation au caractère
près, même consigne des fiches au caractère près, même en-tête des souvenirs, mêmes pages, INDEX, graphe, recherches et
lecture** ; une mémoire anglaise reçoit la consigne des fiches en anglais. 17 suites, 419 contrôles au vert sur la 0.9.1.
Le français de la 0.9.1 EST donc la 0.8.1 de Nexa : les mesures de docs/11-12 valent pour le dépôt. *(Version publique : à l'exception des noms d'exemple des consignes — clients, contacts, lieux — remplacés par des noms fictifs ; seuls ces quelques mots diffèrent.)*
