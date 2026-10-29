# Journal des versions d'EXIA SEED

Chaque version renvoie au document qui la raconte (`docs/`) : la décision, la mesure, les défauts trouvés.
Reconstitué le 16/10/2026 depuis les sauvegardes de chaque version déployée (`staging/exia_seed.v*`) et les documents.

| Version | Date | Où | Ce qu'elle apporte | Documents |
|---|---|---|---|---|
| 0.1.0 | 22/09/2026 | Nexa | Greffe sur Hermès (fournisseur de mémoire), écoute du brut, registre « note ça », consolidation brut → pages, garde-fou anti-secret, consignes de mémoire | 01, 02, 03, 04, A1, A2 |
| 0.2.0 | 26/09/2026 | Nexa | Corrections de la revue du 23/09 | R1, R2 |
| 0.3.0 | 26/09/2026 | Nexa | Le temps des faits : dates vérifiées, « lundi » → date en clair (`temps.py`) | R2 |
| 0.4.0 | 26/09/2026 | Nexa | Le graphe : des pages aux nœuds reliés, moteur FCM (`graphe.py`, `moteur/`) | 05 |
| 0.5.0 | 27/09/2026 | Nexa | Le rappel à blanc : calculé, journalisé, jamais montré (`rappel.py`) | 06 |
| 0.6.0 | 27/09/2026 | Nexa | La requête : `memoire_chercher`, `memoire_lire` — Nexa lit son wiki, le graphe l'y aide (`requete.py`) | 07 |
| 0.7.0 | 29/09/2026 | Nexa | Concepts et champ lexical (thésaurus) ; revue des faux rejets du contrôle de citation | 08 §8-9, R3 |
| 0.8.0 | 29/09/2026 | Nexa | Optimisations mesurées (apostrophe typographique, spécificité des concepts, pistes) | 08 §11-12 |
| 0.9.0 | 01/10/2026 | dépôt seul | Masques de langue fr/en : aucune donnée linguistique dans le code central | 10 |
| 0.8.1 | 16/10/2026 | Nexa | Phase 2 codée (souvenirs qui remontent, activée par `phase: 2`) ; fiche d'identité de chaque sujet ; mots distinctifs ; avis système d'Hermès écrits au nom de « systeme » ; rappel sur le contenu, pas l'enveloppe ; règles de conduite rappelées par la situation ; amorçage par le tour précédent | 11, 12 |
| **0.9.1** | **16/10/2026** | **dépôt** | La 0.8.1 portée dans les masques de langue (consigne des fiches fr/en, en-tête des souvenirs, colonne de l'index, règle « systeme ») ; français identique au caractère près à la 0.8.1 (dépôt de travail ; dans la version publique, les noms d'exemple des consignes sont fictifs) | 10 §7 |
| 0.8.1 + règle 3 | 28/10/2026 | Nexa | Consolidation exhaustive + « en passant » (seul changement) ; mesurée sur une copie de sa mémoire avec son modèle : 22 → 36 questions sur 80 | 13 §19 |
| 0.8.1 + noms composés | 29/10/2026 | Nexa + dépôt | Contrôle de citation : « Météo-France » se retrouve dans « météo france » (trait d'union et apostrophe = espace) ; faux rejet du 28/10 | R3 §7 |
| 0.9.2 (en cours) | 18/10/2026 | dépôt | `memoire_chercher` : la note des faits ne sature plus quand un sujet est nommé (`cab_pull(couverture, 1, 0,25 × activation)`) ; le moteur lit le `speaker` (classement : les faits d'une autre personne que celle nommée sont atténués ; affichage `dit_par`). LoCoMo, 8 conversations fusionnées : 33,2 % → 36,8 % (embeddings 38,3 %) ; réponses vocales écrites en clair dans le brut (`enveloppes.reponse_vocale`) ; mémoire vide : le rappel ne propage plus sur un graphe sans nœud (plantait, trouvé par LongMemEval) ; JSON illisible : les fragments complets sont sauvés ; moteur CREUX (`creux.py`, plafond 2 000 → 20 000 nœuds, mêmes calculs) ; recherche rejouable (ordre fixe des candidats) | 09 §14.5-14.10, 12 §15, 13 §11, §14.4, §16 |

**Ce que publie le dépôt** : la 0.9.1. Nexa tourne en 0.8.1, dont le français est identique (voir `docs/10` §7) — sauf, dans cette version publique, les noms d'exemple des consignes (clients, contacts, lieux), remplacés par des noms fictifs : le texte envoyé au modèle diffère donc de quelques mots de celui de Nexa.
