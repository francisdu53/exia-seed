# 03 — Le registre : « note ça »

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Version :** 1.1
**Date :** 22 septembre 2026
**Statut :** Code, testé (16/16 + revue), déployé chez Nexa — plugin 0.2.0 le 23/09/2026 à 07h25
**Référence :** `SPEC-EXIA-SEED.md` (§6.4 registre, §6.6 confidentialité) · `02-ecoute-brut.md`
(l'autre source de la consolidation) · `04-consolidation.md` (qui range les entrées)
**Origine :** **idée de Francis Babin, 20/09/2026** — *« si je lui dis d'écrire directement dans
une page, cela peut poser problème. Il faut un registre dans lequel est écrit ce qu'elle ne doit
pas oublier, et la consolidation les intègre dans les bons nœuds ensuite. »*
**Changelog 1.2 (27/09) :** ⚠️ **`memoire_noter` n'a jamais fonctionné en production du 22 au 27/09** — Hermès lit `get_tool_schemas()` dans `add_provider`, AVANT l'initialisation ; le plugin ne déclarait l'outil qu'initialisé : « Unknown tool » aux trois appels réels de Nexa. Les tests appelaient le plugin directement, sans le gestionnaire d'Hermès. Corrigé à l'étape 7 (`07-requete.md` §2.1, D5), testé par le vrai `MemoryManager` ; notes perdues rattrapées.
**Changelog 1.1 :** revue du 23/09 — corps d'une note protégé (défaut F : une ligne « ## » créait une fausse entrée ; un « --> » fermait le commentaire de confidentialité) ; filtre anti-secret partagé dans `secrets.py` et élargi à la fin de ligne.
**Changelog 1.0 :** première version — outil `memoire_noter`, recopie de la mémoire native,
garde-fou anti-secret (élargi après échec de test).

---

## 1 — Positionnement

### 1.1 Le carnet, avant la mise au propre

Entre la conversation (le brut) et le savoir rangé (les pages), il manquait une couche : **ce qu'on
note sur le moment**. Un nom de chef d'atelier lâché en passant, une contrainte à ne pas oublier,
une consigne. Le brut le contient, mais noyé ; la page ne l'aura qu'après la consolidation du soir.

```
   brut            ce qui a été dit, dans l'ordre, tout entier
   REGISTRE        ce qu'il ne faut pas perdre — écrit dans la seconde   ← cette étape
   pages           ce qui est su, rangé par sujet
```

### 1.2 Ce que l'étape apporte

1. **L'immédiateté** : l'information est écrite au moment où elle compte, avec sa confidentialité.
2. **Un seul écrivain sur les pages** : l'agent n'écrit jamais dans une page ; la consolidation
   range. C'est la décision de Francis, et elle supprime une classe entière de problèmes.
3. **La capture de la mémoire native d'Hermès** : ce que l'agent retient avec son propre outil de
   mémoire est recopié ici, donc consolidé comme le reste.

---

## 2 — Le terrain

### 2.1 Exposer un outil à l'agent

Le contrat (`agent/memory_provider.py`) prévoit deux méthodes :

```python
def get_tool_schemas(self) -> List[Dict[str, Any]]      # schémas OpenAI function-calling
def handle_tool_call(self, tool_name, args, **kwargs) -> str   # DOIT rendre une chaîne JSON
```

Les outils d'un fournisseur de mémoire ne sont exposés que si l'ensemble d'outils correspondant est
actif côté Hermès (`memory_provider_tools_enabled`, `agent/memory_manager.py:79`).

### 2.2 Le crochet `on_memory_write`

```python
def on_memory_write(self, action: str, target: str, content: str,
                    metadata: Optional[Dict[str, Any]] = None) -> None
```

> *Mirror a built-in memory-tool write (`action`: add | replace | remove ; `target`: memory | user ;
> `metadata`: provenance such as write_origin, session_id, tool_name).*

Hermès garde sa propre mémoire (`MEMORY.md`, `USER.md`) et l'injecte dans le prompt. Ce crochet
prévient EXIA SEED à chaque écriture : c'est la passerelle entre les deux mémoires.

---

## 3 — Décisions d'architecture

### D1 — L'agent n'écrit jamais dans une page

**Contexte.** La première version de la spécification autorisait l'agent à compléter une page
directement.
**Problème.** Deux écrivains sur le même fichier : l'agent en pleine conversation, la consolidation
le soir. Conflits d'écriture, et surtout **risque de dérive** — un agent qui réécrit une page peut
en déformer le contenu sans que personne le voie.
**Décision de Francis (20/09).** Un registre en ajout seul ; la consolidation range.
**Conséquence.** Le modèle de concurrence devient trivial : un seul écrivain sur les pages, et le
registre n'est jamais modifié, seulement complété.

### D2 — L'intégration est notée dans un fichier à part

**Contexte.** Il faut savoir quelles entrées ont déjà été rangées.
**Options.** (a) marquer l'entrée dans `registre.md` (`<!-- intégré:… -->`) · (b) un journal séparé.
**Décision.** (b) : `registre.integre.jsonl`.
**Raison.** (a) exigerait de **réécrire** le registre, ce qui contredit l'ajout seul et ouvre la
porte à une corruption partielle. La spec envisageait (a) ; on s'en écarte pour rester cohérent
avec l'invariant.
**Conséquence.** `registre.md` est strictement immuable ; l'état d'avancement est une projection.

### D3 — Le registre est lu en priorité par le rappel

**Décision (phase 2).** Le rappel lira les entrées **non encore intégrées** avant les pages.
**Raison.** Sans cela, « note ça » ne servirait à rien avant la consolidation du soir : l'agent
aurait écrit l'information sans pouvoir s'en servir dans les deux heures qui suivent.
**Conséquence.** Le volume du registre en attente entre dans le plafond du bloc de rappel
(1 200 tokens) ; un registre qui déborde sera une alerte de télémétrie.

### D4 — Le registre accepte toutes les sessions, le brut non

**Contexte.** Le brut est réservé à la conversation principale (décision D3 du document 01).
**Décision.** L'outil `memoire_noter` est disponible **aussi** pour un cron ou un sous-agent.
**Raison.** Un cron qui lit les emails du matin et repère une demande de devis produit une
information durable. La refuser reviendrait à jeter le meilleur de ce que l'agent fait sans nous.
**Conséquence.** La source de chaque entrée est tracée : `outil:primary`, `outil:cron`,
`memoire_native:user`… On saura toujours d'où vient un souvenir.

### D5 — Un garde-fou lexical contre les secrets

**Contexte.** Une mémoire se relit, se consolide, se versionne dans git, et finira peut-être dans
une archive. Un mot de passe n'y a pas sa place.
**Décision.** Refuser une note qui contient une clé d'API reconnaissable, une clé privée, ou un
mot-clé de mot de passe **suivi d'une valeur**.
**Contrainte inverse, aussi importante.** **Aucune règle sur les longues suites de chiffres** : le
SIRET `123 456 789 00012` doit rester mémorisable, comme un IBAN de client ou un numéro de
téléphone.
**Conséquence.** Le filtre est une ceinture, pas un coffre-fort : il attrape les formes courantes,
pas un secret formulé sans mot-clé.

### D6 — Un identifiant court et stable par entrée

**Décision.** Huit caractères, empreinte SHA-256 de la date et du texte.
**Raison.** Il sert de référence de citation pour la consolidation (`registre:7807d69e`) et de clé
dans le journal d'intégration. Stable : deux entrées identiques à la même minute donnent le même
identifiant, ce qui est le comportement voulu (doublon = même chose).

### D7 — La description de l'outil EST le contrat d'usage

**Contexte.** Un outil mal décrit est un outil mal utilisé : l'agent note trop, ou pas assez.
**Décision.** La description dit quand s'en servir (« note ça », « retiens », ou une information
durable : nom, tarif, règle, échéance, préférence, décision **et sa raison**), impose **un fait
autonome par appel**, et interdit explicitement les secrets.
**Raison.** C'est le seul endroit où l'on peut influencer le comportement de l'agent sans occuper
du contexte en permanence : la description d'un outil n'est lue que lorsque l'outil est candidat.

---

## 4 — Construction

### 4.1 Format

```markdown
# Registre — à retenir

Ajout seul. Chaque entrée est rangée dans une page par la consolidation.

## 2026-09-22 19:22 — 7807d69e · outil:primary · nœud:autoplus_rocheval
<!-- privacy:normal -->
Le chef d'atelier d'Autoplus Rocheval s'appelle Olivier.

## 2026-09-22 19:22 — 9e3c0605 · outil:primary
<!-- privacy:confidentiel -->
Préférence : regrouper les visites de garages le matin.
```

L'en-tête d'une entrée porte : date et heure locales, identifiant, source, et un nœud suggéré
facultatif. La confidentialité est un commentaire HTML : invisible à la lecture, lisible par le
moteur.

### 4.2 Interface

| Méthode | Rôle |
|---|---|
| `noter(texte, source, noeud, privacy) → id` | ajoute une entrée, rend son identifiant |
| `entrees() → [dict]` | relit tout le registre (date, id, source, nœud, privacy, texte) |
| `ids_integres() → set` | lit le journal d'intégration |
| `en_attente() → [dict]` | entrées non encore rangées — ce que voit la consolidation |
| `marquer_integre(id, page, lot)` | ajoute une ligne au journal d'intégration |

La relecture se fait par expression régulière sur les en-têtes d'entrées : le registre reste un
fichier markdown ordinaire, éditable et lisible sans outil.

**Protection du corps (revue du 23/09, défaut F).** Une ligne du texte d'une note qui commencerait
par `#` est préfixée d'une barre oblique inverse : sans cela, « ## 2026-01-01 00:00 — … » dans le
corps d'une note aurait été relu comme une nouvelle entrée. Les séquences `<!--` et `-->` sont
neutralisées, pour qu'aucun texte ne puisse fermer ou imiter le commentaire de confidentialité.

### 4.3 L'outil exposé à l'agent

```json
{"name": "memoire_noter",
 "parameters": {"texte": "le fait à retenir, en une ou deux phrases autonomes",
                "noeud": "sujet principal, ex. autoplus_rocheval (facultatif)",
                "confidentialite": "normal | personnel | confidentiel"}}
```

Réponse en cas de succès :
`{"ok": true, "id": "7807d69e", "message": "Noté. Ce sera rangé dans ta mémoire à la prochaine consolidation."}`

Le message de retour est délibérément explicite : il apprend à l'agent, au fil de l'usage, comment
fonctionne sa propre mémoire.

### 4.4 La recopie de la mémoire native

| Action Hermès | Ce que devient l'entrée |
|---|---|
| `add` / `replace` | le contenu, source `memoire_native:<cible>` |
| `remove` | `[retiré de la mémoire native] <contenu>` |

Le retrait est **tracé, pas exécuté** : EXIA SEED ne supprime rien. La consolidation pourra s'en
servir pour marquer un fait comme dépassé (étape 3 de la phase 3, supersession).

---

## 5 — Le garde-fou anti-secret

*Détail complet, enquête sur le redacteur natif d'Hermès et politique d'ensemble :
`A1-garde-fou-secrets.md`.*

### 5.1 Ce qu'il attrape

```
sk-… (16+)         ghp_… (20+)        xox[bp]-…        AKIA…
-----BEGIN … PRIVATE KEY-----
(mot de passe | password | passwd | mdp | passphrase | code secret | code pin)
        suivi, à moins de 40 caractères, de « : » ou « = » ou « est <valeur> »
```

### 5.2 Le défaut trouvé par les tests

La première version exigeait le séparateur **immédiatement** après le mot-clé
(`mot de passe\s*[:=]`). Résultat au test :

| Texte | Attendu | Obtenu (v1) |
|---|---|---|
| « Le mot de passe NAS : Ab12!cD » | refusé | **accepté** ❌ |

Le mot « NAS » s'intercalait. Le secret a été écrit dans le registre de test, et quatre assertions
suivantes ont cascadé. Correctif : jusqu'à 40 caractères entre le mot-clé et la valeur, et prise en
compte de la forme « mon mdp **est** … ».

### 5.3 Vérification après correctif

| Texte | Verdict |
|---|---|
| « Le mot de passe NAS : Ab12!cD » | refusé |
| « mon mdp est Ab12cD » | refusé |
| « password=hunter22 » | refusé |
| « clé sk-abcdefghijklmnopqrstuvwx1234 » | refusé |
| « Rappelle-moi de changer le mot de passe NAS » | **accepté** — c'est une tâche, pas un secret |
| « SIRET 123 456 789 00012, APE 0000Z » | **accepté** |
| « Tarif : 45 € l'élément » | **accepté** |

Le même filtre s'applique à la recopie de la mémoire native : un secret noté par l'outil d'Hermès
n'entre pas dans EXIA SEED.

---

## 6 — Comportement en cas de panne

| Panne | Effet |
|---|---|
| Écriture impossible | l'outil rend `{"ok": false, "erreur": …}` ; l'agent le dit à l'utilisateur |
| Registre corrompu | les entrées lisibles sont relues ; les autres sont ignorées, jamais réparées automatiquement |
| Journal d'intégration illisible | les entrées sont considérées comme non intégrées → au pire un doublon dans une page, jamais une perte |

Le choix de la dernière ligne est délibéré : **en cas de doute, on préfère ranger deux fois que
perdre une fois.** La consolidation étant idempotente, un doublon est absorbé.

---

## 7 — Mesures

| Grandeur | Valeur |
|---|---|
| Écriture d'une note | < 1 ms |
| Coût en tokens | **zéro** — aucun appel au modèle |
| Coût en contexte | la description de l'outil, ≈ 150 tokens, présente quand l'outil est candidat |

---

## 8 — Tests

Script : `tests/test_etape_3_registre.py`.

| # | Test | Ce qu'il prouve |
|---|---|---|
| 1 | `memoire_noter` est proposé à l'agent | l'outil est exposé |
| 2 | Une note est acceptée, datée, sourcée, avec son nœud | le format et la traçabilité |
| 3 | Une note confidentielle conserve sa marque | D5 et §6.6 de la spec |
| 4 | Mot de passe refusé | le garde-fou attrape la forme courante |
| 5 | Clé d'API refusée | idem sur les clés |
| 6 | Rien de secret n'apparaît dans le fichier | le refus est effectif, pas cosmétique |
| 7 | Ajout natif recopié | la passerelle avec la mémoire d'Hermès fonctionne |
| 8 | Retrait natif tracé | un retrait est une information, pas une suppression |
| 9 | Relecture complète et champs présents | l'analyse du markdown est correcte |
| 10 | Une entrée intégrée sort de la file d'attente | D2 fonctionne |
| 11 | Le registre n'est pas réécrit | l'ajout seul est respecté |
| 12 | Un cron peut noter | D4 |
| 13 | Sa source est tracée `outil:cron` | la provenance est fidèle |
| 14-16 | Télémétrie : notes, notes natives, refus comptés | l'observabilité |

**16 tests réussis sur 16**, après correction du garde-fou (5 échecs au premier passage, tous dus
au même défaut).

---

## 9 — Limites connues

1. **Filtre lexical** : « le code de la porte c'est 4471 » passe. Un filtre sémantique demanderait
   un modèle, donc un coût par note — écarté.
2. **Pas de déduplication** : deux notes identiques à des moments différents créent deux entrées.
   La consolidation les absorbe (idempotence), mais le registre les garde toutes les deux.
3. **Pas de suppression** : une note erronée reste. Elle peut être contredite par une note
   ultérieure ; la supersession (phase 3) traitera ce cas.
4. **En phase 1, une note n'est pas relue** par l'agent dans la conversation : elle est écrite,
   consolidée, mais le rappel n'est pas encore branché.

---

## 10 — Invariants respectés

| Invariant | Comment |
|---|---|
| 1. Le brut est sacré | le registre est lui aussi en ajout seul ; l'intégration vit ailleurs |
| 3. Le moteur voit tout, le modèle reçoit peu | la confidentialité et la source restent côté moteur |
| 4. Panne = dégradation | un échec d'écriture rend une erreur JSON, sans exception |
| 6. Oubli gracieux | rien n'est jamais supprimé, même un retrait de la mémoire native |
