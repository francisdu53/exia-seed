#!/usr/bin/env python3
"""Banc du temps (docs/18 §8) — l'oubli sous conditions, rejoué jour par jour sur l'histoire réelle. Sans modèle.

Pour chaque jour D de la période des journaux : les faits écrits au plus tard ce jour-là, l'usage des pages jusqu'à D,
et le plan d'oubli (`oubli.plan`). Un fait est oublié au premier jour où le plan le désigne. On regarde ensuite si ce
qu'on a oublié a été REDEMANDÉ après la date d'oubli :
- regret « page » : la page du fait a été montrée, trouvée ou lue plus tard ;
- regret « fait » : le fait lui-même figurait plus tard parmi les candidats du rappel (journal du rappel, `faits`).
Mémoire montée en lecture seule.   python3 banc_du_temps.py /m [francis nexa]
"""
import collections, json, sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, "/plugins")
from exia_seed import oubli as O
from exia_seed import pages as P

M = Path(sys.argv[1]); IMP = tuple(sys.argv[2:]) or ("francis", "nexa")
pg = P.lister(M / "pages")
noeuds = {p.entete.get("node") for p in pg}
usage = collections.defaultdict(list)                  # nœud → dates d'usage (montrée, trouvée, lue)
candidats = []                                         # (date, page, début du fait) — candidats du rappel
def j(ts):
    try: return datetime.fromisoformat(str(ts)[:19]).date()
    except Exception: return None
for f in sorted((M / "rappel").glob("*.jsonl")):
    for l in f.read_text(encoding="utf-8").splitlines():
        x = json.loads(l); d = j(x.get("ts"))
        for n in ((x.get("injecte") or {}).get("sujets") or []): usage[n].append(d)
        for c in (x.get("faits") or []): candidats.append((d, c.get("page"), (c.get("fait") or "")[:60]))
for f in sorted((M / "requetes").glob("*.jsonl")):
    for l in f.read_text(encoding="utf-8").splitlines():
        x = json.loads(l); d = j(x.get("ts"))
        if x.get("outil") in ("memoire_chercher", "memoire_lire"):
            for n in (x.get("sujets") or []): usage[n].append(d)
jours = sorted({d for v in usage.values() for d in v if d} | {d for d, _, _ in candidats if d})
debut, fin = jours[0], jours[-1]

class Vue:                                              # la page telle qu'elle était au jour D (faits écrits ≤ D)
    def __init__(self, p, d):
        self.entete, self.chemin = p.entete, p.chemin
        self.sections = {k: [l for l in v if (O._jour(O.meta(l.split("<!--", 1)[-1]).get("dit_le")) or d) <= d]
                         for k, v in p.sections.items()}

oublie = {}                                             # (page, fait) → date d'oubli
epargnes_fin = {}
d = debut
while d <= fin:
    der = {n: max([x for x in v if x and x <= d], default=None) for n, v in usage.items()}
    r = O.plan([Vue(p, d) for p in pg], d, {n: x for n, x in der.items() if x}, implicites=IMP)
    for o in r["oublies"]:
        oublie.setdefault((o["page"], o["fait"]), (d, o["section"], o["noeud"]))
    epargnes_fin = r["epargnes_par_condition"]; total_fin = r["faits"]
    d += timedelta(days=1)

par_section = collections.Counter(s for _, s, _ in oublie.values())
regret_page = regret_fait = 0; exemples = []
for (page, fait), (dj, s, n) in oublie.items():
    rp = any(x and x > dj for x in usage.get(n, []))
    rf = any(dd and dd > dj and pp == page and fait.startswith(debut_fait[:50]) for dd, pp, debut_fait in candidats if debut_fait)
    regret_page += rp; regret_fait += rf
    if rf: exemples.append((dj.isoformat(), page))
pages_videes = sum(1 for p in pg if O.faits_de(p) and all((p.chemin.name, f["fait"]) in oublie for f in O.faits_de(p)))
print(json.dumps({"periode": [debut.isoformat(), fin.isoformat()], "faits_a_la_fin": total_fin, "pages": len(pg),
                  "faits_oublies": len(oublie), "oublies_par_section": dict(par_section), "pages_videes": pages_videes,
                  "regret_page": regret_page, "regret_page_pct": round(100 * regret_page / max(1, len(oublie)), 1),
                  "regret_fait": regret_fait, "regret_fait_pct": round(100 * regret_fait / max(1, len(oublie)), 1),
                  "epargnes_par_condition_au_dernier_jour": epargnes_fin,
                  "exemples_regret_fait": exemples[:10]}, ensure_ascii=False, indent=1))
