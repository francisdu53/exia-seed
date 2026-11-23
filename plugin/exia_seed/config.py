"""Réglages d'EXIA SEED — bloc `memory.exia_seed` de config.yaml, sur des défauts sûrs.

Spec : SPEC-EXIA-SEED.md (spécification interne, non publiée).
"""
from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

DEFAUTS: Dict[str, Any] = {
    "dossier": "memoire",          # relatif à HERMES_HOME
    "seuil_lot_tokens": 25000,     # §3.1 : un lot se ferme à ce volume, ou au changement de jour
    "fermer_lot_fin_de_session": True,   # docs/18 §11 : False = le lot continue d'une session à l'autre ; il se ferme à seuil_lot_tokens ou chaque nuit (cron)
    "fuseau": "",                  # vide = `timezone` de config.yaml, sinon UTC
    "nom_utilisateur": "",         # vide = nom fourni par la plateforme (Telegram…)
    "nom_agent": "assistant",
    "langue": "fr",               # langue de la mémoire : son masque (docs/10) ; inscrite à la création, puis fixe
    "interlocuteurs": [],          # conversation entre personnes, sans agent (banc LoCoMo) : leurs noms
    "phase": 1,                    # 1 = écriture seule ; 2 = rappel injecté
    "consolidation_auto": True,    # consolider dès qu'un lot se ferme (fil d'arrière-plan)
    "consolidation_effort": "low", # tâche mécanique : effort au plancher
    "consolidation_modele": "",    # docs/17 §11 : vide = le modèle principal de l'agent ; ex. « gpt-6.1-terra »
    "consolidation_consigne": "production",  # « production », « adaptee » (Terra, docs/17 §11) ou « petit_modele » (Luna, Haiku 5.5, docs/20)
    "catalogue_observateur_k": 0,   # docs/17 §18 : > 0 = observer la liste ciblée (k pages par message) ; 0 = éteint
    "consolidation_max_tokens_entree": 40000,
    # docs/17 §28-§33 (décision de Francis, 14/11/2026) : un appel au modèle par échange (un message de l'utilisateur et
    # les réponses de l'agent qui suivent) ; panel 3 : couverture 72 → 95 %, bonnes réponses 61,7 → 72,5 %. False = par lots.
    "consolidation_par_echange": False,
    "rappel_a_blanc": True,
    "fiches": True,                # docs/12 : fiche d'identité des pages touchées, à chaque consolidation        # étape 6a : calculer et journaliser le rappel, sans l'injecter
    # Phase 2 (docs/11) : les souvenirs REMONTENT avec le message — le sujet d'abord, puis un ou deux faits.
    "souvenirs_seuil": 0.5,        # score minimal d'un fait pour remonter — PROVISOIRE, fixé par le banc « souvenirs » (docs/11)
    "souvenirs_max_sujets": 3,     # sujets au plus par message
    "souvenirs_faits_par_sujet": 2,  # faits au plus par sujet ; les règles de conduite d'abord
    "amorce_minutes": 30,
    # 14/11/2026 : la note des faits d'un sujet nommé (docs/09 §14.5-14.8). 0,25 : +3,6 points sur LoCoMo ; sur la mémoire
    # de Nexa du 13/11, neutre (+1 question sur 109). None ou « ancienne » = l'ancienne note (« ancienne » : Hermès retire
    # les null de config.yaml quand il le réenregistre) ; « eventail » = le compromis.
    "recherche_poids_sujet": 0.25,
    "rappel_moteur": "ancien",       # 0.9.16 : « montre » = le rappel par convergence (docs/21) ; « ancien » = jusqu'à 0.9.15 ;
    # 0.10.0 : « deux_memoires » = souvenirs + brut, sans modèle (docs/22). Revenir en arrière = remettre « ancien ».
    "deux_memoires_seuil": 0.05,       # chance minimale d'aider pour remonter (choisi sur les messages de réglage de Nexa)
    "deux_memoires_max": 10,           # éléments au plus par message (garde-fou : 1 200 tokens)
    "deux_memoires_regle": True,       # la règle d'abstention en tête du bloc (docs/22 : pièges 4 → 59 / 71 sur le réglage)
    "deux_memoires_correcteur": True,  # le correcteur tiré de la mémoire (fautes de frappe)
    # 14/11/2026 : « oublie ce que je viens de dire » retire aussi les faits DÉJÀ consolidés de ces lignes (registre oublis/,
    # restaurables). Éteint par défaut (15/11) : Francis tranche d'abord la définition de l'oubli (fiches, journaux, git).
    "retrait_retroactif": False,
    # 15/11/2026 : un canal d'échange par fichiers avec un autre interlocuteur (outils/canal.py) ; {} = éteint. Clés :
    # dossier (relatif à HERMES_HOME), correspondant (son nom dans le brut), description (pour la consolidation),
    # uid_correspondant (propriétaire de SES fichiers, 0 par défaut), echanges_max (échanges gardés, 14 par défaut).
    "canal": {},
    "bulletin_seuils": {},         # outils/bulletin.py : seuils de l'utilisateur ({} = ceux proposés dans le script)          # docs/12 §10 : les sujets du message précédent restent un peu actifs (0 = coupé)
}


def charger() -> Dict[str, Any]:
    """Défauts + bloc `memory.exia_seed`, VÉRIFIÉS (A1) ; ne lève jamais. Une valeur fausse est remplacée par
    le défaut : pour les codes défauts et les dernières valeurs valides d'une mémoire, voir `charger_avec_codes`."""
    return charger_avec_codes()[0]


def charger_avec_codes() -> Tuple[Dict[str, Any], List[Tuple[str, str]], Set[str]]:
    """Comme `charger`, et rend aussi les codes défauts [(code, clé)] et les clés invalides (A1, 15/11/2026).

    Avant le 15/11, les valeurs étaient prises telles quelles : une seule valeur fausse pouvait mettre la mémoire
    en retrait (le brut ne s'écrivait plus) sans le moindre signal. Les codes sont INSCRITS par l'appelant, une
    fois la mémoire trouvée (`reglages.appliquer`)."""
    from . import reglages as _reglages
    fournis: Dict[str, Any] = {}
    codes: List[Tuple[str, str]] = []
    plateforme = ""
    try:
        from hermes_cli.config import load_config
        cfg = load_config() or {}
        bloc = (cfg.get("memory") or {}).get("exia_seed") or {}
        if isinstance(bloc, dict):
            fournis = bloc
        else:
            codes.append(("ES-CFG-01", "memory.exia_seed"))
        plateforme = cfg.get("timezone") or ""
    except Exception:
        codes.append(("ES-CFG-01", "config"))
    reglages, codes_verif, invalides = _reglages.verifier(fournis)
    codes += codes_verif
    if not reglages["fuseau"]:                       # vide = le fuseau de la plateforme, vérifié lui aussi
        if not plateforme or _reglages.fuseau_valide(plateforme):
            reglages["fuseau"] = plateforme or "UTC"
        else:
            reglages["fuseau"] = "UTC"
            codes.append(("ES-CFG-02", "fuseau"))
            invalides.add("fuseau")
    return reglages, codes, invalides
