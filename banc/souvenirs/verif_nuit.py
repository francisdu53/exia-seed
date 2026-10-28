"""Après la consolidation de nuit (docs/12 §14) — lecture seule. `photo` : référence des mots et fiches ; sans argument : bilan."""
import json, sys
from pathlib import Path
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, "/opt/data/plugins")
from exia_seed import pages as P
M = Path("/opt/data/memoire"); REF = Path("/opt/data/workspace/banc-fiches/photo-mots-20261016.json")
etat = {p.entete.get("node"): {"mots": p.entete.get("keywords"), "fiche": p.entete.get("summary"), "date": str(p.entete.get("summary_date")),
                               "maj": str(p.entete.get("updated"))} for p in P.lister(M / "pages")}
if sys.argv[1:] == ["photo"]:
    REF.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8"); print(f"photo : {len(etat)} pages"); sys.exit(0)
ref = json.loads(REF.read_text(encoding="utf-8"))
cons = [json.loads(l) for l in (M / "telemetrie" / "consolidations.jsonl").read_text(encoding="utf-8").splitlines()]
apres = [c for c in cons if c["ts"] > "2026-10-16T15"]
print(f"consolidations depuis le déploiement : {len(apres)}")
for c in apres:
    print(f"  {c['ts']} {c['statut']} · faits {c.get('faits_retenus')} · nœuds créés {c.get('noeuds_crees')} · fiches {c.get('fiches')}")
nouvelles = [n for n in etat if n not in ref]
sans = [n for n, v in etat.items() if not v["fiche"]]
bouge = {n: (ref[n]["mots"], v["mots"]) for n, v in etat.items() if n in ref and ref[n]["mots"] != v["mots"]}
fiche_change = [n for n, v in etat.items() if n in ref and ref[n]["fiche"] != v["fiche"]]
print(f"pages {len(etat)} (nouvelles : {nouvelles}) · sans fiche : {sans}")
print(f"fiches réécrites : {len(fiche_change)} {fiche_change}")
print(f"mots distinctifs qui ont BOUGÉ : {bouge or 'aucun'}")
