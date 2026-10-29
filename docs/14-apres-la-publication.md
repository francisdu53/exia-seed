# 14 — Après la publication : le journal continue

> *Version publique : les noms de personnes, d'entreprises et de lieux, et les informations privées, sont fictifs pour les besoins de la démonstration, mais fondés sur des cas réels ; certaines informations ont été retirées par respect de la vie privée — voir `00-AVERTISSEMENT.md`.*

**Version :** 0.1 — 29 octobre 2026. **Pourquoi ce document :** les pages 01 à 13 racontent la construction jusqu'à la
publication du 28/10. Le travail continue chez Nexa, chaque jour ; ce journal en garde la trace, en public, avec la même
règle : la décision, la mesure, l'erreur — dans cet ordre.
**Référence :** `README.md`, `11` §8 (phase 2 en usage réel), `12` §15 (vocal), `R3` §7 (noms composés).

## 1 — La publication (28/10/2026)

**Décision de Francis** : tout publier, journal compris — *« le build in public est très important »* — sous licence
Apache 2.0, dans un dépôt séparé d'EXIA GHOST (*« deux mémoires réellement différentes »*), sans brevet.

**Ce qu'on a appris en préparant la copie publique : anonymiser ne suffit pas.** Remplacer les noms ne retire pas
l'intimité : une dette, un rendez-vous médical ou une confidence restent intimes sous un nom inventé, et l'avertissement
annonce des *cas réels* — le lecteur les lira comme la vie de l'auteur. D'où deux passes, dans cet ordre :

| Passe | Ce qu'elle fait | Outil |
|---|---|---|
| Anonymisation | personnes, entreprises, lieux, identifiants → noms fictifs cohérents d'un document à l'autre | `publier/anonymiser.py` |
| Vie privée | relecture complète par deux relecteurs (61 éléments relevés) ; gravité haute **supprimée**, moyenne **généralisée** ; tarifs décalés ; chaque test qui vérifiait un texte changé avec lui | `publier/vie_privee.py` |
| Vérification | refus de publier si un terme réel, une adresse, un chemin, un jeton reste ; les 21 suites doivent passer **sur la copie** | `publier/verifier.py`, `tests/banc.sh` |

La chaîne est **rejouable** : chaque version du dépôt de travail repasse par elle, et une règle qui ne trouve plus son
texte arrête la publication. L'historique public est **neuf** (un premier commit) : l'historique de travail, qui contient
les vrais noms, ne part jamais.

Le même jour : la note de correction du score LoCoMo d'EXIA GHOST est publiée dans son propre dépôt (`09` §12.2), et un
commentaire présente EXIA SEED sous le *LLM Wiki* de Karpathy.

## 2 — La boucle vocale, prouvée (28/10, 21 h 46)

Le correctif du 26/10 (`12` §15) n'avait encore jamais servi : aucun échange vocal depuis. Le soir de la publication,
Francis envoie un vocal — un remerciement pour un rappel, et un document à faire suivre à l'assurance. Nexa répond en
vocal. Dans le brut :

```
[21:46 francis] "Merci Nexa pour le rappel de tout à l'heure. Cela m'a permis de penser à …"
[21:46 nexa] (vocal) Avec plaisir, Francis. Je suis contente que le rappel t'ait été utile ! …
```

Consolidation de 22 h 03 : **2 faits** (ce qui s'est passé ; ce qui reste à faire), source = la ligne du vocal ;
compteur `reponses_vocales` : 2. **Ce qu'on croyait et qui était faux** : que le compteur du jour se met à jour en direct
— il s'écrit à la consolidation (0 à 21 h 46, 2 le lendemain matin).

## 3 — La nouvelle consolidation, premier jour réel

La règle 3 exhaustive (`13` §19) est en production depuis le matin du 28/10. Les lots du soir sont les premiers à passer
par elle.

| Jours | Messages de Francis | Faits retenus | Faits par message |
|---|---|---|---|
| 23 → 27/10 (ancienne règle) | 79 | 61 | 0,5 à 0,9 selon le jour |
| **28/10 (nouvelle règle)** | **14** | **23** | **1,6** |

C'est le même ordre que l'essai sur copie (422 → 732 faits, `13` §19). **Mais c'est un seul jour**, et le nombre de faits
dépend d'abord de ce dont on parle : à confirmer sur une semaine avant d'en tirer quoi que ce soit.

Parmi les faits du 28/10 : un bulletin météo du matin que Nexa a construit pour Francis. Il demande la météo du Grand
Est (Alsace, Lorraine, Champagne) dans son récapitulatif d'agenda ; Nexa propose les modèles de Météo-France
(AROME, ARPEGE, via Open-Meteo) plutôt que le service d'Apple, pour Strasbourg, Metz, Nancy, Reims, Mulhouse, Colmar et Épinal :
températures, conditions, pluie et rafales, à 6 h en semaine et 9 h le week-end. Les vigilances officielles ne sont pas
automatisées (l'accès à l'API officielle reste à configurer) : le bulletin le dit et donne le lien de la carte. La page
`bulletin_meteo_matinal` est née ce soir-là, dans un lot de 10 faits — et **un fait rejeté à tort** (§4).

## 4 — Un faux rejet : « Météo-France »

*« Francis a choisi Météo-France… »* → rejeté : « nom propre absent des sources ». Francis avait écrit *« météo
france »*, sans majuscules ni trait d'union ; le contrôle cherchait « météo-france ». Correction le 29/10 : trait d'union
et apostrophe valent une espace, des deux côtés ; un nom vraiment absent reste rejeté. Test qui échoue sur l'ancien code ;
21/21 ; déployé chez Nexa sans redémarrage. Détail : `R3` §7.

## 5 — Ce que disent les relecteurs extérieurs

Francis a soumis le dépôt à d'autres IA. Une première analyse, juste sur le fond technique, appelait aussi la
consolidation un *Mixture of Experts* — et approuvait. **C'est inexact** : un MoE aiguille chaque entrée vers quelques
experts spécialisés parmi plusieurs ; EXIA SEED n'a ni experts ni aiguilleur. Le bon nom est **consolidation
incrémentale** : seuls les lots bruts non encore consolidés partent au modèle (`raw/.consolide.jsonl`), un fait nouveau
complète la page existante de son sujet, un fait déjà présent n'est pas réécrit, et seules les pages touchées voient leur
fiche réécrite. C'est le principe de `make` — et celui du cerveau : la consolidation de la nuit, et la reconsolidation
quand on revient sur un souvenir.

Sur l'échelle, la même analyse notait que le moteur creux n'est pas mesuré au-delà de quelques milliers de nœuds. Chez
Nexa, après cinq semaines : **113 nœuds, 375 liens** ; le plafond est à 20 000 et LongMemEval a été traité à 2 834. La
limite réelle n'est pas la taille du graphe mais la qualité de la consolidation — ce que dit déjà le README. Le cas à
mesurer le jour venu : **plusieurs personnes dans une même mémoire**, où le nombre de sujets suit la variété des gens.

**Leçon de méthode** : un relecteur qui acquiesce n'est pas une preuve. On garde ses remarques vérifiables, on vérifie
chacune dans le code.

## 6 — Prochain chantier : la télémétrie (état au 29/10)

| Ce qui existe | État |
|---|---|
| Télémétrie d'EXIA SEED : un fichier par jour depuis le 23/09 (`memoire/telemetrie/`) | écrite, **lue par personne** — 14 compteurs (tours écrits, lots, erreurs, secrets masqués, retraits, réponses vocales, latences d'écriture, requêtes) |
| Lecteur de capteurs écrit par Nexa, bandes nominales fixées par Francis (août 2026) | présents, **branchés sur aucune tâche planifiée** |
| Audit hebdomadaire des systèmes (compétence d'août) | **introuvable** dans ses compétences et ses tâches planifiées au 29/10 |

Rien ne montre aujourd'hui à Francis l'état de santé de Nexa et de sa mémoire. Le chantier : inventaire, puis un
tableau de bord quotidien et des alertes sur bandes — les bandes restent fixées par Francis, Nexa peut en proposer.
