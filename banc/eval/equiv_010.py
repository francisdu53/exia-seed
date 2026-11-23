#!/usr/bin/env python3
"""Équivalence 0.10.0 : le moteur « deux mémoires » du PLUGIN (paquets/seed-0.10.0) rend-il les mêmes candidats que le
prototype du banc (NA1 + accents + correcteur, `Cd5_*_F_test_40__propre.jsonl`) ? Même format de sortie que fournir_n,
pour que preuves.py mesure la même chose. Conteneur Nexa :
  docker exec -u 10000 -w /opt/data/workspace/banc-cartes/eval nexa /opt/hermes/.venv/bin/python3 equiv_010.py lme"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ICI = Path(__file__).resolve().parent
BANC = sys.argv[1]
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, str(ICI / "paquets" / "seed-0.10.0")); sys.path.insert(0, str(ICI.parent / "harnais"))
os.environ["LOCOMO_DONNEES"] = str(ICI.parent / "bancs" / "donnees" / ("lme_oracle_locomo.json" if BANC == "lme" else "locomo10.json"))
import commun as KH                                                       # noqa: E402
from exia_seed import rappel as R                                         # noqa: E402
from exia_seed import deux_memoires as DM                                 # noqa: E402

TRES_TARD = datetime(2100, 1, 1)
IMPLICITES = ("user", "assistant") if BANC == "lme" else ()
ids = set(json.loads((ICI / "scelle.json").read_text())[BANC]["test"])
qs = sorted((q for q in KH.questions(json.loads(Path(KH.DONNEES).read_text(encoding="utf-8"))) if q["id"] in ids), key=lambda q: (q["conv"], q["id"]))
d = ICI / "memoires" / BANC / "_fusion"
rp = R.Rappeleur(d, implicites=IMPLICITES)
toile = DM.Toile(rp, DM.POIDS["souvenirs"], {"correcteur": True, "corr_min": 5})
brute = DM.ToileBrute(d, DM.POIDS["brut"], {"correcteur": True, "corr_min": 5})
masque = rp.memoire().masque
sortie = []
for q in qs:
    ch, actif = DM._Chrono(), {}
    from collections import defaultdict
    actif = defaultdict(int)
    ir = datetime.fromisoformat(q["instant"])
    a = toile.rappeler(q["question"], ir, 40, ch, actif, filtre=TRES_TARD)
    b = brute.rappeler(q["question"], TRES_TARD, ir, masque, 40, ch, actif)
    tous = sorted([{**x, "note": round(x["note"], 3)} for x in a + b], key=lambda x: -x["note"])[:80]
    sortie.append({"id": q["id"], "categorie": q.get("categorie"), "type": q.get("type"),
                   "items": [{k: v for k, v in x.items() if k != "cle"} for x in tous],
                   "capteurs": {"chaud": {"ns": {"requete": int(sum(ch.ms.values()) * 1e6)}}, "activite": dict(actif)}})
f = ICI / "runs" / "candidats" / f"P010_{BANC}_F_test_40__propre.jsonl"
f.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in sortie), encoding="utf-8")
ref = {json.loads(l)["id"]: json.loads(l) for l in (ICI / "runs" / "candidats" / f"Cd5_{BANC}_F_test_40__propre.jsonl").read_text().splitlines()}
mem = lambda items, t: [x["texte"] for x in items if x["type"] == t]
same_f = sum(mem(x["items"], "fait") == mem(ref[x["id"]]["items"], "fait") for x in sortie)
same_t = sum(mem(x["items"], "tour") == mem(ref[x["id"]]["items"], "tour") for x in sortie)
same_fs = sum(set(mem(x["items"], "fait")) == set(mem(ref[x["id"]]["items"], "fait")) for x in sortie)
print(f"{BANC}: {len(sortie)} q · souvenirs identiques (ordre) {same_f} · (ensemble) {same_fs} · tours identiques (ordre) {same_t} → {f.name}")
