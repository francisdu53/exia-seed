# 01 — Le squelette : greffe d'EXIA SEED sur Hermès

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Version :** 1.1
**Date :** 22 septembre 2026
**Statut :** Code, testé (115 tests au total, toutes séries), déployé chez Nexa — plugin 0.2.0 le 23/09/2026 à 07h25
**Référence :** `SPEC-EXIA-SEED.md` (§7 la greffe, §2 invariants) · `02-ecoute-brut.md` · Hermès
Agent v2026.9.14 (0.21.3), fichiers `agent/memory_provider.py`, `plugins/memory/__init__.py`,
`agent/memory_manager.py`, `agent/turn_context.py`
**Origine :** décision de Francis Babin du 15/09/2026 (« feuille blanche », greffe d'un système
mémoriel sur Hermès sans SYNAPSE ni HEIMDALL) · nom **EXIA SEED** arrêté le 20/09/2026 ·
publication open source décidée le 22/09/2026
**Changelog 1.1 :** revue du 23/09 (`R1-revue-2026-09-23.md`) — chemin de production vérifié (crochets, outil exposé sur Telegram, journaux) ; `plugin.yaml` est informatif, liste complétée ; arborescence et mesures mises à jour (10 modules, 1 485 lignes) ; le cron journalise désormais.
**Changelog 1.0 :** première version — contrat vérifié dans le code d'Hermès 0.21.3, sept
décisions d'architecture, plugin construit, testé et déployé.

---

## 1 — Positionnement

### 1.1 Ce que le squelette est

Le squelette est **la partie d'EXIA SEED qui parle à Hermès**. Il ne mémorise rien, ne consolide
rien, ne rappelle rien. Il fait trois choses : se faire découvrir, se faire activer, et recevoir
les événements de la conversation pour les passer aux couches qui travaillent.

```
        ┌──────────────────────── HERMÈS AGENT 0.21.3 ────────────────────────┐
        │  passerelle Telegram · boucle d'agent · compression · crons         │
        │                                                                     │
        │     MemoryManager ──┬── mémoire native (MEMORY.md / USER.md)        │
        │                     │                                               │
        └─────────────────────┼───────────────────────────────────────────────┘
                              │  contrat MemoryProvider (4 méthodes + 18 crochets)
        ┌─────────────────────▼───────────────────────────────────────────────┐
        │  EXIA SEED — plugin utilisateur /opt/data/plugins/exia_seed/        │
        │                                                                     │
        │   ┌── LE SQUELETTE (ce document) ──────────────────────────────┐    │
        │   │  __init__.py   ExiaSeedProvider + register(ctx)            │    │
        │   │  config.py     réglages et défauts                         │    │
        │   │  util.py       temps, hachage, verrou, écriture atomique   │    │
        │   │  plugin.yaml   manifeste                                   │    │
        │   └───────────────┬──────────────┬──────────────┬──────────────┘    │
        │        ingestion.py    registre.py    consolidation.py + pages.py   │
        │         (étape 2)       (étape 3)            (étape 4)              │
        └─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼   /opt/data/memoire/  — brut, registre, pages, graphe
```

### 1.2 Ce qu'il ne fait pas

- Il ne modifie **rien** d'Hermès : pas de correctif, pas de surcharge, pas de fichier touché dans
  `/opt/hermes` — qui est d'ailleurs en lecture seule dans l'image officielle.
- Il n'injecte **rien** dans le contexte de l'agent en phase 1 : `prefetch()` et
  `system_prompt_block()` rendent une chaîne vide.
- Il ne décide pas de ce qui est mémorisé : cette décision appartient à la consolidation (étape 4).

---

## 2 — Le terrain : le contrat d'Hermès, vérifié dans le code

Tout ce qui suit a été lu dans le code source de la version installée, pas dans une documentation.

### 2.1 Découverte des plugins

`plugins/memory/__init__.py`, en-tête du module :

> *Memory provider plugin discovery: bundled `plugins/memory/<name>/`, user
> `$HERMES_HOME/plugins/<name>/`, project `./.hermes/plugins/<name>/` (opt-in via
> HERMES_ENABLE_PROJECT_PLUGINS), then `hermes_agent.memory_providers` entry points.*

Trois sources, dans cet ordre de précédence — **les fournisseurs livrés avec Hermès gagnent**, puis
l'utilisateur, puis le projet. Le commentaire du code précise pourquoi : un dossier déposé dans un
répertoire de travail ne doit jamais pouvoir masquer un fournisseur officiel.

Un dossier est reconnu par une heuristique **textuelle**, sans import (`_is_memory_provider_dir`,
ligne 62) : son `__init__.py` doit contenir `register_memory_provider` ou `MemoryProvider` dans ses
8 premiers kilo-octets. C'est volontairement grossier : Hermès ne veut pas importer du code
arbitraire pour savoir s'il s'agit d'un plugin.

**Conséquence pour EXIA SEED** : le plugin vit dans `$HERMES_HOME/plugins/exia_seed/`, soit
`/opt/data/plugins/exia_seed/` dans le conteneur. Il est donc **dans le volume de données** : il
survit à une mise à jour de l'image, il est inclus dans les sauvegardes, et il se copie avec
l'instance lors d'une duplication.

### 2.2 Activation

Un seul fournisseur externe peut être actif à la fois. Il est désigné par son **nom de dossier**
dans `config.yaml` :

```yaml
memory:
  provider: exia_seed
```

Vérification après déploiement (`hermes memory status`) :

```
  Provider:  exia_seed
  Plugin:    installed ✓
  Status:    available ✓
    • exia_seed  (no setup needed) ← active
```

### 2.3 Enregistrement

`_load_provider_from_dir` (ligne 261) importe le module puis cherche, dans l'ordre :

1. une fonction `register(ctx)` — le chemin officiel ;
2. à défaut, une sous-classe de `MemoryProvider` au niveau du module (`_instantiate_subclass`).

EXIA SEED utilise le premier :

```python
def register(ctx) -> None:
    ctx.register_memory_provider(ExiaSeedProvider())
```

Le commentaire du code d'Hermès signale un piège intéressant : si `register()` lève une exception
**après** avoir enregistré le fournisseur, Hermès garde le fournisseur enregistré plutôt que de
retomber sur la recherche de sous-classe — qui rendrait une seconde instance vierge, « un
downgrade silencieux qui ressemble à un succès ».

**Le manifeste `plugin.yaml` est informatif.** Vérifié le 23/09 dans `plugins/memory/__init__.py` : son
champ `hooks` ne filtre aucun appel — Hermès appelle tout crochet que la classe implémente. Le
fournisseur livré `byterover` n'y déclare d'ailleurs que `on_pre_compress` tout en implémentant les
autres. Notre liste est tenue complète pour la lisibilité, pas pour le fonctionnement.

### 2.4 Le contrat

Quatre méthodes obligatoires, dix-huit crochets optionnels (`agent/memory_provider.py`, classe
`MemoryProvider`, ligne 75).

| Méthode | Obligatoire | Usage dans EXIA SEED | Phase |
|---|---|---|---|
| `name` | ✓ | `"exia_seed"` | 1 |
| `is_available()` | ✓ | toujours vrai — aucune dépendance, aucun réseau | 1 |
| `initialize(session_id, **kwargs)` | ✓ | chemins, réglages, mode écriture selon le contexte | 1 |
| `get_tool_schemas()` | ✓ | `memoire_noter` (étape 3) | 1 |
| `sync_turn(...)` | — | écriture du brut (étape 2) | 1 |
| `handle_tool_call(...)` | — | exécution de `memoire_noter` | 1 |
| `on_memory_write(...)` | — | recopie de la mémoire native dans le registre | 1 |
| `on_pre_compress(messages)` | — | repère de compression dans le brut | 1 |
| `on_session_end`, `on_session_switch` | — | fermeture du lot, déclenchement de la consolidation | 1 |
| `shutdown()` | — | attente courte du fil de consolidation, télémétrie | 1 |
| `prefetch(query)` | — | **le rappel** — rend `""` en phase 1 | 2 |
| `system_prompt_block()` | — | bloc statique — rend `""` en phase 1 | 2 |
| `recall_status()` | — | ce qui a été rappelé, pour que ce ne soit pas silencieux | 2 |
| `queue_prefetch`, `on_delegation`, `identity_signature`, `get_config_schema`, `save_config`, `backup_paths`, `unavailable_reason` | — | non utilisés à ce jour | — |

Deux points du contrat méritent d'être notés :

- **`initialize` reçoit toujours `hermes_home` et `platform`**, et peut recevoir `agent_context`
  (`primary`, `subagent`, `cron`, `flush`), `agent_identity`, `user_id`. La documentation du
  contrat dit explicitement : *« skip writes for non-primary contexts »*.
- **`prefetch` doit être rapide** : *« recall in the background and return cached results »*. Cette
  phrase conditionne toute l'architecture du rappel (étape 6).

### 2.5 Le cycle de vie réel d'une session

Vérifié dans `agent/memory_manager.py` et `agent/turn_context.py` :

```
message entrant
   │
   ├─ (première fois) MemoryManager.initialize_all(session_id, hermes_home=…, platform=…,
   │                                                agent_context=…)      ← ligne 830
   ├─ _memory_turn_start_and_prefetch()  → on_turn_start() puis prefetch_all()   ← turn_context.py:762
   │        le texte rendu est attaché à la COPIE ENVOYÉE du message (api_content)
   ├─ … la boucle d'outils, la réponse …
   └─ MemoryManager.sync_all(user, assistant, …)                          ← ligne 480
            exécuté sur UN FIL D'ARRIÈRE-PLAN, jamais en ligne :
            « a provider's sync_turn may block for minutes »
            le même fil sérialise les écritures : le tour N avant le tour N+1
```

Deux conséquences majeures :

1. **Une écriture lente ne ralentit jamais une réponse.** C'est ce qui autorise EXIA SEED à
   écrire sur disque, puis (étape 4) à lancer une consolidation de 40 secondes.
2. **Ce que la mémoire injecte est rejoué aux tours suivants** (`api_content` — « the exact bytes
   the main loop sent »). C'est pourquoi la phase 2 plafonnera le bloc de rappel : un bloc gras
   recréerait la saturation de contexte de l'ancienne instance.

---

## 3 — Décisions d'architecture

Chaque décision est donnée avec son contexte, les options écartées et sa conséquence.

### D1 — Le dossier s'appelle `exia_seed`, sans tiret

**Contexte.** Hermès importe le dossier du plugin comme un module Python, sous un nom synthétique
(`_hermes_user_memory.<nom>__source_<empreinte>`).
**Options.** `exia-seed` (lisible, conforme aux usages des dépôts) · `exia_seed`.
**Décision.** `exia_seed`.
**Raison.** Un tiret est interdit dans un identifiant Python. Hermès contourne en chargeant par
chemin de fichier, mais un import relatif ou un `importlib.import_module` ailleurs dans la chaîne
casserait. Aucun bénéfice à prendre ce risque.
**Conséquence.** Le nom du dépôt public pourra être `exia-seed` ; le dossier technique reste
`exia_seed`.

### D2 — Aucune exception ne remonte vers Hermès

**Contexte.** Hermès enveloppe déjà les appels aux fournisseurs dans des `suppress(Exception)`.
Une mémoire qui lève une exception ne casserait donc pas la conversation — mais on ne veut pas
dépendre d'une protection écrite par quelqu'un d'autre et susceptible de changer.
**Décision.** Chaque méthode publique capture ses erreurs, les journalise, incrémente un compteur
et rend la main.
**Raison.** Invariant n°4 de la spec : *panne = dégradation, jamais blocage*. La mémoire est un
service d'agrément ; la conversation est le service vital.
**Conséquence.** Une panne d'EXIA SEED est **silencieuse pour l'utilisateur** et **visible dans la
télémétrie** — compteur `erreurs`, plus la trace dans `logs/errors.log`.

### D3 — Seule une session « principale » écrit le brut

**Contexte.** Hermès crée des agents pour bien d'autres choses qu'une conversation : crons,
sous-agents délégués, passes de nettoyage mémoire.
**Options.** (a) tout écrire, en distinguant après coup · (b) filtrer par plateforme (`telegram`
seulement) · (c) filtrer par `agent_context`.
**Décision.** (c) : seul `agent_context` valant `primary` (ou absent) écrit le brut.
**Raison.** La mesure du 20/09 est sans appel : les sessions de crons représentaient
**184 000 tokens par jour**, contre 9 500 pour la conversation réelle. Filtrer par plateforme
aurait laissé passer les crons Telegram ; filtrer après coup aurait consolidé du bruit.
**Conséquence.** Un cron ne pollue pas la mémoire — mais il peut **noter** au registre (étape 3),
parce qu'un email de client repéré la nuit est une information durable.

### D4 — La phase 1 est muette

**Contexte.** Le rappel peut être calculé bien avant d'être digne de confiance.
**Décision.** `prefetch()` et `system_prompt_block()` rendent `""` tant que `phase: 1`.
**Raison.** Deux raisons distinctes. D'abord la qualité : on veut comparer ce que le rappel
*aurait* injecté avec ce que l'agent avait réellement, avant de le brancher. Ensuite le coût :
tout ce qui est injecté est rejoué aux tours suivants (§2.5).
**Conséquence.** Le déploiement de la phase 1 est sans risque perceptible : l'agent se comporte
exactement comme avant.

### D5 — Les réglages vivent dans `config.yaml`, bloc `memory.exia_seed`

**Options.** Un fichier de configuration propre au plugin · des variables d'environnement · le
bloc `memory.<nom>` prévu par Hermès.
**Décision.** Le bloc `memory.exia_seed`.
**Raison.** C'est la convention des fournisseurs livrés (vérifié dans `byterover/__init__.py`,
fonction `_load_plugin_config`). Un seul fichier de configuration pour l'agent, sauvegardé avec
lui, visible dans `hermes memory status`.
**Conséquence.** Un changement de réglage demande un redémarrage de la passerelle. Vérifié le
22/09 : Hermès **relit** la configuration à chaque appel, il n'y a pas de cache de processus — mais
le fournisseur, lui, lit ses réglages une fois, dans `initialize`.

### D6 — Tout sous `HERMES_HOME`, aucun chemin en dur

**Contexte.** Francis veut dupliquer l'instance pour d'autres personnes de son entourage.
**Décision.** Le plugin lit `hermes_home` dans les arguments d'`initialize` ; à défaut il appelle
`hermes_constants.get_hermes_home()`. Tous les chemins sont construits à partir de là.
**Conséquence.** Le plugin est portable tel quel ; seuls les réglages (nom de l'utilisateur, nom
de l'agent) changent d'une instance à l'autre. Cf. `<dossier de l'instance>/DUPLICATION.md`.

### D7 — `is_available()` rend toujours vrai

**Contexte.** Hermès n'active pas un fournisseur qui se déclare indisponible ; il affiche alors
`unavailable_reason()`.
**Décision.** Rendre toujours vrai en phase 1.
**Raison.** À ce stade, EXIA SEED n'a **aucune dépendance** : pas de réseau, pas de clé d'API, pas
de bibliothèque hors bibliothèque standard — sauf PyYAML, déjà présent dans l'image officielle.
**À revoir à l'étape 5** : le graphe FCM exige `numpy`. `is_available()` devra alors vérifier son
import et, s'il manque, rendre faux avec une raison explicite plutôt que de tomber en marche.

---

## 4 — Construction

### 4.1 Arborescence

| Fichier | Rôle | Lignes |
|---|---|---|
| `plugin.yaml` | manifeste : nom, version (0.2.0), description, crochets (informatif, §2.3) | 14 |
| `__init__.py` | la classe `ExiaSeedProvider`, l'outil, `register(ctx)` | 293 |
| `config.py` | défauts et lecture du bloc `memory.exia_seed` | 36 |
| `util.py` | temps, hachage, verrou, écritures atomiques | 68 |
| `ingestion.py` | le brut (étape 2) | 194 |
| `registre.py` | le registre (étape 3) | 94 |
| `secrets.py` | le garde-fou anti-secret (annexe A1) | 67 |
| `consignes.py` | les consignes de mémoire (annexe A2) | 66 |
| `pages.py`, `consolidation.py` | les pages et la consolidation (étape 4) | 609 |
| `outils/consolider.py` | consolidation hors conversation, pour le cron | 58 |

**1 485 lignes, 104 Ko** (version 0.2.0, 23/09/2026).

### 4.2 État interne du fournisseur

```python
self._actif            # bool  — cette session écrit-elle le brut ?
self._contexte         # str   — primary | subagent | cron | flush
self._racine           # Path  — <HERMES_HOME>/memoire
self._reglages         # dict  — défauts + bloc memory.exia_seed
self._brut             # Brut     (None si session non écrivante)
self._registre         # Registre (toujours présent)
self._session          # str   — identifiant de session courant
self._fil_consolidation# Thread — fil d'arrière-plan, au plus un à la fois
self._compteurs        # dict  — télémétrie du processus
```

`initialize()` est le seul endroit où ces champs sont peuplés ; tout le reste les lit. Une
exception pendant l'initialisation met `self._actif = False` : le fournisseur reste chargé mais
inerte, ce qui est exactement le comportement voulu en cas de configuration cassée.

### 4.3 Réglages et défauts (`config.py`)

| Clé | Défaut | Rôle |
|---|---|---|
| `dossier` | `memoire` | sous-dossier de `HERMES_HOME` |
| `seuil_lot_tokens` | 25 000 | fermeture d'un lot de brut |
| `fuseau` | vide → `timezone` de `config.yaml` | horodatage à l'heure de l'utilisateur |
| `nom_utilisateur` | vide → nom fourni par la plateforme | étiquette dans le brut, nœud personnel |
| `nom_agent` | `assistant` | étiquette dans le brut |
| `langue` | `fr` | langue déclarée de l'incarnation |
| `phase` | 1 | 1 = écriture seule ; 2 = rappel injecté |
| `consolidation_auto` | vrai | consolider dès qu'un lot se ferme |
| `consolidation_effort` | `low` | effort de réflexion du modèle consolidateur |
| `consolidation_max_tokens_entree` | 40 000 | budget d'un passage de consolidation |

La lecture est **défensive** : une configuration illisible rend les défauts, sans exception. Seules
les clés connues sont acceptées ; une clé inconnue dans le bloc est ignorée.

### 4.4 Outils partagés (`util.py`)

- **`estimer_tokens(texte)`** — `len / 4`, sans tokeniseur. Sert aux seuils, jamais à une facture.
  Un tokeniseur exact coûterait un chargement de modèle pour un gain nul sur une décision de
  rotation de fichier.
- **`verrou(chemin)`** — verrou inter-processus `fcntl.flock`. Nécessaire : la passerelle et une
  commande `hermes` lancée à la main écrivent dans les mêmes fichiers.
- **`ecrire_json(chemin, données)`** — écriture atomique (fichier temporaire puis `os.replace`).
  Un plantage ne laisse jamais un état à moitié écrit.
- **`sha256_fichier`**, **`ajouter_ligne_jsonl`** — intégrité et journaux en ajout seul.
- **`fuseau(nom)`** — `zoneinfo`, repli sur UTC si la base de fuseaux manque.

### 4.5 Journalisation et compteurs

Le fournisseur tient des compteurs en mémoire (`tours_ecrits`, `tours_ignores`, `lots_fermes`,
`notes_outil`, `notes_natives`, `secrets_refuses`, `erreurs`, `ecriture_ms_total`,
`ecriture_ms_max`) et les **cumule** dans `memoire/telemetrie/<jour>.json` à la fermeture d'un lot
et à l'arrêt. Le cumul se fait sous verrou : plusieurs processus peuvent écrire le même fichier.

**Où vont les messages du plugin.** Vérifié le 23/09 dans `hermes_logging.py` : `agent.log` (niveau
configuré) et `errors.log` (avertissements et erreurs) sont branchés sur la **racine** de la
journalisation Python, sans filtre de composant. Le logger du plugin s'y propage : ses messages
arrivent dans les journaux d'Hermès dès que la passerelle l'a initialisé. Le cron de fin de journée,
lui, tourne dans un processus à part qui n'initialisait aucun journal (défaut H de la revue) :
`outils/consolider.py` appelle désormais `hermes_logging.setup_logging()`.

---

## 5 — Comportement en cas de panne

| Ce qui tombe | Effet sur l'agent | Effet sur la mémoire | Trace |
|---|---|---|---|
| Le plugin ne se charge pas | aucun — Hermès démarre sans fournisseur externe | aucune écriture | avertissement d'Hermès au démarrage |
| `initialize` lève | aucun | fournisseur inerte | `logs/errors.log` |
| Disque plein / droits | aucun | le tour n'est pas écrit | compteur `erreurs` + trace |
| Le fichier d'état est corrompu | aucun | un nouveau lot s'ouvre | lot précédent conservé, non chaîné |
| Configuration illisible | aucun | défauts appliqués | — |
| Le fil de consolidation plante | aucun | lots conservés, repris au passage suivant | trace + `statut` dans la télémétrie |

**Aucune de ces situations n'empêche Nexa de répondre.**

---

## 6 — Mesures (22/09/2026, image `hermes-agent:0.21.3`)

| Grandeur | Mesure |
|---|---|
| Chargement du plugin par Hermès | **63,5 ms** |
| `initialize()` | **18,1 ms** |
| Écriture d'un tour (moyenne sur 200) | **0,53 ms** |
| Écriture d'un tour (pire cas observé) | **1,47 ms** — budget : 5 ms |
| Empreinte mémoire du chargement | 14,5 Mo, dont l'essentiel est le chargeur d'Hermès |
| Taille du plugin sur disque | 88 Ko (v0.1) · 104 Ko (v0.2.0) |

---

## 7 — Tests

Exécutés dans un conteneur jetable, sans réseau, sur l'image de production, avec le **vrai
chargeur** et le **vrai gestionnaire de mémoire** d'Hermès. Script :
`tests/test_phase1_etapes_1_2.py`.

| # | Test | Ce qu'il prouve |
|---|---|---|
| 1 | Le plugin apparaît parmi les fournisseurs découverts | l'heuristique de découverte accepte notre `__init__.py` |
| 2 | Il est instancié via `register(ctx)` | le chemin officiel d'enregistrement fonctionne |
| 3 | `is_available()` est vrai | le fournisseur est activable |
| 4 | Session `primary` → écriture active | le filtre de contexte laisse passer une conversation |
| 5 | Session `cron` → écriture coupée | D3 tient |
| 6 | Session `cron` → **aucun fichier écrit** | le filtre agit avant l'écriture, pas après |

**21 tests réussis sur 21** pour les étapes 1 et 2 réunies (les quinze autres sont détaillés dans
`02-ecoute-brut.md`).

**Au 23/09, six séries et 115 tests**, tous au vert : étapes 1-2 (21), étape 3 (16), étape 4 (25),
annexes A1 (11) et A2 (19), revue (23). Plus deux passages sur GPT-6 réel. Voir `R1-revue-2026-09-23.md`.

---

## 8 — Limites connues et points à valider

1. **`is_available()` ne vérifie pas encore `numpy`** (cf. D7) — à corriger à l'étape 5.
2. **Un seul fournisseur externe à la fois** : contrainte d'Hermès. Si Francis voulait un jour
   faire cohabiter EXIA SEED avec un autre fournisseur, il faudrait qu'EXIA SEED devienne un
   façade qui délègue — non prévu.
3. **Les réglages ne sont relus qu'au redémarrage de la passerelle** : acceptable, mais à
   documenter pour Nexa, qui pourrait vouloir modifier son propre seuil.
4. **L'heuristique de découverte d'Hermès est textuelle** : renommer la classe sans garder le mot
   `MemoryProvider` dans les 8 premiers kilo-octets du fichier rendrait le plugin invisible.
   Sans danger tel quel, mais à savoir avant de réorganiser le code.

---

## 9 — Invariants respectés

| Invariant (spec §2) | Comment le squelette le tient |
|---|---|
| 1. Le brut est sacré | le squelette n'écrit rien lui-même ; il délègue à `ingestion.py` |
| 4. Panne = dégradation | D2 : aucune exception ne sort du plugin |
| 5. Rien hors de `/opt/data` | D6 : tous les chemins dérivent de `HERMES_HOME` |

Les invariants 2 (rappel sans LLM), 3 (moteur ≠ contrat) et 6 (oubli gracieux) concernent les
étapes 4 à 6 et ne sont pas engagés ici.
