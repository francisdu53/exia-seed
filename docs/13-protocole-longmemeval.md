# 13 — Protocole LongMemEval : EXIA SEED face à une mémoire 18 fois plus grosse

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Version :** 0.2 — protocole **pré-enregistré** le 27/10/2026, avant toute dépense ; **résultats complets le même jour (§13) : H1, H2, H3 tiennent, H4 échoue de peu**
**Origine :** Francis, 27/10 — *« faire un benchmark avec LongMemEval… pour surcharger WIKI EXIA et voir comment se
comporte à terme FCM EXIA »* ; option 1 choisie (« ok option 1, je mets 12 $ sur le compte »).
**Référence :** `09-protocole-locomo.md` (le banc dont celui-ci reprend la plomberie, §11-§14).

---

## 1 — Pourquoi LongMemEval

LongMemEval (Wu et al., ICLR 2025, `xiaowu0162/LongMemEval`) : 500 questions sur des conversations entre **un
utilisateur et son assistant** — la situation de Nexa, que LoCoMo (deux humains entre eux) ne reproduisait pas. Il
teste ce que LoCoMo ne testait pas : les **mises à jour** (« j'ai changé de travail »), le raisonnement **dans le
temps** à partir de la date où la question est posée, les **préférences**, et l'**abstention** (30 questions sans
réponse).

## 2 — Les données et l'échelle (mesurées le 27/10, aucun appel)

Version **nettoyée** publiée par les auteurs (`xiaowu0162/longmemeval-cleaned`), dans `$HOME/banc-longmemeval/donnees`
(empreintes `SHA256SUMS`). Trois tailles : *oracle* (seulement les sessions qui portent la réponse), *S* (≈ 48
sessions, 122 k tokens par question), *M* (≈ 500 sessions par question).

**Option retenue : l'oracle**, 500 questions, **948 sessions, 3,27 M tokens** (dont 0,34 M dits par l'utilisateur).
- **Échelle S** : chaque question avec ses seules sessions (1 à 6) — c'est le réglage « oracle » du papier.
- **Échelle F** : les 500 historiques **fusionnés dans une seule mémoire** (comme l'échelle F de LoCoMo) — chaque
  question y cherche sa réponse au milieu des 499 autres historiques. ≈ 18 fois le volume de LoCoMo.

Écartés : S fusionné (49 M tokens, ≈ 77 $), M (≈ 2 $ par question). Coût et durée hors de portée aujourd'hui.

## 3 — Les adaptations, déclarées avant la mesure

1. **Utilisateur et assistant, comme chez Nexa** (`LOCOMO_ROLES=agent`) : `speaker_a = user` (l'utilisateur),
   `speaker_b = assistant` (l'agent), tous deux implicites. **La règle 4 de la consolidation s'applique** : ce que dit
   l'assistant n'est retenu que si l'utilisateur l'a confirmé. **Conséquence prévue** : les 56 questions
   « single-session-assistant » (qui portent sur ce que l'assistant a dit) seront largement perdues par A, B, C et M —
   par construction, non par défaut de la recherche. Rapportées à part, et le score est donné avec et sans elles.
2. **Fusion en UN utilisateur** (`LOCOMO_HOMONYMES=0`) : « user » et « assistant » ne sont pas renommés par
   historique. C'est la construction même de LongMemEval (S et M mêlent les sessions d'autres utilisateurs dans
   l'historique d'un seul). La page de l'utilisateur concentre les faits des 500 historiques : la saturation (docs/09
   §14.7) y sera éprouvée.
3. **Instant de recherche** : 43 questions ont une session datée après elles (le même jour ou le lendemain, au plus
   23 h 19 — défaut du jeu). A filtre par date, B non : l'instant de recherche est le plus tardif des deux. La consigne
   de réponse garde la date officielle de la question (`Current Date`).
4. **Format** : `banc/longmemeval/convertir.py` recopie les tours tels quels dans le format du banc LoCoMo (sessions
   datées, triées) ; aucune reformulation.

## 4 — Ce qui varie, ce qui est fixe

- **Moteurs** (budget 12 faits pour A, B, C, comme LoCoMo) : **A** EXIA SEED 0.9.2 du dépôt (`memoire_chercher`, avec
  la note anti-saturation et la lecture du `speaker`, docs/09 §14.7-14.8) · **B** embeddings bge-m3 · **C** plein texte
  BM25 · **M** toute la mémoire de la question (S, diagnostic : le plafond de la consolidation) · **E** les sessions
  entières de la question (S, le plafond sans mémoire).
- **Consolidation** : gpt-4o-mini, température 0, la consolidation d'EXIA SEED telle quelle (contrôle de citation,
  fiches). **Aucun réglage d'EXIA SEED sur LongMemEval**, ni avant ni pendant.
- **Réponse** : consigne du dépôt officiel **mot pour mot** (`run_generation.py` @ 9e0b455) — version « faits
  extraits » avec raisonnement pas à pas pour A, B, C, M ; version « historique » pour E ; 800 tokens au plus.
  Vérifiée par programme contre le fichier du dépôt.
- **Juge** : consignes officielles par type et pour l'abstention, **mot pour mot** (`evaluate_qa.py` @ 9e0b455,
  `get_anscheck_prompt`), température 0, une passe, « yes » = juste. Vérifiées par programme. **Seul écart** : juge
  gpt-4o-mini au lieu de GPT-4o (budget). Les scores absolus ne sont donc pas directement comparables à ceux publiés ;
  on compare des MOTEURS entre eux, sous le même juge.

## 5 — Hypothèses, fixées avant la mesure

| | Hypothèse | Critère |
|---|---|---|
| **H1** | à l'échelle fusionnée, A vaut les embeddings | exactitude A_F ≥ B_F − 2 points (toutes questions) |
| **H2** | A ne perd pas plus que B en grossissant | perte S → F de A ≤ perte de B |
| **H3** | le wiki daté gère les mises à jour au moins aussi bien | « knowledge-update » : A_F ≥ B_F |
| **H4** | A reste rapide sur une mémoire 18 fois plus grosse | p95(A_F) < 20 ms |
| **P1** | prédiction (règle 4) | « single-session-assistant » : M_S < 30 % |

Tests appariés (McNemar) : A contre B en S et en F, A contre C en F, S contre F pour A et pour B.
**Si H1 ou H2 échoue, c'est écrit et publié tel quel.**

## 6 — Coût et garde-fous

- Estimation : consolidation ≈ 5,2 $ (3,27 M tokens × 1,6 $/M, mesuré sur LoCoMo) ; réponses ≈ 1,7 $ (4 000, dont E
  ≈ 0,6 $) ; juge ≈ 0,3 $. **Total ≈ 7 $.** Francis a mis 12 $ (marge : l'estimation du banc LoCoMo complet était
  fausse d'un facteur 2).
- **Plafond dur : 10 $** cumulés pour le run (`PLAFOND=10`) ; arrêt local, une relance reprend sans repayer (cache).
- **Étalonnage** : la consolidation commence par 40 questions tirées au sort (graine 2710) ; le coût réel par token
  est extrapolé aux 500 ; **si la projection dépasse 9 $, arrêt et retour à Francis** avant d'aller plus loin. Ces 40
  questions ne servent à aucun réglage (il n'y en a pas) et restent dans la mesure.
- Clé : `$HOME/banc-locomo/.cle-openai` (600), montée en lecture seule dans le conteneur jetable, jamais affichée.

## 7 — Ce que ce banc ne dira pas

- Un score comparable aux classements publiés de LongMemEval (juge différent, réglage oracle et non S).
- Le comportement à 49 M tokens (S fusionné) : c'est l'étape suivante, si celle-ci la justifie.
- Le français : LongMemEval est anglais (masque `en`).

## 8 — Mise en œuvre (éprouvée à blanc le 27/10, 0 $)

`banc/longmemeval/` : `convertir.py` (hôte), `repondre_lme.py`, `juger_lme.py`, `bilan_lme.py`, `lancer.sh` ; les
étapes `preparer`, `fusionner`, `recuperer`, `embeddings` sont celles du banc LoCoMo, rendues compatibles sans rien
changer pour LoCoMo (`LOCOMO_ROLES`, `LOCOMO_HOMONYMES`, instant fourni par le jeu, `preparer --fils N`). Essai à blanc
(modèle factice, sans réseau) : 12 questions, toutes les étapes ; la règle 4 écarte bien les phrases de l'assistant.
Non-régression LoCoMo : jeu à blanc avec homonymes, toutes les étapes.

    cd banc/longmemeval && RUN=oracle PLAFOND=10 sh lancer.sh preparer <ids…> --fils 6
    … fusionner · recuperer · embeddings · repondre_lme · juger_lme · bilan_lme

## 9 — Étalonnage (27/10, 40 questions tirées au sort, graine 2710) — 0,097 $
- 76 sessions (262 015 tokens, 8 % du volume) → 136 appels, 0,097 $ ; **projection consolidation : 1,22 $** pour les
  500 questions (l'estimation de 5,2 $ supposait le surcoût de LoCoMo, où chaque appel relisait davantage d'index :
  1,37 token lu par token de conversation ici, 6,8 sur LoCoMo). Projection totale ≈ 3,5 $ < 9 $ : on continue (§6).
- 172 faits retenus, 126 fragments rejetés : **111 par la règle 4** (paroles de l'assistant non confirmées par
  l'utilisateur : « The Wix 51348 air filter is a direct replacement… »), 15 par le contrôle de citation (nombre ou nom
  propre absent des sources, trop peu de mots en commun). Conforme à §3.1.
- Défaut vu en passant (dépôt, non corrigé) : dans une mémoire en anglais, `log.md` est en anglais mais les MOTIFS de
  rejet restent en français (« repose seulement sur des paroles de l'agent ») — chaînes du contrôle hors des masques.

## 10 — Le banc complet, premier passage (27/10, 11 h 49 → 12 h 47 UTC) — 2,19 $ ; A et C manquants
**Défaut d'EXIA SEED trouvé** : l'étape `recuperer` (moteurs A et C) s'est arrêtée sur une exception —
`moteur/fcm.py:254`, `np.max` sur un tableau vide, appelé par `Rappeleur.__init__` (`rappel.py:102`). **74 des 500
mémoires de question n'ont AUCUN fait** (toutes leurs sessions ne portaient que des paroles de l'assistant, écartées par
la règle 4) : le moteur ne sait pas chercher dans une mémoire vide, il plante au lieu de rendre « rien ». Chez Nexa la
mémoire n'est jamais vide, mais une instance neuve (multi-utilisateur, docs/09 §14.8) le serait. Correction en attente
de l'accord de Francis (O4) ; elle ne touche aucun réglage.

**Résultats partiels** (500 questions, juge officiel, gpt-4o-mini) :

| | tout | sans « assistant » | utilisateur | assistant | préférence | multi-sessions | mises à jour | temps | abstention |
|---|---|---|---|---|---|---|---|---|---|
| E_S — sessions entières | **77,4** | 74,8 | 95,3 | 98,2 | 60,0 | 66,9 | 81,9 | 70,9 | 76,7 |
| M_S — toute la mémoire | 42,4 | 44,4 | 53,1 | 26,8 | 30,0 | 39,7 | 44,4 | 40,9 | 73,3 |
| B_S — embeddings, sa mémoire | 42,8 | 44,8 | 53,1 | 26,8 | 26,7 | 39,7 | 48,6 | 40,2 | 76,7 |
| B_F — embeddings, mémoire fusionnée | 35,4 | 37,6 | 53,1 | 17,9 | 33,3 | 27,3 | 50,0 | 29,1 | 56,7 |

- **La consolidation est le plafond** : toute la mémoire (M) 42,4 % contre les sessions entières (E) 77,4 % — 35
  points perdus à l'écriture, comme sur LoCoMo (41,6 contre 71,8). En S, B égale M : la recherche n'y perd rien.
- **P1 tient** : questions « assistant » 26,8 % (prédit < 30 %) — la règle 4, par construction.
- **Même ce que dit l'utilisateur est à moitié perdu** : 53,1 % contre 95,3 % — la consolidation ne garde que ce
  qu'elle juge « utile plus tard » (règle 3), LongMemEval demande des détails.
- **Les embeddings perdent 7,4 points en fusionnant** (B_S 42,8 → B_F 35,4 ; 72 contre 35, p = 0,0004).
- **La surcharge est plus faible que prévu** : la mémoire fusionnée compte 2 398 faits, 1 960 nœuds, 3 375 arêtes —
  2,3 fois LoCoMo, pas 18 fois : le volume de texte était 18 fois plus grand, mais la consolidation en garde peu.

## 11 — Correction : la mémoire vide (27/10, accord de Francis : « ok »)
- **Premier essai, retiré** : une garde dans `moteur/fcm.py`. Refusé par `test_etape_5_graphe.py`, qui exige le moteur
  **identique au bit près** à celui d'EXIA GHOST V2.7.2 (SHA-256) : on ne modifie pas le moteur, on l'enveloppe.
- **Retenu** : `rappel.py`, au démarrage du rappel — `propagate({})` seulement si le graphe a des nœuds
  (`moteur.n_concepts`), sinon un repos vide. Seul appel concerné : la propagation des entrées (`rappel.py`, plus bas)
  ne part jamais sans nœud. `memoire_chercher` rend alors « Rien de lié dans ta mémoire ».
- Test : `tests/test_memoire_vide.py` — échoue sur la version d'avant (`ValueError: zero-size array…`), passe après.
  **19 suites, toutes réussies.** Aucun réglage touché : les mesures LoCoMo restent valables.
- **Chez Nexa (0.8.1)** : même défaut, même endroit — non corrigé (rien n'est déployé sans accord) ; sa mémoire n'est
  pas vide, mais une instance neuve le serait (multi-utilisateur).
- Même défaut dans le moteur C **du banc** (`banc/locomo/recuperer.py`, `bm25`, écrit pour LoCoMo) : `memoire()` rend
  None sur une mémoire vide. Garde ajoutée (rien à chercher → liste vide).
- Suite du banc relancée pour A et C seulement (`$HOME/banc-longmemeval/lancer-oracle-AC.sh`) : la consolidation, B,
  M et E sont repris tels quels (cache).

## 12 — Les pistes de correction que LongMemEval désigne (à décider par Francis, rien n'est fait)
Ce que mesure le premier passage (§10) : **la consolidation perd 35 points** (M 42 % contre E 77 %), comme sur LoCoMo.
Trois causes, trois pistes, par ordre de gain attendu :
1. **Les détails dits par l'utilisateur sont jetés** (questions « utilisateur » : 53 % contre 95 %). La règle 3
   (« ne retiens que ce qui sera utile plus tard ») écarte les détails que LongMemEval interroge (le nom d'un magasin, un
   prix, une couleur). Piste : la couche **brute de Karpathy** existe déjà (`raw/`, source de vérité, citée par chaque
   fait) ; quand les faits ne suffisent pas, chercher aussi dans le brut et rendre la ligne citée. Le wiki reste la
   mémoire « compilée » ; le brut devient le recours, comme chez Karpathy (sources → wiki → schéma).
2. **Ce que l'assistant a dit est jeté, même quand c'est vrai qu'il l'a dit** (questions « assistant » : 27 % contre
   98 %). La règle 4 protège contre l'auto-persuasion — ce que dit l'agent ne devient pas une VÉRITÉ. Piste : garder ces
   paroles comme des faits **sur la conversation** (« l'assistant a recommandé le filtre Wix 51348 », `dit_par:
   assistant`, non confirmé) — vrais, puisqu'il l'a dit, et marqués comme non vérifiés. Rien ne change pour ce qui est
   tenu pour vrai.
3. **La fusion de mémoires** (B perd 7,4 points de S à F) : la réponse d'EXIA SEED sera connue avec A_F (§13).
Chaque piste sera mesurée seule (O3), sur un échantillon tiré avant de regarder, puis sur la mémoire de Nexa (banc 10)
avant tout déploiement — LongMemEval n'est pas Nexa.

## 13 — Résultats complets (27/10, 16 h 36 UTC) — 2,66 $ au total
**Aucun réglage d'EXIA SEED sur LongMemEval** : la 0.9.2 telle que sortie de LoCoMo, plus la seule garde « mémoire vide »
(§11). Les 500 questions n'avaient jamais été regardées. C'est la première mesure entièrement vierge d'EXIA SEED.

| 500 questions | tout | sans « assistant » | utilisateur | assistant | préférence | multi-sessions | mises à jour | temps | abstention |
|---|---|---|---|---|---|---|---|---|---|
| E_S — sessions entières | 77,4 | 74,8 | 95,3 | 98,2 | 60,0 | 66,9 | 81,9 | 70,9 | 76,7 |
| M_S — toute la mémoire | 42,4 | 44,4 | 53,1 | 26,8 | 30,0 | 39,7 | 44,4 | 40,9 | 73,3 |
| A_S — EXIA SEED | 41,0 | 42,8 | 51,6 | 26,8 | 23,3 | 31,4 | 54,2 | 38,6 | 80,0 |
| B_S — embeddings | 42,8 | 44,8 | 53,1 | 26,8 | 26,7 | 39,7 | 48,6 | 40,2 | 76,7 |
| C_S — plein texte | 39,4 | 41,0 | 53,1 | 26,8 | 10,0 | 29,8 | 54,2 | 34,6 | 86,7 |
| **A_F — EXIA SEED, fusionnée** | **34,2** | 36,0 | 50,0 | 19,6 | 33,3 | 23,1 | **54,2** | 25,2 | **63,3** |
| **B_F — embeddings, fusionnée** | **35,4** | 37,6 | 53,1 | 17,9 | 33,3 | 27,3 | 50,0 | 29,1 | 56,7 |
| C_F — plein texte, fusionnée | 31,6 | 33,8 | 50,0 | 14,3 | 23,3 | 19,0 | 45,8 | 29,1 | 60,0 |

| Hypothèse (§5) | Mesure | |
|---|---|---|
| H1 A_F ≥ B_F − 2 | 34,2 contre 35,4 (26 / 32, p = 0,51) | **tient** |
| H2 perte(A) ≤ perte(B) | −6,8 contre −7,4 | **tient** (échouait sur LoCoMo) |
| H3 mises à jour A_F ≥ B_F | 54,2 contre 50,0 (72 questions, non significatif) | **tient** |
| H4 p95(A_F) < 20 ms | 23,4 ms (médiane 11,4 ; B : 538 ms) | **échoue** |
| P1 assistant M_S < 30 % | 26,8 % | **tient** (prédit) |

- A contre B en S : 41,0 contre 42,8 (17 / 26, p = 0,22) ; A contre C en F : 34,2 contre 31,6 (43 / 30, p = 0,16).
- En S, A rend 3,0 faits en moyenne (B jusqu'à 12) : sur une mémoire de quelques faits, B rend presque tout (≈ M).
- **H4 échoue de peu, et c'est une information** : 1 960 nœuds (contre 726 sur LoCoMo) font passer la recherche de
  4,8 à 23,4 ms (p95). Toujours 23 fois plus rapide que B ; mais la latence croît avec le graphe : à mesurer avant
  toute promesse sur une mémoire de centaines de milliers de faits (l'embarqué, §14.9 de docs/09).
- Le plafond reste la consolidation (M 42 % contre E 77 %) : les trois pistes du §12 visent là.

**Ce que ça dit de la thèse** : sur un jeu jamais vu, sans réglage, à l'échelle fusionnée, EXIA SEED vaut les
embeddings (écart de 1,2 point, non significatif), perd un peu moins qu'eux en grossissant, et fait un peu mieux sur
les mises à jour et l'abstention — sans modèle d'embedding. La confirmation propre que LoCoMo ne pouvait plus donner
(docs/09 §14.10, réserve de méthode).

## 14 — Test : une consolidation exhaustive (27/10, accord de Francis : « go pour ça oui ») — pré-enregistré
**Idée de Francis** : *« le mieux n'est pas d'essayer d'optimiser la consolidation afin que cela soit plus
exhaustif ? »* — la correction en amont (docs/12), avant le recours au brut (§12, piste 1).

**Variante** (banc seulement, `LOCOMO_CONSOLIDATION=exhaustive`, `banc/locomo/preparer.py`) : la règle 3 de la consigne
« ne retiens que ce qui sera UTILE PLUS TARD : personnes, entreprises, lieux… » devient « garde TOUT fait que
l'utilisateur dit de lui et de son monde — personnes, animaux, lieux, biens, achats, activités, projets, préférences,
expériences, santé, travail — AVEC ses détails concrets (noms, marques, modèles, nombres, prix, quantités, couleurs,
dates, durées). Un petit détail vaut d'être gardé : l'utilisateur peut le demander plus tard. » La règle 4
(l'assistant) ne change pas. Vérifié dans un conteneur : la règle 3 est remplacée, la 4 intacte, le masque partagé
non touché. **Le dépôt ne change pas tant que la mesure n'a pas parlé.**

**Partage des questions, fixé AVANT** (tirage 2710, `donnees/tirage-2710.json`) : les **200 premières** = jeu de
DÉVELOPPEMENT (on y regarde, on y règle) ; les **300 autres** = jeu de CONFIRMATION, gardé intact pour valider la
version retenue. Les 40 de l'étalonnage (§9) sont dans les 200.

**Mesures** (échelle S ; référence = le run `oracle` sur les mêmes 200 questions) :
- **E1** — la consolidation garde davantage : M_S (toute la mémoire) gagne au moins 5 points.
- **E2** — EXIA SEED en profite : A_S ne baisse pas.
- Coûts relevés : faits par question, coût de consolidation, taille des contextes.
**Plafond du run : 2 $** (Francis a accordé ≈ 1,5 $).

## 15 — État de l'art : RippleMem (lu le 27/10 ; arXiv 2608.13334, 13/08/2026)
Ji, Li, Cheng, Zhou, Zhang, Tan, Qin — Communication University of China (Pékin). *« From Isolated Retrieval to
Associative Recollection for Long-Term Agent Memory »* : la même intuition qu'EXIA SEED (se souvenir par association,
pas par recherche isolée), une mise en œuvre opposée. Lu sur la version HTML ; les chiffres des tableaux viennent d'un
résumé de la page, à revérifier sur le PDF avant toute citation.

| | RippleMem | EXIA SEED |
|---|---|---|
| Graphe | événements ; arêtes sémantiques (cosinus d'embeddings) et structurelles (personnes, lieux, temps) | pages-sujets d'un wiki ; arêtes de co-occurrence datées, concepts |
| Association | voisinage borné à h sauts, pas de propagation d'activation | **propagation d'activation** (carte cognitive floue, `cab_pull`) |
| Embeddings | oui : nœuds, arêtes, amorçage (Qwen3-Embedding / BGE-M3) | **aucun** |
| LLM à la recherche | oui : un contrôleur décide d'élargir et formule ce qui manque | **aucun** (déterministe) |
| Écriture | extraction LLM par fenêtres de tours, unités autonomes, sans filtre « utile plus tard » | consolidation LLM, contrôle de citation, règles 3-4 |
| Résultats annoncés | LoCoMo J 87,1 ; LongMemEval-S 84,8-86,6 (GPT-4.1-mini partout) | LoCoMo F 36,8 ; LongMemEval oracle F 34,2 (gpt-4o-mini) |
| Coût | construction ≈ 30 fois moins chère que Zep / Mem0g | recherche 4-23 ms, 60 Mo, sans modèle |

**Ce qu'on en retient** : (1) l'antériorité de l'idée « associative » existe — la nouveauté d'EXIA SEED tient dans la
propagation d'activation sans embeddings ni LLM à la recherche, sur un wiki lisible, avec citation contrôlée : à écrire
ainsi pour l'enveloppe Soleau et la publication ; (2) leur écriture ne filtre pas l'« utile plus tard » et leurs scores
sont deux fois les nôtres sous un lecteur comparable — cohérent avec notre diagnostic (§10, §12) : le gros de l'écart
est à l'écriture, d'où le test du §14.

### 14.1 Résultat sur les 200 questions de développement (27/10, 17 h 22 UTC) — 0,68 $
| 200 questions, échelle S | tout | utilisateur (24) | assistant (26) | préférence (12) | multi (41) | mises à jour (32) | temps (54) | abstention (11) |
|---|---|---|---|---|---|---|---|---|
| M — toute la mémoire, consigne actuelle → exhaustive | 42,0 → **57,5** | 66,7 → 91,7 | 23,1 → 15,4 | 25,0 → 58,3 | 29,3 → 65,9 | 50,0 → 75,0 | 40,7 → 42,6 | 81,8 → 72,7 |
| **A — EXIA SEED** | 40,0 → **54,5** | 62,5 → 91,7 | 23,1 → 19,2 | 8,3 → 50,0 | 22,0 → 41,5 | 56,2 → 81,2 | 40,7 → 42,6 | 81,8 → 90,9 |
| B — embeddings | 42,0 → 57,0 | 66,7 → 91,7 | 23,1 → 15,4 | 25,0 → 58,3 | 31,7 → 61,0 | 50,0 → 75,0 | 40,7 → 48,1 | 72,7 → 54,5 |
| C — plein texte | 40,0 → 50,5 | 62,5 → 87,5 | 23,1 → 23,1 | 16,7 → 33,3 | 24,4 → 39,0 | 56,2 → 75,0 | 37,0 → 37,0 | 81,8 → 90,9 |

- **E1 tient** : M gagne 15,5 points (+43 / −12, p < 0,0001). **E2 tient** : A gagne 14,5 points (+41 / −12,
  p = 0,0001). B et C gagnent autant : c'est la MÉMOIRE qui s'améliore, pour tous les moteurs.
- Faits : 928 → 1 330 (+43 %) ; mémoires vides 31 → 19 ; coût de consolidation identique (0,515 $ contre 0,508 $ pour
  les mêmes 200 questions) — c'est la lecture qui coûte, pas l'écriture. Une session sur ≈ 380 non consolidée (JSON
  mal formé par le modèle : sorties plus longues, à surveiller).
- Ce que dit l'utilisateur : 62-67 % → **92 %** (sessions entières : 95 %). Le détail perdu à l'écriture est revenu.
- Inchangé : le temps (≈ 42 %, autre cause) ; l'assistant baisse un peu (règle 4, voulu).
- **A contre B : 54,5 contre 57,0** (8 / 13, p = 0,38). L'écart restant est dans les questions multi-sessions (41,5
  contre 61,0) : en S, A rend 4,2 faits en moyenne quand la mémoire en a ≈ 6,7 ; B en rend jusqu'à 12, donc presque tout.
  Piste de recherche (pas de consolidation) : remplir le budget quand la mémoire est petite.
- **Réserve** : jeu de DÉVELOPPEMENT (regardé). La confirmation se fait sur les 300 autres questions, et à l'échelle
  fusionnée — non encore mesurée.

### 14.2 Deux améliorations suivantes, écrites avant leur mesure (27/10, Francis : « je te laisse faire ce qu'il faut pour améliorer EXIA SEED »)
Diagnostic sur le jeu de développement (gratuit) :
- **Questions multi-sessions perdues par A** (8 sur 13 des « B juste, A faux ») : les faits manquants ne portent pas
  les mots de la question — « luxury items » ↔ « User splurged on a Gucci handbag for $1,200 », « furniture » ↔
  « User got a new coffee table ». Le thésaurus contient des THÈMES abstraits (« organization », « boundaries »), pas
  les CATÉGORIES courantes. → variante **+categories** : la règle 12 demande aussi la catégorie de chaque chose, avec ses
  noms courants au singulier et au pluriel. Exemples de la consigne choisis HORS des 200 conversations (agrafeuse,
  tulipe, Toyota Corolla, violoncelle ; « drill » écarté : 7 conversations le contiennent).
- **Questions de temps perdues même avec toute la mémoire** (20 sur 54) : l'événement daté est dit EN PASSANT — « By
  the way, I started watering my herb garden every morning today » — et seule la demande est retenue. → variante
  **+passage** : « ce qui est dit en passant compte autant que la demande : ce que l'utilisateur a fait, commencé,
  fini, acheté, réparé, reçu — chacun en fragment, avec QUAND ».
- Chacune est mesurée SEULE contre « exhaustive » (runs `oracle-exh-cat`, `oracle-exh-pas`, 200 questions, plafond 2 $
  chacun) ; la combinaison ensuite si les deux gagnent. Une piste écartée : « remplir le budget » quand la mémoire est
  petite — gain propre à l'oracle S (mémoires de ≈ 7 faits, où B rend tout), sans valeur à l'échelle de Nexa.

### 14.3 Résultats des deux variantes (200 questions de développement) — 0,66 $ + 0,68 $
| 200 q., S | tout | utilis. | assist. | préf. | multi | MAJ | temps | abst. |
|---|---|---|---|---|---|---|---|---|
| M exhaustive / **+categories** / **+passage** | 57,5 / 56,0 / **61,5** | 91,7 / 91,7 / 91,7 | 15,4 / 19,2 / 11,5 | 58,3 / 58,3 / 83,3 | 65,9 / 58,5 / 61,0 | 75,0 / 68,8 / 75,0 | 42,6 / 46,3 / **55,6** | 72,7 / 63,6 / 81,8 |
| A exhaustive / +categories / +passage | 54,5 / 51,5 / **56,5** | 91,7 / 95,8 / 91,7 | 19,2 / 19,2 / 11,5 | 50,0 / 58,3 / 66,7 | 41,5 / 41,5 / 48,8 | 81,2 / 68,8 / 68,8 | 42,6 / 35,2 / **51,9** | 90,9 / 90,9 / 90,9 |
| B exhaustive / +categories / +passage | 57,0 / 54,5 / **63,0** | 91,7 / 95,8 / 95,8 | 15,4 / 19,2 / 11,5 | 58,3 / 50,0 / 83,3 | 61,0 / 58,5 / 63,4 | 75,0 / 65,6 / 75,0 | 48,1 / 42,6 / 57,4 | 54,5 / 63,6 / 81,8 |

- **+categories : écartée.** Aucun gain (A −3, n.s.) ; le modèle n'a pas suivi la consigne — pour le sac Gucci, pas de
  catégorie « luxury item », il réutilise « shopping » et « finances ».
- **+passage : retenue.** Temps +9 à +13 points pour M, A, B ; M +4 (17 / 9, p = 0,17), B +6 (23 / 11, p = 0,058), A +2
  (n.s.). Faits : 1 333 → 1 466. En S, A profite moins que B (B rend presque toute la mémoire, ≈ 7 faits) : l'échelle
  fusionnée tranchera.

### 14.4 Correction : le JSON illisible ne fait plus perdre la session (dépôt, `consolidation.py`)
Les échecs « JSON illisible » montent avec les consignes plus riches (2 → 3 → 6 réponses sur ≈ 720) : sorties coupées à
la limite de longueur (2 000 tokens au banc) ou virgule / guillemet de travers. EXIA SEED jetait toute la session.
`_sauver` garde les fragments COMPLETS écrits avant l'erreur (décodage élément par élément) ; ils passent le contrôle
de citation comme les autres. Sur les 5 sessions perdues de +passage : **41 fragments sauvés**. Test
`tests/test_json_sauve.py` (6 cas) ; **20 suites, toutes réussies.**

### 14.5 Confirmation (pré-enregistrée) : `exhaustive+passage` + sauvetage, sur les 300 questions intactes et en F
Run `confirm-lme` : les 500 questions consolidées avec la version retenue (les 200 de développement repris du cache de
`oracle-exh-pas` — mêmes réponses du modèle, sauvetage en plus — les 300 autres payées), fusion, A B C M en S et A B C
en F. **Référence** : run `oracle` (consigne actuelle). **Critères** : sur les 300 questions intactes, M_S et A_S gagnent
au moins 5 points ; en F (500), A_F gagne au moins 5 points et H1 tient toujours (A_F ≥ B_F − 2). Plafond 3,2 $ (cache
de 0,68 $ compris).

### 14.6 Confirmation — résultats (27/10, 18 h 12 → 19 h 06 UTC ; 1,98 $ cumulés dans le run, cache de 0,68 $ compris)
**Échelle S, les 300 questions INTACTES** (référence : run `oracle`, consigne actuelle) :

| 300 q. intactes | référence | version retenue | | McNemar |
|---|---|---|---|---|
| M — toute la mémoire | 42,7 | **61,0** | +18,3 | 93 / 38, p = 2·10⁻⁶ |
| **A — EXIA SEED** | 41,7 | **55,0** | **+13,3** | 74 / 34, p = 0,00015 |
| B — embeddings | 43,3 | 61,0 | +17,7 | 88 / 35, p = 2·10⁻⁶ |
| C — plein texte | 39,0 | 52,3 | +13,3 | 75 / 35, p = 0,00017 |
| E — sessions entières | 76,7 | — | | |

**Le critère tient** (M_S et A_S ≥ +5) : le gain de la consolidation n'était pas propre au jeu de développement. Par
type (A) : utilisateur 45 → 75, multi-sessions 36 → 50, temps 37 → 49, mises à jour 53 → 73, préférences 33 → 50,
assistant 30 → 30, abstention 79 → 63 (19 questions). En S, B dépasse A (61,0 contre 55,0 ; B seul 30, A seul 12,
p = 0,008) : sur une mémoire de ≈ 8 faits, B rend presque tout, A trie.

**Échelle F : le plafond du graphe est franchi.** Avec la consolidation exhaustive, la mémoire fusionnée compte 2 834
nœuds (3 901 faits) : au-delà de `PLAFOND_NOEUDS = 2000` (spec §5.2), le graphe n'est pas recalculé — A_F et C_F n'ont
rien rendu (7,8 % = les seules abstentions justes ; latence 0,05 ms). Ce n'est pas un résultat, c'est la limite
annoncée par la spec : « au-delà de 2 000 nœuds, passer en représentation creuse ». Mesure, plafond relevé à 3 000
POUR LE BANC SEULEMENT (matrice pleine) : calcul du graphe 1,4 s ; **mémoire vive 202 Mo** pendant la recherche (60 Mo à
726 nœuds) ; **recherche 21,5 ms** en médiane (4,2 ms à 726 nœuds). La matrice pleine croît au carré : la représentation
creuse (≈ 1 Mo à 5 000 nœuds selon la spec ; le graphe réel a 11 396 arêtes pour 2 834 nœuds, 0,14 % de remplissage)
devient le chantier suivant — et la condition de la vision embarquée (docs/09 §14.9).

**Échelle F, mesurée avec le plafond relevé à 3 000 (banc seulement)** — 19 h 08 → 19 h 18 UTC :

| F | référence | version retenue | | McNemar |
|---|---|---|---|---|
| **A_F, 500 q.** | 34,2 | **44,4** | **+10,2** | 100 / 49, p = 4·10⁻⁵ |
| A_F, 300 intactes | 33,7 | 43,3 | +9,6 | 62 / 33, p = 0,004 |
| B_F, 500 q. | 35,4 | 46,6 | +11,2 | 104 / 48, p = 7·10⁻⁶ |
| C_F, 500 q. | 31,6 | 40,2 | +8,6 | 90 / 47, p = 0,0003 |

- **Le critère tient** : A_F gagne 10 points (9,6 sur les seules questions intactes).
- **A_F contre B_F : 44,4 contre 46,6** (A seul 45, B seul 56, p = 0,32) — **H1 échoue de 0,2 point** (seuil −2),
  sans différence significative ; sur les 300 intactes : 43,3 contre 46,3 (p = 0,34). **H2 tient** (perte S → F :
  A −11,4, B −15,0). **H3 échoue** (mises à jour 63,9 contre 70,8). **H4 échoue** : 21 ms en médiane, 33 ms p95 avec
  la matrice pleine à 2 834 nœuds (B : 315 / 496 ms). A bat le plein texte (50 / 29, p = 0,024). Abstention : A 63,3,
  B 40,0.
- Dépense du run : 1,63 $ (2,31 $ moins le cache repris). **Journée LongMemEval : 6,31 $.**

**Bilan de la confirmation** : la consolidation exhaustive + « en passant » est un gain réel et reproductible pour
TOUS les moteurs (+10 à +18 points, à l'aveugle). EXIA SEED reste au contact des embeddings à l'échelle fusionnée
(−2,2 points, non significatif), perd moins qu'eux en grossissant, et invente moins ; il ne passe plus la barre de
H1 à 0,2 point près. La matrice pleine est la limite de taille et de vitesse : la représentation creuse est le
prochain chantier d'ingénierie. Rien n'est changé dans le dépôt pour la consolidation (variante du banc), rien chez
Nexa.

## 16 — Le moteur creux et la recherche rejouable (27/10 au soir ; Francis : « je te laisse tout faire »)
**Moteur creux** (`plugin/exia_seed/creux.py`, spec §5.2) : `charger_moteur` rend un `MoteurCreux` — les mêmes calculs
que `moteur/fcm.py` (sigmoïde λ = 5, seuil 0,5, entrées tenues, 3 itérations, arrêt sous 0,001) sur les seules arêtes
(`np.bincount`), sans matrice n × n. `moteur/fcm.py` reste identique au bit près à EXIA GHOST V2.7.2 et sert de
référence (`charger_moteur_plein`). `PLAFOND_NOEUDS` : 2 000 → 20 000 (le plafond devient le temps de calcul du graphe).
- `tests/test_creux.py` : 48 propagations sur 12 graphes aléatoires — écart maximal 4·10⁻¹⁶, même classement.
- Graphes réels, résultats de `memoire_chercher` comparés un par un : LongMemEval fusionné (2 834 nœuds) 497 / 500
  identiques, LoCoMo fusionné 599 / 600 ; les écarts sont des égalités de note rangées autrement (voir ci-dessous).
- Mesures (même conteneur, même mémoire) :

| | matrice pleine | **creux** |
|---|---|---|
| LongMemEval fusionné, 2 834 nœuds — recherche médiane / p95 | 18,1 / 27,5 ms | **10,4 / 17,8 ms** |
| — mémoire vive du processus | 196 Mo | **123 Mo** |
| LoCoMo fusionné, 726 nœuds — médiane / p95 | 3,6 / 8,6 ms | **2,8 / 4,1 ms** |
| 2 000 nœuds synthétiques — une propagation | — | **0,8 ms** |

Le reste de la mémoire vive (123 Mo) n'est plus la matrice : faits, index plein texte, cache du rappel — à mesurer
avant toute promesse pour l'embarqué.

**Recherche rejouable** : deux lancements du MÊME moteur donnaient 3 recherches sur 500 dans un ordre différent —
l'ensemble des sujets candidats (`requete.py`) était parcouru dans l'ordre de hachage de Python, qui change à chaque
lancement ; à note exactement égale, il décidait. Corrigé (`sorted(candidats)`) : **500 / 500 identiques** sur trois
lancements à graines de hachage différentes. Le rappel de la phase 2 : ce qui est MONTRÉ (bloc, faits, sujets) était
déjà identique 300 / 300 ; seul l'ordre de listes de la trace de diagnostic (`etages`) varie.

**21 suites, toutes réussies** (`test_etape_5_graphe.py` : l'alerte à 80 % éprouvée avec un plafond provisoire de 2 400 ;
inspection de la matrice via `get_weights`, reconstruite à la demande).

**Confirmation rejouée avec le moteur creux** (19 h 33 UTC, 0,001 $) : graphe fusionné recalculé sans dérogation
(2 834 nœuds, 11 396 arêtes, 1,1 s) ; **scores identiques** (A_F 44,4 ; A_S 55,8 ; aucune question ne change de
verdict) ; **H4 tient de nouveau : 11,2 ms en médiane, 18,1 ms p95** (33,4 ms avec la matrice pleine). Hypothèses de la
version retenue : H1 échoue de 0,2 point (n.s.), H2 tient, H3 échoue, H4 tient, P1 tient.

## 17 — Ce que les bancs mesurent, et ce qu'ils ne mesurent pas (Francis, 27/10/2026)
> *« Les résultats sont à relativiser et à pondérer : on est en train de créer un système de mémoire pour la vraie
> vie, où une véritable relation entre l'agent et son ou ses utilisateurs se crée au fil du temps. Les benchmarks ne
> sont qu'un test et non une expérience de véritable utilisation. C'est ce qu'on est en train de faire avec Nexa :
> avoir aussi un retour empirique. »*

**Ce que LoCoMo et LongMemEval mesurent** : retrouver un fait précis dans des conversations écrites pour le test, et
y répondre — une question, une réponse attendue, un juge. Utile et reproductible : c'est ainsi qu'on a trouvé la
saturation, le `speaker` non lu, la mémoire vide, la consolidation trop sélective, le plafond du graphe, la recherche
non rejouable. Aucun de ces défauts n'aurait été vu aussi vite chez Nexa.

**Ce qu'ils ne mesurent pas, et pourquoi c'est l'essentiel d'EXIA SEED** :
1. **Une seule vraie vie.** Les échelles « fusionnées » mêlent des centaines de vies écrites comme celle d'un seul
   utilisateur ; les liens d'association y relient des histoires étrangères (§16 : 16 % des faits rendus viennent de la
   bonne histoire, pour A comme pour B). Chez Nexa, un lien du graphe est une association réelle (« vécu ensemble »).
2. **Le temps long.** Une relation se construit sur des mois : préférences qui se précisent, règles de travail
   corrigées, projets qui avancent. Les bancs sont des instantanés.
3. **Le souvenir qui remonte seul** (phase 2) : aucun banc ne le mesure ; c'est pourtant ce qui a retrouvé la liste de
   courses du 15/10 sans qu'on le demande (docs/12, 24/10).
4. **Ce qui ne doit PAS être retenu** : la règle 4 (l'agent ne se croit pas lui-même) coûte 11 points sur
   LongMemEval et protège de l'auto-persuasion dans la vraie vie ; les bancs la sanctionnent, l'usage la justifie.
5. **L'auditabilité** : chaque fait cite sa ligne de conversation, chaque score se recalcule, chaque recherche se
   rejoue à l'identique (§16). Les bancs ne la notent pas ; une entreprise, un avionneur ou un utilisateur la demande.

**Donc** : les bancs sont des tests de non-régression et des loupes à défauts, pas la preuve de la valeur. La preuve
de la valeur est empirique, chez Nexa — et elle doit être mesurée elle aussi, pas racontée : les journaux du rappel
(`memoire/rappel/`), le banc des souvenirs sur sa vraie mémoire (docs/11-12, bancs 9-10), et les retours de Francis.
Toute publication présentera les deux, dans cet ordre de poids.

## 18 — L'effet du modèle qui répond (27/10, accord de Francis : « fais le test avec GPT 4.1 mini ») — 2,85 $
Run `lecteur-41mini` : mêmes mémoires et mêmes contextes que `confirm-lme` (copiés), même juge (gpt-4o-mini) ; seul le
modèle qui RÉPOND passe de gpt-4o-mini à **gpt-4.1-mini**. 500 questions.

| 500 q. | gpt-4o-mini | **gpt-4.1-mini** | | McNemar |
|---|---|---|---|---|
| E_S — sessions entières (le plafond) | 77,4 | **89,4** | +12,0 | 76 / 16, p = 2·10⁻¹⁰ |
| M_S — toute la mémoire | 61,4 | 67,4 | +6,0 | 40 / 10 |
| A_S — EXIA SEED | 55,8 | 62,2 | +6,4 | 41 / 9 |
| B_S — embeddings | 61,6 | 67,0 | +5,4 | 40 / 13 |
| **A_F — EXIA SEED, fusionnée** | 44,4 | **52,4** | **+8,0** | 57 / 17, p = 3·10⁻⁶ |
| **B_F — embeddings, fusionnée** | 46,6 | **51,6** | +5,0 | 50 / 25, p = 0,005 |

- **À l'échelle fusionnée, A dépasse B : 52,4 contre 51,6** (A seul 45, B seul 41, p = 0,75 — égalité statistique).
  **H1, H2, H3, H4 tiennent tous** (H2 : perte S → F de A 9,8 contre 15,4 ; H3 : mises à jour 73,6 contre 72,2 ; H4 :
  18 ms). P1 échoue (assistant : M_S 32,1 % > 30 %) — le lecteur plus fort tire davantage des rares faits confirmés.
- **A profite plus que B d'un meilleur lecteur** à l'échelle fusionnée (+8,0 contre +5,0) : ses 12 faits contiennent
  la réponse plus souvent qu'un lecteur faible ne savait l'en tirer.
- Abstention en F : A 83,3 %, B 66,7 %. Le plafond (E) monte à 89 % : l'écart E − M (22 points) est désormais
  l'essentiel du chemin restant, à l'écriture de la mémoire.
- En S, B reste devant (67,0 contre 62,2) : artefact connu des mémoires de ≈ 8 faits (§14.6).

**Journée LongMemEval : 9,16 $** (6,31 + 2,85).

## 19 — La consigne exhaustive dans EXIA SEED, et son test sur la mémoire de Nexa (27/10 ; Francis : « go pour la prochaine étape logique… tu peux faire un test sur la mémoire de Nexa sans l'affecter »)
**Portage (dépôt, `langues/fr.py` et `langues/en.py`)** : la règle 3 devient « garde TOUT fait que l'utilisateur dit de
lui et de son monde — personnes, entreprises, lieux, biens, achats, tarifs, règles de travail, préférences, décisions et
leur raison, événements, échéances, intentions, activités, projets, expériences, santé — AVEC ses détails concrets […].
Ce qui est dit EN PASSANT compte autant que la demande […], avec QUAND c'est arrivé. » Elle garde **toutes les
catégories métier de l'ancienne règle** (entreprises, tarifs, règles de travail, décisions, échéances, intentions) —
écart déclaré avec la variante mesurée sur LongMemEval, qui ne les nommait pas. L'ancienne règle reste dans chaque masque
(`REGLE3_SELECTIVE`) ; au banc, `LOCOMO_CONSOLIDATION=selective` la rejoue. 21 suites réussies. **Rien chez Nexa.**

**Test sur la mémoire de Nexa, pré-enregistré** (`banc/nexa/`, données dans `$HOME/banc-nexa-exh`) :
- **Copie** de ses 126 lots FERMÉS (23/09 → 27/10), de la chaîne d'intégrité et du registre ; sa mémoire vivante est
  seulement lue. Reconsolidée deux fois depuis zéro, conteneurs jetables, réglages de production (francis / nexa, fr,
  Europe/Paris, 40 000 tokens, fiches), **même modèle pour les deux** : gpt-4o-mini par l'API (son modèle de production,
  GPT-6 Astra, n'est pas utilisé : ce banc mesure l'effet de la CONSIGNE).
- **Mesures** : (1) taille — faits, nœuds, arêtes, coût de consolidation ; (2) **couverture** — part des messages de
  Francis (hors avis système, ≥ 6 mots) cités par au moins un fait, et part de ceux qui portent un détail concret
  (nombre, nom propre) ; (3) **questions** — 80 messages de Francis à détail concret, tirés au sort (graine 2710) ; pour
  chacun, gpt-4o-mini écrit UNE question qu'il pourrait poser plus tard et sa réponse, à partir du seul message ; on
  répond avec toute la mémoire (M) et avec `memoire_chercher` (A) de chaque variante ; juge de LongMemEval.
- **Critère** : la nouvelle consigne couvre davantage (2) et répond mieux (3) sans dégrader ce que l'ancienne retenait ;
  son coût et sa taille sont relevés pour la consolidation de nuit. Plafond : 1,5 $ par variante.

### 19.1 Premier essai : invalide — le petit modèle ne sait pas consolider la vraie vie de Nexa (0,25 $ + 0,14 $)
- Faux départ (0,14 $) : tout l'historique en quelques appels de 40 000 tokens, réponse plafonnée à 2 000 → 14 pages
  pour un mois. Corrigé : rejeu jour par jour, comme ses nuits, réponse jusqu'à 8 000 tokens.
- Rejeu jour par jour avec **gpt-4o-mini** : **51 faits** (ancienne consigne) et **68** (nouvelle) pour 126 lots — sa
  vraie mémoire en compte 552 ; 99 et 105 fragments rejetés ; couverture des messages de Francis 7,7 % et 10,3 % ;
  **5 / 80 questions** justes dans les deux cas. Motifs de rejet : **72 « repose seulement sur des paroles de
  l'agent »** (chez Nexa, c'est souvent elle qui énonce — « facture 41 préparée », « rappel programmé » — et Francis
  confirme d'un mot : le petit modèle ne cite pas la confirmation), **22 « nombre absent des sources »** (il ajoute
  l'année « 2026 » aux dates ; le contrôle de citation le bloque, à raison).
- **Enseignement** : sur des conversations RÉELLES (agent qui agit, confirmations brèves, outils), la consolidation
  d'EXIA SEED exige un modèle capable ; les conversations propres de LongMemEval ne le montraient pas. Le contrôle de
  citation a fait son travail : rien d'inventé n'est entré.
- **§19.2** : le même rejeu, dans le conteneur de Nexa, par SON modèle de production (GPT-6 Astra, effort « low »,
  abonnement Codex de Francis — décision de Francis : « on devrait être tranquille sur le coût »), sans copier ses
  identifiants ; écriture dans `workspace/banc-exh/` seulement ; sa mémoire vivante non ouverte.

### 19.2 Le test avec SON modèle (GPT-6 Astra, effort « low », abonnement Codex) — nuit du 27/10, 20 h 51 → 21 h 39 UTC
Rejeu jour par jour des 126 lots (23/09 → 27/10) dans le conteneur de Nexa, sur les copies `workspace/banc-exh/` ;
sa mémoire vivante non ouverte (dernière consolidation réelle inchangée). Aucune exception, aucun lot bloqué. Mesure
(questions, réponses, juge : gpt-4o-mini par l'API, 0,06 $), identique pour les deux mémoires.

| Mémoire de Nexa reconsolidée | ancienne règle 3 | **nouvelle règle 3** |
|---|---|---|
| Faits | 422 | **732** (+73 %) |
| Nœuds / arêtes du graphe | 91 / 212 | 129 / 435 |
| Messages de Francis cités par au moins un fait (633) | 54,0 % | **71,4 %** |
| — ceux qui portent un détail concret (435) | 54,9 % | **71,0 %** |
| **Questions sur ses vrais messages (80)** | 22 (27,5 %) | **36 (45,0 %)** |
| Durée du rejeu (34 jours d'historique) | 21 min | 33 min |

- **Questions : 16 gagnées, 2 perdues, p = 0,0013.** Le gain mesuré sur LongMemEval se reproduit sur la vraie vie de
  Nexa, en français, avec son modèle de production.
- Coût de la consolidation : 0 $ (abonnement) ; ≈ 1 minute de plus par nuit à son rythme actuel.
- Limites : questions écrites par gpt-4o-mini à partir d'un seul message (des détails, pas des associations) ; lecteur
  gpt-4o-mini sur 12 faits de `memoire_chercher` ; un seul tirage de 80. La mémoire de production (552 faits) a été
  construite par plusieurs versions successives : elle n'est comparable à aucune des deux.
- **Rien n'est déployé chez Nexa** : la décision revient à Francis.

### 19.3 Déploiement chez Nexa (28/10/2026, accord de Francis : « déploie chez Nexa »)
- **Un seul changement** (O3) : la règle 3 de `consolidation.py` (0.8.1, consigne écrite dans le code) remplacée par
  celle du dépôt, au caractère près — vérifié par programme (l'ancienne règle de la 0.8.1 = `REGLE3_SELECTIVE`). Le
  reste de la 0.8.1 est intact : ni moteur creux, ni sauvetage du JSON, ni masques (à proposer séparément).
- 17 suites applicables à la 0.8.1, toutes réussies sur le candidat (`staging/exia_seed.exhaustive-candidat-20261028`).
- **Sans redémarrage** : la consolidation (cron de 23 h 55 et fermeture de lot par la passerelle) tourne dans un
  processus neuf qui relit `consolidation.py`. Vérifié dans son conteneur : la nouvelle règle est chargée, l'ancienne
  absente, la règle 4 intacte. Première nuit concernée : 28/10.
- Les 552 faits déjà écrits restent ceux de l'ancienne règle ; la copie reconsolidée (732 faits, §19.2) n'a PAS
  remplacé sa mémoire — ce serait une décision à part.
- Sauvegarde : `staging/exia_seed.avant-exhaustive-20261028`.
