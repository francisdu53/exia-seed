import json, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, "/opt/data/workspace/banc-souvenirs/plugins")
from exia_seed.rappel import Rappeleur
B = Path("/opt/data/workspace/banc-souvenirs")
L = [json.loads(l) for l in (B / "juge.jsonl").read_text(encoding="utf-8").splitlines()]
rap = {}; stats = {"utile": Counter(), "rien": Counter()}; pages = {"utile": Counter(), "rien": Counter()}
sans_resume = Counter()
for l in L:
    montre = [x for x in l["V1"] if x["score"] >= 0.5]
    if not montre:
        continue
    h = l["instantane"]
    if h not in rap:
        rap[h] = Rappeleur(B / "instantanes" / h, implicites=("francis", "nexa"))
    r = rap[h]; m = r.memoire(); a = r.activer(m, l["message"])
    origine = {}
    for etage, xs in a["etages"].items():
        for x in xs:
            n = x.split("→")[-1]
            origine.setdefault(n, etage)
    top = max(montre, key=lambda x: x["score"])["page"]
    noeud = next((n for n, f in m.fichiers.items() if f == top), "?")
    voie = origine.get(noeud, "propagation (lié à un autre sujet)")
    u = set(l["utiles"]); k = "utile" if set(x["fait"] for x in montre) & u else "rien"
    stats[k][voie] += 1; pages[k][noeud] += 1
for k in ("utile", "rien"):
    print(f"── rappels {k.upper()} ({sum(stats[k].values())}) — par où le premier sujet est arrivé :")
    for v, c in stats[k].most_common(): print(f"    {c:3}  {v}")
    print("   sujets les plus fréquents :", ", ".join(f"{n} ({c})" for n, c in pages[k].most_common(6)))
