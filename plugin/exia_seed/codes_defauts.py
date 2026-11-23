"""Codes défauts d'EXIA SEED — à la manière d'un OBD-II (décision A2, 15/11/2026).

Chaque panne a un CODE STABLE, une gravité et l'action prise. Le code est inscrit dans la télémétrie de la
mémoire (`telemetrie/defauts.jsonl`, ajout seul) et dans le journal du processus. C'est l'outil de
l'administrateur pour diagnostiquer et corriger ; il n'est jamais montré tel quel à l'utilisateur.

Règle de vie privée : une ligne de défaut porte le NOM d'un réglage, jamais sa VALEUR (un réglage peut contenir
un nom de personne).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# code → (gravité, sens). Gravités : « mineur » (rien n'est perdu, rien ne s'arrête), « majeur » (une partie du
# service est dégradée ou en pause, rien n'est perdu), « critique » (une mémoire ne fonctionne pas).
CATALOGUE: Dict[str, Tuple[str, str]] = {
    "ES-CFG-01": ("majeur", "réglages illisibles : valeurs par défaut, puis dernières valeurs valides de la mémoire"),
    "ES-CFG-02": ("majeur", "réglage d'écriture invalide : dernière valeur valide (sinon défaut) ; le brut continue"),
    "ES-CFG-03": ("majeur", "langue demandée différente de celle de la mémoire : la langue de la mémoire est gardée"),
    "ES-CFG-04": ("mineur", "réglage inconnu : ignoré"),
    "ES-CFG-05": ("majeur", "réglage de consolidation invalide : consolidation en pause ; le brut continue"),
    "ES-CFG-06": ("mineur", "réglage de lecture invalide : dernière valeur valide (sinon défaut)"),
    "ES-CFG-07": ("critique", "réglages d'écriture invalides sur une mémoire neuve : mémoire non créée"),
}

FICHIER = Path("telemetrie") / "defauts.jsonl"


def gravite(code: str) -> str:
    return CATALOGUE.get(code, ("majeur", ""))[0]


def inscrire(racine: Optional[Path], code: str, cle: str = "", action: str = "") -> Dict[str, str]:
    """Inscrit un code défaut dans la télémétrie de la mémoire et dans le journal. Ne lève jamais.

    `cle` : le nom de ce qui est en cause (un nom de réglage), jamais une valeur. Sans `racine` (mémoire
    introuvable ou non créée), le code ne va qu'au journal du processus."""
    ligne = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "code": code,
             "gravite": gravite(code), "cle": str(cle)[:60], "action": action}
    niveau = logging.ERROR if ligne["gravite"] == "critique" else logging.WARNING
    logger.log(niveau, "EXIA SEED %s (%s) %s — %s", code, ligne["gravite"], ligne["cle"], action or CATALOGUE.get(code, ("", ""))[1])
    if racine is not None:
        try:
            f = Path(racine) / FICHIER
            if Path(racine).exists():
                f.parent.mkdir(parents=True, exist_ok=True)
                with open(f, "a", encoding="utf-8") as sortie:
                    sortie.write(json.dumps(ligne, ensure_ascii=False) + "\n")
        except Exception:
            logger.exception("EXIA SEED : code défaut %s non inscrit dans la télémétrie", code)
    return ligne


__all__ = ["CATALOGUE", "FICHIER", "gravite", "inscrire"]
