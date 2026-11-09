#!/usr/bin/env python3
"""docs/18 §8 — ce que l'oubli ferait sur LongMemEval (pire cas : rien n'y est jamais rappelé entre deux questions).
Pour chaque question, sa mémoire (run confirm-lme, échelle S) et le plan d'oubli au jour de la question, sans usage."""
import collections, json, sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, "/plugins")
from exia_seed import oubli as O
from exia_seed import pages as P
B = Path("/banc"); D = json.loads((B / "donnees" / "lme_oracle_locomo.json").read_text())
tot = oub = 0; vides = 0; par_type = collections.defaultdict(lambda: [0, 0]); ecarts = []; par_section = collections.Counter()
for c in D:
    q = c["qa"][0]; mem = B / "runs" / "confirm-lme" / "memoires" / c["sample_id"]
    if not (mem / "pages").exists():
        continue
    jour = datetime.fromisoformat(q["instant"]).date()
    r = O.plan(P.lister(mem / "pages"), jour, {}, implicites=("user", "assistant"))
    n, o = r["faits"], len(r["oublies"]); tot += n; oub += o
    par_section.update(x["section"] for x in r["oublies"])
    t = par_type[q["type"]]; t[0] += 1; t[1] += (n > 0 and o == n)
    vides += (n > 0 and o == n)
print(json.dumps({"questions": len(D), "faits": tot, "faits_oublies_au_jour_de_la_question": oub,
                  "pct": round(100 * oub / max(1, tot), 1), "oublies_par_section": dict(par_section),
                  "questions_dont_TOUTE_la_memoire_est_oubliee": vides,
                  "par_type": {k: {"questions": v[0], "memoire_entierement_oubliee": v[1]} for k, v in par_type.items()}},
                 ensure_ascii=False, indent=1))
