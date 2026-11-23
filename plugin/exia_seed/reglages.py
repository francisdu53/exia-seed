"""Vérification des réglages d'une mémoire (décision A1, 15/11/2026).

Avant : un réglage était pris tel quel. Une valeur fausse pouvait mettre toute la mémoire en retrait — le brut
cessait de s'écrire, en silence (mesuré le 15/11 : langue différente, seuil « 25k », nom d'agent en liste) — ou
glisser sans alerte (fuseau mal écrit → UTC).

Maintenant, chaque réglage est vérifié (type, valeurs possibles) et rangé dans un des trois groupes :
- ÉCRITURE (le brut) : une valeur fausse est remplacée par la dernière valeur valide de la mémoire (sinon le
  défaut) ; le brut continue de s'écrire ; code ES-CFG-02. Sur une mémoire NEUVE, rien n'est créé (ES-CFG-07) :
  on refuse plutôt que de démarrer de travers.
- CONSOLIDATION : une valeur fausse met la consolidation EN PAUSE (ES-CFG-05) ; le brut attend, rien n'est perdu ;
  une fois le réglage réparé, la consolidation suivante rattrape la file.
- LECTURE (rappel, souvenirs) : dernière valeur valide, sinon défaut (ES-CFG-06).
Un réglage inconnu est ignoré (ES-CFG-04). La langue d'une mémoire existante fait foi (ES-CFG-03).

Chaque mémoire garde ses derniers réglages valides dans `.reglages_valides.json` (comme Hermès garde la
dernière version lisible de son config.yaml).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Set, Tuple

from . import codes_defauts
from .config import DEFAUTS
from .util import ecrire_json, lire_json

FICHIER_VALIDES = ".reglages_valides.json"
CONSIGNES = ("production", "adaptee", "petit_modele")


class MemoireNonCreee(ValueError):
    """Réglages d'écriture invalides sur une mémoire neuve (ES-CFG-07)."""


# ── les vérificateurs ────────────────────────────────────────────────────────
def _entier(mini=None, maxi=None) -> Callable[[Any], bool]:
    return lambda x: (isinstance(x, int) and not isinstance(x, bool)
                      and (mini is None or x >= mini) and (maxi is None or x <= maxi))


def _nombre(mini=None, maxi=None) -> Callable[[Any], bool]:
    return lambda x: (isinstance(x, (int, float)) and not isinstance(x, bool)
                      and (mini is None or x >= mini) and (maxi is None or x <= maxi))


def _booleen(x) -> bool:
    return isinstance(x, bool)


def _texte(vide=True, maxi=200) -> Callable[[Any], bool]:
    return lambda x: isinstance(x, str) and len(x) <= maxi and (vide or bool(x.strip()))


def _parmi(*valeurs) -> Callable[[Any], bool]:
    return lambda x: not isinstance(x, bool) and x in valeurs


def fuseau_valide(nom: Any) -> bool:
    if not isinstance(nom, str) or not nom or len(nom) > 64:
        return False
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(nom)
        return True
    except Exception:
        return False


def _fuseau(x) -> bool:
    return x == "" or fuseau_valide(x)                 # vide = le fuseau de la plateforme


def _dossier(x) -> bool:
    if not isinstance(x, str) or not x.strip() or len(x) > 200 or "\\" in x:
        return False
    p = Path(x)
    return not p.is_absolute() and ".." not in p.parts


def _langue(x) -> bool:
    from . import langues
    return isinstance(x, str) and x.strip().lower() in {m.code for m in langues.tous()}


def _liste_textes(x) -> bool:
    return isinstance(x, list) and len(x) <= 50 and all(isinstance(n, str) and len(n) <= 100 for n in x)


def _effort(x) -> bool:
    return x is None or isinstance(x, bool) or (isinstance(x, str) and len(x) <= 20)


def _poids_sujet(x) -> bool:
    """`recherche_poids_sujet` (0.9.5) : None ou « ancienne » = l'ancienne note (le réglage de Nexa ; « ancienne » survit au
    réenregistrement de config.yaml par Hermès, qui retire les null), « eventail », ou un nombre 0..1."""
    return x is None or x in ("ancienne", "eventail") or (isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x <= 1)


def _seuils_bulletin(x) -> bool:
    """`bulletin_seuils` (0.9.5) : {nom: nombre} — les seuils proposés par outils/bulletin.py, remplacés un par un."""
    return isinstance(x, dict) and all(isinstance(k, str) and isinstance(v, (int, float)) and not isinstance(v, bool)
                                       for k, v in x.items())


_CLES_CANAL = {"dossier", "correspondant", "description", "uid_correspondant", "uid_agent", "echanges_max"}


def _canal(x) -> bool:
    """`canal` (0.9.6) : {} (éteint) ou {dossier, correspondant[, description, uid_correspondant, uid_agent,
    echanges_max]} — outils/canal.py. Une valeur fausse prend la dernière valide, sinon {} : le canal s'éteint."""
    if x == {}:
        return True
    return (isinstance(x, dict) and set(x) <= _CLES_CANAL and _dossier(x.get("dossier"))
            and isinstance(x.get("correspondant"), str) and 0 < len(x["correspondant"].strip()) <= 100
            and isinstance(x.get("description", ""), str) and len(x.get("description", "")) <= 500
            and all(isinstance(x[k], int) and not isinstance(x[k], bool) and x[k] >= 0
                    for k in ("uid_correspondant", "uid_agent") if k in x)
            and (isinstance(x.get("echanges_max", 14), int) and not isinstance(x.get("echanges_max", 14), bool)
                 and 1 <= x.get("echanges_max", 14) <= 1000))


ECRITURE, CONSOLIDATION, LECTURE = "ecriture", "consolidation", "lecture"

SCHEMA: Dict[str, Tuple[str, Callable[[Any], bool]]] = {
    "dossier": (ECRITURE, _dossier),
    "seuil_lot_tokens": (ECRITURE, _entier(100, 10_000_000)),
    "fermer_lot_fin_de_session": (ECRITURE, _booleen),
    "fuseau": (ECRITURE, _fuseau),
    "nom_utilisateur": (ECRITURE, _texte(vide=True, maxi=100)),
    "nom_agent": (ECRITURE, _texte(vide=True, maxi=100)),          # vide : conversation sans agent (LoCoMo)
    "langue": (ECRITURE, _langue),
    "interlocuteurs": (ECRITURE, _liste_textes),
    "consolidation_auto": (CONSOLIDATION, _booleen),
    "consolidation_effort": (CONSOLIDATION, _effort),
    "consolidation_modele": (CONSOLIDATION, _texte(vide=True, maxi=200)),
    "consolidation_consigne": (CONSOLIDATION, _parmi(*CONSIGNES)),
    "catalogue_observateur_k": (CONSOLIDATION, _entier(0, 1000)),
    "consolidation_max_tokens_entree": (CONSOLIDATION, _entier(1000, 10_000_000)),
    "fiches": (CONSOLIDATION, _booleen),
    # réglages ajoutés après 122e8eb (0.9.5, 0.9.6 — intégration chez Nexa, 15/11/2026)
    "consolidation_par_echange": (CONSOLIDATION, _booleen),
    "retrait_retroactif": (CONSOLIDATION, _booleen),
    "phase": (LECTURE, _parmi(1, 2)),
    "rappel_a_blanc": (LECTURE, _booleen),
    "souvenirs_seuil": (LECTURE, _nombre(0)),
    "souvenirs_max_sujets": (LECTURE, _entier(0, 50)),
    "souvenirs_faits_par_sujet": (LECTURE, _entier(0, 50)),
    "amorce_minutes": (LECTURE, _nombre(0, 24 * 60)),
    "recherche_poids_sujet": (LECTURE, _poids_sujet),
    # 0.9.16 (20/11/2026) : le moteur du rappel automatique — « ancien » (jusqu'à 0.9.15, défaut) ou « montre » (docs/21)
    "rappel_moteur": (LECTURE, _parmi("ancien", "montre", "deux_memoires")),
    # 0.10.0 (docs/22) : le rappel « deux mémoires »
    "deux_memoires_seuil": (LECTURE, _nombre(0, 1)),
    "deux_memoires_max": (LECTURE, _entier(1, 50)),
    "deux_memoires_regle": (LECTURE, _booleen),
    "deux_memoires_correcteur": (LECTURE, _booleen),
    "bulletin_seuils": (LECTURE, _seuils_bulletin),
    "canal": (LECTURE, _canal),
}
_CODE = {ECRITURE: "ES-CFG-02", CONSOLIDATION: "ES-CFG-05", LECTURE: "ES-CFG-06"}

# Les réglages qui ont un vérificateur DÉDIÉ. Le test exige que ce soit tous ceux de DEFAUTS.
DEDIES = frozenset(SCHEMA)


def _comme_le_defaut(defaut: Any) -> Callable[[Any], bool]:
    if isinstance(defaut, bool):
        return _booleen
    if isinstance(defaut, int):
        return _entier()
    if isinstance(defaut, float):
        return _nombre()
    if isinstance(defaut, str):
        return _texte(vide=True, maxi=500)
    if isinstance(defaut, list):
        return lambda x: isinstance(x, list)
    return lambda x: True


# Un réglage ajouté à DEFAUTS sans vérificateur dédié (une version plus récente du moteur) n'empêche JAMAIS le
# chargement : il est vérifié par le type de son défaut et rangé en « lecture » (une valeur fausse prend le défaut,
# rien ne s'arrête). Une assertion à l'import aurait arrêté toute la mémoire — le contraire de A1.
for _cle, _defaut in DEFAUTS.items():
    SCHEMA.setdefault(_cle, (LECTURE, _comme_le_defaut(_defaut)))


def valide(cle: str, valeur: Any) -> bool:
    try:
        return cle in SCHEMA and bool(SCHEMA[cle][1](valeur))
    except Exception:
        return False


def groupe(cle: str) -> str:
    return SCHEMA[cle][0] if cle in SCHEMA else ""


# ── 1. vérifier (sans rien lire ni écrire) ──────────────────────────────────
def verifier(fournis: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Tuple[str, str]], Set[str]]:
    """Défauts + réglages fournis VALIDES. Rend (réglages, codes [(code, clé)], clés invalides)."""
    reglages = dict(DEFAUTS)
    codes: List[Tuple[str, str]] = []
    invalides: Set[str] = set()
    for cle, valeur in (fournis or {}).items():
        cle = str(cle)
        if cle not in SCHEMA:
            codes.append(("ES-CFG-04", cle))
        elif valide(cle, valeur):
            reglages[cle] = valeur.strip().lower() if cle == "langue" else valeur
        else:
            codes.append((_CODE[groupe(cle)], cle))
            invalides.add(cle)
    return reglages, codes, invalides


# ── 2. appliquer à une mémoire (dernières valeurs valides, langue, pause) ────
def _langue_de(racine: Path) -> str:
    from . import langues
    f = racine / langues.FICHIER
    deja = f.read_text(encoding="utf-8").strip() if f.exists() else ""
    if not deja and (racine / "pages").exists() and any((racine / "pages").glob("*.md")):
        deja = langues.DEFAUT
    return deja


def _neuve(racine: Path) -> bool:
    return not racine.exists() or not any(racine.iterdir())


def appliquer(racine: Path, reglages: Dict[str, Any], codes: Iterable[Tuple[str, str]],
              invalides: Set[str]) -> Tuple[Dict[str, Any], bool]:
    """Complète `reglages` (sortis de `verifier`) pour la mémoire `racine` et inscrit les codes défauts.

    Rend (réglages effectifs, consolidation_en_pause). Lève `MemoireNonCreee` si un réglage d'écriture est
    invalide sur une mémoire neuve (rien n'est créé)."""
    racine = Path(racine)
    reglages = dict(reglages)
    neuve = _neuve(racine)
    ecriture_fausse = sorted(c for c in invalides if groupe(c) == ECRITURE)
    if neuve and ecriture_fausse:
        for cle in ecriture_fausse:
            codes_defauts.inscrire(None, "ES-CFG-07", cle, "mémoire non créée")
        raise MemoireNonCreee("réglages d'écriture invalides pour une mémoire neuve : " + ", ".join(ecriture_fausse))

    derniers = lire_json(racine / FICHIER_VALIDES, {}) if not neuve else {}
    derniers = {k: v for k, v in (derniers if isinstance(derniers, dict) else {}).items() if valide(k, v)}
    actions: Dict[str, str] = {}
    for cle in invalides:
        if groupe(cle) == CONSOLIDATION:
            actions[cle] = "consolidation en pause"
        elif cle in derniers:
            reglages[cle] = derniers[cle]
            actions[cle] = "dernière valeur valide"
        else:
            actions[cle] = "valeur par défaut"
    for code, cle in codes:
        codes_defauts.inscrire(racine, code, cle, actions.get(cle, "ignoré" if code == "ES-CFG-04" else ""))

    langue = _langue_de(racine)
    if langue and langue != reglages.get("langue"):
        codes_defauts.inscrire(racine, "ES-CFG-03", "langue", "langue de la mémoire gardée")
        reglages["langue"] = langue

    pause = any(groupe(c) == CONSOLIDATION for c in invalides)

    # La copie des derniers réglages valides : on n'y range que des valeurs vérifiées, jamais une valeur fausse.
    nouveaux = {**derniers, **{k: reglages[k] for k in SCHEMA if k not in invalides and valide(k, reglages[k])}}
    if nouveaux != derniers:
        racine.mkdir(parents=True, exist_ok=True)
        ecrire_json(racine / FICHIER_VALIDES, nouveaux)
    return reglages, pause


__all__ = ["SCHEMA", "DEDIES", "CONSIGNES", "FICHIER_VALIDES", "MemoireNonCreee", "verifier", "appliquer", "valide",
           "groupe", "fuseau_valide"]
