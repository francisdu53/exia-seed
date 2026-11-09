#!/usr/bin/env python3
"""docs/18 §10 — les dates d'événement calculées par le CODE (`temps.proposer`), comparées à celles des modèles, sur les
mêmes faits du banc 17 (premier panel). Sans modèle.   python3 dates_code_modeles.py"""
import json, re, sys, collections
from pathlib import Path
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, "/plugins")
from exia_seed import temps as T
from exia_seed import langues
B = Path("/banc"); JOURS = json.loads((B / "jours.json").read_text()); FR = langues.masque("fr")
FAIT = re.compile(r"^- (.*?) <!-- (.*?) -->\s*$")
RUNS = {"Astra": "gpt-6-astra/r1", "Terra (consigne adaptée)": "gpt-6.1-terra/t1", "Luna (consigne Terra, 40 000)": "gpt-6-luna/l1",
        "Luna (consigne Terra, 10 000)": "gpt-6-luna/k10000r1"}
for extra in ("m2a1", "m2b1"):
    if (B / "runs" / "gpt-6-luna" / extra).exists():
        RUNS[f"Luna (marche 2 {extra[2]})"] = f"gpt-6-luna/{extra}"
for nom, run in RUNS.items():
    c = collections.Counter()
    for j in JOURS:
        mem = B / "runs" / run / j / "memoire"
        dep = B / ("depart-10000" if "10000" in run or "m2" in run else "depart") / j / "memoire"
        avant = {m.group(1) for p in (dep / "pages").glob("*.md") for l in p.read_text(encoding="utf-8").splitlines() for m in [FAIT.match(l)] if m}
        brut = {f.name: f.read_text(encoding="utf-8").splitlines() for f in (mem / "raw").glob("*.md")}
        for p in (mem / "pages").glob("*.md"):
            for l in p.read_text(encoding="utf-8").splitlines():
                m = FAIT.match(l)
                if not m or m.group(1) in avant:
                    continue
                meta = dict(t.split(":", 1) for t in m.group(2).split() if ":" in t)
                lignes = []
                for ref in meta.get("src", "").split(","):
                    r = re.match(r"raw/([^:]+):(\d+)(?:-(\d+))?", ref)
                    if r and r.group(1) in brut:
                        lignes += [brut[r.group(1)][k - 1] for k in range(int(r.group(2)), int(r.group(3) or r.group(2)) + 1) if k <= len(brut[r.group(1)])]
                ancre = T._lire(meta.get("dit_le", "").replace("_", "T"))[0]
                code, regle = T.proposer("\n".join(lignes), ancre, FR)
                mod = meta.get("event_time")
                c["faits"] += 1
                if mod:
                    c["modele_date"] += 1
                    if code is None: c["modele_seul"] += 1
                    elif code[:10] == mod[:10]: c["accord"] += 1
                    else:
                        c["desaccord"] += 1; c[f"desaccord_{regle}"] += 1
                        print("   DÉSACCORD", nom[:12], "| modèle", mod, "| code", code, "| dit le", meta.get("dit_le"), "|", " ".join(T.sans_horodatage(x) for x in lignes)[:160])
                elif code:
                    c["code_seul"] += 1; c[f"code_seul_{regle}"] += 1
    print(nom, dict(c))
