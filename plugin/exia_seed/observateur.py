"""Mode observateur de la liste ciblée (docs/17 §17-18) — ne change RIEN à la consolidation.

À chaque passage, la consolidation envoie au modèle la liste de toutes les pages existantes. Le banc a montré qu'à
grande échelle on peut n'envoyer que les pages que la recherche fait remonter, message par message. Avant de le faire
en production, on l'OBSERVE sur la vraie mémoire : la sélection est calculée et notée, la liste complète part
toujours au modèle. Après le passage, on note dans quelles pages existantes le modèle a rangé ses faits, et si ces
pages étaient dans la sélection — le rappel, mesuré sur la vie réelle, à mesure que la mémoire grandit.

Journal : `telemetrie/catalogue_observateur.jsonl`. Une panne ici n'arrête jamais la consolidation.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional

_MSG = re.compile(r"^\[(raw/[^\]]+|registre:[^\]]+)\] ?(.*)$")


def messages_des_sources(blocs: Iterable[str]) -> List[str]:
    """Les messages du lot : un en-tête « [HH:MM qui] » et ses lignes de suite ; chaque note du registre à part."""
    textes, courant = [], ""
    for l in blocs:
        m = _MSG.match(l)
        if not m:
            continue
        ref, t = m.groups()
        if ref.startswith("registre:") or re.match(r"\[\d\d:\d\d ", t):
            if courant:
                textes.append(courant)
            courant = t
        else:
            courant += " " + t
    if courant:
        textes.append(courant)
    return textes


def selection(racine: Path, blocs: Iterable[str], presents: Iterable[str], implicites=(), k: int = 30) -> Optional[Dict]:
    """Les k meilleures pages de CHAQUE message (même cascade que `memoire_chercher`), réunies. None si pas de graphe."""
    from .rappel import Rappeleur
    t0 = time.perf_counter()
    p = set(presents) - set(implicites)
    R = Rappeleur(racine, implicites=tuple(implicites))
    m = R.memoire()
    if m is None:
        return None
    textes = messages_des_sources(blocs)
    garder = set()
    for t in textes:
        a = R.activer(m, t)
        loc = {}
        for n, v in a["entrees"].items():
            if n in p:
                loc[n] = max(loc.get(n, 0.0), 1.0 + v)
        for n, v in a["actives"].items():
            if n in p:
                loc[n] = max(loc.get(n, 0.0), v)
        garder |= set(sorted(loc, key=loc.get, reverse=True)[:k])
    return {"k": k, "messages": len(textes), "pages": len(p), "selection": sorted(garder),
            "duree_ms": round((time.perf_counter() - t0) * 1000, 1)}


def bilan(obs: Dict, existants: Iterable[str], acceptes: Iterable, creees: Iterable[str], implicites=()) -> Dict:
    """Après le passage : les pages existantes où le modèle a rangé des faits, dans ou hors de la sélection."""
    ex = set(existants) - set(implicites)
    ranges = sorted({a[0] for a in acceptes if a[0] in ex})
    sel = set(obs.get("selection") or ())
    hors = [n for n in ranges if n not in sel]
    return {**{k: v for k, v in obs.items() if k != "selection"}, "selection_taille": len(sel),
            "rattachements": len(ranges), "dans_selection": len(ranges) - len(hors), "hors_selection": hors,
            "noeuds_crees": len(list(creees))}
