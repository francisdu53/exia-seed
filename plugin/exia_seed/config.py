"""Réglages d'EXIA SEED — bloc `memory.exia_seed` de config.yaml, sur des défauts sûrs.

Spec : SPEC-EXIA-SEED.md (spécification interne, non publiée).
"""
from __future__ import annotations

from typing import Any, Dict

DEFAUTS: Dict[str, Any] = {
    "dossier": "memoire",          # relatif à HERMES_HOME
    "seuil_lot_tokens": 25000,     # §3.1 : un lot se ferme à ce volume, ou au changement de jour
    "fuseau": "",                  # vide = `timezone` de config.yaml, sinon UTC
    "nom_utilisateur": "",         # vide = nom fourni par la plateforme (Telegram…)
    "nom_agent": "assistant",
    "langue": "fr",               # langue de la mémoire : son masque (docs/10) ; inscrite à la création, puis fixe
    "interlocuteurs": [],          # conversation entre personnes, sans agent (banc LoCoMo) : leurs noms
    "phase": 1,                    # 1 = écriture seule ; 2 = rappel injecté
    "consolidation_auto": True,    # consolider dès qu'un lot se ferme (fil d'arrière-plan)
    "consolidation_effort": "low", # tâche mécanique : effort au plancher
    "consolidation_max_tokens_entree": 40000,
    "rappel_a_blanc": True,
    "fiches": True,                # docs/12 : fiche d'identité des pages touchées, à chaque consolidation        # étape 6a : calculer et journaliser le rappel, sans l'injecter
    # Phase 2 (docs/11) : les souvenirs REMONTENT avec le message — le sujet d'abord, puis un ou deux faits.
    "souvenirs_seuil": 0.5,        # score minimal d'un fait pour remonter — PROVISOIRE, fixé par le banc « souvenirs » (docs/11)
    "souvenirs_max_sujets": 3,     # sujets au plus par message
    "souvenirs_faits_par_sujet": 2,  # faits au plus par sujet ; les règles de conduite d'abord
    "amorce_minutes": 30,          # docs/12 §10 : les sujets du message précédent restent un peu actifs (0 = coupé)
}


def charger() -> Dict[str, Any]:
    """Défauts + bloc `memory.exia_seed` ; ne lève jamais (config illisible = défauts)."""
    reglages = dict(DEFAUTS)
    try:
        from hermes_cli.config import load_config
        cfg = load_config() or {}
        bloc = (cfg.get("memory") or {}).get("exia_seed") or {}
        if isinstance(bloc, dict):
            reglages.update({k: v for k, v in bloc.items() if k in DEFAUTS})
        if not reglages["fuseau"]:
            reglages["fuseau"] = cfg.get("timezone") or "UTC"
    except Exception:
        reglages["fuseau"] = reglages["fuseau"] or "UTC"
    return reglages
