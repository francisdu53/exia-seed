# 02 — L'écoute : le brut

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Version :** 1.1
**Date :** 22 septembre 2026
**Statut :** Code, testé, déployé chez Nexa — plugin 0.2.0 le 23/09/2026 à 07h25
**Référence :** `SPEC-EXIA-SEED.md` (§3.1 format, §6.1 ingestion, §2 invariants) ·
`01-squelette.md` (§2.5 cycle de vie) · `04-consolidation.md` (le brut est sa matière première)
**Origine :** couche « sources brutes » du *LLM Wiki* d'Andrej Karpathy (avril 2026) · périmètre
arrêté le 20/09/2026 sur mesure de l'historique de l'instance précédente
**Changelog 1.1 :** revue du 23/09 — masquage des secrets jusqu'à la fin de la ligne (D10) ; consignes réécrites : trois cas, message de consigne jamais écrit, journal des retraits (D11) ; dernier tour persistant ; numérotation robuste des lots (D12).
**Changelog 1.0 :** première version — périmètre mesuré, format arrêté, chaîne d'intégrité,
correction du rôle de `on_pre_compress` par rapport à la spécification initiale.

---

## 1 — Positionnement

### 1.1 La couche « source de vérité »

Le brut est la première des deux couches de fichiers d'EXIA SEED. C'est ce que Karpathy appelle les
*raw sources* : les ingrédients, avant que le wiki ne les cuisine.

```
   CONVERSATION            →   raw/2026-09-22_01.md        →   pages/autoplus-rocheval.md
   (Telegram, CLI…)            ajout seul, jamais modifié       réécrites à chaque consolidation
                               signées, chaînées                historique dans git
        étape 2                      étape 2                          étape 4
```

**Toute page consolidée doit pouvoir être retracée jusqu'à des lignes de brut.** C'est ce qui rend
la mémoire auditable : quand un fait paraît faux, on remonte à ce qui a été réellement dit.

### 1.2 Ce que l'étape fait

Écrire chaque échange, au moment où il a lieu, dans un fichier lisible, en ajout seul, avec son
horodatage et son locuteur. Fermer le lot quand il est plein ou quand la journée change. Le signer.

### 1.3 Ce qu'elle ne fait pas

Aucune analyse, aucune extraction, aucun appel au modèle, aucune mutation du graphe. C'est de
l'écriture, et rien d'autre : c'est ce qui permet de tenir un budget de 5 ms.

---

## 2 — Le terrain

### 2.1 Ce que `sync_turn` reçoit

```python
def sync_turn(self, user_content: str, assistant_content: str, *,
              session_id: str = "", messages: Optional[List[Dict]] = None,
              turn_author: Optional[Dict] = None) -> None
```

**Le texte de l'utilisateur et la réponse de l'agent, séparément** — pas les appels d'outils, pas
leurs résultats. Le périmètre du brut est donc garanti **par le contrat d'Hermès lui-même**, pas
par un filtre qu'il faudrait maintenir.

Deux détails vérifiés dans `agent/memory_manager.py` (`sync_all`, ligne 480) :

- Hermès applique `_strip_skill_scaffolding(user_content)` avant de transmettre : les préambules
  injectés par une compétence ne polluent pas le brut.
- Si le texte utilisateur nettoyé est vide, **aucun fournisseur n'est appelé**.

`turn_author` (`{"id", "name", "is_bot"}`) désigne qui a écrit le message — utile dans un canal
partagé, où plusieurs personnes parlent à l'agent.

### 2.2 Le fil d'arrière-plan

Toujours dans `sync_all`, le commentaire du code d'Hermès est explicite :

> *Never inline: a provider's `sync_turn` may block for minutes, which kept `run_conversation`
> open after the user saw the response. The single worker also serializes writes (turn N before N+1).*

Deux garanties qui structurent EXIA SEED : **écrire ne ralentit jamais une réponse**, et **les
tours arrivent dans l'ordre**. La seconde autorise un modèle d'écriture simple, sans file d'attente
ni numéro de séquence.

### 2.3 Les frontières de session

| Crochet | Quand Hermès l'appelle | Ce qu'EXIA SEED en fait |
|---|---|---|
| `on_session_end(messages)` | vraie fin de session, jamais par tour | ferme le lot (`fin_de_session`) |
| `on_session_switch(new_id, reset=…, rewound=…)` | `/new`, `/resume`, `/branch`, compression | rebind de l'identifiant ; si `reset` : ferme le lot |
| `on_pre_compress(messages)` | juste avant une compression d'historique | pose un repère dans le brut |

`reset=True` signifie « vraie nouvelle conversation ». `rewound=True` signifie « même session, mais
l'historique a été tronqué » : dans ce cas on ne ferme rien, parce que la conversation continue.

---

## 3 — Décisions d'architecture

### D1 — Le brut, c'est la conversation. Pas les sorties d'outils

**Contexte.** Un tour d'agent produit trois sortes de texte : ce que dit l'utilisateur, ce que
répond l'agent, et ce que renvoient les outils (lecture de fichier, requête, tableur).

**Mesure décisive** (20/09/2026, sur `state.db` de l'instance précédente, 15 289 messages) :

| Source | Volume |
|---|---|
| Conversation réelle (utilisateur + agent, hors crons) | **≈ 9 500 tokens / jour** |
| Sorties d'outils dans ces mêmes sessions | **1 987 000 tokens — 94 % du volume** |
| Sessions de crons | ≈ 184 000 tokens / jour |

**Options.** (a) tout écrire, trier à la consolidation · (b) écrire conversation + sorties d'outils
tronquées · (c) conversation seule.
**Décision.** (c).
**Raison.** Une sortie d'outil est du matériau de travail, déjà déposé sur disque par `bigout`, et
sans valeur mémorielle : personne ne se souvient du contenu brut d'un tableur, on se souvient de ce
qu'on en a conclu. Et le coût est décisif : tout écrire ferait passer la consolidation d'**un
passage tous les deux à trois jours** à **sept passages par jour**, soit ≈ 185 000 tokens
quotidiens pour aucun gain.
**Conséquence.** Ce qu'un outil révèle d'important n'entre dans la mémoire que **distillé** : par
le registre (étape 3) ou par la consolidation d'une conversation qui en parle.

### D2 — Un lot par fichier, trois déclencheurs de fermeture

**Options.** Un fichier par jour, fixe · un fichier par session · un fichier par volume.
**Décision.** Les trois à la fois : le lot se ferme au **seuil de 25 000 tokens**, au **changement
de jour**, ou à la **fin de session**.
**Raison.** Le volume borne le coût d'un passage de consolidation (un lot doit tenir dans le budget
d'entrée du modèle). La date donne un repère humain et un rythme naturel — c'est la décision de
Francis du 20/09 : « on déclenche dans l'un des deux cas ». La fin de session évite qu'une
conversation close attende le lendemain pour être rangée.
**Conséquence.** À un rythme de 9 500 tokens par jour, c'est la fin de journée qui commande ; le
seuil prendra le relais quand l'activité montera.

### D3 — L'empreinte ne vit pas dans le fichier qu'elle certifie

**Contexte.** La spécification initiale (reprise de la spec 05c d'EXIA GHOST) plaçait `hash` et
`previous_hash` dans l'en-tête YAML du fichier.
**Problème découvert en codant.** Écrire l'empreinte dans le fichier **modifie le contenu dont on
vient de calculer l'empreinte**. Il faudrait alors hacher « tout sauf ces deux lignes » — une règle
subtile, donc fragile, et impossible à vérifier avec un simple `sha256sum`.
**Décision.** L'empreinte vit dans `raw/.chaine.jsonl`, un registre en ajout seul, une ligne par lot
fermé.
**Conséquence.** `sha256sum raw/2026-09-22_01.md` suffit à vérifier un lot. Écart assumé avec la
spec, consigné dans la spec elle-même.

### D4 — L'état du lot ouvert est persistant

**Contexte.** La passerelle redémarre : mise à jour, plantage, `gateway restart`.
**Décision.** `raw/.etat.json` garde le lot en cours, son volume, son jour, sa session.
**Raison.** Sans lui, chaque redémarrage ouvrirait un lot neuf ; une journée agitée laisserait dix
fichiers d'un échange, et la consolidation paierait dix passages.
**Conséquence.** Après un redémarrage, l'écriture **reprend dans le même fichier**. C'est le seul
fichier mutable du dossier `raw/` — et il ne contient aucune donnée de conversation.

### D5 — Verrou inter-processus, pas verrou de fil

**Contexte.** La passerelle écrit depuis son fil d'arrière-plan ; mais `hermes` en ligne de
commande, un cron sans agent ou l'outil de consolidation sont des **processus** distincts.
**Décision.** `fcntl.flock` sur un fichier dédié, autour de chaque écriture et de chaque fermeture.
**Raison.** Un verrou de fil (`threading.Lock`) ne protège rien entre deux processus. Deux
écritures simultanées entrelaceraient les lignes.

### D6 — Horodatage à la minute, dans le fuseau de l'utilisateur

**Décision.** `[19:11 francis]`, heure locale de l'utilisateur, héritée du réglage `timezone`
d'Hermès.
**Raison.** Le brut est lu par un humain et par un modèle ; « 19:11 » veut dire quelque chose pour
les deux, « 17:11 UTC » non. La minute suffit : l'ordre est donné par l'ordre des lignes, garanti
par le fil unique d'Hermès (§2.2).
**Rappel de terrain** : l'ancienne instance envoyait ses rappels de cron à 19h00 en croyant les
envoyer à 17h00, parce que les heures étaient interprétées en UTC. D'où le réglage explicite.

### D7 — Le nom configuré prime sur le nom de la plateforme

**Contexte.** `turn_author["name"]` rend le pseudonyme Telegram (« Jean5 XYZ_T7 »).
**Décision.** Si `nom_utilisateur` est configuré, il gagne ; sinon on prend le nom de la plateforme ;
sinon « utilisateur ».
**Raison.** Le nœud personnel de la mémoire doit s'appeler `francis`, pas `jean5_xyz_t7`. Et un
changement de pseudonyme sur Telegram ne doit pas créer un second locuteur dans l'histoire.

### D8 — L'estimation des tokens vaut mieux qu'un tokeniseur

**Décision.** `len(texte) / 4`.
**Raison.** Le seuil de 25 000 tokens sert à décider quand couper un fichier. Une erreur de 15 %
décale la coupure, sans conséquence. Un tokeniseur exact coûterait un chargement de modèle et une
dépendance, pour une décision qui n'en a pas besoin.
**Conséquence.** Les chiffres de volume du brut sont des **ordres de grandeur**, et le disent.

### D9 — `on_pre_compress` ne sauve rien : il pose un repère

**Correction de la spécification initiale.** On avait écrit que ce crochet servirait à capturer ce
qu'Hermès s'apprête à jeter — présenté comme « le gain que l'ancienne instance n'avait pas ».
**En réalité**, `sync_turn` écrit chaque échange au moment où il a lieu : **rien ne peut être perdu
à la compression**. Le vrai gain, c'est l'écriture continue.
**Décision.** Le crochet écrit un commentaire dans le brut
(`<!-- 19:40 compression de l'historique — 12 messages -->`) et rend `""`.
**Raison.** Ce repère a une valeur de diagnostic : il date les moments où l'agent a perdu du
contexte, ce qui aidera à interpréter ses réponses de cette période.

---

### D10 — Les secrets sont masqués à l'écriture

Ajouté le 22/09/2026, après vérification qu'Hermès ne masque **pas** ce que l'utilisateur tape (son
redacteur ne couvre que les journaux et les sorties d'outils). Le brut remplace la valeur d'un mot
de passe ou d'une clé par `[secret masqué]`, garde la phrase, et compte l'opération.
**Revue du 23/09** : la valeur est désormais masquée **jusqu'à la fin de la ligne** — une phrase de
passe à plusieurs mots fuyait à partir de son deuxième mot.
**Voir l'annexe `A1-garde-fou-secrets.md`.**

### D11 — L'utilisateur peut refuser qu'un tour soit écrit

Trois cas (annexe `A2-consignes-memoire.md`, version 1.1) :

| Formule | Effet |
|---|---|
| « ne note pas ça **:** … » (annoncé) | le message courant n'est pas écrit |
| « ne note pas ça » (sans annonce) | le message courant n'est pas écrit, **le précédent est retiré** |
| « oublie ce que je viens de dire » | le précédent est retiré ; le message de consigne n'est pas écrit |

**Le message qui porte une consigne n'est jamais écrit** : une instruction n'est pas un souvenir,
et, écrite, elle trompait le consolidateur sur le tour voisin (défaut G, trouvé sur GPT-6 réel).
Un tour **retiré** n'est jamais supprimé : il est inscrit dans `raw/.retraits.jsonl`, que la
consolidation respecte, y compris quand son lot est déjà fermé.

### D12 — Le lot suivant prend le premier numéro libre

**Revue du 23/09.** La version 1.0 numérotait les lots en comptant les fichiers du jour. Un fichier
déplacé à la main aurait produit un numéro déjà pris : l'ouverture en mode exclusif aurait échoué et
le tour aurait été perdu. Le numéro est désormais le premier libre, ouvert ou fermé.

## 4 — Construction

### 4.1 Format d'un lot

```markdown
---
type: raw
date: 2026-09-22
session_id: 20260922_191052_a7f3
lang: fr
ouvert_le: 2026-09-22T19:11:10+02:00
---

## Échanges

[19:11 francis] Demain je passe chez Autoplus Rocheval, ils ont 3 voitures grêlées.
[19:11 nexa] Très bien. Veux-tu que je prépare la visite ?
<!-- 19:40 compression de l'historique — 12 messages -->
```

Une ligne par message. Un message sur plusieurs lignes est écrit tel quel : la citation (étape 4)
travaille par **numéro de ligne réel dans le fichier**, ce qui reste exact quoi qu'il arrive.

### 4.2 Cycle de vie

```
            premier échange du jour
                    │
                    ▼
        raw/2026-09-22_01_open.md          .etat.json = {fichier, jour, tokens, session}
                    │
      ┌─────────────┼──────────────┬─────────────────────┐
      │             │              │                     │
  25 000 tokens  minuit      fin de session      nouvelle conversation (reset)
      └─────────────┴──────────────┴─────────────────────┘
                    ▼
        raw/2026-09-22_01.md   (figé)
                    │
                    ├─ empreinte SHA-256 → raw/.chaine.jsonl
                    └─ déclenche la consolidation (étape 4)
```

### 4.3 Algorithme d'écriture

```
ecrire_tour(session, qui, texte_utilisateur, texte_agent) :
    masquer les secrets des deux textes (annexe A1), compter
    si les deux textes sont vides → ne rien faire
    consigne ← detecter(texte_utilisateur)                         (annexe A2)
    prendre le verrou
        état ← lire .etat.json
        si état existe :
            si état.jour ≠ aujourd'hui        → fermer("changement_de_jour")
            sinon si état.tokens + ajout > seuil et état.tokens > 0
                                               → fermer("seuil_atteint")
        si pas d'état → ouvrir un lot au premier numéro libre (en-tête YAML)
        si consigne vise le tour précédent et .dernier_tour.json existe :
            ajouter une ligne à .retraits.jsonl ; poser un repère ; vider .dernier_tour.json
        si consigne (quelle qu'elle soit) :
            poser le repère « échange non conservé » ; rendre la main SANS écrire le tour
        écrire les lignes horodatées
        .dernier_tour.json ← {nom FINAL du lot, première et dernière ligne}
        état.tokens += ajout ; écrire .etat.json (atomique)
    relâcher le verrou
```

Le test `état.tokens > 0` évite un cas limite : un premier message plus gros que le seuil
ouvrirait, fermerait et rouvrirait un lot vide.

### 4.4 Structures

`raw/.etat.json` — le seul fichier mutable :

```json
{"fichier": "2026-09-22_01_open.md", "jour": "2026-09-22", "tokens": 1043,
 "session_id": "20260922_191052_a7f3", "ouvert_le": "2026-09-22T19:11:10+02:00"}
```

`raw/.chaine.jsonl` — une ligne par lot fermé, jamais modifiée :

```json
{"fichier": "2026-09-22_01.md", "sha256": "sha256:b9621b56…", "precedent": "genese",
 "ferme_le": "2026-09-22T23:55:00+02:00", "raison": "fin_de_journee", "tokens": 1043,
 "consolide": false}
```

Le champ `consolide` est **informatif** : l'avancement réel de la consolidation vit dans
`raw/.consolide.jsonl` (étape 4), pour ne jamais avoir à réécrire une ligne de la chaîne.

`raw/.dernier_tour.json` — le dernier tour écrit, sous le nom **final** de son lot ; il survit à la
fermeture (revue du 23/09) :

```json
{"fichier": "2026-09-23_01.md", "lignes": [17, 18]}
```

`raw/.retraits.jsonl` — une ligne par retrait, jamais modifiée ; fait autorité pour la consolidation :

```json
{"fichier": "2026-09-23_01.md", "lignes": [13, 14], "qui": "francis",
 "consigne": "hors_brut_et_precedent", "ts": "2026-09-23T07:11:49+02:00"}
```

---

## 5 — Intégrité

### 5.1 Ce que la chaîne garantit

Chaque lot fermé porte son empreinte et celle du lot précédent. Le premier maillon pointe vers
`genese`. Modifier un lot ancien casse la vérification **à partir de ce point**, et le dit.

```bash
# vérifier un lot
sha256sum raw/2026-09-22_01.md
# rejouer toute la chaîne
python3 - <<'EOF'
import json, hashlib, pathlib
p, precedent = pathlib.Path("raw"), "genese"
for ligne in (p / ".chaine.jsonl").read_text().splitlines():
    m = json.loads(ligne)
    reel = "sha256:" + hashlib.sha256((p / m["fichier"]).read_bytes()).hexdigest()
    etat = "OK" if reel == m["sha256"] and m["precedent"] == precedent else "ROMPU"
    print(etat, m["fichier"]); precedent = m["sha256"]
EOF
```

### 5.2 Ce qu'elle ne garantit pas

Elle **détecte** une modification, elle ne l'**empêche** pas : un utilisateur qui a les droits peut
réécrire un lot et sa ligne de chaîne. C'est une preuve d'intégrité, pas un coffre-fort. La
protection réelle vient de git (étape 4) et des sauvegardes.

---

## 6 — Concurrence et performance

| Situation | Traitement |
|---|---|
| Deux tours rapprochés | fil unique d'Hermès : sérialisés par construction |
| Passerelle + commande `hermes` | verrou `flock` : le second attend |
| Fermeture pendant une écriture | même verrou : l'un des deux passe en premier, jamais d'entrelacement |
| Redémarrage en pleine écriture | l'écriture est un `append` ; au pire le dernier tour manque, l'état reste cohérent |

Mesures : **0,53 ms par tour** en moyenne sur 200 tours consécutifs, **1,47 ms** au pire cas
observé, pour un budget de 5 ms.

---

## 7 — Comportement en cas de panne

| Panne | Effet |
|---|---|
| Disque plein | le tour n'est pas écrit, compteur `erreurs`, la conversation continue |
| `.etat.json` illisible | un nouveau lot s'ouvre ; l'ancien reste sur disque, non chaîné (récupérable à la main) |
| Fermeture impossible (droits) | le lot reste ouvert ; il sera fermé au prochain déclencheur |
| Fuseau horaire absent du système | repli sur UTC, journalisé |

---

## 8 — Mesures (22/09/2026)

| Grandeur | Valeur |
|---|---|
| Écriture d'un tour, moyenne (200 tours) | 0,53 ms |
| Écriture d'un tour, pire cas | 1,47 ms |
| Taille d'un lot type (journée de conversation) | ≈ 9 500 tokens, ≈ 38 Ko |
| Coût en tokens | **zéro** — aucun appel au modèle |

---

## 9 — Tests

Script : `tests/test_phase1_etapes_1_2.py`, exécuté dans un conteneur jetable sans réseau.

| # | Test | Ce qu'il prouve |
|---|---|---|
| 1 | Un lot s'ouvre au premier échange, avec son en-tête YAML | le format est respecté dès l'ouverture |
| 2 | 3 échanges → 6 lignes, attribuées à `francis` et `nexa` | l'attribution et l'ordre sont corrects |
| 3 | Le nom configuré prime sur « Jean5 XYZ_T7 » | D7 tient |
| 4 | Latence < 5 ms | le budget d'écriture est tenu |
| 5 | `on_pre_compress` pose un repère et rend `""` | D9 tient, rien n'est injecté |
| 6 | Fermeture au seuil ; `precedent = genese` | D2 et la chaîne s'amorcent correctement |
| 7 | Nouvelle session → fermeture ; chaînage exact | les frontières de session sont respectées |
| 8 | Empreintes recalculées = chaîne | l'intégrité est vérifiable |
| 9 | **Une falsification est détectée** | la chaîne sert à quelque chose |
| 10 | Écriture via le vrai `MemoryManager` d'Hermès | le chemin de production fonctionne |
| 11 | Compteurs de télémétrie persistés | l'observabilité existe dès l'étape 2 |

**21 tests réussis sur 21** pour les étapes 1 et 2.

---

## 10 — Limites connues

1. **Volume estimé, pas mesuré** (D8) : les seuils sont approximatifs de ±15 %.
2. **Langue déclarée, pas détectée** : `lang: fr` vient de la configuration. Un échange en anglais
   sera étiqueté `fr`. Sans conséquence aujourd'hui ; à revoir si l'usage devient bilingue.
3. **Horodatage à la minute** : deux messages de la même minute ne se distinguent que par leur ordre.
4. **Messages multi-lignes** : écrits tels quels ; la consolidation cite par numéro de ligne, ce qui
   reste exact, mais un fait peut citer trois lignes pour une seule phrase.
5. **Le comptage des lignes relit le fichier du lot à chaque tour** pour connaître le numéro de la
   première ligne écrite. Sans conséquence à 25 000 tokens par lot (≈ 100 Ko, mesuré à 0,5 ms par
   tour) ; à revoir si le seuil augmentait beaucoup.
6. **Pas de purge** : le brut grossit indéfiniment (≈ 14 Mo par an au rythme actuel). C'est voulu —
   invariant n°1 — mais méritera une politique d'archivage à l'échelle de plusieurs années.

---

## 11 — Invariants respectés

| Invariant | Comment |
|---|---|
| 1. Le brut est sacré | ajout seul ; aucune réécriture ; aucune suppression ; empreinte hors du fichier |
| 2. Le rappel ne coûte aucun appel au modèle | l'écriture non plus |
| 4. Panne = dégradation | toutes les erreurs sont capturées et comptées |
| 5. Rien hors de `/opt/data` | `<HERMES_HOME>/memoire/raw/` |
