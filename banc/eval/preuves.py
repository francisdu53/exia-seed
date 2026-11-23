#!/usr/bin/env python3
"""Capteur gratuit de qualité : la PREUVE est-elle dans le bloc ? (aucun modèle, aucun token)

LoCoMo et LongMemEval disent quelles répliques portent la réponse :
  LoCoMo        `evidence` de chaque question (« D3:5 » = session 3, réplique 5)
  LongMemEval   les répliques `has_answer` du jeu d'origine (`longmemeval_oracle.json`, 896 répliques, 479 questions)
On retrouve chaque réplique dans le BRUT de la mémoire (même texte au début de la ligne), donc son fichier et ses lignes.
Un élément donné au lecteur COUVRE une réplique-preuve s'il cite une de ses lignes (souvenir : ses citations
`src:raw/<f>:<ligne>` ; tour de RAG : ses répliques). Mesures par question : part des répliques-preuves couvertes,
« touchée » (au moins une). Le bloc est reconstruit exactement comme `paqueter.py` (même budget, même compteur).
Sert à régler N sur les jeux de RÉGLAGE sans dépenser de tokens, et à suivre chaque échelon de la phase 1.
Hôte : ${PYTHON_EMBEDDINGS:-python3} preuves.py <candidats…> --budgets 450,1350,4500
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI)); sys.path.insert(0, str(ICI.parent / "harnais"))
import capteurs as C                                            # noqa: E402
import echelle as EC                                            # noqa: E402
from paqueter import paqueter                                    # noqa: E402

TOUR = re.compile(r"^\[(\d\d:\d\d) ([^\]]+)\] (.*)$")
DONNEES = ICI.parent / "bancs" / "donnees"
norm = lambda t: re.sub(r"\W+", " ", (t or "").lower()).strip()[:80]


def repliques_du_brut(memoire: Path):
    """{(fichier, ligne_debut): (ligne_fin, texte normalisé)} et un index texte → [(fichier, ligne_debut)]."""
    plages, index = {}, defaultdict(list)
    for f in sorted((memoire / "raw").glob("*.md")):
        lignes = f.read_text(encoding="utf-8").splitlines()
        cour = None
        for n, l in enumerate(lignes, start=1):
            m = TOUR.match(l)
            if m:
                cour = n; plages[(f.name, n)] = n; index[norm(m.group(3))].append((f.name, n))
            elif cour is not None and l.strip() and not l.startswith("#"):
                plages[(f.name, cour)] = n
    return plages, index


_CACHE = {}


def or_des_questions(banc: str):
    """{id question: [textes des répliques-preuves]}."""
    if banc in _CACHE:
        return _CACHE[banc]
    sortie = {}
    if banc == "locomo":
        for c in json.loads((DONNEES / "locomo10.json").read_text(encoding="utf-8")):
            textes = {t["dia_id"]: t["text"] for k, v in c["conversation"].items() if re.fullmatch(r"session_\d+", k) for t in v}
            for k, q in enumerate(c["qa"]):
                sortie[f"{c['sample_id']}:{k}"] = [textes[e] for e in q.get("evidence", []) if e in textes]
    else:
        orig = json.loads((DONNEES / "longmemeval_oracle.json").read_text(encoding="utf-8"))
        for x in orig:
            sortie[f"{x['question_id']}:0"] = [t["content"] for s in x["haystack_sessions"] for t in s if t.get("has_answer")]
    _CACHE[banc] = sortie
    return sortie


def evaluer(fichier: Path, budgets):
    m = re.match(r"^(?P<c>[^_]+)_(?P<b>lme|locomo)_(?P<e>[SF])_", fichier.name)
    banc, ech = m["b"], m["e"]
    gold = or_des_questions(banc)
    jetons = C.Jetons()
    cand = [json.loads(l) for l in fichier.read_text(encoding="utf-8").splitlines() if l.strip()]
    memo = {}
    res = {b: {"n": 0, "touchees": 0, "part": 0.0, "sans_preuve_trouvee_dans_brut": 0} for b in budgets}
    for x in cand:
        textes = gold.get(x["id"], [])
        if not textes:
            continue
        conv = x["id"].rsplit(":", 1)[0]
        mem = EC.dossier(ICI / "memoires" / banc, conv, ech)          # test 1 : EVAL_MEMOIRE
        if mem not in memo:
            if len(memo) > 12:
                memo.clear()
            memo[mem] = repliques_du_brut(mem)
        plages, index = memo[mem]
        pref = EC.prefixe(conv, ech)
        cibles = []                                    # une cible par réplique-preuve : [(fichier, début, fin)…]
        for t in textes:
            pos = [(f, d) for f, d in index.get(norm(t), []) if f.startswith(pref) and (not pref or f[len(pref):len(pref) + 1].isdigit())]   # « X_abs_… » n'est pas « X » (23/11)
            cibles.append([(f, d, plages[(f, d)]) for f, d in pos])
        for b in budgets:
            r = res[b]
            if not any(cibles):
                r["sans_preuve_trouvee_dans_brut"] += 1; continue
            _, pris, _ = paqueter(x.get("items", []), b, jetons)
            cites = set()
            for k in pris:
                it = x["items"][k]
                if it.get("type") == "tour":
                    for ln in it.get("lignes") or [it["src"][1]]:
                        cites.add((it["src"][0], ln))
                else:
                    for f, ln in it.get("refs") or ([it["src"]] if it.get("src") else []):
                        cites.add((f, ln))
            couv = [any(f2 == f and d <= ln <= fin for f, d, fin in c for f2, ln in cites) for c in cibles if c]
            r["n"] += 1; r["touchees"] += int(any(couv)); r["part"] += sum(couv) / len(couv)
            r.setdefault("par_question", {})[x["id"]] = bool(any(couv))
    for b, r in res.items():
        if r["n"]:
            r["touchees_pct"] = round(100 * r["touchees"] / r["n"], 1); r["part_pct"] = round(100 * r["part"] / r["n"], 1)
    return res


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    budgets = [None if b == "tout" else int(b) for b in
               (sys.argv[sys.argv.index("--budgets") + 1] if "--budgets" in sys.argv else "450").split(",")]
    args = [a for a in args if a not in (sys.argv[sys.argv.index("--budgets") + 1] if "--budgets" in sys.argv else "",)]
    sortie = {}
    for a in args:
        f = Path(a) if Path(a).is_absolute() else ICI / "runs" / "candidats" / a
        r = evaluer(f, budgets)
        sortie[f.name] = {**{str(b): v for b, v in r.items()}, "memoire": EC.MEM}
        print(f.name, " · ".join(f"B{b}: preuve touchée {v.get('touchees_pct')} % · couverte {v.get('part_pct')} % (n {v['n']}, introuvables {v['sans_preuve_trouvee_dans_brut']})" for b, v in r.items()))
    (ICI / "rapports").mkdir(exist_ok=True)
    with (ICI / "rapports" / "preuves.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(sortie, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
