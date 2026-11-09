#!/usr/bin/env python3
"""Banc 17 §19 — détecteur de doublons DÉTERMINISTE (sans modèle), éprouvé sur les mémoires du banc. Gratuit.

Un doublon : deux pages pour la même chose sous deux noms. Le code de consolidation ne rattache un fait à une page
existante que si le nom donné par le modèle est EXACTEMENT un titre ou un alias connu ; il ne consulte pas la FCM.
Le détecteur la consulte après coup. Trois règles, de la plus sûre à la plus large :
- R1 mêmes racines : les noms (titre + alias), réduits à leurs racines sans les mots vides, sont identiques
  (« coworker holiday mugs » / « coworkers holiday mugs ») ;
- R2 alias partagé : un alias de plusieurs mots commun aux deux pages, ou d'un seul mot si elles ont des voisins
  communs dans le graphe (deux « Alex » sans voisins communs : deux personnes) ;
- R3 noms proches et même voisinage : racines communes ≥ 50 % (Jaccard) ET voisins communs dans le graphe ≥ 30 %.

    python3 doublons.py <mémoire> [<mémoire de départ>]   → paires candidates (JSON sur la sortie)
"""
import itertools, json, re, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, "/plugins")
from exia_seed import graphe as G
from exia_seed import pages as P
from exia_seed import rappel as RP

IMPLICITES = {"user", "assistant", "francis", "nexa"}


def _mot(w):
    """Mot entier, pluriel ôté (pas de racine tronquée : « instacart » ≠ « instagram »)."""
    for fin in ("ies", "es", "s", "x"):
        if len(w) > len(fin) + 3 and w.endswith(fin):
            return w[: -len(fin)] + ("y" if fin == "ies" else "")
    return w


def racines(textes, vides):
    return {_mot(w) for t in textes for w in G._norm(t).split() if len(w) >= 2 and w not in vides and not w.isdigit()}


def charger(mem: Path):
    from exia_seed import langues
    vides = RP._mots_vides(langues.de_la_memoire(mem))
    pg = {}
    for p in P.lister(mem / "pages"):
        n = p.entete.get("node")
        if not n or n in IMPLICITES:
            continue
        alias = [a for l in (p.entete.get("aliases") or {}).values() for a in (l or [])]
        pg[n] = {"fichier": p.chemin.name, "type": p.entete.get("node_type"),
                 "racines": racines([n.replace("_", " ")] + alias, vides),
                 "alias": {G._norm(a).strip() for a in alias if a}}
    voisins = defaultdict(set)
    f = mem / "graphe" / "aretes.json"
    for a in (json.loads(f.read_text()) if f.exists() else []):
        voisins[a["a"]].add(a["b"]); voisins[a["b"]].add(a["a"])
    for n in pg:
        pg[n]["voisins"] = voisins.get(n, set()) - IMPLICITES
    return pg


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0


def detecter(mem: Path, depart: Path = None):
    pg = charger(mem)
    from exia_seed import langues
    vides = RP._mots_vides(langues.de_la_memoire(mem))
    anciens = {p.entete.get("node") for p in P.lister(depart / "pages")} if depart else set()
    par_racine = defaultdict(set)
    for n, x in pg.items():
        for r in x["racines"]:
            par_racine[r].add(n)
    cand = set()
    for n, x in pg.items():
        for r in x["racines"]:
            if len(par_racine[r]) <= 60:                      # une racine trop répandue ne propose rien seule
                cand |= {tuple(sorted((n, m))) for m in par_racine[r] if m != n}
    out = []
    for a, b in sorted(cand):
        if depart and a in anciens and b in anciens:
            continue                                          # on cherche les doublons créés pendant le banc
        x, y = pg[a], pg[b]
        jv = jaccard(x["voisins"], y["voisins"]); jr = jaccard(x["racines"], y["racines"])
        commun = x["alias"] & y["alias"]
        regle = None
        noms_x = {frozenset(_mot(w) for w in a0.split() if w not in vides) for a0 in x["alias"] | {a.replace("_", " ")}}
        noms_y = {frozenset(_mot(w) for w in a0.split() if w not in vides) for a0 in y["alias"] | {b.replace("_", " ")}}
        if noms_x & noms_y - {frozenset()}:
            regle = "R1"                                      # même nom aux pluriels et à l'ordre des mots près
        elif any(len(c.split()) >= 2 for c in commun):
            regle = "R2"                                      # un alias de plusieurs mots en commun
        elif jr >= 0.5 and jv >= 0.3:
            regle = "R3"                                      # suggestion faible : à vérifier, jamais fusionnée seule
        if regle:
            out.append({"a": x["fichier"], "b": y["fichier"], "regle": regle, "racines_j": round(jr, 2), "voisins_j": round(jv, 2),
                        "nouvelle": [p for p, nn in ((x["fichier"], a), (y["fichier"], b)) if nn not in anciens]})
    return out


if __name__ == "__main__":
    mem = Path(sys.argv[1]); dep = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    r = detecter(mem, dep)
    print(json.dumps({"memoire": str(mem), "paires": r, "par_regle": {k: sum(x["regle"] == k for x in r) for k in ("R1", "R2", "R3")}},
                     ensure_ascii=False))
