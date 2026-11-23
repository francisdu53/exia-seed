#!/usr/bin/env python3
"""Rapport des tests du 23/11 (interférence, question abîmée) — lit interference/runs.tsv, rapports/preuves.jsonl et les
candidats (latence à chaud, RAM). Sortie Markdown sur la sortie standard."""
from __future__ import annotations

import json
import math
from pathlib import Path

ICI = Path(__file__).resolve().parent
CONCS = ("NA1", "S2", "Rp", "Rh")
NOMS = {"NA1": "NA1 (0.10.0 candidate)", "S2": "S2 montre 1.0.0", "Rp": "Rp embeddings souvenirs", "Rh": "Rh RAG hybride brut"}


def mcnemar(a: dict, b: dict):
    ids = set(a) & set(b)
    x = sum(1 for i in ids if a[i] and not b[i]); y = sum(1 for i in ids if b[i] and not a[i])
    n = x + y
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(min(x, y) + 1)) / 2 ** n) if n else 1.0
    return x, y, p


def main() -> int:
    runs = [l.split("\t") for l in (ICI / "interference" / "runs.tsv").read_text(encoding="utf-8").splitlines() if l.strip()]
    preuves = {}
    for l in (ICI / "rapports" / "preuves.jsonl").read_text(encoding="utf-8").splitlines():
        for k, v in json.loads(l).items():
            preuves[k] = v                                       # la dernière mesure l'emporte
    R = {}
    for f, mem in runs:
        p = preuves.get(f)
        cand = ICI / "runs" / "candidats" / f
        if not p or not cand.exists():
            R[f] = None; continue
        lignes = [json.loads(x) for x in cand.read_text(encoding="utf-8").splitlines() if x.strip()]
        lat = sorted(x["capteurs"]["chaud"]["ns"].get("requete", 0) / 1e6 for x in lignes if "capteurs" in x)
        man = json.loads(cand.with_suffix(".manifeste.json").read_text(encoding="utf-8"))
        R[f] = {"p450": p["450"].get("touchees_pct"), "p1350": p["1350"].get("touchees_pct"), "n": p["450"]["n"],
                "pq": p["450"].get("par_question", {}), "lat50": lat[len(lat) // 2] if lat else None,
                "lat95": lat[int(0.95 * (len(lat) - 1))] if lat else None, "ram": (man.get("ram") or {}).get("pic_mo")}
    nom = lambda c, b, t: f"{c}_{b}_F_test_{40 if c in ('NA1', 'S2') else 200}__{t}.jsonl"
    cell = lambda r: "—" if not r else f"{r['p450']:.1f}"
    print("# Tests du 23/11 — interférence et question abîmée (capteur de preuve, aucun modèle)\n")
    print("Mesure : part des questions dont une réplique-preuve est DANS le bloc donné au lecteur (budget 450 tokens ;"
          " entre parenthèses : 1 350). Jeu TEST : LoCoMo 196 questions, LongMemEval 100.\n")
    # ---- test 2
    modes = [("b-propre", "propre"), ("b-typo:0.1", "fautes 10 %"), ("b-typo:0.25", "fautes 25 %"), ("b-typo:0.5", "fautes 50 %"),
             ("b-trou:0.2", "mots perdus 20 %"), ("b-trou:0.4", "mots perdus 40 %")]
    print("## Test 2 — question abîmée (mémoire F)\n")
    for b in ("locomo", "lme"):
        print(f"### {'LoCoMo' if b == 'locomo' else 'LongMemEval'}\n")
        print("| | " + " | ".join(m for _, m in modes) + " |"); print("|---" * (len(modes) + 1) + "|")
        for c in CONCS:
            base = R.get(nom(c, b, "b-propre"))
            cells = []
            for t, _ in modes:
                r = R.get(nom(c, b, t))
                if not r:
                    cells.append("—"); continue
                d = f" ({r['p450'] - base['p450']:+.1f})" if base and t != "b-propre" else f" ({r['p1350']:.1f})"
                cells.append(f"{r['p450']:.1f}{d}")
            print(f"| {NOMS[c]} | " + " | ".join(cells) + " |")
        print()
        for t, m in modes:
            a = R.get(nom("NA1", b, t))
            if not a:
                continue
            s = []
            for c in ("Rp", "Rh", "S2"):
                o = R.get(nom(c, b, t))
                if o:
                    x, y, p = mcnemar(a["pq"], o["pq"]); s.append(f"{c} {x}/{y} (p = {p:.3g})")
            print(f"- {m} — NA1 contre " + " · ".join(s))
        print()
    # ---- test 1
    print("## Test 1 — interférence (la même question, une mémoire de plus en plus grosse)\n")
    for b, pts in (("lme", [("m_seule", "1"), ("m_g10", "10"), ("m_g50", "50"), ("m_g200", "200"), ("b-propre", "500")]),
                   ("locomo", [("m_seule", "1"), ("b-propre", "10"), ("m_mixte", "10 + 500 LME")])):
        print(f"### {'LongMemEval' if b == 'lme' else 'LoCoMo'} — conversations dans la mémoire\n")
        print("| | " + " | ".join(p for _, p in pts) + " | latence à chaud p50 / p95 (ms), de la plus petite à la plus grosse | RAM pic (Mo) |")
        print("|---" * (len(pts) + 3) + "|")
        for c in CONCS:
            rs = [R.get(nom(c, b, t)) for t, _ in pts]
            lat = " → ".join(f"{r['lat50']:.0f}/{r['lat95']:.0f}" if r and r["lat50"] is not None else "—" for r in (rs[0], rs[-1]))
            ram = " → ".join(f"{r['ram']:.0f}" if r and r.get("ram") else "—" for r in (rs[0], rs[-1]))
            print(f"| {NOMS[c]} | " + " | ".join(cell(r) for r in rs) + f" | {lat} | {ram} |")
        print()
        a0, a1 = R.get(nom("NA1", b, pts[0][0])), R.get(nom("NA1", b, pts[-1][0]))
        for c in CONCS:
            r0, r1 = R.get(nom(c, b, pts[0][0])), R.get(nom(c, b, pts[-1][0]))
            if r0 and r1:
                x, y, p = mcnemar(r0["pq"], r1["pq"])
                print(f"- {c} : perdues en grossissant {x}, gagnées {y} (p = {p:.3g})")
        print()
    for b in ("lme", "locomo"):
        a, k = R.get(nom("NA1", b, "b-propre")), R.get(nom("NA1", b, "m_controle"))
        if a and k:
            print(f"- Contrôle {b} : NA1 sur la fusion refaite = {k['p450']:.1f} contre {a['p450']:.1f} sur l'originale ; "
                  f"mêmes réponses question par question : {a['pq'] == k['pq']}")
    manq = [f for f, r in R.items() if r is None]
    if manq:
        print(f"\n⚠️ {len(manq)} passage(s) sans mesure : " + ", ".join(manq))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
