import json, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, "/opt/data/workspace/banc-souvenirs/plugins")
from exia_seed.rappel import Rappeleur
B = Path("/opt/data/workspace/banc-souvenirs")
lignes = [json.loads(l) for l in (B / "juge.jsonl").read_text(encoding="utf-8").splitlines()]
rap = {}
for l in lignes:
    h = l["instantane"]
    if h not in rap:
        rap[h] = Rappeleur(B / "instantanes" / h, implicites=("francis", "nexa"))
    r = rap[h]; m = r.memoire()
    a = r.activer(m, l["message"])
    nommes = set()
    for etage in ("alias", "mot_alias"):
        for x in a["etages"].get(etage, []):
            nommes.add(x.split("→")[-1])
    l["nommes"] = sorted(n for n in nommes if not n.startswith("concept:"))
    l["fichiers_nommes"] = sorted({m.fichiers.get(n) for n in l["nommes"] if m.fichiers.get(n)})
for tranche in ("reglage", "verification"):
    L = [l for l in lignes if l["tranche"] == tranche]
    for ms in (1, 2, 3):
        parle = utile = rien = 0
        for l in L:
            u = set(l["utiles"])
            groupes = defaultdict(list)
            for x in l["V1"]:
                if x["page"] in l["fichiers_nommes"]:
                    groupes[x["page"]].append(x)
            ordre = sorted(groupes, key=lambda p: -max(x["score"] for x in groupes[p]))[:ms]
            if not ordre:
                continue
            parle += 1
            pages_utiles = {x["page"] for x in l["V1"] + l["V2"] if x["fait"] in u}
            ok = any(p in pages_utiles for p in ordre)
            utile += ok; rien += (not ok)
        print(f"{tranche:12} sujets NOMMÉS (max {ms}) : parle {parle:3} · sujet utile {utile:3} · pour rien {rien:3} · ({100*utile/max(1,parle):.0f} % utiles)")
n = sum(1 for l in lignes if l["nommes"]); print(f"messages nommant au moins un sujet : {n}/{len(lignes)}")
for l in lignes:
    if l["instant"].startswith("2026-10-15T16:5") and "courses" in l["message"]:
        print("15/10 16:50 — sujets nommés :", l["nommes"])
