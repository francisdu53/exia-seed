#!/usr/bin/env python3
"""Banc 17 §13 — bilan : liste complète contre liste ciblée, à grande échelle (LongMemEval fusionnée). Sans modèle.

Lit les runs catalogue-complet-1/2 et catalogue-cible-1/2 (`catalogue_lme.py`). Seuils C1-C4 du §13 ; rappel de la
recherche ; tokens réels. Écrit `runs/catalogue-bilan.json` (agrégats) et `runs/catalogue-doublons-prive.json`.

    python3 comparer_catalogue_lme.py           (sur l'hôte)
"""
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

RUNS = Path(sys.argv[1] if len(sys.argv) > 1 else "$HOME/banc-longmemeval/runs")
BASE = RUNS / "catalogue-base" / "memoires" / "_fusion"
PREFIXE = __import__("os").environ.get("CATALOGUE_PREFIXE", "catalogue")       # §14 : catalogue-terra
CONDITIONS = {c: (f"{PREFIXE}-{c}-1", f"{PREFIXE}-{c}-2") for c in ("complet", "cible")}
IMPLICITES = {"user", "assistant"}
FAIT = re.compile(r"^- (.*?) <!-- (.*?) -->\s*$")
RAW_Q = re.compile(r"^(.*)_\d{4}-\d\d-\d\d_\d\d\.md$")
ENTETE = re.compile(r"^\[(\d\d:\d\d) ([a-z_]+)\] ?(.*)$")


def refs(meta):
    s = re.search(r"(?:^| )src:(\S+)", meta); out = set()
    for ref in (s.group(1).split(",") if s else []):
        r = re.match(r"raw/([^:]+):(\d+)(?:-(\d+))?", ref)
        if r:
            out |= {(r.group(1), k) for k in range(int(r.group(2)), int(r.group(3) or r.group(2)) + 1)}
    return out


def pages(mem: Path):
    """{page (fichier) : lignes de brut NOUVEAU citées}"""
    out = {}
    for p in (mem / "pages").glob("*.md"):
        c = set()
        for l in p.read_text(encoding="utf-8").splitlines():
            m = FAIT.match(l)
            if m:
                c |= {x for x in refs(m.group(2)) if (mem / "raw" / x[0]).exists()}
        out[p.name] = c
    return out


def noeud_de(p: Path) -> str:
    m = re.search(r"^node: (.+)$", p.read_text(encoding="utf-8"), re.M)
    return m.group(1).strip() if m else p.stem


def couverture(mem: Path, cites: set):
    n = c = 0
    for f in (mem / "raw").glob("*.md"):
        courant = None
        msgs = []
        for i, l in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            m = ENTETE.match(l)
            if m:
                if courant: msgs.append(courant)
                courant = [i, i, m.group(3)] if m.group(2) == "user" else None
            elif courant is not None and l.strip() and not l.startswith(("<!--", "#", "---")):
                courant[1] = i; courant[2] += " " + l.strip()
        if courant: msgs.append(courant)
        for a, b, t in msgs:
            if len(t.split()) >= 6:
                n += 1; c += any((f.name, k) in cites for k in range(a, b + 1))
    return c, n


def doublons(pa, pb, existantes):
    ligne_b = defaultdict(set)
    for page, lignes in pb.items():
        for l in lignes:
            ligne_b[l].add(page)
    out = []
    for page, lignes in pa.items():
        if page in existantes or not lignes:
            continue
        vers = Counter(q for l in lignes for q in ligne_b.get(l, ()) if q in existantes)
        if vers:
            cible, k = vers.most_common(1)[0]
            if k * 2 > len(lignes):
                out.append((page, cible))
    return out


def mcnemar(a, b):
    sa = sum(x and not y for x, y in zip(a, b)); sb = sum(y and not x for x, y in zip(a, b)); n = sa + sb
    return sa, sb, (min(1.0, 2 * sum(math.comb(n, k) for k in range(min(sa, sb) + 1)) / 2 ** n) if n else 1.0)


def main():
    existantes = {p.name for p in (BASE / "pages").glob("*.md")}
    noeud = {p.name: noeud_de(p) for p in (BASE / "pages").glob("*.md")}
    res, pg = {}, {}
    for cond, runs in CONDITIONS.items():
        res[cond] = []
        for run in runs:
            d = RUNS / run; mem = d / "memoire"; b = json.loads((d / "bilan.json").read_text())
            pg[run] = pages(mem)
            cites = set().union(*pg[run].values())
            cv, n = couverture(mem, cites)
            appels = [json.loads(l) for l in (d / "appels.jsonl").read_text().splitlines() if l.strip()]
            cons = [a for a in appels if a["role"] == "consolidation"]
            # rattachements à une page qui existait au départ (hors utilisateur et assistant), par question
            ratt = {(page, RAW_Q.match(f).group(1)) for page, lignes in pg[run].items() if page in existantes
                    and noeud.get(page) not in IMPLICITES for f, _ in lignes if RAW_Q.match(f)}
            vus = defaultdict(set)
            for l in (d / "liste.jsonl").read_text().splitlines():
                x = json.loads(l); vus[x["question"]] |= set(x["gardes"])
            dans = sum(noeud.get(page) in vus[q] for page, q in ratt)
            res[cond].append({"run": run, "justes": [r["juste"] for r in b["detail"]], "faits": b["faits"],
                              "rejets": b["rejets"], "perdus": b["perdus"], "couverts": cv, "messages": n,
                              "pages_nouvelles": len(set(pg[run]) - existantes),
                              "rattachements": len(ratt), "rattachements_dans_la_liste": dans,
                              "entree": sum(a["entree"] for a in cons), "entree_cache": sum(a["entree_cache"] for a in cons),
                              "usd_consolidation": round(sum(a["usd"] for a in cons), 4),
                              "usd_run": round(sum(a["usd"] for a in appels), 4)})
            r = res[cond][-1]
            print(f"{run} : {sum(r['justes'])}/{len(r['justes'])} justes, couverture {cv}/{n}, {r['faits']} faits, "
                  f"{r['pages_nouvelles']} pages nouvelles, rattachements {dans}/{len(ratt)} dans la liste, "
                  f"entrée {r['entree']}, {r['usd_run']} $")
    c1, c2 = CONDITIONS["complet"]; k1, k2 = CONDITIONS["cible"]
    db = {"bruit": doublons(pg[c1], pg[c2], existantes) + doublons(pg[c2], pg[c1], existantes),
          "cible": doublons(pg[k1], pg[c1], existantes) + doublons(pg[k2], pg[c2], existantes)}
    moy = lambda cond, f: sum(f(r) for r in res[cond]) / 2
    q = {c: round(100 * moy(c, lambda r: sum(r["justes"]) / len(r["justes"])), 1) for c in res}
    cv = {c: round(100 * moy(c, lambda r: r["couverts"] / max(1, r["messages"])), 1) for c in res}
    a = [x for r in res["cible"] for x in r["justes"]]; b = [x for r in res["complet"] for x in r["justes"]]
    rappel = sum(r["rattachements_dans_la_liste"] for r in res["complet"]) / max(1, sum(r["rattachements"] for r in res["complet"]))
    hors = sum(r["rattachements"] - r["rattachements_dans_la_liste"] for r in res["cible"])
    v = {"questions_pct": q, "couverture_pct": cv,
         "doublons_probables": {k: len(x) for k, x in db.items()},
         "lots_perdus_cible": sum(r["perdus"] for r in res["cible"]),
         "mcnemar_cible_contre_complet": dict(zip(("seul_cible", "seul_complet", "p"), mcnemar(a, b))),
         "rappel_de_la_recherche_pct": round(100 * rappel, 1),
         "cible_rattachements_hors_liste": hors,
         "entree_reelle_moy": {c: round(moy(c, lambda r: r["entree"])) for c in res},
         "usd_consolidation_moy": {c: round(moy(c, lambda r: r["usd_consolidation"]), 3) for c in res},
         "usd_total": round(sum(r["usd_run"] for c in res for r in res[c]), 3)}
    v.update({"C1": q["cible"] >= q["complet"] - 5, "C2": cv["cible"] >= cv["complet"] - 5,
              "C3": v["lots_perdus_cible"] == 0, "C4": len(db["cible"]) <= len(db["bruit"]) + 2})
    (RUNS / f"{PREFIXE}-bilan.json").write_text(json.dumps({"verdict": v, "detail": res}, ensure_ascii=False, indent=1))
    (RUNS / f"{PREFIXE}-doublons-prive.json").write_text(json.dumps(db, ensure_ascii=False, indent=1))
    print(json.dumps(v, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
