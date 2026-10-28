# A2 — Les consignes de mémoire (annexe transversale)

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Version :** 1.1
**Date :** 23 septembre 2026
**Statut :** Code, testé (19/19 + revue 23/23 + 73 de non-régression), vérifié sur GPT-6 réel,
déployé chez Nexa (plugin 0.2.0) le 23/09/2026 à 07h25
**Référence :** `02-ecoute-brut.md` (§3 D11, §4 écriture) · `04-consolidation.md` (D17) ·
`A1-garde-fou-secrets.md` · `R1-revue-2026-09-23.md` (défauts B, B', G)
**Origine :** Francis Babin, 22/09/2026 — *« il n'existe aucun moyen de dire ne l'écris pas du
tout »*
**Changelog 1.1 :** revue du 23/09 — « ne note pas ça » sans annonce vise aussi ce qui vient d'être
dit (défaut B) ; le tour porteur d'une consigne n'est plus jamais écrit (défaut G, trouvé sur GPT-6
réel) ; retraits dans un journal dédié qui survit à la fermeture des lots (défaut B').
**Changelog 1.0 :** première version — deux formules détectées sans modèle, repère pour le
hors-brut, marquage non destructif pour le retrait.

---

## 1 — Positionnement

### 1.1 Le manque

Le garde-fou anti-secret (annexe A1) masque ce qu'une machine sait reconnaître : mots de passe,
clés. Tout le reste est écrit tel quel — et c'est voulu : une mémoire qui trie à la source ne vaut
rien.

Mais il manquait le geste inverse : **la décision de l'utilisateur**. Une confidence sur un client,
une colère, une affaire de famille n'ont aucune raison d'être consolidées, versionnées et relues
six mois plus tard, même si elles ne contiennent aucun secret technique.

### 1.2 Trois cas

| Ce que dit l'utilisateur | Ce qui est protégé |
|---|---|
| « Ne note pas ça **:** j'ai un souci avec un client » · « hors mémoire **—** … » | **le message courant** : la consigne annonce ce qui suit |
| « Ne note pas ça » · « Ne note pas ça, c'est personnel » · « n'écris pas ça » | **le message courant ET le précédent** : « ça » désigne ce qui vient d'être dit |
| « Oublie ce que je viens de dire » · « efface ce que j'ai dit » · « retire mon dernier message » | **le message précédent** |

Dans les trois cas, **le message qui porte la consigne n'est jamais écrit** : il ne reste qu'un
repère horodaté.

---

## 2 — Décisions

### D1 — Détection déterministe, sans appel au modèle

**Options.** (a) laisser l'agent comprendre l'intention et appeler un outil · (b) détecter la
formule par expression régulière à l'écriture.
**Décision.** (b).
**Raison.** Un garde-fou qui dépend du jugement d'un modèle n'est pas un garde-fou : il fonctionne
la plupart du temps. C'est précisément le constat de l'annexe A1 : la prudence de Nexa pendant
l'année Projet Alpha reposait sur son jugement, pas sur le moteur.
**Conséquence.** La consigne marche même si le modèle ne l'a pas comprise, même s'il est en panne.

### D2 — Le hors-brut laisse un repère, pas un trou

Quand un tour n'est pas conservé, une ligne le dit :
`<!-- 21:55 échange non conservé à la demande de francis -->`.
**Raison.** Une mémoire avec des trous invisibles ment par omission. En relisant un brut six mois
plus tard, on doit pouvoir distinguer « il ne s'est rien passé » de « il s'est passé quelque chose
qu'on n'a pas gardé ». Le repère ne contient **rien** du contenu : ni texte, ni résumé, ni sujet.

### D3 — Le retrait marque, il ne supprime pas

**Options.** (a) réécrire le fichier sans les lignes retirées · (b) les inscrire dans un journal
des retraits que la consolidation respecte.
**Décision.** (b) : `raw/.retraits.jsonl`, en ajout seul.
**Raison.** (a) violerait l'invariant n°1 et **casserait la chaîne d'intégrité** d'un lot déjà
fermé. Et cela créerait un précédent — « on peut réécrire le brut » — qui ruinerait la valeur de
preuve de toute la couche.
**Conséquence.** Le contenu retiré reste lisible par qui a accès au VPS ; il n'entre simplement
jamais dans la mémoire consolidée. On dit ce qu'on fait, et on ne promet pas une suppression qu'on
ne fait pas.

### D4 — Le journal des retraits fait autorité, et survit aux fermetures

**Défaut B' (revue du 23/09).** En version 1.0, le « dernier tour » était gardé dans l'état du lot
ouvert, remis à zéro à chaque fermeture. Un retrait demandé juste après la fermeture de 23h55 ne
savait plus quoi viser — il échouait même avec une exception.
**Décision.** Le dernier tour écrit vit dans son propre fichier (`raw/.dernier_tour.json`), sous le
nom **final** de son lot ; le retrait s'inscrit dans `raw/.retraits.jsonl` quel que soit l'état du
lot visé, **ouvert ou fermé**. Un lot fermé n'est jamais touché : sa chaîne reste intacte (vérifié
par test).

### D5 — La consolidation obéit au journal

Le lecteur de lots (`_lignes_de`) exclut les lignes inscrites au journal des retraits. Vérifié par
test et sur GPT-6 réel : le modèle ne voit ni le contenu retiré, ni les repères.

### D6 — Sans annonce, « ça » désigne ce qui vient d'être dit

**Défaut B (revue du 23/09).** En version 1.0, « ne note pas ça » ne protégeait que le message
courant. Or dans l'usage naturel du français, on se confie **puis** on dit « ne note pas ça ».
Reproduit : *« Je prépare une surprise pour l'anniversaire d'un ami »*, puis *« Ne note pas
ça, c'est personnel »* → **la confidence partait au consolidateur**. Le vœu explicite de
l'utilisateur n'était pas respecté.
**Règle adoptée.** Si la consigne est suivie d'un **deux-points ou d'un tiret**, elle annonce ce qui
suit dans le même message : seul ce message est protégé. Sinon, elle vise **aussi** le message
précédent.
**Le doute profite à l'oubli.** Quand l'utilisateur écrit « J'ai un souci avec X, ne note pas ça »
en un seul message, la règle protège ce message et retire aussi le précédent, peut-être anodin.
C'est l'échec choisi : au pire, un tour anodin n'est pas consolidé ; jamais une confidence ne l'est.

### D7 — Le message qui porte la consigne n'est jamais écrit

**Défaut G (revue du 23/09) — trouvé sur GPT-6 réel, pas par les tests.** En version 1.0, la
demande « Oublie ce que je viens de dire » était écrite dans le brut. Le tour retiré étant caché au
modèle, **la demande lui apparaissait juste après le tour d'avant** — en l'occurrence, le tarif grêle
de Francis. Le modèle a logiquement conclu que c'était le tarif qu'il fallait oublier : **un fait
juste était perdu par la consigne censée en protéger un autre.**
**Décision.** Tout message porteur d'une consigne est remplacé par un repère, quelle que soit la
consigne. **Une instruction n'est pas un souvenir.**
**Preuve.** Même conversation, même modèle : 3 faits retenus sans le tarif avant la correction,
4 faits avec le tarif après — et aucune des deux confidences dans les pages.

### D8 — Les gestes sont comptés

`tours_non_conserves` (tout message de consigne) et `retraits` (tout tour précédent retiré)
entrent dans la télémétrie quotidienne. S'ils montent beaucoup : faux positifs de la détection, ou
défiance envers la mémoire — deux problèmes qu'il vaut mieux voir que deviner.

---

## 3 — Construction

### 3.1 Les expressions

```python
RE_RETRAIT_PRECEDENT  # (oublie|efface|retire|supprime|annule) … (ce que je viens de dire |
                      #  ce que j'ai dit | ce que je t'ai dit | mon dernier message | ma dernière phrase)
                      # ou : ne (note|mémorise|garde|retiens) pas … ce que je viens de dire
RE_HORS_BRUT          # ne (note|mémorise|garde|retiens|enregistre|conserve) pas
                      # n'(écris|enregistre|en garde) pas · hors (mémoire|brut|dossier) · off the record
_RE_ANNONCE           # juste après la formule : (ça|ca|cela)? suivi de « : » « — » « – »
```

Ordre d'évaluation : retrait explicite d'abord (« ne note pas ce que je viens de dire » contient
aussi la formule du hors-brut), puis hors-brut, annoncé ou rétrospectif selon `_RE_ANNONCE`.

### 3.2 Fichiers

| Fichier | Nature | Contenu |
|---|---|---|
| `raw/.dernier_tour.json` | état, réécrit | `{"fichier": "2026-09-23_01.md", "lignes": [17, 18]}` — nom FINAL du lot |
| `raw/.retraits.jsonl` | ajout seul | `{"fichier", "lignes", "qui", "consigne", "ts"}` — fait autorité pour la consolidation |

Après un retrait, `.dernier_tour.json` est vidé : un second « oublie ça » ne remonte pas plus loin.

### 3.3 Exemple de brut (version 1.1)

```markdown
[07:11 francis] Samedi matin je passe chez Autoplus Valmont, le chef d'atelier s'appelle Damien.
[07:11 nexa] Noté, samedi matin chez Autoplus Valmont.
[07:11 francis] Je cherche un cadeau pour un ami, garde-le pour toi.
[07:11 nexa] D'accord.
<!-- 07:11 retrait: 2026-09-23_01.md lignes 13-14 non consolidables, demandé par francis -->
<!-- 07:11 échange non conservé à la demande de francis -->
[07:11 francis] Pour la grêle, je facture 1 810 € pour un sinistre d'environ 200 bosses.
[07:11 nexa] Compris, 1 810 € pour 200 bosses environ.
```

Un humain lit l'histoire complète, marques comprises. Le modèle consolidateur ne reçoit que les
lignes 11-12 et 17-18.

---

## 4 — Portée

| Ce que dit Francis | Détecté comme |
|---|---|
| « Ne note pas ça : j'ai un souci avec un client. » | hors-brut **annoncé** — ce message seulement |
| « hors mémoire — je te raconte » | hors-brut annoncé |
| « Ne note pas ça, c'est personnel. » | hors-brut **rétrospectif** — ce message et le précédent |
| « n'écris pas ça s'il te plaît » | hors-brut rétrospectif |
| « Oublie ce que je viens de dire. » | retrait du précédent |
| « efface ce que j'ai dit » | retrait du précédent |
| « **Note que** Olivier est chef d'atelier. » | rien — c'est l'inverse |
| « Il faut que je **note les tarifs sur le devis**. » | rien — parle d'autre chose |

---

## 5 — Tests

| Série | Ce qu'elle prouve | Résultat |
|---|---|---|
| `test_annexe_A2_consignes.py` | détection des formules, repères, retrait marqué, tour retiré conservé dans le fichier, invisible au modèle, **la demande de retrait n'est pas écrite**, compteurs | **19/19** |
| `test_revue_20260923.py` §B, §B' | la confidence suivie de « ne note pas ça » ne part plus au modèle ; le tour d'avant reste visible ; retrait **à travers une fermeture de lot**, chaîne intacte | inclus dans **23/23** |
| **GPT-6 réel**, 23/09 | deux confidences protégées par les deux formules, aucune dans les pages ; le tarif grêle voisin retenu | **4 faits justes, 0 fuite** |

---

## 6 — Limites connues

1. **Le retrait ne remonte que d'un tour.** « Oublie tout ce qu'on a dit ce matin » n'est pas
   reconnu.
2. **Un message de consigne est entièrement perdu.** « Oublie ce que je viens de dire, et note que le
   rendez-vous est jeudi » : le rendez-vous est perdu avec la consigne. Règle d'usage : une consigne,
   un message.
3. **Faux positifs possibles.** Une phrase contenant « ne note pas » dans un autre sens serait prise
   pour une consigne — et, sans deux-points, retirerait aussi le tour précédent. Le repère dans le
   brut rend l'événement visible, donc corrigible.
4. **Ce n'est pas une suppression.** Le texte reste dans le fichier de brut et dans l'historique git.
   Une suppression réelle est un geste manuel, tracé, fait à la demande.
5. **Rien n'est rétroactif.** Un tour déjà consolidé en page avant la consigne n'en sort pas : il
   faudra une opération explicite sur la page (prévue avec la supersession, phase 3).
6. **En phase 1, Nexa ne confirme pas** que le tour n'a pas été écrit. En phase 2, le rappel pourra le
   lui dire.

---

## 7 — Invariants

| Invariant | Statut |
|---|---|
| 1. Le brut est sacré | **respecté** : rien n'est réécrit ni supprimé ; un lot fermé n'est jamais touché ; les retraits vivent dans un journal à part |
| 2. Le rappel ne coûte aucun appel | la détection est une expression régulière |
| 4. Panne = dégradation | une erreur de détection n'empêche jamais l'écriture d'un tour normal |
