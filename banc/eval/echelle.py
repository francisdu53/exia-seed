"""Test 1 (23/11) — quelle mémoire interroger pour une question : EVAL_MEMOIRE (vide = comportement d'origine).

  (vide)     échelle S : la mémoire de la conversation ; échelle F : `_fusion` (toutes réunies)
  _seule     la mémoire de la conversation SEULE, mais interrogée comme à l'échelle F (sans filtre de date) : le point
             « 1 conversation » de la courbe d'interférence
  _g<N>      la fusion de N conversations qui contient celle de la question (`_g<N>_<groupe>`, groupes dans
             `interference/groupes.json`, mémoires construites par fusion_eval.py)
  <nom>      une mémoire fusionnée donnée (`_fusion`, `_mixte`, `_controle`…)
Le brut d'une mémoire fusionnée est préfixé par la conversation (`raw/<conv>_<fichier>`), celui d'une mémoire seule non.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ICI = Path(__file__).resolve().parent
MEM = os.environ.get("EVAL_MEMOIRE", "")
_G = {}


def dossier(racine: Path, conv: str, echelle: str) -> Path:
    if not MEM:
        return racine / ("_fusion" if echelle == "F" else conv)
    if MEM == "_seule":
        return racine / conv
    if MEM.startswith("_g"):
        if not _G:
            _G.update(json.loads((ICI / "interference" / "groupes.json").read_text(encoding="utf-8")))
        return racine / f"{MEM}_{_G[racine.name][conv]}"
    return racine / MEM


def prefixe(conv: str, echelle: str) -> str:
    if not MEM:
        return f"{conv}_" if echelle == "F" else ""
    return "" if MEM == "_seule" else f"{conv}_"
