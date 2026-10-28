# 05 — Le graphe : des pages aux nœuds reliés

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Version :** 1.0
**Date :** 26 septembre 2026
**Statut :** **Déployé le 26/09/2026** (sans redémarrage) — 30/30 tests de l'étape, 180/180 toutes suites ; essai sur une copie de la
mémoire réelle (17 pages, 104 faits) ; plugin 0.4.0. Conception validée par Francis le 26/09 (*« go,
les tests nous diront si tes hypothèses sont bonnes »*).
**Référence :** `SPEC-EXIA-SEED.md` §5 (le graphe), §4 (métadonnées), §10.1 · `04-consolidation.md`
(les pages que le graphe relie) · `R2-revision-2026-09-26.md` (`dit_le`)
**Origine :** Francis Babin, 20/09 — un nœud FCM = une page ; 10/06 — *« la provenance des arêtes est
dans le MVP : une arête créée sans histoire l'a perdue à jamais »* ; 26/09 — *« go pour l'étape 5 »*.
**Changelog 1.0 :** code, tests, confrontation aux prévisions (§9) — une prévision fausse, expliquée ;
règle « l'utilisateur est implicite » ajoutée à D2 ; trois optimisations sans changement de résultat.
**Changelog 0.1 :** conception.

---

## 1 — Positionnement

Les étapes 1 à 4 ont produit des **pages** : un nœud par sujet (Autoplus Valmont, facturation, Amandine…),
chacune avec ses faits datés et sourcés. Elles ne se connaissent pas. L'étape 5 les **relie** : quand
un sujet s'allume, ceux qui lui sont liés doivent pouvoir s'allumer aussi. C'est la matière du rappel
associatif (étape 6), qui n'est **pas** construit ici.

```
pages (étape 4) ──► graphe (étape 5) ──► rappel à blanc (étape 6) ──► télémétrie (étape 7)
  les faits          qui est lié à qui     ce qui serait remonté          est-ce utile ?
```

**Ce que l'étape 5 n'injecte pas** : rien ne change pour Nexa. Le graphe est calculé, rangé, versionné,
mesuré — et lu par personne jusqu'à l'étape 6.

---

## 2 — Le terrain

### 2.1 Ce que valent les modules FCM de V2.7.2 (audit du 26/09)

| Module | Verdict | Raison, mesurée |
|---|---|---|
| `causal/fcm.py` — `FCMEngine` | **repris tel quel** | numpy seul ; nœuds identifiés par nom ; convention `W[cible, source]`, propagation `sigmoid(W @ A)` |
| `causal/hopfield.py` | **gardé pour l'étape 6** | opérateur matriciel pur, numpy seul |
| `causal/triplet_extractor.py` | **écarté** | sur les 104 faits réels : 13 « triplets », **tous des dates ou des âges**, zéro relation entre deux sujets. Le sujet est codé `"user"` en dur ; motifs à la 1re personne (« j'habite… ») alors que les faits sont à la 3e ; l'apostrophe typographique ’ les fait échouer. Sur 97 lignes brutes de Francis : 8, idem. |
| `fcm_store.py`, `weight_store.py` | **écartés** | matrices denses en JSON, 15 noms de domaines de l'ancienne Nexa codés en dur, erreurs d'écriture avalées, fenêtre où `load()` rend `None` pendant la rotation |
| `fcm_lifecycle.py`, `sprouting.py`, `fcm_signature.py`, `concept_tagger.py` | **écartés** | exigent un embedder, KMeans, ChromaDB ou KeyBERT ; `sprouting` charge spaCy et torch **à l'import** (18 s mesurées) |
| `surprise.py` | **reporté en phase 3** | apprend en comparant prédiction et observation : il faut un rappel qui prédit (étape 6) et de l'usage |
| `fcm_recall.py` | écarté | compare deux empreintes déjà calculées par embedding ; ne transforme pas une question en nœuds |
| `memories/resonance.py` | écarté | matrice 5×5 fixe des cinq types de mémoire d'EXIA ; pas un graphe de sujets |
| `memories/score_utils.py` (`cab_pull`…) | **gardé pour l'étape 6** | fonctions pures, zéro dépendance |

Pièges de `FCMEngine` relevés par l'audit :
- `add_node` refuse au-delà de **50 nœuds** (codé en dur) → on construit le moteur **en une fois** par
  son constructeur, qui accepte n'importe quelle taille (les sondes du 20/09 l'ont fait à 5 000).
- **Plancher de la sigmoïde** : au repos, chaque nœud flotte entre 0,076 et 0,11. Le rappel devra lire
  l'activation **au-dessus du repos**, pas l'activation brute (étape 6).
- Seuls les nœuds `is_input=True` gardent la valeur injectée : tous les nœuds seront marqués entrée.
- `causal/__init__.py` importe quatre autres modules : le moteur est donc **copié seul** dans le plugin
  (fichier inchangé, empreinte SHA-256 consignée), pas importé depuis le paquet EXIA.

### 2.2 D'où peuvent venir les liens — mesuré sur les vraies pages

| Source | Ce qu'elle trouve sur 17 pages / 104 faits | Qualité |
|---|---|---|
| **Mention** : un fait de A cite B par son nom ou un alias | 15 paires, 23 mentions — **dont 13 vers `francis`** | faible et dominée par un seul nœud |
| **Co-citation, même ligne** : deux faits de A et B tirés de la même phrase | 13 paires | **forte et juste** : Autoplus Valmont — Pascal Ménard (4), facturation — Autoplus Valmont (4), débosselage — Autoplus Valmont (3) |
| **Co-citation, lignes voisines (± 3)** | 19 paires | plus large ; trouve des liens vrais que personne n'a écrits (facturation — réutilisation des outils : la règle est née pendant l'envoi des factures) |
| Triplets V2.7.2 | 0 relation | inutilisable (§2.1) |

**Le constat qui fonde la conception** : ce qui a été **vécu ensemble** — dit dans la même phrase ou
dans des échanges voisins — relie mieux que ce qui a été **nommé**. C'est aussi le principe de la
mémoire humaine : l'hippocampe lie ce qui est vécu ensemble, dans le même épisode.

---

## 3 — Décisions d'architecture

### D1 — Le graphe est une fonction des pages
Les pages (versionnées par git) sont la seule source de vérité. Le graphe est **recalculé
intégralement** depuis elles, de façon déterministe : mêmes pages → même graphe, au bit près.
**Écarté** : un graphe tenu à jour par petites touches, qui peut dériver des pages sans qu'on le voie.
Coût : quelques millisecondes à 17 nœuds ; à mesurer à 2 000 (§8).
*Écart à la spec §10.1* (« le rejeu du journal reconstruit la matrice ») : la garantie devient plus
forte — **le recalcul depuis les pages reconstruit exactement le graphe**.

### D2 — Deux sources de liens, toutes deux sans modèle
1. **Vécu ensemble** — deux faits de nœuds différents citent la même ligne de brut (preuve forte), ou
   des lignes du même lot distantes de 1 à 3 (preuve plus faible, décroissante avec la distance).
2. **Nommé** — un fait du nœud A contient le nom ou un alias (≥ 4 lettres, sans accents, en mot entier)
   du nœud B.

**L'utilisateur et l'agent sont implicites** *(ajouté au codage)* : leur nom écrit dans un fait n'est
pas une preuve « nommé ». Le modèle écrit « Francis a… » dans presque chaque fait ; sans cette règle,
francis ↔ liste de courses pesait 0,43 sur six seules phrases « Francis a effectué ses courses… », et
avec le temps tout aurait été relié à lui. Même logique que le contrôle de citation (D5 du doc 04).
Les liens « vécu ensemble » vers eux restent : eux sont réels.

**Écartés** : les triplets (§2.1) ; demander au modèle de consolidation « quels autres nœuds ce fait
concerne » (spec §6.2) — possible plus tard dans le même appel, mais c'est de la confiance là où les
deux sources ci-dessus sont des **preuves vérifiables**. À réévaluer si le graphe s'avère trop creux.

### D3 — Des liens symétriques
Être dit ensemble ou se citer, c'est une **association**, pas une causalité. Les liens sont symétriques ;
les liens dirigés (« a mené à », « a causé ») viendront en phase 3 avec leurs propres preuves.

### D4 — Le poids : preuves saturées, puis amorties par la popularité
Pour chaque paire, on additionne ses preuves `e` (même ligne 1,0 · voisine à distance d : 0,5/d ·
mention 0,7), puis :

```
s(a,b) = 1 − exp(−e / κ)                       saturation : dix preuves ne valent pas dix fois une
w(a,b) = s(a,b) / √(d(a) · d(b))  (d ≥ 1)       d(x) = somme des s de x : sa popularité
```

La seconde ligne est la **normalisation symétrique d'un graphe**, standard en théorie spectrale des
graphes : un lien vers un nœud qui touche tout (`francis`) pèse moins qu'un lien vers un nœud rare
(`pascal_menard`). En clair : *un indice commun à tout le monde n'apprend rien*. κ et les poids des
preuves sont des valeurs de départ, calibrées au codage sur les données réelles et consignées.
**Écarté** : l'information mutuelle ponctuelle (PMI), plus juste en théorie mais instable sur des
comptes aussi petits (1 à 4 preuves par paire).

### D5 — Chaque lien porte sa provenance
Pour chaque arête : ses preuves — type, fait source (page + texte court), lignes de brut, `dit_le`.
*« D'où vient ce lien ? »* a toujours une réponse. Exigence de Francis du 10/06, tenue dès le MVP.

### D6 — Un format texte, versionné avec les pages
`memoire/graphe/` :
- `noeuds.json` — nœuds dans un ordre stable (date de création, puis nom), type, alias ;
- `aretes.json` — la liste creuse des arêtes, poids et preuves ;
- `rapport.json` — chiffres du dernier calcul (§7).

Commités avec la consolidation : **`git log graphe/aretes.json` raconte l'histoire du graphe**. Aucune
matrice sur disque : elle est reconstruite en mémoire depuis la liste creuse quand le rappel en a
besoin (32 Mo à 2 000 nœuds en `float64`, rien à 17). **Écarté** : un instantané `.npz` binaire — illisible,
lourd dans git, redondant avec D1.

### D7 — Calculé après chaque consolidation
Dans le même processus à part (D18 du doc 04), après l'écriture des pages et avant le commit. Zéro
appel au modèle. Un échec du graphe **n'annule pas** la consolidation : les pages sont écrites, le
graphe sera recalculé au passage suivant (panne = dégradation). Un outil `outils/graphe.py` le calcule
à la demande (premier calcul, contrôle).

### D8 — Plafond 2 000 nœuds, alerte à 80 %
Spec §5.2. Au-delà : représentation creuse, pas plus de RAM.

---

## 4 — Algorithme

```
1. lire les pages                → nœuds (ordre stable), faits (texte, src, dit_le)
2. index des lignes citées       → (lot, ligne) → [(nœud, fait)]
3. preuves « vécu ensemble »     → pour chaque ligne citée, les autres nœuds sur la même ligne
                                   (1,0) et sur les lignes du même lot à distance 1..3 (0,5/d)
4. preuves « nommé »             → alias de chaque nœud (normalisés) cherchés dans les faits des autres
5. pour chaque paire             → e, s, puis w normalisé (D4) ; pas de boucle sur soi-même
6. écrire noeuds.json, aretes.json, rapport.json (tri stable → sortie identique au bit près)
```

Pour l'étape 6 : `charger_moteur()` rend un `FCMEngine` construit depuis ces deux fichiers.

---

## 5 — Prévisions (à confronter au codage)

| Grandeur | Prévision |
|---|---|
| Nœuds / arêtes sur les données du 26/09 | 17 / ≈ 25 à 35 |
| Voisins les plus forts de `autoplus_valmont` | `pascal_menard`, `facturation`, `debosselage_sans_peinture`, `autoplus_rocheval` |
| Poids des liens vers `francis` | nettement sous ceux entre nœuds rares |
| Nœuds isolés | quelques-uns (`achat_outillage`, `amandine`… un seul fait) — **attendu, pas un défaut** |
| Calcul complet, 17 nœuds | < 20 ms |
| Calcul complet, 2 000 nœuds synthétiques | < 2 s (en arrière-plan) |
| Propagation depuis `autoplus_valmont` (au-dessus du repos) | ses voisins directs s'allument, `stephane` ou `achat_outillage` non |

---

## 6 — Tests prévus

1. **Déterminisme** : deux calculs sur les mêmes pages → fichiers identiques au bit près.
2. **Recalcul = reconstruction** : effacer `graphe/`, recalculer → identique.
3. Même ligne > ligne voisine > rien ; la distance affaiblit.
4. Mention par alias, sans accents, en mot entier (« Rocheval » ne relie pas « Rochevalette »).
5. Amortissement : un nœud relié à tout pèse moins par lien qu'un nœud rare.
6. Symétrie ; aucune boucle sur soi-même.
7. Provenance : toute arête a au moins une preuve, et chaque preuve pointe vers un fait existant.
8. Un fait retiré par l'utilisateur (`.retraits`) ou une page supprimée → ses liens disparaissent.
9. Plafond : au-delà de 2 000 nœuds, refus propre et alerte.
10. Échec du graphe → consolidation quand même réussie, pages écrites.
11. `charger_moteur()` → `FCMEngine` dont `W[cible, source]` correspond à `aretes.json`.
12. Performance : 2 000 nœuds synthétiques.
13. **Sur les vraies pages** (copie) : confronter §5.
14. Non-régression : les 150 tests existants.

---

## 7 — Télémétrie

`graphe/rapport.json` à chaque calcul : nœuds, arêtes, densité, degré max et son nœud, nœuds isolés,
part des preuves par type, durée du calcul, taille du plus grand groupe connexe, alerte plafond.

---

## 8 — Implémentation

| Fichier | Rôle | Lignes |
|---|---|---|
| `graphe.py` | lecture des pages, preuves, poids, rapport, `charger_moteur()` | ≈ 280 |
| `moteur/fcm.py` | `FCMEngine` de V2.7.2, **inchangé** — SHA-256 `bb74b91d…c8931e` (vérifié par test) | 421 |
| `outils/graphe.py` | `--calculer`, `--voisins NŒUD`, `--propager NŒUD` (au-dessus du repos) | ≈ 80 |
| `consolidation.py` | appel après l'écriture des pages ; échec toléré et tracé (`graphe` dans la télémétrie) | + 12 |
| `pages.py` | analyseur YAML compilé (libyaml) quand il existe | + 3 |

**Trois optimisations, résultat identique au bit près** (vérifié par `cmp` sur la copie réelle) :
1. paires « vécu ensemble » par fenêtre glissante sur les lignes triées, au lieu de toutes les paires ;
2. recherche des alias par suites de mots dans un dictionnaire, au lieu de tester chaque alias de
   chaque nœud sur chaque fait (14 millions de tests à 2 000 nœuds) ;
3. YAML compilé : 2,6 s → 0,3 s pour 2 000 pages.
Effet mesuré à 2 000 nœuds : **7,5 s → 2,4 s → 0,48 s**.

---

## 9 — Prévisions confrontées aux résultats

Sur une copie de la mémoire réelle du 26/09 (17 pages, 104 faits) :

| Prévision (§5) | Mesuré | |
|---|---|---|
| 17 nœuds, ≈ 25 à 35 arêtes | 17 nœuds, **24** arêtes (21 après la règle « implicite ») | ≈ |
| Voisins de `autoplus_valmont` : `pascal_menard`, `facturation`, `debosselage_sans_peinture`, `autoplus_rocheval` | exactement ces quatre (facturation 0,32 · Ménard 0,27 · débosselage 0,21 · Rocheval 0,21) | ✓ |
| Liens vers `francis` nettement plus faibles | **faux au premier calcul** : francis ↔ liste de courses 0,43 (bruit « nommé », corrigé par la règle implicite) et francis ↔ application personnelle 0,48 — **vrai lien** (19 preuves « vécu ensemble » : un sujet personnel suivi sur sa fiche). Après correction : depuis `autoplus_valmont`, francis ne s'allume qu'à +0,05 | ✗ puis ✓ |
| Quelques nœuds isolés (Outillage, Amandine…) | `amandine`, `achat_outillage`, `reperage_temporel_assistant`, `application_liste_courses` | ✓ |
| Calcul < 20 ms à 17 nœuds | 15,9 ms, puis **5,8 à 8 ms** | ✓ |
| Calcul < 2 s à 2 000 nœuds | **7,5 s** au premier codage → **0,48 s** (§8) | ✗ puis ✓ |
| Propagation depuis `autoplus_valmont` : voisins allumés, pas le reste | débosselage +0,38 · Ménard +0,37 · facturation +0,34 · Rocheval +0,31 · destinataires +0,22 · francis +0,05 ; 9 nœuds à moins de +0,05 | ✓ |

Propagation < 50 ms à 2 000 nœuds : **4 à 13 ms**. Mais **charger** le moteur depuis les fichiers prend
0,5 à 0,9 s à 2 000 nœuds : le rappel (étape 6) devra le charger une fois et le garder en mémoire.

---

## 10 — Tests

`tests/test_etape_5_graphe.py` — **30 tests**, tous au vert : déterminisme et reconstruction (2) ;
sources et forces, dont « Rochevalette ≠ Rocheval » et accents (7) ; utilisateur implicite, avec le contrôle
inverse (2) ; amortissement du hub (1) ; symétrie, boucles, `W[cible, source]`, propagation (4) ;
provenance (3) ; retraits et page supprimée (2) ; plafond, ancien graphe conservé (2) ; panne du
graphe sans perte de consolidation, puis rattrapage (3) ; empreinte du moteur (1) ; échelle 2 000
nœuds, propagation, alerte 80 % (3). Non-régression : **180/180** toutes suites.

---

## 11 — Déploiement

**Sans redémarrage de la passerelle** : `__init__.py` est inchangé, et la consolidation tourne dans un
processus à part (D18 du doc 04) qui relit le code sur disque à chaque passage. Il suffit de copier
les fichiers ; le graphe réel est calculé par `outils/graphe.py --calculer`, puis à chaque consolidation.

**Réalisé le 26/09/2026** : 0.3.0 sauvegardée (`staging/exia_seed.v0.3-deploye-20260926`), 0.4.0
copiée, passerelle **non** redémarrée. Premier graphe réel : **17 nœuds, 104 faits, 21 arêtes**, plus
grand groupe connexe 13, 4 isolés, preuves 40 même ligne · 30 voisines · 9 nommé, **7,7 ms**. Commit
`a0d2936` dans l'historique de la mémoire.

---

## 12 — Limites connues

1. **Graphe creux au départ** : 17 nœuds, beaucoup avec un seul fait. Il se densifiera avec l'usage ;
   c'est précisément ce que l'étape 7 mesurera.
2. Les alias sont ceux que le modèle a donnés (2 à 3 par nœud) : la source « nommé » en dépend.
3. Deux sujets évoqués dans la même conversation mais à plus de 3 lignes d'écart ne sont pas liés.
4. Pas d'oubli des liens : c'est la phase 3 (§6.5 de la spec).
5. La preuve d'échelle (2 000 nœuds) est synthétique : les données réelles n'en ont que 17.
6. `aretes.json` pèse ≈ 3,3 Mo à 2 000 nœuds et il est réécrit à chaque consolidation : git en garde
   les différences, à surveiller.
7. Le chargement du moteur (0,5-0,9 s à 2 000 nœuds) impose un cache au rappel (étape 6).
8. **Voie active à construire** *(échange avec Francis, 26/09)* : le rappel associatif est la voie
   passive et gratuite ; la voie active est le modèle lui-même, qui comprend le contexte. Pour qu'elle
   soit complète, Nexa doit pouvoir **chercher** dans sa mémoire (outil), pas seulement y noter. Un
   raté du graphe devient alors une question de coût, pas d'échec.
