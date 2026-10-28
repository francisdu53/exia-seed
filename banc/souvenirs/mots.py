import json, sys, math
from collections import Counter
from pathlib import Path
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, "/opt/data/workspace/banc-souvenirs/plugins")
from exia_seed.rappel import Rappeleur
B = Path("/opt/data/workspace/banc-souvenirs")
L = [json.loads(l) for l in (B / "juge.jsonl").read_text(encoding="utf-8").splitlines() if json.loads(l)["tranche"] == "reglage"]
rap = {}; mots = {"utile": Counter(), "rien": Counter()}; idf = {}
for l in L:
    montre = [x for x in l["V1"] if x["score"] >= 0.5]
    if not montre: continue
    h = l["instantane"]
    if h not in rap: rap[h] = Rappeleur(B / "instantanes" / h, implicites=("francis", "nexa"))
    r = rap[h]; m = r.memoire(); a = r.activer(m, l["message"])
    k = "utile" if set(x["fait"] for x in montre) & set(l["utiles"]) else "rien"
    for x in a["etages"].get("mot_alias", []):
        w = x.split("→")[0]; mots[k][w] += 1
        n_alias = len(m.mots_alias.get(w, ())); df = sum(1 for f in m.faits if (" " + w[:5]) in f["norm"])
        idf[w] = (n_alias, df, len(m.faits))
for k in ("rien", "utile"):
    print(f"── mots d'alias déclencheurs, rappels {k.upper()} (réglage) :")
    print("   " + " · ".join(f"{w}({c}, faits {idf[w][1]}/{idf[w][2]})" for w, c in mots[k].most_common(18)))
