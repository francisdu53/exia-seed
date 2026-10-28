"""Les masques de langue — aucune donnée linguistique dans le code central (docs/10).

Repris d'EXIA GHOST V2.7.2 (`exia/linguistics/` : une interface, un masque par langue, un registre) et
élargi à ce dont EXIA SEED a besoin : mots vides, dates relatives, nombres en lettres, séparateurs de
milliers, consignes de mémoire, consigne de consolidation, textes lus par le modèle.

    from exia_seed import langues
    m = langues.de_la_memoire(racine)        # la langue est une propriété de la MÉMOIRE
    m.mots_vides, m.en_clair(d), m.textes["rien_de_lie"]

Changer de langue = enregistrer un masque. Une langue inconnue est REFUSÉE (jamais de repli silencieux),
et une mémoire construite dans une langue ne se relit pas avec le masque d'une autre.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .base import Masque

_REGISTRE: Dict[str, Masque] = {}
FICHIER = ".langue"                 # dans le dossier de la mémoire, suivi par git
DEFAUT = "fr"                       # une mémoire sans fichier .langue a été construite en français (0.1 → 0.8)


def enregistrer(masque: Masque) -> None:
    _REGISTRE[masque.code] = masque


def _charger() -> None:
    if not _REGISTRE:
        from . import en, fr  # noqa: F401 — chaque module s'enregistre à l'import


def masque(code: str) -> Masque:
    _charger()
    code = (code or "").strip().lower()
    if code not in _REGISTRE:
        raise ValueError(f"langue inconnue : « {code} » — masques disponibles : {', '.join(sorted(_REGISTRE))}")
    return _REGISTRE[code]


def tous() -> List[Masque]:
    _charger()
    return [_REGISTRE[c] for c in sorted(_REGISTRE)]


def de_la_memoire(racine) -> Masque:
    """Le masque de la mémoire `racine` : celui de son fichier `.langue`, sinon le français."""
    f = Path(racine) / FICHIER
    try:
        code = f.read_text(encoding="utf-8").strip()
    except OSError:
        code = DEFAUT
    return masque(code or DEFAUT)


def fixer(racine, code: str) -> Masque:
    """Inscrit la langue d'une mémoire (à sa création) ; refuse un changement de langue.

    Une mémoire existante sans `.langue` est française (tout ce qui précède la 0.9) : demander une
    autre langue sur elle est refusé, comme pour une mémoire marquée."""
    m = masque(code)
    racine = Path(racine)
    f = racine / FICHIER
    deja = f.read_text(encoding="utf-8").strip() if f.exists() else ""
    if not deja and (racine / "pages").exists() and any((racine / "pages").glob("*.md")):
        deja = DEFAUT
    if deja and deja != m.code:
        raise ValueError(f"la mémoire {racine} est en « {deja} », la configuration demande « {m.code} » — "
                         f"une mémoire ne change pas de langue")
    if not f.exists():
        racine.mkdir(parents=True, exist_ok=True)
        f.write_text(m.code + "\n", encoding="utf-8")
    return m


__all__ = ["Masque", "enregistrer", "masque", "tous", "de_la_memoire", "fixer", "FICHIER", "DEFAUT"]
