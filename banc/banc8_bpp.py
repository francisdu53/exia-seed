#!/usr/bin/env python3
"""Banc 8, passage B++ (conteneur, GPT-6) — B+ avec champ lexical vivant et budget égal (9 faits), docs/08 §9.

Chaque instantané est recopié avec thesaurus.json, son graphe recalculé (les concepts deviennent des
nœuds) ; memoire_chercher (v2 + B+) reçoit LES MÊMES requêtes ; seuls les faits nouveaux sont jugés.
Mesures sur le réglage (23-25/09) et la vérification (26/09).

    python3 banc8_bplus.py /opt/data/workspace/banc-6b /opt/data/workspace/banc-8 [plugins]
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

SOURCE, SORTIE = Path(sys.argv[1]), Path(sys.argv[2])
sys.argv = sys.argv[:4]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import banc8_juge as J                                                     # noqa: E402
from exia_seed import graphe as G                                          # noqa: E402
from exia_seed.requete import Lecteur                                      # noqa: E402
from exia_seed.util import estimer_tokens                                  # noqa: E402

VERIF = "2026-09-26"


def main() -> int:
    rejeu = {json.loads(l)["n"]: json.loads(l) for l in (SOURCE / "rejeu.jsonl").read_text(encoding="utf-8").splitlines()}
    requetes = {json.loads(l)["n"]: json.loads(l) for l in (SORTIE / "requetes.jsonl").read_text(encoding="utf-8").splitlines()}
    res = [json.loads(l) for l in (SORTIE / "resultats8_bplus.jsonl").read_text(encoding="utf-8").splitlines()]
    lecteurs, concepts = {}, {}
    for x in res:
        r = requetes[x["n"]]
        s = r["instantane"]
        if s not in lecteurs:
            d = SORTIE / "instantanes_bpp" / s
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(SOURCE / "instantanes" / s, d)
            shutil.rmtree(d / "requetes", ignore_errors=True)
            shutil.copy(SORTIE / "thesaurus.json", d / "thesaurus.json")
            rap = G.calculer(d, implicites=("francis", "nexa"))
            concepts[s] = (rap["noeuds"], rap["aretes"])
            lecteurs[s] = Lecteur(d, implicites=("francis", "nexa"))
        c = lecteurs[s].chercher(x["requete"], 9, datetime.fromisoformat(r["instant"]), faits_max=9)
        faits = [f["fait"] for y in c.get("resultats", []) for f in y["faits"]]
        faits += [p["fait"] for p in (c.get("pistes") or {}).get("faits", []) if p["fait"] not in faits]
        x["FCM B++"] = faits[:9]
        anciens = set().union(*(set(x[k]) for k in ("FCM", "FCM+pistes", "Embeddings", "Plein texte", "FCM v2", "FCM B+")))
        nouveaux = [f for f in x["FCM B++"] if f not in anciens]
        if nouveaux:
            l = rejeu[x["n"]]
            x["utiles"] = sorted(set(x["utiles"]) | J.juger(30_000 + x["n"], l["message"], l["reponse"], nouveaux))
        x["verification"] = r["instant"] >= VERIF
        print(f"  {x['n']:3} {'VÉRIF' if x['verification'] else 'régl.'} « {x['requete'][:36]:36} » B++ {len(x["FCM B++"])} faits, {len(nouveaux)} nouveaux", flush=True)
    (SORTIE / "resultats8_bpp.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in res), encoding="utf-8")
    noms = ["FCM B++", "FCM B+", "FCM v2", "Embeddings", "Plein texte"]
    bilan = {"graphes": {s: {"noeuds": n, "aretes": a} for s, (n, a) in concepts.items()}}
    for jeu, garde in (("reglage_23_25", lambda x: not x["verification"]), ("verification_26", lambda x: x["verification"]), ("tout", lambda x: True)):
        xs = [x for x in res if garde(x)]
        tot = sum(len(x["utiles"]) for x in xs)
        b = {"messages": len(xs), "utiles_dans_l_union": tot}
        for k in noms:
            trouves = sum(len(set(x[k]) & set(x["utiles"])) for x in xs)
            proposes = sum(len(x[k]) for x in xs)
            autres = [o for o in noms if not (o.startswith("FCM") and k.startswith("FCM")) and o != k]
            b[k] = {"utiles": trouves, "rappel": round(trouves / tot, 3) if tot else None,
                    "precision": round(trouves / proposes, 3) if proposes else None,
                    "parle_pour_rien": sum(1 for x in xs if x[k] and not set(x[k]) & set(x["utiles"])),
                    "seul_a_trouver": sum(len((set(x[k]) & set(x["utiles"])) - set().union(*(set(x[o]) for o in autres))) for x in xs),
                    "tokens": round(sum(estimer_tokens(" ".join(x[k])) for x in xs) / max(1, len(xs)))}
        bilan[jeu] = b
    bilan["cout_banc_tokens_total"] = sum(v.get("tokens", 0) for v in J.CACHE.values())
    (SORTIE / "bilan8_bpp.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in bilan.items() if k != "graphes"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
