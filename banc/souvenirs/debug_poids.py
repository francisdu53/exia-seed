import json, sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, "/opt/data/workspace/banc-fiches/plugins")
from exia_seed import rappel as R
B = Path("/opt/data/workspace/banc-souvenirs")
l = next(json.loads(s) for s in (B / "juge_fiches.jsonl").read_text(encoding="utf-8").splitlines() if json.loads(s)["instant"] == "2026-10-15T16:50")
for racine in ("instantanes", "instantanes_mots"):
    r = R.Rappeleur(B / racine / l["instantane"], implicites=("francis", "nexa")); m = r.memoire()
    print("==", racine, "courants:", len(m.mots_courants), "· courses courant ?", ("courses", "application_liste_courses") in m.mots_courants,
          "· keywords page:", next((n.get("mots") for n in __import__("exia_seed.graphe", fromlist=["x"])._lire(m.racine)[0] if n["noeud"] == "application_liste_courses"), "?"))
    for w in (1.0, 0.75, 0.5):
        R.POIDS_MOT_COMMUN = w
        a = r.activer(m, l["message"])
        v = r.rappeler(l["message"], datetime.fromisoformat(l["instant"]))
        top = sorted({(x["page"], round(x["score"], 3)) for x in v.get("faits", [])}, key=lambda t: -t[1])[:4]
        print(f"   poids {w}: entrée courses {a['entrees'].get('application_liste_courses', 0):.3f} · actives courses {a['actives'].get('application_liste_courses', 0):.3f} · top {top}")
    print("   étages:", {k: v[:6] for k, v in a["etages"].items()})
