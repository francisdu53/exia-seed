"""L'oubli sous conditions (docs/18 §3) — le PLAN, calculé sans modèle et sans rien écrire.

Un fait décline avec le temps passé sans usage : s = exp(−Δt/τ), τ par section (épisodique 30 j, sémantique 30 j,
procédural 90 j, prospectif 30 j après l'échéance — docs/18 §9). Δt part de son dernier renfort : sa date d'écriture (`dit_le`), ou
la dernière fois que sa page a servi (montrée, trouvée ou lue). Sous SEUIL, il est oublié — sauf s'il remplit une
condition de non-oubli : une date récurrente (échéance ou date d'événement sur un sujet récurrent : anniversaire,
contrat, assurance…), `protected`, une note « note ça », une catégorie protégée (pages de l'utilisateur et de l'agent,
consignes à l'agent, concepts protégés). Ce module rend le plan ; l'appliquer est le travail d'un autre (un seul
écrivain), et le banc du temps (docs/18 §8) le rejoue sur l'histoire réelle.
"""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

# τ de départ de la spec (§6.5) : épisodique 7 j. Mesuré au banc (docs/18 §9) : à 7 j, l'oubli fait perdre 3,6 points de
# bonnes réponses dans le pire cas (aucun rappel), à 30 j 0,8 point. Retenu : 30 j pour l'épisodique et le prospectif.
TAU = {"episodic": 30.0, "semantic": 30.0, "procedural": 90.0, "prospective": 30.0}
SEUIL = 0.05                                   # ≈ 3 τ sans usage
CONCEPTS_PROTEGES = ("anniversaire", "assurance", "sante", "facturation", "fiscalite", "cotisations_sociales",
                     "statut_juridique", "succession", "dette", "contrat", "famille", "juridique",
                     "birthday", "insurance", "health", "billing", "tax", "contract", "family", "legal")
CONCEPTS_RECURRENTS = ("anniversaire", "assurance", "fiscalite", "cotisations_sociales", "contrat", "abonnement",
                       "birthday", "insurance", "tax", "contract", "subscription")
MOTS_RECURRENTS = ("anniversaire", "contrat", "assurance", "abonnement", "garantie", "controle technique", "impot",
                   "echeance", "renouvellement", "cotisation", "loyer", "bail", "birthday", "anniversary", "contract",
                   "insurance", "subscription", "warranty", "renewal", "lease", "tax")
_FAIT = re.compile(r"^- (.*?) <!-- (.*?) -->\s*$")


def _plat(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def _jour(v) -> Optional[date]:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("_", "T")[:16]).date()
    except Exception:
        try:
            return date.fromisoformat(str(v)[:10])
        except Exception:
            return None


def meta(texte: str) -> Dict[str, str]:
    out = {}
    for t in texte.split():
        if ":" in t:
            k, v = t.split(":", 1)
            out[k] = v
    return out


def faits_de(page) -> List[Dict]:
    """Les faits d'une page (`pages.Page`), avec leur section et leurs métadonnées."""
    out = []
    for cle, lignes in page.sections.items():
        for l in lignes:
            m = _FAIT.match(l)
            if m:
                out.append({"section": cle, "fait": m.group(1), "meta": meta(m.group(2)), "ligne": l})
    return out


def condition(f: Dict, page_noeud: str, page_type: str, implicites: Iterable[str],
              proteges: Iterable[str] = CONCEPTS_PROTEGES) -> Optional[str]:
    """La première condition de non-oubli remplie, ou None."""
    m = f["meta"]
    concepts = set((m.get("concepts") or "").split(",")) - {""}
    texte = _plat(f["fait"])
    recurrent = bool(concepts & set(CONCEPTS_RECURRENTS)) or any(w in texte for w in MOTS_RECURRENTS)
    if (m.get("echeance") or m.get("event_time")) and recurrent:
        return "date_recurrente"
    if m.get("protected") == "true":
        return "protege"
    if "registre:" in (m.get("src") or ""):
        return "note_demandee"
    if page_noeud in set(implicites):
        return "page_utilisateur_ou_agent"
    if page_type == "etat_agent":
        return "consigne_agent"
    if concepts & set(proteges):
        return "concept_protege"
    return None


def force(f: Dict, aujourdhui: date, derniere_utilisation: Optional[date], tau: Optional[Dict[str, float]] = None) -> float:
    m = f["meta"]
    renfort = max([d for d in (_jour(m.get("dit_le")), derniere_utilisation) if d and d <= aujourdhui], default=None)
    if f["section"] == "prospective":
        ech = _jour(m.get("echeance"))
        if ech and ech > aujourdhui:
            return 1.0                              # une intention à venir ne décline pas
        renfort = max([d for d in (renfort, ech) if d], default=renfort)
    if renfort is None:
        return 1.0                                  # sans date, on ne décide rien (fail-closed)
    return math.exp(-max(0, (aujourdhui - renfort).days) / (tau or TAU).get(f["section"], 30.0))


def plan(pages: Iterable, aujourdhui: date, usages: Dict[str, date], implicites: Iterable[str] = (),
         proteges: Iterable[str] = CONCEPTS_PROTEGES, seuil: float = SEUIL, tau: Optional[Dict[str, float]] = None) -> Dict:
    """Ce qui serait oublié aujourd'hui. `usages` : nœud → dernière date où sa page a servi."""
    oublies, epargnes, total = [], {}, 0
    for p in pages:
        n, t = p.entete.get("node"), p.entete.get("node_type")
        for f in faits_de(p):
            total += 1
            s = force(f, aujourdhui, usages.get(n), tau)
            if s >= seuil:
                continue
            c = condition(f, n, t, implicites, proteges)
            if c:
                epargnes[c] = epargnes.get(c, 0) + 1
                continue
            oublies.append({"noeud": n, "page": p.chemin.name, "section": f["section"], "fait": f["fait"],
                            "force": round(s, 4), "dit_le": f["meta"].get("dit_le")})
    return {"date": aujourdhui.isoformat(), "faits": total, "oublies": oublies, "epargnes_par_condition": epargnes}


def appliquer(racine: Path, resultat: Dict, maintenant: Optional[datetime] = None) -> Dict:
    """Retire les faits du plan de leurs pages ; une page sans faits est retirée. Chaque fait oublié est écrit dans
    `oublis/AAAA-MM.jsonl` (texte, métadonnées, page, date, force) : `restaurer` le remet. Le brut et git gardent la
    trace. L'APPELANT tient le verrou (un seul écrivain) puis recalcule l'index et le graphe."""
    import json
    from . import pages as _pages
    from .util import ajouter_ligne_jsonl
    quand = (maintenant or datetime.now()).isoformat(timespec="seconds")
    par_page: Dict[str, set] = {}
    for o in resultat.get("oublies") or []:
        par_page.setdefault(o["page"], set()).add(o["fait"])
    retires, pages_retirees = 0, []
    journal = Path(racine) / "oublis" / f"{quand[:7]}.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)
    for p in _pages.lister(Path(racine) / "pages"):
        cibles = par_page.get(p.chemin.name)
        if not cibles:
            continue
        for cle, lignes in p.sections.items():
            garder = []
            for l in lignes:
                m = _FAIT.match(l)
                if m and m.group(1) in cibles:
                    ajouter_ligne_jsonl(journal, {"ts": quand, "page": p.chemin.name, "noeud": p.entete.get("node"),
                                                  "section": cle, "ligne": l, "raison": "declin"})
                    retires += 1
                else:
                    garder.append(l)
            p.sections[cle] = garder
        if any(_FAIT.match(l) for v in p.sections.values() for l in v):
            p.ecrire()
        else:
            ajouter_ligne_jsonl(journal, {"ts": quand, "page": p.chemin.name, "noeud": p.entete.get("node"),
                                          "entete": json.loads(json.dumps(p.entete, default=str)), "raison": "page_vide"})
            p.chemin.unlink(); pages_retirees.append(p.chemin.name)
    return {"faits_retires": retires, "pages_retirees": pages_retirees, "journal": str(journal)}


def restaurer(racine: Path, page: str, fait_prefixe: str = "") -> int:
    """Remet dans leur page les faits oubliés de `page` (tous, ou ceux qui commencent par `fait_prefixe`)."""
    import json
    from . import pages as _pages
    remis = 0
    for f in sorted((Path(racine) / "oublis").glob("*.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            x = json.loads(l)
            if x.get("page") != page or "ligne" not in x:
                continue
            m = _FAIT.match(x["ligne"])
            if not m or not m.group(1).startswith(fait_prefixe):
                continue
            chemin = Path(racine) / "pages" / page
            p = next((q for q in _pages.lister(chemin.parent) if q.chemin.name == page), None)
            if p is None:
                ent = next((json.loads(y).get("entete") for y in f.read_text(encoding="utf-8").splitlines()
                            if json.loads(y).get("page") == page and json.loads(y).get("entete")), None) or {"node": x.get("noeud")}
                p = _pages.Page.nouvelle(chemin.parent, ent.get("node"), ent.get("node_type", "concept"),
                                         ent.get("aliases") or {}, str(ent.get("created", ""))[:10], "restauration")
                p.entete.update(ent)                      # la fiche, les dates, la provenance d'avant l'oubli
            if x["ligne"] not in p.sections.setdefault(x["section"], []):
                p.sections[x["section"]].append(x["ligne"]); p.ecrire(); remis += 1
    return remis
