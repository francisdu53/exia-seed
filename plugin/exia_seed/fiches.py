"""La fiche d'identité d'un sujet (docs/12) — une phrase : ce que c'est, à quoi ça sert, où le trouver.

Né de l'incident du 15/10 : la page de l'application de courses avait 42 faits (rayons, boutons, zones) et
AUCUN ne disait ce qu'était l'application. Le rappel la trouvait, mais par ses détails ; le souvenir utile
était son identité. C'est aussi la ligne de résumé que le wiki de Karpathy met devant chaque page de son index.

    rediger(pages, appel_llm, date)    une phrase par page, écrite DEPUIS LA PAGE ENTIÈRE (la page fait foi,
                                       pas le lot du jour), contrôlée comme un fait, posée dans l'en-tête :
                                           summary: …        summary_date: AAAA-MM-JJ
    a_rafraichir(pages)                les pages sans fiche, ou modifiées depuis leur fiche

Contrôle (comme la règle 2 de la consolidation) : tout nom propre, tout nombre, tout chemin de la fiche doit
figurer dans la page. Une fiche refusée laisse l'ancienne en place. Une panne n'arrête rien (partiel > rien).
"""
from __future__ import annotations

import json
import re
from typing import Callable, Dict, List, Optional, Tuple

from . import pages as _pages

AppelLLM = Callable[[List[Dict[str, str]]], str]

PAGES_PAR_APPEL = 10            # un appel pour dix pages : la nuit touche rarement plus
CARACTERES_PAR_PAGE = 3000      # les faits d'une page, au plus (le général se voit dans les premiers)
FICHE_MAX = 320                 # caractères ; au-delà ce n'est plus une phrase d'identité

# La consigne au modèle vit dans le masque de langue de la mémoire (docs/10) : `masque.consigne_fiches()`.

_RE_CHEMIN = re.compile(r"[\w.~-]*/[\w./-]*\w|\b[\w-]+\.(?:md|py|json|csv|pdf|html|yaml|txt)\b|https?://\S+")


def a_rafraichir(pages: List[_pages.Page]) -> List[_pages.Page]:
    return [p for p in pages if any(p.sections.values())
            and (not p.entete.get("summary") or str(p.entete.get("summary_date") or "") < str(p.entete.get("updated") or ""))]


def _faits(p: _pages.Page) -> List[Tuple[str, str]]:
    """(section, texte) — le durable d'abord (sémantique, procédural), puis ce qui s'est passé."""
    ordre = ("semantic", "procedural", "prospective", "episodic")
    return [(s, _pages._RE_META.sub("", l[2:]).strip()) for s in ordre for l in p.sections.get(s, [])]


def _texte_page(p: _pages.Page) -> str:
    alias = [str(a) for l in (p.entete.get("aliases") or {}).values() for a in (l or []) if a]
    return " ".join([str(p.entete.get("node", "")).replace("_", " ")] + alias + [t for _, t in _faits(p)])


def _bloc(p: _pages.Page, t: Dict[str, str]) -> str:
    alias = ", ".join(str(a) for l in (p.entete.get("aliases") or {}).values() for a in (l or []) if a)
    lignes = [f"=== {p.entete.get('node')} ({p.entete.get('node_type')}) — {t['fiche_alias']} : {alias or '—'}"]
    if p.entete.get("summary"):
        lignes.append(f"{t['fiche_actuelle']}{p.entete['summary']}")
    if p.entete.get("keywords") is not None:
        lignes.append(f"{t['mots_actuels']}{', '.join(map(str, p.entete['keywords'])) or t['aucun']}")
    reste = CARACTERES_PAR_PAGE
    for s, t in _faits(p):
        if len(t) + 3 > reste:
            break
        lignes.append(f"- [{s}] {t}"); reste -= len(t) + 3
    return "\n".join(lignes)


def controler(fiche: str, p: _pages.Page, connus=()) -> Tuple[bool, str]:
    """Une fiche n'apporte rien que la page n'ait déjà : noms propres, nombres, chemins vérifiés.
    `connus` : l'utilisateur et l'agent, implicites dans toutes les pages (essai du 16/10 : « Francis » refusé)."""
    from . import graphe as _graphe
    from .consolidation import _noms_propres, _nombres
    fiche = re.sub(r"\s+", " ", fiche or "").strip()
    if not fiche:
        return False, "vide"
    if len(fiche) > FICHE_MAX:
        return False, f"trop longue ({len(fiche)} car.)"
    texte = _texte_page(p)
    norm = _graphe._norm(texte)
    mots = {w[:5] for w in norm.split()} | {_graphe._norm(c).strip()[:5] for c in connus if c}
    for nom in _noms_propres(fiche):
        n = _graphe._norm(nom).strip()
        # « Phone » lu dans « iPhone » (essai du 16/10) : le nom peut être une partie d'un mot de la page
        # « LIEN-PRIVE-RECETTES » (un nom de fichier, rattrapage du 16/10) : comparé sans les espaces nés des tirets
        if n[:5] not in mots and n.replace(" ", "") not in norm.replace(" ", ""):
            return False, f"nom absent de la page : {nom}"
    masque = _pages._masque(p.chemin)                          # séparateur de milliers de la langue (docs/10)
    nombres = set(_nombres(texte, masque))
    for n in _nombres(fiche, masque):
        if n not in nombres:
            return False, f"nombre absent de la page : {n}"
    for c in _RE_CHEMIN.findall(fiche):
        if c.rstrip(".,;)") not in texte:
            return False, f"chemin absent de la page : {c}"
    return True, ""


def mots_valides(mots, p: _pages.Page, connus=()) -> List[str]:
    """Les mots distinctifs gardés : un mot seul, présent dans le nom ou les alias de la page (le rappel les compare
    aux mots d'alias), quatre au plus. Un mot inventé est écarté sans refuser la fiche."""
    from . import graphe as _graphe
    permis = set(_graphe._norm(" ".join([str(p.entete.get("node", "")).replace("_", " ")] + [
        str(a) for l in (p.entete.get("aliases") or {}).values() for a in (l or []) if a])).split())
    # l'utilisateur et l'agent sont dans presque chaque message (« Coucou Nexa ») : jamais distinctifs (essai du 16/10)
    exclus = {_graphe._norm(c).strip() for c in connus if c}
    garde = []
    for m in mots or []:
        w = _graphe._norm(str(m)).strip()
        if w and " " not in w and w in permis and w not in garde and w not in exclus:
            garde.append(w)
    return garde[:4]


def _poser(p: _pages.Page, fiche: str, date: str, mots=None) -> None:
    """summary (puis keywords) juste après les alias : l'en-tête se lit de haut en bas, l'identité avant l'histoire."""
    nouv = {}
    for k, v in p.entete.items():
        if k in ("summary", "summary_date", "keywords"):
            continue
        nouv[k] = v
        if k == "aliases":
            nouv["summary"], nouv["summary_date"] = fiche, date
            if mots is not None:
                nouv["keywords"] = list(mots)
    nouv.setdefault("summary", fiche); nouv.setdefault("summary_date", date)
    if mots is not None:
        nouv.setdefault("keywords", list(mots))
    elif p.entete.get("keywords") is not None:
        nouv["keywords"] = p.entete["keywords"]
    p.entete.clear(); p.entete.update(nouv)


def _extraire(reponse: str) -> Dict[str, Tuple[str, Optional[list]]]:
    """{nœud: (fiche, mots)} ; l'ancienne forme {nœud: "phrase"} reste lue (mots = None : inchangés)."""
    s = (reponse or "").strip()
    debut, fin = s.find("{"), s.rfind("}")
    if debut < 0 or fin <= debut:
        return {}
    try:
        f = json.loads(s[debut:fin + 1]).get("fiches") or {}
    except (ValueError, AttributeError):
        return {}
    if not isinstance(f, dict):
        return {}
    sortie = {}
    for k, v in f.items():
        if isinstance(v, str):
            sortie[str(k)] = (v, None)
        elif isinstance(v, dict) and isinstance(v.get("fiche"), str):
            mots = v.get("mots")
            sortie[str(k)] = (v["fiche"], [str(x) for x in mots] if isinstance(mots, list) else None)
    return sortie


def rediger(pages: List[_pages.Page], appel_llm: AppelLLM, date: str, ecrire: bool = True, connus=()) -> Dict:
    """Rédige, contrôle et pose la fiche de chaque page. `ecrire=False` : essai à blanc (rien sur disque)."""
    from .util import estimer_tokens
    rapport = {"statut": "ok", "demandees": len(pages), "ecrites": [], "inchangees": [], "refusees": [],
               "absentes": [], "appels": 0, "tokens_entree": 0, "tokens_sortie": 0, "proposees": {}, "mots": {}}
    par_noeud = {str(p.entete.get("node")): p for p in pages}
    noeuds = list(par_noeud)
    for i in range(0, len(noeuds), PAGES_PAR_APPEL):
        lot = [par_noeud[n] for n in noeuds[i:i + PAGES_PAR_APPEL]]
        masque = _pages._masque(lot[0].chemin)                 # la langue de la MÉMOIRE (docs/10)
        messages = [{"role": "system", "content": masque.consigne_fiches()},
                    {"role": "user", "content": masque.textes["fiches_pages"] + "\n\n" + "\n\n".join(_bloc(p, masque.textes) for p in lot)}]
        try:
            reponse = appel_llm(messages)
        except Exception as e:                       # un lot en panne n'arrête pas les autres
            rapport["statut"] = "partiel"
            rapport["refusees"] += [(str(p.entete.get("node")), f"appel : {type(e).__name__}") for p in lot]
            continue
        rapport["appels"] += 1
        rapport["tokens_entree"] += sum(estimer_tokens(m["content"]) for m in messages)
        rapport["tokens_sortie"] += estimer_tokens(reponse or "")
        fiches = _extraire(reponse)
        for p in lot:
            n = str(p.entete.get("node"))
            brut, mots = fiches.get(n, ("", None))
            fiche = re.sub(r"\s+", " ", brut).strip()
            if not fiche:
                rapport["absentes"].append(n); continue
            ok, raison = controler(fiche, p, connus)
            if not ok:
                rapport["refusees"].append((n, raison, fiche)); continue
            rapport["proposees"][n] = fiche
            if mots is not None:
                mots = mots_valides(mots, p, connus)
                rapport["mots"][n] = mots
            if fiche == p.entete.get("summary") and (mots is None or mots == p.entete.get("keywords")):
                rapport["inchangees"].append(n)
            else:
                rapport["ecrites"].append(n)
            if ecrire:
                _poser(p, fiche, date, mots)
                p.ecrire()
    return rapport
