#!/usr/bin/env python3
"""LongMemEval — le bilan (docs/13) : exactitude par moteur, échelle, type ; abstention à part ; tests appariés ;
hypothèses fixées avant la mesure ; latences ; dépense. Aucun appel au modèle.

    python3 bilan_lme.py
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict

sys.path.insert(0, "/locomo")
import commun as K                                                # noqa: E402
import modele                                                     # noqa: E402

ASSISTANT = "single-session-assistant"     # perdu par construction (règle 4), rapporté à part — docs/13 §3


def mcnemar(a, b, ids):
    sa = sum(a[i] and not b[i] for i in ids); sb = sum(b[i] and not a[i] for i in ids); n = sa + sb
    p = min(1.0, 2 * sum(math.comb(n, k) for k in range(min(sa, sb) + 1)) / 2 ** n) if n else 1.0
    return {"seul_1": sa, "seul_2": sb, "p": round(p, 4)}


def main() -> int:
    qs = {q["id"]: q for q in K.questions(K.charger_donnees(K.selection_du_run()))}
    lab = {f.stem: {x["id"]: x["label"] == "CORRECT" for x in K.lire_jsonl(f)} for f in sorted((K.RUN / "jugements").glob("*.jsonl"))}
    groupes = defaultdict(list)
    for i, q in qs.items():
        groupes["tout"].append(i)
        groupes["abstention" if q.get("abstention") else q["type"]].append(i)
        if q["type"] != ASSISTANT:
            groupes["tout sauf assistant"].append(i)
    table = {k: {g: {"justes": sum(l[i] for i in ids if i in l), "n": sum(i in l for i in ids),
                     "pct": round(100 * sum(l[i] for i in ids if i in l) / max(1, sum(i in l for i in ids)), 1)}
                 for g, ids in groupes.items()} for k, l in lab.items()}
    pct = lambda k, g="tout": (table.get(k, {}).get(g) or {}).get("pct")
    paires = {}
    for x, y in (("A_S", "B_S"), ("A_F", "B_F"), ("A_F", "C_F"), ("A_S", "A_F"), ("B_S", "B_F")):
        if x in lab and y in lab:
            ids = [i for i in qs if i in lab[x] and i in lab[y]]
            paires[f"{x} contre {y}"] = mcnemar(lab[x], lab[y], ids)
    lat = {}
    for f in sorted((K.RUN / "contextes").glob("*.jsonl")):
        v = sorted(x["latence_ms"] for x in K.lire_jsonl(f))
        if v:
            lat[f.stem] = {"p50_ms": v[len(v) // 2], "p95_ms": v[int(0.95 * len(v)) - 1]}
    h = {}
    if None not in (pct("A_F"), pct("B_F")):
        h["H1 A_F ≥ B_F − 2"] = {"A_F": pct("A_F"), "B_F": pct("B_F"), "tient": pct("A_F") >= pct("B_F") - 2}
    if None not in (pct("A_S"), pct("A_F"), pct("B_S"), pct("B_F")):
        h["H2 perte(A) ≤ perte(B)"] = {"perte_A": round(pct("A_S") - pct("A_F"), 1), "perte_B": round(pct("B_S") - pct("B_F"), 1),
                                       "tient": pct("A_S") - pct("A_F") <= pct("B_S") - pct("B_F")}
    if None not in (pct("A_F", "knowledge-update"), pct("B_F", "knowledge-update")):
        h["H3 mises à jour : A_F ≥ B_F"] = {"A_F": pct("A_F", "knowledge-update"), "B_F": pct("B_F", "knowledge-update"),
                                            "tient": pct("A_F", "knowledge-update") >= pct("B_F", "knowledge-update")}
    if lat.get("A_F"):
        h["H4 p95(A_F) < 20 ms"] = {"p95_ms": lat["A_F"]["p95_ms"], "tient": lat["A_F"]["p95_ms"] < 20}
    if pct("M_S", ASSISTANT) is not None:
        h["P1 (prédiction) assistant : M_S < 30 %"] = {"M_S": pct("M_S", ASSISTANT), "tient": pct("M_S", ASSISTANT) < 30}
    sortie = {"table": table, "apparies": paires, "hypotheses": h, "latences": lat,
              "fusion": json.loads((K.RUN / "fusion.json").read_text()) if (K.RUN / "fusion.json").exists() else {},
              "depense": modele.depense()}
    (K.RUN / "bilan.json").write_text(json.dumps(sortie, indent=1, ensure_ascii=False))
    ordre = ["tout", "tout sauf assistant", "single-session-user", ASSISTANT, "single-session-preference", "multi-session",
             "knowledge-update", "temporal-reasoning", "abstention"]
    print("moteur  " + " | ".join(f"{g[:14]:>14}" for g in ordre))
    for k in sorted(table):
        print(f"{k:7} " + " | ".join(f"{(table[k].get(g) or {}).get('pct', '—'):>14}" for g in ordre))
    for k, v in paires.items():
        print(f"  {k} : {v}")
    for k, v in h.items():
        print(f"  {k} : {v}")
    print("  latences :", lat)
    print("  dépense :", round(sortie["depense"]["total"]["usd"], 3), "$")
    return 0


if __name__ == "__main__":
    sys.exit(main())
