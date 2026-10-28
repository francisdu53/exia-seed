#!/usr/bin/env python3
"""Étape 6 — le bilan (docs/09 §5), sans appel au modèle.

Score J (justes / questions) par moteur × échelle, catégories 1-4 (la mesure principale) et catégorie 5 à part,
par tranche : VÉRIFICATION (les 8 conversations jamais regardées — les chiffres annoncés) et PILOTE (à part).
Puis les critères fixés avant la mesure : H1 (A ≥ B − 2 points en F), H2 (A perd ≤ B de S à F), H3 (D perd
plus que A), H4 (latence de A). Plus la dépense réelle, par rôle.

    python3 bilan.py
"""
from __future__ import annotations

import json
import sys

import commun as K
import modele


def main() -> int:
    qs = {q["id"]: q for q in K.questions(K.charger_donnees(K.selection_du_run()))}
    lab = {f.stem: {x["id"]: x["label"] for x in K.lire_jsonl(f)} for f in sorted((K.RUN / "jugements").glob("*.jsonl"))}
    tranches = [t for t in ("verification", "pilote") if any(q["tranche"] == t for q in qs.values())]
    table = {}
    for cle, l in lab.items():
        for t in tranches:
            for groupe, cats in (("cat1-4", {1, 2, 3, 4}), ("cat5", {5}), *((f"cat{c}", {c}) for c in (1, 2, 3, 4))):
                ids = [i for i, q in qs.items() if q["tranche"] == t and q["categorie"] in cats and i in l]
                if ids:
                    table.setdefault(t, {}).setdefault(cle, {})[groupe] = {
                        "justes": sum(l[i] == "CORRECT" for i in ids), "questions": len(ids),
                        "J": round(100 * sum(l[i] == "CORRECT" for i in ids) / len(ids), 2)}
    # Bonnes pratiques (docs/09 §13) : bruit du juge (passes), F1 indépendant du juge, test apparié A contre B
    import math, statistics
    bruit, f1s, apparies = {}, {}, {}
    for f in sorted((K.RUN / "jugements").glob("*.jsonl")):
        L = [x for x in K.lire_jsonl(f) if qs[x["id"]]["categorie"] != 5 and qs[x["id"]]["tranche"] == "verification" or
             (qs[x["id"]]["categorie"] != 5 and not any(q["tranche"] == "verification" for q in qs.values()))]
        n = max((len(x.get("passes") or []) for x in L), default=0)
        if n:
            js = [100 * sum((x["passes"][p] if p < len(x["passes"]) else "") == "CORRECT" for x in L) / len(L) for p in range(n)]
            bruit[f.stem] = {"J_par_passe": [round(j, 2) for j in js], "moyenne": round(statistics.mean(js), 2),
                             "ecart_type": round(statistics.pstdev(js), 2)}
    for f in sorted((K.RUN / "f1").glob("*.jsonl")) if (K.RUN / "f1").exists() else []:
        for t_ in tranches:
            v = [x["f1"] for x in K.lire_jsonl(f) if qs[x["id"]]["tranche"] == t_ and qs[x["id"]]["categorie"] != 5]
            if v:
                f1s.setdefault(t_, {})[f.stem] = round(100 * sum(v) / len(v), 2)
    for t_ in tranches:
        for a_, b_ in (("A_S", "B_S"), ("A_F", "B_F"), ("A_S", "C_S"), ("A_F", "C_F")):
            if a_ in lab and b_ in lab:
                ids = [i for i, q in qs.items() if q["tranche"] == t_ and q["categorie"] != 5 and i in lab[a_] and i in lab[b_]]
                sa = sum(lab[a_][i] == "CORRECT" and lab[b_][i] != "CORRECT" for i in ids)
                sb = sum(lab[b_][i] == "CORRECT" and lab[a_][i] != "CORRECT" for i in ids)
                n_ = sa + sb
                p_ = min(1.0, 2 * sum(math.comb(n_, k) for k in range(min(sa, sb) + 1)) / 2 ** n_) if n_ else 1.0
                apparies.setdefault(t_, {})[f"{a_} contre {b_}"] = {"seul_" + a_: sa, "seul_" + b_: sb, "p_mcnemar": round(p_, 4)}
    lat = {}
    for f in sorted((K.RUN / "contextes").glob("*.jsonl")):
        v = sorted(x["latence_ms"] for x in K.lire_jsonl(f))
        lat[f.stem] = {"p50_ms": v[len(v) // 2], "p95_ms": v[int(0.95 * len(v)) - 1]} if v else {}
    criteres = {}
    for t in tranches:
        J = lambda k: (table.get(t, {}).get(k, {}).get("cat1-4") or {}).get("J")
        if J("A_F") is not None and J("B_F") is not None:
            criteres.setdefault(t, {})["H1 A_F ≥ B_F − 2"] = {"A_F": J("A_F"), "B_F": J("B_F"), "tient": J("A_F") >= J("B_F") - 2}
        if None not in (J("A_S"), J("A_F"), J("B_S"), J("B_F")):
            criteres.setdefault(t, {})["H2 perte(A) ≤ perte(B)"] = {"perte_A": round(J("A_S") - J("A_F"), 2),
                                                                   "perte_B": round(J("B_S") - J("B_F"), 2),
                                                                   "tient": J("A_S") - J("A_F") <= J("B_S") - J("B_F")}
        if None not in (J("A_S"), J("A_F"), J("D_S"), J("D_F")):
            criteres.setdefault(t, {})["H3 perte(D) > perte(A)"] = {"perte_D": round(J("D_S") - J("D_F"), 2),
                                                                   "perte_A": round(J("A_S") - J("A_F"), 2),
                                                                   "tient": J("D_S") - J("D_F") > J("A_S") - J("A_F")}
    if lat.get("A_F"):
        criteres["H4 p95(A, F) < 20 ms"] = {"p95_ms": lat["A_F"]["p95_ms"], "tient": lat["A_F"]["p95_ms"] < 20}
    bilan = {"modele": K.MODELE, "table": table, "criteres": criteres, "latences": lat, "depense": modele.depense(),
             "bruit_du_juge": bruit, "f1": f1s, "tests_apparies": apparies,
             "fusion": json.loads((K.RUN / "fusion.json").read_text()) if (K.RUN / "fusion.json").exists() else None}
    (K.RUN / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1))
    for t in tranches:
        print(f"\n── {t.upper()} — score J, catégories 1-4 (cat. 5 à part)")
        print(f"{'':6}" + "".join(f"{g:>16}" for g in ("cat1-4", "cat1", "cat2", "cat3", "cat4", "cat5")))
        for k in sorted(table.get(t, {})):
            r = table[t][k]
            print(f"{k:6}" + "".join(f"{(str(r[g]['J']) + ' % (' + str(r[g]['questions']) + ')') if g in r else '—':>16}"
                                     for g in ("cat1-4", "cat1", "cat2", "cat3", "cat4", "cat5")))
    print("\nF1 (papier LoCoMo, sans juge), cat. 1-4 :", json.dumps(f1s, ensure_ascii=False))
    print("Bruit du juge (J par passe, cat. 1-4) :", json.dumps({k: (v["moyenne"], v["ecart_type"]) for k, v in bruit.items()}))
    print("Tests appariés (McNemar) :", json.dumps(apparies, ensure_ascii=False))
    print("\nCritères :", json.dumps(criteres, ensure_ascii=False, indent=1))
    print("Dépense :", json.dumps(bilan["depense"]["total"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
