#!/usr/bin/env python3
"""Lecture de la grille « correcteur » (ou de sa confirmation) : preuve touchée au budget 450 par variante, banc et
condition ; moyenne pondérée par le nombre de questions ; corrections faites par question (propre et abîmée).
    python3 lire_grille_correcteur.py reglage        (grille)      python3 lire_grille_correcteur.py test   (confirmation)"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ICI = Path(__file__).resolve().parent
JEU = sys.argv[1] if len(sys.argv) > 1 else "reglage"
P = {}
for l in (ICI / "rapports" / "preuves.jsonl").read_text(encoding="utf-8").splitlines():
    for k, v in json.loads(l).items():
        P[k] = v
PREF = sys.argv[2] if len(sys.argv) > 2 else "C"
pat = re.compile(rf"^(?P<v>{PREF}[^_]+)_(?P<b>lme|locomo)_F_{JEU}_40__(?P<c>.+)\.jsonl$")
T, N, COR = defaultdict(dict), {}, defaultdict(dict)
for k, v in P.items():
    m = pat.match(k)
    if not m:
        continue
    T[m["v"]][(m["b"], m["c"])] = v["450"]["touchees_pct"]
    N[(m["b"], m["c"])] = v["450"]["n"]
    f = ICI / "runs" / "candidats" / k
    if f.exists():
        ls = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
        COR[m["v"]][(m["b"], m["c"])] = sum(x["capteurs"]["activite"].get("corrections", 0) for x in ls) / max(1, len(ls))
conds = sorted({c for d in T.values() for c in d}, key=lambda x: (x[0], ["propre", "typo:0.1", "typo:0.25", "typo:0.5", "trou:0.2", "trou:0.4"].index(x[1])))
print("| variante | " + " | ".join(f"{b} {c}" for b, c in conds) + " | pondéré propre | pondéré abîmé |")
print("|---" * (len(conds) + 3) + "|")
for v in sorted(T, key=lambda x: (x != PREF + "base", x)):
    d = T[v]
    pp = [(d[c], N[c]) for c in conds if c in d and c[1] == "propre"]
    pa = [(d[c], N[c]) for c in conds if c in d and c[1] != "propre"]
    moy = lambda xs: sum(a * n for a, n in xs) / max(1, sum(n for _, n in xs))
    print(f"| {v} | " + " | ".join(f"{d.get(c, float('nan')):.1f}" for c in conds) + f" | {moy(pp):.1f} | {moy(pa):.1f} |")
print("\ncorrections par question (propre → abîmé) :")
for v in sorted(COR):
    print(f"  {v}: " + " · ".join(f"{b} {c} {x:.2f}" for (b, c), x in sorted(COR[v].items())))
