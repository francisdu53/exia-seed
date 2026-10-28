# A1 — Le garde-fou anti-secret (annexe transversale)

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Version :** 1.1
**Date :** 22 septembre 2026
**Statut :** Code, testé (11/11 + revue), déployé chez Nexa — plugin 0.2.0 le 23/09/2026 à 07h25
**Référence :** `02-ecoute-brut.md` (§4 écriture du brut) · `03-registre.md` (§5) ·
Hermès `agent/redact.py`, `agent/chat_completion_helpers.py:1486`
**Origine :** question de Francis Babin, 22/09/2026 — *« Nexa pendant Projet Alpha était déjà très
prudente […] peut-être qu'Hermès est nativement comme ça, ou alors c'est grâce à la nature de Nexa
elle-même dans SOUL.md et AGENTS.md »* · contexte immédiat : la création de la boîte
`contact@exemple.fr` et de son mot de passe
**Changelog 1.1 :** revue du 23/09 — **la valeur est masquée jusqu'à la fin de la ligne** (défaut A : une phrase de passe à plusieurs mots fuyait à partir de son deuxième mot).
**Changelog 1.0 :** première version — enquête sur le redacteur natif d'Hermès, module partagé,
masquage du brut, refus au registre.

---

## 1 — Positionnement

### 1.1 Le problème

Une mémoire n'est pas une conversation qui s'efface. Elle est **relue** à chaque rappel,
**consolidée** par un modèle, **versionnée dans git**, **sauvegardée**, et — dans le cas d'EXIA
SEED — destinée à être **publiée en open source** dans sa structure. Un mot de passe écrit dedans y
survivrait à sa propre rotation, et ressortirait des mois plus tard dans un contexte que personne
n'aura prévu.

### 1.2 La réponse à la question de Francis

**Ce n'était pas Hermès. C'était elle.**

Hermès possède bien un redacteur (`agent/redact.py`), actif par défaut
(`security.redact_secrets: true`). Mais son en-tête de module est explicite sur son périmètre :

> *Regex-based secret redaction **for logs and tool output**.*

Et le masquage au moment de l'enregistrement, qui avait existé, a été **retiré** en 2026 — le
commentaire du code (`chat_completion_helpers.py:1486`) explique pourquoi :

> *Masking a credential to `***` here poisons that replay: the model reads back its own
> `PGPASSWORD='***' psql …` call and copies the placeholder into the next tool call, breaking every
> credential-dependent command on the second turn (#43083). The masking also provided no real
> protection — the same secret still leaks verbatim through tool OUTPUT […]. Keeping secrets out of
> the replayable store is a separate tokenization/vault concern.*

**Conclusion.** Ce que l'utilisateur tape n'est jamais masqué : ni dans `state.db`, ni dans ce que
reçoit un fournisseur de mémoire. La prudence observée pendant l'année Projet Alpha — Nexa qui
demandait de purger après une information sensible — venait de **son âme et de ses règles**, pas du
moteur. Elle reposait donc sur le jugement d'un modèle, c'est-à-dire sur quelque chose qui peut
varier d'une version à l'autre.

Un garde-fou déterministe était nécessaire.

---

## 2 — Décisions

### D1 — Deux comportements, selon la couche

| Couche | Comportement | Pourquoi |
|---|---|---|
| **Registre** (`memoire_noter`) | **refuser**, avec un message clair | Noter est un geste délibéré : on peut le refuser, et l'agent peut l'expliquer à l'utilisateur. |
| **Brut** (la conversation) | **masquer la valeur**, garder la phrase | On ne peut pas refuser d'écrire une conversation : le brut est la source de vérité de ce qui s'est dit. Mais la valeur du secret n'a pas besoin d'y être. |

C'est la seule asymétrie du système, et elle est volontaire.

### D2 — Aucune règle sur les longues suites de chiffres

**Contexte.** La tentation est forte : un numéro de carte, un IBAN, un code sont des suites de
chiffres.
**Décision.** Aucune règle de ce type.
**Raison.** Le SIRET `123 456 789 00012` doit être mémorisable — c'est une donnée de travail, elle
figure sur chaque facture. Un numéro de téléphone de client aussi. Un filtre sur les chiffres
rendrait la mémoire inutile pour le métier de Francis.
**Conséquence assumée.** Un code communiqué sans mot-clé (« le code de la porte c'est 4471 »)
passe.

### D3 — Une seule définition, partagée

**Décision.** Le filtre vit dans `secrets.py`, importé par l'ingestion et par le fournisseur.
**Raison.** La première version avait le filtre dans `__init__.py`, utilisable seulement par le
registre. Dupliquer l'expression régulière pour le brut aurait garanti la divergence des deux
copies à la première correction.

### D4 — Le mot-clé reste, la valeur disparaît

```
avant :  Le mot de passe de contact@exemple.fr : Ab12!cDeF
après :  Le mot de passe de contact@exemple.fr : [secret masqué]
```

**Raison.** La phrase reste compréhensible — pour un humain qui relit, comme pour le modèle qui
consolidera. Remplacer toute la phrase produirait un brut troué, incompréhensible six mois plus
tard. Et le fait « Francis a communiqué un mot de passe ce jour-là » est une information légitime.

### D5 — Un masquage est journalisé et compté

**Décision.** Chaque masquage incrémente le compteur `secrets_masques` de la télémétrie et écrit un
avertissement dans les journaux : *« secret masqué dans le brut — il n'a pas été écrit en clair »*.
**Raison.** Un garde-fou muet ne s'améliore jamais. Un compteur qui monte est le signal qu'il faut
changer une pratique — ou rappeler à l'utilisateur de ne pas dicter ses mots de passe.

---

## 3 — Construction

### 3.1 Ce qui est reconnu

| Forme | Exemple |
|---|---|
| Clé OpenAI / compatible | `sk-…` (16 caractères et plus) |
| Jeton GitHub | `ghp_…` (20 et plus) |
| Jeton Slack | `xox[bp]-…` |
| Clé AWS | `AKIA…` |
| Clé privée | `-----BEGIN … PRIVATE KEY-----` |
| Mot-clé suivi d'une valeur | `mot de passe`, `password`, `passwd`, `mdp`, `passphrase`, `code secret`, `code pin` — suivis, à moins de 40 caractères, de `:` ou `=` ou de « est <valeur> » ; **la valeur court jusqu'à la fin de la ligne** |

**Jusqu'à la fin de la ligne, pas jusqu'au premier espace** (revue du 23/09, défaut A). La version
1.0 masquait `\S+`, c'est-à-dire un seul mot : « Le mot de passe du wifi : correct horse battery
staple » devenait « … : [secret masqué] horse battery staple ». Masquer quelques mots de trop est
l'échec sûr ; en laisser passer un ne l'est pas.

Les 40 caractères de tolérance viennent d'un **défaut trouvé au test** : la première version
exigeait le séparateur immédiatement après le mot-clé, et laissait passer « Le mot de passe **NAS**
: Ab12 », parce qu'un mot s'intercalait.

### 3.2 Interface

```python
contient_secret(texte) -> bool          # le registre refuse
masquer(texte) -> (texte_masqué, n)     # le brut masque et compte
```

`masquer` conserve le séparateur (`:`, `=`) ou le verbe (« est ») et ne remplace que ce qui suit.

---

## 4 — Portée réelle

| Texte | Verdict | Raison |
|---|---|---|
| « Le mot de passe NAS : Ab12!cD » | **masqué** | mot-clé + valeur |
| « mon mdp est Ab12cD » | **masqué** | forme verbale |
| « password=hunter22 » | **masqué** | affectation |
| « clé sk-abcdef… » | **masqué** | forme reconnaissable |
| « Le mot de passe du wifi : correct horse battery staple » | **masqué en entier** | phrase de passe (v1.1) |
| « mdp : Ab12 cD!7 » | **masqué en entier** | mot de passe à espace (v1.1) |
| « Rappelle-moi de changer le mot de passe NAS » | conservé | aucune valeur : c'est une tâche |
| « SIRET 123 456 789 00012 » | conservé | donnée de travail (D2) |
| « Tarif : 45 € l'élément » | conservé | donnée de travail |
| « le code de la porte c'est 4471 » | **non détecté** | limite assumée (D2) |

---

## 5 — Tests — 22/09/2026

| # | Test | Ce qu'il prouve |
|---|---|---|
| 1 | Le tour est écrit malgré le secret | le brut masque, il ne refuse pas (D1) |
| 2 | Le mot de passe n'apparaît pas dans le fichier | le masquage est effectif |
| 3 | La clé d'API n'apparaît pas | idem sur les clés |
| 4 | La phrase reste lisible avec son marqueur | D4 |
| 5 | Le SIRET est conservé | D2 |
| 6 | Le tarif est conservé | D2 |
| 7 | « changer le mot de passe NAS » reste intact | pas de faux positif sur une tâche |
| 8 | Le compteur `secrets_masques` vaut 2 | D5 |
| 9-11 | Le registre refuse toujours, rien n'y est écrit | non-régression de l'étape 3 |

**11 réussis sur 11.** Non-régression complète : **21 (étapes 1-2) + 16 (étape 3) + 25 (étape 4)**,
soit **73 tests au total**, tous au vert.

Script : `tests/test_annexe_A1_secrets.py`.

---

## 6 — Limites, et la règle d'usage qui va avec

1. **Filtre lexical** : un secret formulé sans mot-clé reconnu passe (D2).
1 bis. **Masquage jusqu'à la fin de la ligne** : « mot de passe : Ab12 et le login est utilisateur » perd
   aussi « et le login est utilisateur ». Excès de prudence assumé.
2. **Le brut n'est plus strictement fidèle à ce qui a été tapé** — c'est un écart assumé avec
   l'invariant n°1. Nuance importante : le fichier reste en **ajout seul** et n'est **jamais
   modifié après coup** ; le masquage a lieu **au moment de l'écriture**, et il est compté.
   L'alternative — écrire le secret puis « nettoyer » plus tard — violerait bien plus gravement
   l'invariant.
3. **La règle d'usage prime sur le filtre.** Un identifiant ne se dicte pas à un assistant : il
   s'écrit directement dans un fichier protégé.

*(passage retiré de la version publique : données personnelles)*

---

## 7 — Invariants

| Invariant | Statut |
|---|---|
| 1. Le brut est sacré | **respecté avec un écart documenté** : ajout seul, jamais modifié après écriture ; seule la valeur d'un secret est remplacée à l'écriture, et le remplacement est compté |
| 3. Le moteur voit tout, le modèle reçoit peu | renforcé : le modèle consolidateur ne verra jamais un secret |
| 4. Panne = dégradation | le filtre ne peut pas faire échouer une écriture : en cas d'erreur, le texte passe tel quel plutôt que de perdre le tour |
