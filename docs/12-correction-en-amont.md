# 12 — La correction en amont : fiches d'identité, avis système, « qui parle »

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Version :** 0.2 — 16 octobre 2026 ; **déployé chez Nexa en 0.8.1, phase 1** (calculé et journalisé, rien n’est encore montré à Nexa) — §13
**Origine :** Francis, 16/10, après le banc des souvenirs (docs/11) : *« avec les métadonnées des souvenirs, on devrait
avoir les bons souvenirs qui remontent. Donc est-ce un problème à l'écriture… ? Le truc est peut-être en amont. »*
— puis *« oui go, corrige en amont d'abord »*.
**Référence :** `11-souvenirs-qui-remontent.md`, `04-consolidation.md`, `06-rappel.md`

## 1 — Ce que le diagnostic a montré

Le 15/10, le rappel trouvait la page de l'application de courses — mais elle avait **42 faits** (rayons, boutons,
zones) et **aucun ne disait ce qu'était l'application**. Le souvenir utile était l'identité du sujet ; la mémoire
n'avait que ses détails. C'est aussi ce qui manquait par rapport à notre propre base : le wiki de Karpathy met devant
chaque page de son index **une ligne de résumé** ; notre INDEX.md ne montrait que des alias.

## 2 — Ce qui a été essayé et ABANDONNÉ, sur données : un filet de rareté sur les mots d'alias

Hypothèse : le bruit vient des mots d'alias génériques (« données », « assistant », « application », « place ») qui,
seuls, allument un sujet (étage 2 du rappel). Mesure par déclenchement « mot → sujet » visible, sur les deux quinzaines
(`banc/souvenirs/declencheurs.py`) :

| Signal candidat | Réglage (utiles / déclenchements) | Vérification |
|---|---|---|
| Mot rare dans les faits (1-3 faits) | 7/33 (21 %) | 6/35 (17 %) |
| Mot fréquent dans les faits (10 +) | 16/51 (31 %) | 42/118 (36 %) |
| Rareté dans les paroles de Francis | « facture » 0,38 ≈ « waiting » 0,38 ; « courses » 0,46 ≈ « application » 0,43 | — |
| Mot à majuscule dans son alias | 3/10 | 2/5 (presque aucun alias n'en a) |
| Longueur de l'alias porteur | aucune séparation | aucune séparation |

**Aucun signal symbolique ne sépare le bruit de l'utile** ; les mots rares sont même *moins* utiles. Supprimer l'étage 2
retirerait 55 souvenirs utiles pour 73 inutiles. Le filet n'a pas été construit : régler un filtre sans signal, c'est
ajuster sur le réglage (la leçon de docs/08 §11). Le bruit est une question de *sens* — seul celui qui écrit la page
peut en juger.

## 3 — La fiche d'identité (`fiches.py`)

Une phrase par sujet, 35 mots au plus : **ce que c'est, à quoi ça sert, où le trouver** (si les faits le disent).
- **Écrite depuis la page entière**, pas depuis le lot du jour : la page fait foi. Le durable d'abord (sémantique,
  procédural), puis le reste, 3 000 caractères au plus par page, dix pages par appel.
- **Contrôlée comme un fait** (règle 2 de la consolidation) : tout nom propre, nombre, chemin de la fiche doit figurer
  dans la page ; l'utilisateur et l'agent sont implicites. Refusée → l'ancienne reste. Panne → rien ne change.
- **Stable** : la fiche actuelle est montrée au modèle, « si elle reste juste, rends-la telle quelle ».
- **Posée** dans l'en-tête (`summary`, `summary_date`, juste après les alias) et lisible en tête de page (`> …`).
- **Montrée** : juste après le titre du sujet dans les souvenirs qui remontent (phase 2) ; dans `memoire_lire` ;
  dans INDEX.md, **tronquée à 110 caractères** (l'index est relu par Nexa : il garde sa taille, la page a le reste).
- **Tenue à jour** : à chaque consolidation, pour les seules pages touchées (un second appel, court).
  Réglage `fiches: true` (config.yaml) ; `fiches: false` la coupe.
- **Rattrapage** des pages existantes : `outils/fiches.py --racine … --sortie propositions.json` (essai à blanc par
  défaut), `--ecrire` pour poser (commit git).

**Essai à blanc sur une copie de la mémoire de Nexa (53 pages)** : 6 appels, 15 784 tokens envoyés, 2 826 reçus ;
51 fiches acceptées, 2 refusées par deux défauts du contrôle, corrigés depuis (« Phone » lu dans « iPhone » ; « Francis »,
implicite, absent du texte des pages). Exemple :

> *application de liste de courses* — « Une application de courses partagée avec Claire pour préparer les achats de
> Francis par zones du magasin sans doublons, dont les accès et la procédure API sont documentés dans
> workspace/courses-app/README.md. »

### Coût en tokens (la question de Francis, 16/10)

| Où | Coût | Quand |
|---|---|---|
| Rattrapage des 53 pages | ≈ 18 600 tokens | une fois |
| Consolidation de nuit | ≈ 300 tokens par page touchée, un appel | chaque nuit |
| Souvenirs joints | ≈ 50 tokens par sujet (190 caractères en moyenne), 150 au plus | quand un souvenir remonte |
| INDEX.md | ≈ taille actuelle (fiche tronquée à 110 caractères) | quand Nexa le lit |

## 4 — La mesure (banc « souvenirs », étape `fiches`)

Résultat (format phase 2 : seuil 0,5, 3 sujets × 2 faits ; un message « aidé » = au moins un sujet remonté dont un fait
MONTRÉ ou la fiche est jugé utile) :

| | Réglage (91 messages parlent) | Vérification (94) |
|---|---|---|
| Aidé par un fait montré | 45 (49 %) | 36 (38 %) |
| Aidé par la fiche | 45 | 33 |
| **Aidé par l'un ou l'autre** | **52 (57 %)** | **44 (47 %)** |
| … dont par la fiche SEULE | 7 | 8 |
| Pour rien | 39 | 50 |

- La fiche est jugée utile **aussi souvent qu'un fait** ; elle aide seule 7-8 messages de plus par quinzaine
  (+8 / +9 points). Gain **stable d'une quinzaine à l'autre**, et sans réglage : aucun paramètre n'a été choisi sur le
  réglage — c'est la seule correction de la série qui ne peut pas être de l'ajustement.
- **Le cas de l'incident** (15/10, 16:50, « on va préparer la liste de courses ») : la fiche — rédigée depuis la page
  telle qu'elle était à 16:50, AVANT la règle ajoutée après l'erreur — est jugée utile. Idem sur les messages de courses
  du 10/10 et sur « pourquoi tu n'as pas été voir directement… ».
- **Honnêtement** : le bruit reste élevé (39 et 50 messages « pour rien »). La fiche rend chaque souvenir plus parlant ;
  elle ne choisit pas mieux les sujets. Le bruit d'un souvenir est mesuré : il ne détourne pas Nexa (docs/11 §5).
- Coût du banc : fiches 28 710 tokens, juge 103 521 tokens (quota Codex).

Protocole : chaque fiche est rédigée **depuis la page telle qu'elle était à l'instant du message** (pas de fiche
d'aujourd'hui pour un message du 1er octobre — la fiche des courses mentionne une règle née le 15/10) ; une fois par
version distincte de page (71 versions pour 185 messages qui parlent) ; puis le juge aveugle du banc 8 (même consigne,
« sois exigeant ») dit si la fiche des sujets remontés était utile.

## 5 — Les avis système (`ingestion.py`)

Hermès injecte comme un **message de l'utilisateur** les comptes rendus de ses sous-agents et processus
(« [ASYNC DELEGATION BATCH COMPLETE — …] », « [IMPORTANT: Background process … »). Rien ne les distingue : même auteur,
même identifiant Telegram ; le marqueur interne d'Hermès ne sert qu'à l'affichage. EXIA SEED les écrivait donc **au nom
de Francis**.

Mesuré le 16/10 : 1 495 lignes d'avis dans 26 lots, **15 % du brut** (≈ 41 000 tokens en trois semaines), relues par la
consolidation de nuit — pour **un fait sur 502** (le modèle les écartait déjà de lui-même). Le défaut coûtait des tokens,
pas des faux souvenirs. Et 44 des 362 messages du banc des souvenirs étaient des avis, pas Francis.

Correction : un avis (les formes réelles d'Hermès 0.21.3, pas « tout crochet en majuscules » — un « [IMPORTANT] »
écrit par Francis reste sa parole) est écrit au nom de **`systeme`**, réduit à son en-tête et aux titres de ses tâches
(400 caractères au plus ; 5 599 → 199 sur le cas d'essai) ; une phrase comme « ne note pas ça » citée dans un avis n'est
pas une consigne de Francis. La réponse de Nexa, elle, reste entière. La consolidation traite « systeme » comme
l'assistant (règle 4 : retenu seulement si Francis confirme).

## 6 — « Qui parle » : le trou du filet

Variante trouvée en relisant le contrôle de citation : la consolidation reconnaissait une ligne de l'agent à son
en-tête « [hh:mm nexa] » — donc **seulement la première ligne** d'un message de Nexa ; ses lignes suivantes passaient
pour des paroles de Francis. Mesure : **0 fait** concerné (le modèle respecte la règle 4 de lui-même) — mais le filet
avait un trou. Corrigé : le locuteur est celui de l'en-tête du message, pour toutes ses lignes.

## 7 — Mieux choisir : le diagnostic des parasites (banc `variante`, 16/10 après-midi)

Question de Francis : *« est-ce qu'on a eu une réelle amélioration… ? Est-ce qu'il y a moyen de faire mieux ? »*
La fiche rend chaque souvenir plus parlant ; elle ne choisit pas mieux. Deux causes mesurées :
- **Quatre sujets parasites** prenaient un tiers des souvenirs montrés pour presque rien : plateforme de données
  (39 montrés, 0 utile), JEV (29, 1), délégation (22, 1), contrôle des documents (28, 9). Tous entrent par UN mot :
  « model » (JEV, 42 fois — l'enveloppe d'Hermès « Model: ? »), « subagent », « delegation », « avant », « données »,
  « place », « platform ».
- **La racine** : le score d'un fait est `cab_pull(activation, 1, couverture)` = activation + couverture × (1 − activation),
  **jamais sous l'activation du sujet**. Un mot seul (étage 2) donne 0,6 > seuil 0,5 : TOUS les faits du sujet passent,
  sans un mot commun avec le message. Le parasite et le vrai souvenir associatif passent par **le même canal** : le
  15/10, les faits de l'application de courses n'ont presque aucun mot commun avec la liste de produits — le souvenir
  remonte par pure association (« courses » → l'application), ce qui est le rôle même de la FCM.

Étape `variante` du banc : les 362 messages rejoués sur la mémoire de leur époque, au format phase 2 ; le juge aveugle
ne voit que ce qui est NOUVEAU (déjà jugé = déjà jugé). Contrôle : la variante « base » retrouve exactement 52 / 44.

## 8 — Les enveloppes d'Hermès (`enveloppes.py`)

Le rappel se fait sur le CONTENU, pas sur le protocole : délégation → buts et comptes rendus des tâches (sans « A
background fan-out unit… », « Role: leaf Model: ? ») ; processus → la commande et sa sortie ; document reçu → son NOM
(« 041-2026 AUTOPLUS VALMONT ») ; compaction et autres avis → rien. Un seul module connaît ces formes (l'ingestion
l'utilise aussi). JEV 29 → 7, délégation 22 → 6 ; mais leurs places sont reprises par les parasites des mots courants.

## 9 — Les mots distinctifs (écrits avec la fiche, même appel)

Pour chaque page, 0 à 4 mots SEULS tirés des alias, écrits par la consolidation avec la fiche (`keywords` dans
l'en-tête), contrôlés (un mot doit être dans les alias ; jamais l'utilisateur ni l'agent — « nexa » avait été proposé).
Au rappel (étage 2), un mot d'alias NON distinctif est **courant** : il n'allume le sujet qu'à `POIDS_MOT_COMMUN` (0,5),
sous le seuil — ses faits doivent alors ressembler au message. Trois essais, dans l'ordre, sans rien cacher :

| Essai | Réglage : aidés / pour rien | Vérification : aidés / pour rien | Verdict |
|---|---|---|---|
| Enveloppes seules (référence) | 53 / 38 | 46 / 48 | |
| Mots, consigne 1 (« désigne ce sujet même hors contexte ») | 34 / 10 | 19 / 14 | **rejeté** : perd la moitié des utiles, dont l'incident des courses (« courses » jugé trop courant) |
| Mots, consigne 2 (« quand l'utilisateur emploie ce mot, parle-t-il presque toujours de CE sujet ? ») | 35 / 10 | 21 / 17 | rejeté : perd encore les **règles de conduite** |
| **Consigne 2 + règles de conduite exemptées + mots de 4 lettres** | **45 / 17** | **43 / 26** | **retenu** |

- La consigne 2 a un exemple **absent de la mémoire** (un potager), pas celui des courses : ne pas souffler au banc.
- **Règles de conduite (etat_agent)** : elles se rappellent par la SITUATION (« fais-moi une facture » → « vérifier
  avant envoi »), donc par des mots courants ; une entité, par son NOM — comme la mémoire procédurale humaine, appelée
  par le contexte. Les mots distinctifs ne s'appliquent qu'aux entités et concepts.
- Mots distinctifs de 4 lettres (« exia », « seed », « acme ») : comptent, en correspondance exacte seulement.
- **Honnêteté de méthode** : l'exemption des règles a été décidée en regardant les pertes sur les DEUX quinzaines ; la
  vérification n'est donc plus parfaitement aveugle pour ce choix. Le poids 0,5 et 0,75 donnent exactement le même
  résultat (tout poids < ≈ 0,83 met le mot seul sous le seuil) : le poids est en pratique un interrupteur.
- Les parasites : plateforme 39 → 0, JEV 29 → 0, délégation 22 → 6 ; le contrôle des documents (une règle, exemptée)
  reste fréquent (41) mais utile une fois sur trois.
- **L'incident** : sur tous les messages de courses, l'application remonte SEULE (la recette de pâtes parasite a
  disparu), et le message du 15/10 16:50 est aidé.

## 10 — L'amorçage (la mémoire de travail)

Les sujets du message précédent (moins de 30 minutes) restent un peu actifs : leur activation × `AMORCE` (0,5) se cumule
aux indices du message par **cab_pull** — un « ou » probabiliste, a + b(1 − a) : deux indices faibles qui convergent font
un indice fort. L'amorce SEULE reste sous le seuil (vérifié par un test) : rien n'est resservi sans écho — d'autant que
le bloc du tour précédent est déjà dans l'historique de Nexa. Réglage `amorce_minutes` (0 = coupé).

| | Réglage : aidés / pour rien | Vérification : aidés / pour rien |
|---|---|---|
| Sans amorçage (§9) | 45 / 17 | 43 / 26 |
| **Avec amorçage** | **47 / 18** | **45 / 26** |

+2 de chaque côté, presque sans bruit : « Vas-y, tu peux envoyer » → la facturation ; « la partie WIKI n'est pas
saturée » → EXIA SEED ; « La date d'intervention était aujourd'hui » → Autoplus Valmont. Le cas qui l'avait motivé
(15/10 16:52, « tu as oublié qu'on a une application ») n'est PAS rattrapé (0,3 + 0,3 cumulés restent juste sous le
seuil) : non forcé, pour ne pas régler sur un exemple.
Les vrais ratés restants sont surtout **les souvenirs de Francis lui-même** (sa propre page —
12 et 17 ratés) : la page de l'utilisateur, liée à tout, n'est rappelée que si le message lui fait écho. Prochain chantier.

## 11 — Bilan de la journée

| Format phase 2 (seuil 0,5, 3 sujets × 2 faits + fiche) | Réglage | Vérification |
|---|---|---|
| Faits seuls (docs/11) | 45 aidés · 46 pour rien | 36 aidés · 58 pour rien |
| + fiche d'identité | 52 · 39 | 44 · 50 |
| + enveloppes | 53 · 38 | 46 · 48 |
| + mots distinctifs (règles exemptées) | 45 · 17 | 43 · 26 |
| **+ amorçage** | **47 · 18 (72 % utiles)** | **45 · 26 (63 % utiles)** |

Par rapport aux faits seuls : autant ou plus de messages aidés, **moitié moins de souvenirs inutiles**, précision 49 % →
72 % (réglage) et 38 % → 63 % (vérification). Rien de tout cela n'ajoute d'appel au modèle chez Nexa : les mots
distinctifs viennent dans le même appel que la fiche ; enveloppes, poids et amorçage sont du calcul (< 1 ms).
Coût des bancs du 16/10 (quota Codex) : juge 148 743 tokens, fiches du banc 31 989, trois rédactions de fiches et mots
sur la copie 58 491 — ≈ 239 000 tokens, une fois.

## 12 — Tests

`tests/test_fiches.py` (52 : fiches, mots distinctifs, règles, mots courts, amorçage) · `tests/test_avis_systeme.py` (16) ·
toutes les suites existantes au vert : 16 suites, 359 contrôles (le test R2 regarde désormais l'appel de consolidation).

## 13 — Déploiement chez Nexa : 0.8.1, 16/10/2026, 14 h 35 (accord de Francis : « go, je te laisse déployer »)

1. **Avant** : Nexa inactive (dernière conversation le 15/10 au soir ; un rappel programmé à 13 h 30), aucune
   consolidation en cours. Sauvegardes : plugin 0.8.0 (`staging/exia_seed.v0.8.0-prod-avant-0.8.1-20261016`),
   mémoire complète (`<dossier de l'instance>/memoire-avant-0.8.1-20261016.tgz`), `config.yaml`
   (`staging/config.yaml.avant-0.8.1-20261016`). La copie de l'essai à blanc et la mémoire de Nexa étaient au même commit
   (547f6a9) : l'essai portait bien sur sa vraie mémoire.
2. **Rattrapage** des 53 pages avec le code 0.8.1 (`outils/fiches.py --ecrire`) : 7 appels, ≈ 21 400 tokens ; 53 fiches
   et leurs mots distinctifs posés. Deux défauts trouvés EN déployant, corrigés et testés :
   - le commit git de l'outil n'avait pas d'identité → refusé **en silence** ; l'outil s'identifie désormais comme la
     consolidation et AFFICHE le résultat du commit (`"git": "ok"`) ;
   - « LIEN-PRIVE-RECETTES » (un nom de fichier) lu comme nom propre et mal comparé à cause des tirets → page refusée à
     tort ; comparaison sans les espaces nés des tirets (test qui échoue sur l'ancien code, passe sur le nouveau).
   Commits mémoire : `6174469` (fiches, 53 pages), `ff4c702` (INDEX + graphe recalculé : 99 nœuds, 319 arêtes).
3. **Non-déterminisme** : sur la vraie mémoire, le modèle a redonné « valmont » à Autoplus Valmont et « delegation » à la
   délégation (absents de l'essai du banc). « delegation » est sans effet (règle de conduite, exemptée) ; « valmont »
   est à surveiller (un mot distinctif peut aussi désigner autre chose).
4. **INDEX.md** : 8 114 → 11 032 caractères (≈ + 730 tokens à chaque lecture par Nexa) — plus que prévu, la troncature
   à 110 caractères limite sans annuler.
5. **Plugin** 0.8.1 installé (identique au staging), passerelle arrêtée proprement (SIGTERM, relancée par s6 en ≈ 20 s),
   Telegram reconnecté à 14 h 35 min 56 ; connexions Telegram : 2 établies (pas de boucle zombie, cf. 20/08).
6. **Fumée, lecture seule, code installé sur la vraie mémoire** : mémoire construite en 308 ms (une fois), rappel 1-2 ms.
   Courses → l'application SEULE, avec sa fiche ; « courbe des ventes » → silence (la plateforme de données remontait) ;
   « facture pour Autoplus Valmont » → la bonne page, avec la règle des destinataires.
7. **Phase 1 conservée** : les souvenirs sont calculés et journalisés (`memoire/rappel/*.jsonl`), pas montrés.

## 14 — Reste à faire
- Observer une consolidation de nuit (fiches des pages touchées, mots distinctifs stables ?), puis refaire le test isolé
  de l'incident avec les vraies fiches, puis activer la phase 2 (docs/11, étape 5) avec l'accord de Francis.
- Les souvenirs de l'utilisateur lui-même (§10) ; la stabilité des mots distinctifs d'une nuit à l'autre (le modèle
  n'est pas déterministe : la consigne « rends-les tels quels » et la télémétrie diront s'ils bougent).
- ~~Porter 0.8.1 dans le dépôt de publication~~ — **fait le 16/10 : 0.9.1** (docs/10 §7) ; le français de la 0.9.1 est
  identique au caractère près à la 0.8.1 de Nexa (`test_langues.py`, REF = 0.8.1) — hors noms d'exemple des consignes, fictifs dans la version publique.
- **Anonymiser** docs/11 et docs/12 avant publication (prénoms, garages, adresses) — fait pour cette version publique (`00-AVERTISSEMENT.md`).

## 15 — Les réponses vocales (26/10/2026, accord de Francis : « je te laisse faire les étapes »)
**Constat** (relevé du 26/10) : depuis que Francis parle à Nexa en vocal, ses messages entrent dans le brut, transcrits
sur place (faster-whisper, entre guillemets) ; mais quand Nexa **répond** en vocal, Hermès renvoie pour toute réponse
`[[audio_as_voice]]` + `MEDIA:<fichier>.mp3`. Le texte prononcé n'existe que dans l'appel de l'outil `text_to_speech`
du tour. Du 23 au 25/10, **8 réponses vocales** sont entrées dans le brut réduites à ce marqueur : la consolidation ne
les a jamais lues.

**Décision de Francis** : *« on peut faire le même traitement pour les réponses faites en vocal »* — une réponse vocale
est une réponse écrite comme une autre : entière dans le brut, et retenue comme fait seulement si l'utilisateur l'a
confirmée (règle 4 de la consolidation, inchangée). Les 8 réponses déjà perdues ne sont pas rattrapées (Francis : sans
intérêt durable ; les rattraper aurait demandé de refaire des consolidations, avec un risque de doublons).

**Le correctif** (`enveloppes.reponse_vocale`, appelé par `sync_turn`) : Hermès passe déjà à `sync_turn` la liste
`messages` du tour. Quand la réponse commence par le marqueur vocal, on y prend le `text` de chaque appel
`text_to_speech` **du tour en cours** (tout ce qui suit le dernier message de l'utilisateur), dans l'ordre, et on écrit
`(vocal) <texte prononcé>` à la place du marqueur (repère `repere_vocal` des masques : « (vocal) » / « (voice) »). Texte
introuvable : le marqueur reste tel quel — on ne perd jamais plus qu'avant. Le masquage des secrets s'applique au texte
prononcé comme à tout le brut. Compteur de télémétrie : `reponses_vocales`.

**Tests** : `tests/test_reponse_vocale.py` (10 vérifications, forme de tour relevée dans `state.db`) ; les 18 suites du
dépôt passent. Portage 0.8.1 (Nexa) : mêmes lignes, repère écrit en dur ; 17 suites passent (`test_langues.py` ne
s'applique pas à la 0.8.1, qui n'a pas de masques — elle échoue de la même façon sur la version en production).

**Défaut du banc trouvé en passant (non corrigé)** : `tests/banc.sh` rend le code de sortie de `grep`, pas celui de la
suite : une suite qui plante sur une exception est annoncée réussie (code 0). Lire les lignes « réussis », pas le code.

**Première preuve réelle — 28/10/2026, 21 h 46.** Francis envoie un vocal (merci pour le rappel, un document d'un proche
à envoyer à l'assurance) ; Nexa répond en vocal. Dans le brut : `[21:46 francis] "Merci Nexa…"` puis
`[21:46 nexa] (vocal) Avec plaisir, Francis…` — la réponse prononcée est écrite en clair. Consolidation de 22 h 03 :
**2 faits** dans la page de ce proche (ce qui s'est passé ; ce qui reste à faire), source = la ligne du vocal ; compteur
`reponses_vocales` : 2. La boucle vocale est fermée, dans les deux sens.

