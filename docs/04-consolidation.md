# 04 — La consolidation : du brut aux pages

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Version :** 1.2
**Date :** 22 septembre 2026
**Statut :** Code, testé (27/27 + revue 23/23 + R2 33/33), 6 passages sur GPT-6 réel ; plugin 0.2.0 déployé le 23/09/2026 à 07h25, **0.3.0 déployé le 26/09/2026 à 17h36**
**Référence :** `SPEC-EXIA-SEED.md` (§6.2 consolidation, §3.2 pages, §4 métadonnées) ·
`02-ecoute-brut.md` et `03-registre.md` (les deux entrées) · `05-graphe.md` (à venir : les nœuds
deviendront un graphe) · *LLM Wiki* d'Andrej Karpathy (l'étape de compilation)
**Origine :** spécification EXIA GHOST `05c_MODULE_MEMOIRE_WIKI.md` §5.2 · cinq décisions de
Francis Babin du 20/09/2026 (déclenchement, oubli, confidentialité, registre, plafond de rappel)
**Changelog 1.3 (27/09) :** règle 12 — les **concepts** du thésaurus (B+, `08-banc-fcm-embeddings.md` §8-10) : 1 à 3 par fragment, concepts existants redonnés au modèle, un concept nouveau n'entre que défini et utilisé ; métadonnée `concepts:` ; thésaurus écrit par la consolidation seule.
**Changelog 1.2 :** révision R2 du 26/09 (détail : `R2-revision-2026-09-26.md`) — la consolidation de la passerelle tourne dans un **processus à part** (D14, D18) ; **le temps des faits** : `dit_le` écrit par le code, `event_time`/`echeance` vérifiés, date en clair (D19, règle 11, §6.1) ; l'horodatage des lignes ne justifie plus aucun chiffre et les nombres en lettres comptent (§5.2).
**Changelog 1.1 :** revue du 23/09 — **D2 corrigée** (justification inexacte) ; lots vides sans appel au modèle (D15) ; verrou git orphelin (D16) ; retraits de l'utilisateur respectés (D17) ; fragments et métadonnées assainis (§6.3) ; le cron journalise ; deux passages réels supplémentaires (§9.3).
**Changelog 1.0 :** première version — prompt, contrôle de citation lexical en remplacement du NLI,
deux défauts trouvés par le modèle réel et corrigés, déploiement.

---

## 1 — Positionnement

### 1.1 L'étape de compilation

C'est le moment où les ingrédients deviennent un plat. Karpathy : *« Avec le RAG, tu cuisines à
chaque fois que tu as faim. »* Ici, on cuisine **une fois**, et la connaissance s'accumule.

```
  brut (conversations)  ─┐
                         ├─►  1 appel LLM  ─►  contrôle déterministe  ─►  pages
  registre (notes)      ─┘         ▲                                        │
                                   │                                        ▼
                     catalogue des nœuds existants  ◄──────────────  INDEX.md, log.md,
                     (pour réutiliser, pas dupliquer)                 chaîne, git
```

### 1.2 Les deux moitiés

| Moitié | Nature | Coût |
|---|---|---|
| Classer, reformuler, nommer les nœuds | **1 appel au modèle** par passage | ≈ 26 000 tokens pour un lot plein |
| Vérifier, écrire, indexer, signer, versionner | **déterministe, zéro appel** | quelques dizaines de ms |

Le modèle propose ; le code dispose. Cette séparation est la raison pour laquelle une mémoire
écrite par un LLM peut rester fiable.

---

## 2 — Le terrain

### 2.1 Appeler le modèle depuis un plugin

Hermès expose `call_llm` (`agent/auxiliary_client.py:7223`) — le même chemin que sa propre
compression d'historique :

```python
call_llm(task="exia_seed_consolidation", provider=…, model=…, messages=[…],
         reasoning_config=parse_reasoning_effort("low"), timeout=300)
```

Résolution de la route (`_resolve_task_provider_model`, ligne 5653) : **arguments explicites >
`auxiliary.<task>` dans la configuration > `auto`**. Une tâche inconnue d'Hermès — la nôtre — tombe
donc sur `auto`, c'est-à-dire la détection automatique d'après les identifiants disponibles.

Le texte de la réponse s'extrait avec `extract_content_or_reasoning(reponse)`, qui gère les modèles
qui répondent dans un champ de raisonnement plutôt que dans le contenu.

### 2.2 Le fil d'arrière-plan

`spawn_context_thread` (`agent/memory_provider.py:29`) :

> *Unstarted thread running target under the spawner's contextvars. Every memory-provider
> background job (prefetch, sync, writer loops) must go through this.*

Les variables de contexte d'Hermès (route du modèle, portée du profil, protections d'interruption)
sont recopiées dans le fil. Un `threading.Thread` nu les perdrait.

### 2.3 Les crons d'Hermès

`hermes cron create <planning> --script <fichier> --no-agent` :

> *Skip the LLM entirely — run --script on schedule and deliver its stdout directly. **Empty stdout
> = silent.***

C'est exactement ce qu'il faut pour une consolidation de fin de journée : **zéro token si tout va
bien**, un message seulement en cas d'anomalie. Le script doit vivre sous `~/.hermes/scripts/`.

Ce script tourne dans un **processus à part**, qui n'hérite pas de la configuration des journaux de
la passerelle. Depuis la revue du 23/09, `outils/consolider.py` appelle
`hermes_logging.setup_logging()` : ses messages rejoignent `agent.log` et `errors.log`.

*(À noter pour plus tard : `--monitor-script` exécute un script à chaque tick et ne réveille
l'agent que si sa sortie a changé. C'est le mécanisme du point du soir « silence gratuit » demandé
par Francis.)*

### 2.4 git

`git` est présent dans l'image officielle d'Hermès (listé parmi les utilitaires système du
Dockerfile). Vérifié dans le conteneur : `/usr/bin/git`, et un commit réel a été produit pendant
les tests.

---

## 3 — Décisions d'architecture

### D1 — Un seul appel au modèle par passage

**Options.** Un appel par fait · un appel par lot · un appel par page à mettre à jour.
**Décision.** Un appel par passage, tous lots et notes confondus, dans la limite du budget.
**Raison.** Le modèle a besoin de **voir l'ensemble** pour décider qu'une information en précise
une autre, et pour réutiliser les bons nœuds. Un appel par fait coûterait dix fois plus et
produirait des nœuds incohérents entre eux.

### D2 — Le fournisseur et le modèle sont passés explicitement

**Contexte.** La route `auto` d'Hermès (`_resolve_auto_route`) résout dans cet ordre : (1) le
fournisseur et le modèle **principaux** de l'agent ; (2) si ceux-ci sont indisponibles, la chaîne
de secours configurée ; (3) à défaut, une chaîne de découverte (OpenRouter, Nous, fournisseurs par
clé d'API…).
**Décision.** Lire `model.provider` et `model.default` dans la configuration, et les passer en
arguments explicites à `call_llm`.
**Raison.** En temps normal, `auto` choisirait exactement la même route. La différence se joue
**quand le fournisseur principal tombe** — quota Codex épuisé, par exemple : `auto` basculerait
alors **en silence** sur une autre chaîne, peut-être un autre abonnement. Avec le fournisseur
explicite, la consolidation **échoue franchement** : le lot reste en attente (D11) et sera repris
quand le quota reviendra. Une mémoire ne doit pas dépenser un autre abonnement à l'insu de son
propriétaire.

> **Correction du 23/09/2026.** La version 1.0 de ce document affirmait que, sans fournisseur
> explicite, une consolidation lancée par le cron « pourrait partir sur l'abonnement Claude ».
> C'était inexact : le code d'Hermès prend d'abord la route principale. La justification ci-dessus
> est la bonne. Voir `R1-revue-2026-09-23.md` §5.

### D3 — Effort de réflexion : `low`

**Raison.** Classer des énoncés et citer des lignes est une tâche mécanique. Mesuré en août 2026
sur l'instance précédente : le raisonnement peut être multiplié par 21 entre deux niveaux d'effort.
**Vérification.** Les trois passages réels sur GPT-6 à `low` ont produit un classement correct,
y compris sur les cas subtils (une proposition de l'agent confirmée par l'utilisateur).

### D4 — Un contrôle de citation lexical remplace la vérification NLI

**Contexte.** La spécification EXIA GHOST prévoit une vérification par modèle d'inférence
(NLI cross-encoder) entre le fait consolidé et sa source.
**Contrainte.** L'instance n'a pas ce modèle, et on refuse de l'installer : plusieurs centaines de
Mo, un chargement au démarrage, pour une instance qui tourne sur un VPS partagé.
**Décision.** Un contrôle **déterministe et lexical**, plus strict que ce que la spec demandait
sur les points vérifiables : nombres, noms propres, recouvrement de vocabulaire, et provenance.
**Compromis assumé.** Un garde-fou lexical ne comprend pas le sens : une affirmation fausse
formulée avec les mots de la source peut passer ; une reformulation fidèle mais très éloignée
lexicalement peut être rejetée. Le second cas est le moins grave (on perd un fait, on ne le fausse
pas), et il est mesuré (compteur `fragments_rejetes`).

### D5 — Le nom de l'utilisateur et celui de l'agent sont toujours « connus »

**Défaut trouvé par le modèle réel, 22/09.** Le fragment *« Une contrainte personnelle demande
à **Francis** de regrouper les visites de garages le matin »* a été rejeté : « Francis » n'apparaissait pas dans la
note du registre citée. **Un fait important était perdu.**
**Raison du défaut.** Le nom de l'utilisateur est implicite dans tout ce qu'il dit : il ne se
présente pas à chaque phrase.
**Décision.** Les noms configurés (`nom_utilisateur`, `nom_agent`) sont exclus du contrôle des noms
propres.

### D6 — Une règle de rattachement dynamique, et précise

**Première version (22/09, matin).** *« Ce qui concerne sa personne se rattache à son nœud. »*
**Résultat mesuré.** Tout partait sur la fiche de l'utilisateur : ses tarifs, ses relances, et même
la consigne « arrête les listes à puces » — qui concerne le comportement de l'agent, pas lui.
**Version retenue.** Sa **santé**, sa **famille**, ses **contraintes et habitudes personnelles**
vont sur son nœud ; ses tarifs, ses clients, ses projets ont **leurs propres nœuds** ; une consigne
de comportement donnée à l'agent est un nœud de type `etat_agent`.
**Vérification.** Au passage suivant : 10 faits, 0 rejet, et cinq nœuds correctement typés.

### D7 — Les pages sont mutables ; l'historique est dans git

**Contexte.** Le brut est immuable. Les pages, non : une page se complète, se corrige, s'enrichit.
**Décision.** Réécriture complète du fichier à chaque consolidation, et `git commit` par passage.
**Raison.** Une page est une **vue compilée**, pas une source. Sa vérité est dans le brut. Ce qu'il
faut garder, c'est l'historique de ses états — c'est précisément le métier de git.
**Conséquence.** `git log -p pages/autoplus-rocheval.md` répond à « que savait-elle le 22 septembre ? ».

### D8 — L'avancement se note dans des journaux séparés

**Décision.** `raw/.consolide.jsonl` (lots traités) et `registre.integre.jsonl` (notes rangées),
tous deux en ajout seul.
**Raison.** Marquer un lot « consolidé » dans `raw/.chaine.jsonl` exigerait de **réécrire une ligne
de la chaîne d'intégrité** — exactement ce qu'une chaîne d'intégrité interdit.

### D9 — Un alias rattache au nœud existant

**Décision.** Avant de créer un nœud, on cherche le nom proposé — et ses alias — parmi les nœuds
existants, en forme normalisée.
**Exemple vérifié.** Le modèle propose `garage_de_rocheval` ; la page `autoplus_rocheval` porte l'alias
« garage de Rocheval » : le fait rejoint la page existante. **Aucun doublon de nœud.**
**Raison.** Sans cela, la mémoire se fragmente en synonymes, et le graphe (étape 5) perd tout son
intérêt : deux nœuds pour une même chose ne s'activent jamais ensemble.

### D10 — L'écriture est idempotente

**Décision.** Un fait déjà présent dans une section (comparaison normalisée) n'est pas réécrit.
**Raison.** Si un lot est repris après un échec, ou si le modèle redit deux fois la même chose, la
page ne doit pas se remplir de doublons.

### D11 — Une réponse illisible laisse le lot en attente

**Décision.** Si le JSON ne se lit pas, on journalise `echec_json` **sans marquer les lots comme
consolidés**.
**Raison.** Un échec de format est transitoire. Le lot sera repris au passage suivant, sans
intervention. Vérifié par test.

### D12 — Verrou non bloquant : jamais deux consolidations à la fois

**Décision.** `flock` en mode non bloquant ; si une consolidation tourne, la seconde rend
`deja_en_cours` immédiatement.
**Raison.** Deux consolidations simultanées écriraient les mêmes pages. Et comme les lots restent
en attente tant qu'ils ne sont pas traités, rien n'est perdu : le prochain passage les reprend.

### D13 — Un budget d'entrée, et le reste au prochain passage

**Décision.** 40 000 tokens estimés par passage ; les lots qui dépassent attendent.
**Raison.** Borne le coût d'un passage et la latence. Un premier passage après une longue absence
ne doit pas envoyer 300 000 tokens d'un coup.

### D14 — Deux déclencheurs, dont un silencieux

| Déclencheur | Mécanisme | Coût si rien à faire |
|---|---|---|
| Un lot se ferme | fil d'arrière-plan lancé par le fournisseur, qui lance **un processus à part** (D18) | — (ne se déclenche que s'il y a un lot) |
| Fin de journée, 23h55 Paris | cron Hermès `--no-agent` + script | **zéro token, zéro message** |

---

### D18 — La consolidation de la passerelle tourne dans un processus à part *(R2, 26/09)*

Le fil d'arrière-plan ne fait plus l'appel au modèle : il lance `outils/consolider.py` — le chemin du
cron. **Raison** : dans la passerelle, le client auxiliaire d'Hermès 0.21.3 relançait après un 401
avec un jeton périmé ; 8 échecs sur 8 du 24 au 26/09, alors que le cron, processus neuf, réussissait
(R2 §3.1). **Écarté** : appeler sans fournisseur explicite (le chemin « auto » marchait pour la
compression) — mais hors passerelle, « auto » pourrait choisir un autre abonnement, ce que D2
interdit ; corriger Hermès — pas notre code. Délai borné à 900 s ; le verrou D12 empêche tout
chevauchement.

### D19 — Le temps des faits : trois moments, trois responsables *(R2, 26/09)*

`dit_le` (quand la phrase a été dite) est écrit **par le code** depuis la première source citée ;
`event_time` (quand la chose arrive) et `echeance` sont **proposés par le modèle et vérifiés par le
code** (`temps.py`, symbolique, < 1 ms, fail-closed : une date injustifiée est retirée, le fait
gardé). Le modèle garde les mots de l'utilisateur ; le code ajoute la date en clair. **Raison** :
« lundi » n'a de sens que rapporté au moment où on le dit ; les modèles calculent mal un jour de
semaine. Règle de Francis : un jour cité sans date = le **prochain** de ce nom. Détail et
vérifications : R2 §3.2.

### D15 — Un lot sans conversation ne coûte aucun appel

**Revue du 23/09 (défaut C).** Un lot peut ne contenir que des repères : consigne « ne note pas
ça », repère de compression, ou lignes toutes retirées. La fermeture forcée de 23h55 pouvait en
produire. La version 1.0 appelait quand même le modèle, avec une liste de sources vide.
**Décision.** Si aucune ligne de conversation ni aucune note n'est à consolider, les lots sont
marqués traités (`lot: vide` dans `raw/.consolide.jsonl`), le passage est journalisé avec le statut
`vide`, et **aucun appel n'est fait**. Le cron reste silencieux sur ce statut.

### D16 — Un verrou git orphelin est retiré

**Revue du 23/09 (défaut E).** Un redémarrage de la passerelle pendant un `git commit` laisse
`.git/index.lock`. Tous les commits suivants échouaient alors — en silence, puisque l'échec git ne
fait pas échouer la consolidation.
**Décision.** Avant chaque commit, un `index.lock` vieux de plus de dix minutes est retiré. Aucun
commit légitime de la mémoire ne dure aussi longtemps ; un verrou récent est respecté.

### D17 — Les retraits de l'utilisateur sont respectés

Le lecteur de lots exclut les lignes inscrites dans `raw/.retraits.jsonl` (annexe A2, D3-D5). Ces
lignes restent dans leur fichier — un lot fermé n'est jamais modifié — mais ne sont jamais montrées
au modèle. Vérifié sur GPT-6 réel le 23/09 : deux confidences retirées, aucune dans les pages.

## 4 — Le prompt

### 4.1 Ce que le modèle reçoit

```
SYSTÈME : 11 règles + (si configuré) la règle de rattachement à l'utilisateur
UTILISATEUR :
    NŒUDS EXISTANTS
    - autoplus_rocheval (entite) : Autoplus Rocheval, garage de Rocheval
    - tarifs (concept) : tarifs, prix
    SOURCES
    ── raw/2026-09-22_01.md : conversation du mardi 22 septembre 2026 (heure de Paris)
    [raw/2026-09-22_01.md:11] [19:11 francis] Demain je passe chez Autoplus Rocheval…
    [raw/2026-09-22_01.md:12] [19:11 nexa] Très bien. Veux-tu que je prépare la visite ?
    [registre:7807d69e] (normal) Le chef d'atelier d'Autoplus Rocheval s'appelle Olivier.
```

Chaque ligne porte **sa référence exacte**, qui est aussi la forme attendue dans les citations. Le
numéro est le **numéro réel de la ligne dans le fichier**, pas un rang dans l'extrait : une
citation reste vérifiable indéfiniment. La ligne `──` qui ouvre chaque lot donne sa date et son jour
de semaine *(R2)* ; sans crochets, elle ne peut pas être citée.

### 4.2 Les onze règles, et leur raison d'être

| # | Règle | Ce qu'elle empêche |
|---|---|---|
| 1 | Un fait autonome, sans formule de politesse | des fragments incompréhensibles hors contexte |
| 2 | Citer ses sources ; nombres, dates et noms doivent y figurer | l'invention |
| 3 | Ne retenir que ce qui servira plus tard | une mémoire noyée sous le bavardage |
| 4 | **Ce que l'agent a dit n'est retenu que si l'utilisateur l'a confirmé** | que l'agent se convainque lui-même |
| 5 | Quatre sections typées | un tout-venant sans rythme d'oubli |
| 6 | Réutiliser un nœud existant, sinon en créer un avec alias fr et en | la fragmentation en synonymes |
| 7 | Un événement ordinaire ne crée pas de nœud | l'explosion du graphe |
| 8 | Confidentialité explicite | qu'une information sensible sorte de la conversation |
| 9 | `protected` réservé aux événements de vie | qu'un déclin efface un anniversaire |
| 10 | Confiance graduée : affirmé 1,0 · supposé 0,7 · déduit 0,5 | qu'une déduction pèse autant qu'un fait |
| 11 | **Dates** *(R2)* : `event_time` = quand la chose arrive, `echeance` = la limite ; un jour de semaine = le prochain ; garder les mots de l'utilisateur | « lundi » sans date, et la date de la conversation prise pour celle de l'événement |

### 4.3 Format de sortie

```json
{"fragments": [{"noeud": "autoplus_rocheval", "nouveau": false, "type_noeud": "entite",
  "alias": {"fr": [], "en": []}, "section": "semantic",
  "fait": "Le chef d'atelier d'Autoplus Rocheval s'appelle Olivier.",
  "src": ["raw/2026-09-22_01.md:11", "raw/2026-09-22_01.md:13"],
  "conf": 1.0, "event_time": null, "echeance": null, "speaker": "francis",
  "privacy": "normal", "protected": false}]}
```

L'extraction accepte un JSON entouré de texte ou de balises de code : on prend du premier `{` au
dernier `}`. Tolérance volontaire : un modèle qui commente sa réponse ne doit pas faire perdre un
lot.

---

## 5 — Le contrôle de citation

### 5.1 Les cinq règles

| Règle | Rejet si… | Ce qu'elle protège |
|---|---|---|
| **Provenance** | aucune source citée, ou une source absente de ce qu'on a envoyé | invention pure, hallucination de fichier |
| **Nombres** | un nombre du fait n'apparaît pas dans les lignes citées | tarifs, montants, SIRET, dates chiffrées |
| **Noms propres** | un nom propre du fait n'apparaît pas dans les lignes citées | interlocuteurs et entreprises inventés |
| **Vocabulaire** | moins de 40 % des mots pleins du fait ont une racine commune avec la source | la paraphrase qui dérive |
| **Origine humaine** | toutes les lignes citées sont des paroles de l'agent | l'agent qui se cite lui-même |

### 5.2 Détails d'implémentation

- **Mots pleins** : mots de 3 lettres ou plus, ou nombres, hors liste de mots vides français et
  anglais (≈ 90 mots).
- **Racine** : les cinq premiers caractères. Assez pour rapprocher « grêlées » et « grêlés », trop
  court pour rapprocher deux mots différents dans une phrase courte — le seuil de 40 % compense.
- **Minimum absolu** : 1 mot commun si le fait compte 3 mots pleins ou moins, 2 sinon.
- **Noms propres** : mots capitalisés de 3 lettres ou plus, **hors premier mot d'une phrase** (qui
  est capitalisé par grammaire, pas par nature).
- **Horodatage exclu** *(R2)* : `[HH:MM locuteur]` est retiré des lignes citées avant tout contrôle.
  Jusqu'au 26/09, un chiffre inventé passait s'il tombait sur l'heure ou la minute de la ligne
  (« 55 € » inventé, ligne dite à 16h55).
- **Nombres en lettres** *(R2)* : « huit », « dix-huit », « trente », « midi »… comptent comme leurs
  chiffres. Un fait vrai (« de 8 h à 18 h » pour « à partir de huit heures ») était rejeté le 25/09.
- **Plage de lignes** : `raw/x.md:12-14` est déplié en trois références ; une plage de plus de
  50 lignes est refusée (citation trop vague pour vérifier quoi que ce soit).

### 5.3 Ce qu'il n'attrape pas

- Une **affirmation fausse composée avec les mots de la source** : « Olivier n'est plus chef
  d'atelier » passe si « Olivier » et « chef d'atelier » sont dans la ligne citée. C'est la limite
  d'un contrôle lexical ; la supersession (phase 3) et la confiance graduée l'atténuent.
- Une **attribution erronée** : un fait vrai rattaché au mauvais nœud.
- Un **contresens de section** : un fait durable classé en épisodique.

Ces trois angles morts sont assumés, et mesurés indirectement : ils se verraient dans le rappel.

---

## 6 — L'écriture des pages

### 6.1 Format

```markdown
---
node: autoplus_rocheval
node_type: entite
aliases: {fr: [Autoplus Rocheval, garage de Rocheval], en: [Autoplus Rocheval]}
created: '2026-09-22'
updated: '2026-09-22'
consolidated_from: [raw/2026-09-22_01.md, registre:7807d69e]
consolidation_model: gpt-6-astra
strength: 1.0
---

# Autoplus Rocheval

## Sémantique
- Le chef d'atelier d'Autoplus Rocheval s'appelle Olivier. <!-- conf:1.0 src:raw/…:11,raw/…:13 dit_le:2026-09-22T19:11 speaker:francis lot:2026-09-22_192832 -->

## Procédural
- Les visites doivent se faire le matin : l'atelier est débordé l'après-midi. <!-- conf:1.0 src:… -->

## Prospectif
- Passer chez Autoplus Rocheval demain matin pour 3 voitures grêlées (échéance : mercredi 23/09/2026). <!-- conf:1.0 src:… dit_le:2026-09-22T19:11 echeance:2026-09-23 -->
```

Le fait est lisible ; les métadonnées vivent dans le commentaire. C'est l'application concrète du
principe §4.7 de la spec : **le moteur voit tout, le lecteur voit le fait**.

*(R2)* Une exception volontaire : la **date vérifiée** d'un fait est aussi écrite en clair dans le
texte (« (→ lundi 28/09/2026 à 16h45) »), parce que « lundi » seul ne se lit plus au bout d'une
semaine. `dit_le` figure sur **tous** les faits ; les 68 faits antérieurs à R2 l'ont reçu par
`outils/ancrer.py` (R2 §7).

### 6.2 Les quatre sections et leurs rythmes

| Section | Contenu | Oubli (τ) |
|---|---|---|
| Sémantique | faits durables | 30 jours |
| Épisodique | ce qui s'est passé, daté | 7 jours |
| Procédural | règles de conduite | 90 jours |
| Prospectif | intentions, échéances | jusqu'à l'échéance |

Les durées sont celles validées par Francis le 20/09, à recalibrer à l'usage. L'oubli lui-même est
l'étape 7.

### 6.3 Mise à jour d'une page

1. Chargement : en-tête YAML + sections existantes.
2. Rattachement du nœud proposé (D9) ; fusion des alias, sans doublon.
3. **Assainissement** (revue du 23/09, défaut D) : le fait est ramené sur une seule ligne, les
   séquences `<!--` et `-->` sont neutralisées, et les valeurs de métadonnées perdent leurs espaces
   (`speaker:Francis Babin` → `speaker:Francis_Babin`). Sans cela, un « --> » dans le texte fermait
   le commentaire trop tôt, et la phase 2 n'aurait pas pu relire les métadonnées sans ambiguïté.
4. Ajout du fragment **si absent** (D10).
5. `updated` à la date du jour ; `consolidated_from` complété des nouvelles sources.
6. Réécriture atomique (fichier temporaire puis remplacement).

---

## 7 — Index, journal, chaîne, git

| Fichier | Nature | Rôle |
|---|---|---|
| `INDEX.md` | régénéré | catalogue lisible : nœud, type, alias, nombre de faits par section, date. Filet de secours du rappel au démarrage à froid |
| `log.md` | ajout seul | une entrée par passage : sources, faits retenus, nœuds créés, **et chaque rejet avec sa raison** |
| `pages/.chaine.jsonl` | ajout seul | empreinte de l'ensemble des pages après chaque passage, chaînée |
| `.git/` | historique | un commit par passage : `consolidation <lot> — N faits, M nouveaux nœuds` |

Le journal des rejets est important : c'est là qu'on verra, avec le temps, si le modèle dérive ou
si le contrôle est trop strict.

---

## 8 — Cycle complet

```
un lot se ferme (étape 2)
   └─► le fournisseur lance un fil       ← rend la main en ~3 ms
          │
          ├─ verrou non bloquant (D12) — sinon « déjà en cours », on repassera
          ├─ sélection des lots + notes dans le budget (D13)
          ├─ construction du prompt (catalogue de nœuds + sources numérotées)
          ├─ 1 appel au modèle (D1, D2, D3)                    ← ≈ 40 s
          ├─ extraction du JSON  ──► illisible ? statut echec_json, lots conservés (D11)
          ├─ contrôle de citation, fragment par fragment (§5)
          ├─ écriture des pages (§6)
          ├─ journaux d'avancement (D8), INDEX.md, log.md, chaîne, git (§7)
          └─ une ligne dans telemetrie/consolidations.jsonl
```

---

## 9 — Mesures

### 9.1 Trois passages sur GPT-6 Astra réel

Conversation de test : une visite prévue, un chef d'atelier, deux tarifs, une remarque sur la
météo, une relance proposée par l'agent puis confirmée, une consigne de style, une note
confidentielle.

| Passage | Faits | Rejets | Durée | Entrée ≈ | Sortie ≈ | Constat |
|---|---|---|---|---|---|---|
| 1 | 8 | 0 | 44,9 s | 980 | 1 036 | juste, mais la contrainte personnelle forme un nœud isolé |
| 2 | 9 | 1 | 37,9 s | 1 031 | 842 | règle de rattachement trop forte ; **contrainte personnelle rejetée** |
| 3 | **10** | **0** | 38,8 s | 1 073 | 933 | tout est juste |

**Ce que le modèle a fait de lui-même** : ignoré la météo ; classé « passer le matin » en règle et
la visite du lendemain en intention datée ; retenu la relance de mars **seulement parce que
l'utilisateur a dit « oui »**, en citant les deux lignes ; typé « arrête les listes à puces » en
`etat_agent` ; conservé la confidentialité de la note personnelle.

### 9.2 Coût attendu en service

| | |
|---|---|
| Conversation réelle mesurée | ≈ 9 500 tokens / jour |
| Passages de consolidation | **1 par jour** (fin de journée) |
| Entrée par passage | ≈ 10 000 à 26 000 tokens selon le remplissage |
| Sortie par passage | ≈ 1 000 tokens |
| Latence | ≈ 40 s, **en arrière-plan** |

---

### 9.3 Deux passages supplémentaires — revue du 23/09

Conversation : un rendez-vous et un chef d'atelier, **une première confidence suivie de « ne note
pas ça, c'est personnel »**, un tarif grêle, **une seconde confidence suivie de « oublie ce que je
viens de dire »**, une relance à programmer.

| Version | Faits | Confidences dans les pages | Tarif grêle | Durée | Entrée ≈ | Sortie ≈ |
|---|---|---|---|---|---|---|
| 0.2 avant correction G | 3 | aucune | **absent** | 17 s | 872 | 271 |
| **0.2.0 finale** | **4** | **aucune** | **présent** | 18 s | 840 | 368 |

Le premier passage a révélé le défaut G (annexe A2, D7) : la demande « oublie ce que je viens de
dire », écrite dans le brut, apparaissait au modèle juste après le tarif — le tour retiré étant
caché — et le modèle a écarté le tarif. Ce passage est le **cinquième** sur le vrai modèle, et le
**troisième** à révéler un défaut que les tests factices n'avaient pas vu.

## 10 — Tests

### 10.1 Modèle factice — 25 tests

Le modèle factice renvoie cinq faits justes et **quatre pièges** :

| Piège | Rejeté pour |
|---|---|
| « Le tarif est de **55 €** pour un élément seul » (source : « 45 € ») | nombre absent des sources : 55 |
| « Le directeur s'appelle **Martin** » | nom propre absent des sources : Martin |
| « Relancer en avril » — proposé par l'agent, jamais confirmé | repose seulement sur des paroles de l'agent |
| Source `raw/inexistant.md:3` | aucune source valide citée |

Également vérifiés : trois pages créées avec les bonnes sections · la confidentialité portée
jusqu'à la page · `INDEX.md` régénéré · `log.md` expliquant chaque rejet · le lot marqué consolidé ·
la note du registre intégrée · la chaîne des pages amorcée sur `genese` · un commit git ·
le rattachement par alias sans doublon de nœud · « rien à faire » sans aucun appel · réponse
illisible → lot conservé · déclenchement en arrière-plan rendant la main en 3 ms · reprise
automatique du lot précédemment échoué · une ligne de télémétrie par passage.

**25 réussis sur 25.** Script : `tests/test_etape_4_consolidation.py`.

### 10.2 Non-régression

Après les deux correctifs du §11, la suite complète a été rejouée : **25/25**.

### 10.3 Revue du 23/09

`tests/test_revue_20260923.py` — 23 tests, dont pour la consolidation : lot vide sans appel (D15),
verrou git orphelin (D16), retraits exclus y compris à travers une fermeture de lot (D17),
assainissement des fragments (§6.3). **Chaque défaut a d'abord été reproduit sur la version 0.1**,
puis prouvé corrigé. Toutes séries confondues : **115 tests**, tous au vert.

### 10.4 Révision R2 du 26/09

`tests/test_R2_temps.py` — 33 tests (le calcul des dates, une consolidation complète, l'horodatage,
les nombres en lettres, les lignes de suite). Deux tests de `test_etape_4` réécrits parce que le
comportement a changé à dessein (R2 §6). Le banc lui-même est désormais dans le dépôt :
`sh tests/banc.sh`. Toutes séries confondues : **150 tests**, tous au vert.

---

## 11 — Deux défauts trouvés par le modèle réel

Les tests factices étaient tous au vert quand ces deux défauts existaient encore. **Seul un passage
sur le vrai modèle les a révélés.**

### 11.1 Un fait personnel perdu

- **Symptôme.** Passage 2 : 1 rejet — *« nom propre absent des sources : Francis »*.
- **Cause.** Le modèle avait écrit « demande à **Francis** de regrouper les visites » ; la note du registre
  disait « regrouper les visites de garages le matin », sans le prénom.
- **Gravité.** Élevée : un fait **confidentiel et durable** était silencieusement jeté. Dans une
  mémoire, un rejet injustifié est aussi grave qu'une invention.
- **Correctif.** D5 — les noms de l'utilisateur et de l'agent sont toujours considérés comme connus.
- **Preuve.** Passage 3 : la contrainte est acceptée, rangée dans `francis.md`, marquée
  `privacy:confidentiel`.

### 11.2 Une fiche devenue fourre-tout

- **Symptôme.** Passage 2 : tarifs, relances et consigne de style, tous rangés sur la fiche de
  l'utilisateur.
- **Cause.** Ma règle de rattachement, écrite trop large : « ce qui concerne sa personne ».
- **Gravité.** Moyenne, mais structurante : une fiche fourre-tout ruine le routage du graphe —
  un nœud qui s'active pour tout n'informe sur rien.
- **Correctif.** D6 — santé, famille, contraintes personnelles seulement ; tarifs, clients et
  projets ont leurs propres nœuds ; le comportement de l'agent est un `etat_agent`.
- **Preuve.** Passage 3 : cinq nœuds, correctement séparés et typés.

**Leçon consignée** : un jeu de tests factices valide la mécanique, jamais le jugement. Toute étape
qui fait intervenir un modèle se termine par un passage sur le modèle réel.

---

## 12 — Déploiement

```yaml
memory:
  provider: exia_seed
  exia_seed: {nom_utilisateur: francis, nom_agent: nexa, phase: 1}
```

- `hermes memory status` → *Plugin installed ✓ · Status available ✓ · exia_seed ← active*
- Cron `af65b68a0d29` : `55 23 * * *` (Paris), `--no-agent`, script `exia_seed_consolider.sh`
- Essai à vide dans l'environnement réel : `{"statut": "rien"}`
- **Version 0.3.0 déployée le 26/09/2026 à 17h36** (R2 §8) ; 0.2.0 conservée dans `staging/exia_seed.v0.2-deploye-20260926`
- **Version 0.2.0 déployée le 23/09/2026 à 07h25** après la revue ; passerelle redémarrée en 20 s ;
  version 0.1 conservée dans `staging/exia_seed.v0.1-deploye-20260922`
- **Retour arrière** : retirer les deux lignes du bloc `memory`, redémarrer la passerelle.
  Sauvegarde : `backups/config/config.yaml.avant-exia-seed-20260922_173239`

---

## 13 — Limites connues

1. **Contrôle lexical** (§5.3) : trois angles morts assumés.
2. **Granularité des nœuds** : elle dépend du jugement du modèle. À observer sur les vraies
   conversations ; le prompt pourra se préciser.
3. **Latence ≈ 40 s** : acceptable seulement parce que la consolidation tourne en arrière-plan.
4. **Pas encore de graphe** : les nœuds existent comme pages, sans liens entre eux. C'est l'étape 5.
5. **Pas encore de supersession** : deux faits contradictoires coexistent dans la page. Le rappel
   tranchera par récence (phase 2), la supersession explicite viendra en phase 3.
6. **Les pages ne sont pas encore relues** par l'agent : c'est le rappel (étape 6) et la phase 2.
7. **Dates** *(R2)* : « lundi en huit », « dans trois jours », « fin du mois » ne sont pas vérifiables
   symboliquement ; la date proposée est retirée, le fait reste ancré par `dit_le` (R2 §9).

---

## 14 — Invariants respectés

| Invariant | Comment |
|---|---|
| 1. Le brut est sacré | la consolidation lit le brut, ne l'écrit ni ne le modifie jamais |
| 2. Le rappel ne coûte aucun appel | la consolidation en coûte un, mais **hors du chemin de réponse** |
| 3. Le moteur voit tout, le modèle reçoit peu | les métadonnées restent dans les commentaires des pages |
| 4. Panne = dégradation | échec JSON, verrou occupé, modèle indisponible : les lots attendent |
| 5. Rien hors de `/opt/data` | pages, journaux, dépôt git, télémétrie |
| 6. Oubli gracieux | rien n'est supprimé : un lot consolidé reste, une note intégrée reste |
