#!/usr/bin/env python3
"""Carte de vie de la mémoire (docs/18 §2) — l'usage réel de chaque page, et le poids mort. LECTURE SEULE.

Pour chaque page : son âge, sa dernière écriture, et son usage, à quatre niveaux, lus dans les journaux existants :
- TOUCHÉE   : la recherche l'a allumée pour un message (journal du rappel, `entrees`) — signal faible ;
- MONTRÉE   : le rappel automatique l'a donnée à l'agent avec un message (`injecte.sujets`) ;
- TROUVÉE   : l'agent l'a obtenue en cherchant (`memoire_chercher`, journal des requêtes) ;
- LUE       : l'agent l'a ouverte (`memoire_lire`).
Une page UTILISÉE a été montrée, trouvée ou lue au moins une fois. Le POIDS MORT : les pages jamais utilisées, et
celles qui ne l'ont plus été depuis longtemps. Les conditions de non-oubli (docs/18 §3) sont signalées par page.

    python3 /opt/data/plugins/exia_seed/outils/carte_de_vie.py [mémoire] [--json] [--ecrire]
    (--ecrire : dépose telemetrie/carte_de_vie.json ; sans lui, rien n'est écrit)
"""
import collections
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
M = Path(ARGS[0] if ARGS else "/opt/data/memoire")
FAIT = re.compile(r"^- (.*?) <!-- (.*?) -->\s*$")


def _jour(ts):
    try:
        return datetime.fromisoformat(str(ts)[:19]).date()
    except Exception:
        return None


def pages(mem: Path):
    out = {}
    for p in sorted((mem / "pages").glob("*.md")):
        t = p.read_text(encoding="utf-8")
        tete = t.split("\n---", 1)[0]
        def champ(nom):
            m = re.search(rf"^{nom}: (.+)$", tete, re.M)
            return m.group(1).strip().strip("'\"") if m else ""
        n = champ("node") or p.stem
        metas = [m.group(2) for l in t.splitlines() for m in [FAIT.match(l)] if m]
        out[n] = {"page": p.name, "type": champ("node_type"), "cree": champ("created"), "ecrit": champ("updated"),
                  "faits": len(metas),
                  "echeances": sum("echeance:" in x for x in metas), "dates": sum("event_time:" in x for x in metas),
                  "proteges": sum("protected:true" in x for x in metas),
                  "prives": sum("privacy:" in x for x in metas)}
    return out


def usage(mem: Path, connus):
    u = collections.defaultdict(lambda: {"touchee": 0, "montree": 0, "trouvee": 0, "lue": 0, "derniere": None})
    def note(n, cle, j):
        if n in connus:
            x = u[n]; x[cle] += 1
            if cle != "touchee" and j and (x["derniere"] is None or j > x["derniere"]):
                x["derniere"] = j
    jours = set()
    for f in sorted((mem / "rappel").glob("*.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            try:
                x = json.loads(l)
            except Exception:
                continue
            j = _jour(x.get("ts")); jours.add(j)
            for n in (x.get("entrees") or {}):
                note(n, "touchee", j)
            for n in ((x.get("injecte") or {}).get("sujets") or []):
                note(n, "montree", j)
    for f in sorted((mem / "requetes").glob("*.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            try:
                x = json.loads(l)
            except Exception:
                continue
            j = _jour(x.get("ts")); jours.add(j)
            cle = {"memoire_chercher": "trouvee", "memoire_lire": "lue"}.get(x.get("outil"))
            for n in (x.get("sujets") or []) if cle else []:
                note(n, cle, j)
    jours.discard(None)
    return u, (min(jours) if jours else None), (max(jours) if jours else None)


def main():
    pg = pages(M)
    u, debut, fin = usage(M, set(pg))
    aujourdhui = fin or date.today()
    lignes = []
    for n, x in pg.items():
        y = u.get(n, {"touchee": 0, "montree": 0, "trouvee": 0, "lue": 0, "derniere": None})
        cree = _jour(x["cree"]) if x["cree"] else None
        utilisee = y["montree"] + y["trouvee"] + y["lue"]
        lignes.append({"noeud": n, **x, **{k: y[k] for k in ("touchee", "montree", "trouvee", "lue")},
                       "derniere_utilisation": y["derniere"].isoformat() if y["derniere"] else None,
                       "age_j": (aujourdhui - cree).days if cree else None,
                       "inutilise_depuis_j": (aujourdhui - (y["derniere"] or cree)).days if (y["derniere"] or cree) else None,
                       "jamais_utilisee": utilisee == 0,
                       "condition_non_oubli": bool(x["echeances"] or x["proteges"])})
    n = len(lignes)
    jamais = [l for l in lignes if l["jamais_utilisee"]]
    jamais_touchee = [l for l in jamais if l["touchee"] == 0]
    vieilles = [l for l in lignes if (l["age_j"] or 0) >= 30]
    resume = {"memoire": str(M), "periode_journaux": [str(debut), str(fin)], "pages": n,
              "jamais_utilisees": len(jamais), "jamais_utilisees_pct": round(100 * len(jamais) / max(1, n), 1),
              "jamais_meme_touchees": len(jamais_touchee),
              "pages_de_30_jours_ou_plus": len(vieilles),
              "dont_jamais_utilisees": sum(l["jamais_utilisee"] for l in vieilles),
              "inutilisees_depuis_30_jours": sum((l["inutilise_depuis_j"] or 0) >= 30 for l in lignes),
              "avec_condition_de_non_oubli": sum(l["condition_non_oubli"] for l in lignes),
              "poids_mort_faits": sum(l["faits"] for l in jamais), "faits_total": sum(l["faits"] for l in lignes),
              "par_type": dict(collections.Counter(l["type"] for l in lignes)),
              "par_type_jamais_utilisees": dict(collections.Counter(l["type"] for l in jamais))}
    if "--json" in sys.argv:
        print(json.dumps({"resume": resume, "pages": lignes}, ensure_ascii=False, indent=1))
    else:
        print(json.dumps(resume, ensure_ascii=False, indent=1))
        print("\nles 15 pages les plus utilisées :")
        for l in sorted(lignes, key=lambda l: -(l["montree"] + l["trouvee"] + l["lue"]))[:15]:
            print(f"  {l['noeud']:40} montrée {l['montree']:>3} · trouvée {l['trouvee']:>3} · lue {l['lue']:>2}")
    if "--ecrire" in sys.argv:
        (M / "telemetrie").mkdir(parents=True, exist_ok=True)
        (M / "telemetrie" / "carte_de_vie.json").write_text(json.dumps({"resume": resume, "pages": lignes},
                                                                        ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
