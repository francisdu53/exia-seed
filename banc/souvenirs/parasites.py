import json, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, "/opt/data/workspace/banc-fiches/plugins")
from exia_seed.rappel import Rappeleur
B = Path("/opt/data/workspace/banc-souvenirs")
CIBLES = {"plateforme_donnees_meteo", "jev", "delegation_assistant", "controle_documents_assistant"}
L = [json.loads(s) for s in (B / "juge_fiches.jsonl").read_text(encoding="utf-8").splitlines()]
rap = {}; chemins = defaultdict(Counter); faits = defaultdict(Counter)
for l in L:
    pages = {x["page"] for x in l["V1"] if x["score"] >= 0.5}
    h = l["instantane"]
    if h not in rap: rap[h] = Rappeleur(B / "instantanes" / h, implicites=("francis", "nexa"))
    r = rap[h]; m = r.memoire()
    cib = [n for n in CIBLES if m.fichiers.get(n) in pages]
    if not cib: continue
    a = r.activer(m, l["message"])
    for n in cib:
        entres = [f"{et}:{e.split('→')[0]}" for et, v in a["etages"].items() for e in v if e.endswith("→" + n)]
        if not entres: entres = ["propagation" if n in a["actives"] else "?"]
        for e in entres: chemins[n][e] += 1
        for x in l["V1"]:
            if x["score"] >= 0.5 and x["page"] == m.fichiers.get(n): faits[n][x["fait"][:90]] += 1
for n in CIBLES:
    print(f"── {n} : chemins {chemins[n].most_common(8)}")
    for f, c in faits[n].most_common(3): print(f"     {c}× {f}")
