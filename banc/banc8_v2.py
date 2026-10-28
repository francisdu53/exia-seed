#!/usr/bin/env python3
"""Banc 8, passage v2 (conteneur, GPT-6) — memoire_chercher v2 (plein texte → FCM → pistes), docs/08 D7-D8.

Réutilise requetes.jsonl, embeddings.jsonl et resultats8.jsonl (mêmes requêtes, mêmes jugements) ; ne fait
juger que les faits NOUVEAUX proposés par la v2. Tous les moteurs sont ensuite mesurés contre le même
ensemble d'utiles (agrandi), séparément sur le RÉGLAGE (23-25/09) et la VÉRIFICATION (26/09).

    python3 banc8_v2.py /opt/data/workspace/banc-6b /opt/data/workspace/banc-8 [plugins]
"""
import json
import sys
from datetime import datetime
from pathlib import Path

SOURCE, SORTIE = Path(sys.argv[1]), Path(sys.argv[2])
sys.argv = sys.argv[:4]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import banc8_juge as J                                                     # noqa: E402  (juge, cache, prompt identiques)
from exia_seed.requete import Lecteur                                      # noqa: E402
from exia_seed.util import estimer_tokens                                  # noqa: E402

VERIF = "2026-09-26"


def main() -> int:
    rejeu = {json.loads(l)["n"]: json.loads(l) for l in (SOURCE / "rejeu.jsonl").read_text(encoding="utf-8").splitlines()}
    requetes = {json.loads(l)["n"]: json.loads(l) for l in (SORTIE / "requetes.jsonl").read_text(encoding="utf-8").splitlines()}
    res = [json.loads(l) for l in (SORTIE / "resultats8.jsonl").read_text(encoding="utf-8").splitlines()]
    lecteurs = {}
    for x in res:
        r = requetes[x["n"]]
        s = r["instantane"]
        if s not in lecteurs:
            lecteurs[s] = Lecteur(SOURCE / "instantanes" / s, implicites=("francis", "nexa"))
        c = lecteurs[s].chercher(x["requete"], 2, datetime.fromisoformat(r["instant"]))
        v2 = [f["fait"] for y in c.get("resultats", []) for f in y["faits"]]
        v2 += [p["fait"] for p in (c.get("pistes") or {}).get("faits", []) if p["fait"] not in v2]
        x["FCM v2"] = v2[:9]
        anciens = set(x["FCM"]) | set(x["FCM+pistes"]) | set(x["Embeddings"]) | set(x["Plein texte"])
        nouveaux = [f for f in x["FCM v2"] if f not in anciens]
        if nouveaux:
            l = rejeu[x["n"]]
            x["utiles"] = sorted(set(x["utiles"]) | J.juger(10_000 + x["n"], l["message"], l["reponse"], nouveaux))
        x["verification"] = r["instant"] >= VERIF
        print(f"  {x['n']:3} {'VÉRIF' if x['verification'] else 'régl.'} « {x['requete'][:36]:36} » v2 {len(x['FCM v2'])} faits, {len(nouveaux)} nouveaux", flush=True)
    (SORTIE / "resultats8_v2.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in res), encoding="utf-8")

    noms = ["FCM v2", "Embeddings", "Plein texte", "FCM+pistes", "FCM"]
    bilan = {}
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
    (SORTIE / "bilan8_v2.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(bilan, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
