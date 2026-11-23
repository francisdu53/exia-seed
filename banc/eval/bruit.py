#!/usr/bin/env python3
"""Test 2 (23/11) — la QUESTION abîmée, comme dans la vraie vie (frappe sur téléphone, mots perdus d'un vocal).

EVAL_BRUITQ="sorte:taux", appliqué par les fournisseurs (fournir_n / fournir_seed / fournir_rag) à chaque question, de
façon DÉTERMINISTE (même graine = id de la question + mode) : tous les concurrents reçoivent exactement la même question.
  typo:T   une faute de frappe dans une part T des mots de 4 lettres ou plus : lettres voisines inversées, lettre
           oubliée, lettre doublée, ou touche voisine du clavier (QWERTY, les bancs sont en anglais)
  trou:T   une part T des mots disparaît (indice partiel)
Le nombre de mots touchés est T × (mots éligibles), arrondi au hasard (sans biais). Aucun modèle.
    python3 bruit.py lme 5          → 5 exemples par mode (inspection)
"""
from __future__ import annotations

import hashlib
import os
import random
import re

MODE = os.environ.get("EVAL_BRUITQ", "")
_CLAVIER = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
VOISINS = {}
for r, ligne in enumerate(_CLAVIER):
    for c, ch in enumerate(ligne):
        v = set()
        for dr in (-1, 0, 1):
            rr = r + dr
            if 0 <= rr < len(_CLAVIER):
                for dc in (-1, 0, 1):
                    cc = c + dc
                    if (dr or dc) and 0 <= cc < len(_CLAVIER[rr]):
                        v.add(_CLAVIER[rr][cc])
        VOISINS[ch] = sorted(v)
JETON = re.compile(r"^(\W*)(.*?)(\W*)$", re.S)


def _faute(mot: str, rnd: random.Random) -> str:
    bas = mot.lower()
    op = rnd.choice(("inverser", "oublier", "doubler", "voisine"))
    i = rnd.randrange(1, len(mot) - 1)                 # jamais la première lettre (on la rate rarement)
    if op == "inverser":
        s = bas[:i] + bas[i + 1] + bas[i] + bas[i + 2:]
    elif op == "oublier":
        s = bas[:i] + bas[i + 1:]
    elif op == "doubler":
        s = bas[:i] + bas[i] + bas[i:]
    else:
        s = bas[:i] + rnd.choice(VOISINS.get(bas[i], [bas[i]])) + bas[i + 1:]
    if s == bas:                                        # inversion de deux lettres identiques : on oublie plutôt
        s = bas[:i] + bas[i + 1:]
    return s.upper() if mot.isupper() else (s.capitalize() if mot[:1].isupper() else s)


def _combien(n: int, taux: float, rnd: random.Random) -> int:
    x = taux * n
    return int(x) + (rnd.random() < x - int(x))


def bruiter(question: str, qid: str, mode: str = MODE) -> str:
    if not mode:
        return question
    sorte, taux = mode.split(":")
    taux = float(taux)
    rnd = random.Random(hashlib.sha256(f"{qid}|{mode}".encode()).hexdigest())
    jetons = question.split()
    if sorte == "typo":
        elig = [k for k, t in enumerate(jetons) if len(JETON.match(t).group(2)) >= 4 and JETON.match(t).group(2).isalpha()]
        for k in rnd.sample(elig, _combien(len(elig), taux, rnd)):
            a, coeur, z = JETON.match(jetons[k]).groups()
            jetons[k] = a + _faute(coeur, rnd) + z
        return " ".join(jetons)
    if sorte == "trou":
        n = min(_combien(len(jetons), taux, rnd), len(jetons) - 1)
        partis = set(rnd.sample(range(len(jetons)), n))
        return " ".join(t for k, t in enumerate(jetons) if k not in partis)
    raise ValueError(f"mode de bruit inconnu : {mode}")


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path
    banc, n = sys.argv[1], int(sys.argv[2])
    ici = Path(__file__).resolve().parent
    d = json.loads((ici.parent / "bancs" / "donnees" / ("lme_oracle_locomo.json" if banc == "lme" else "locomo10.json")).read_text(encoding="utf-8"))
    qs = [(f"{c['sample_id']}:{k}", q["question"]) for c in d for k, q in enumerate(c["qa"])][:n]
    for qid, q in qs:
        print(f"\n{q}")
        for m in ("typo:0.1", "typo:0.25", "typo:0.5", "trou:0.2", "trou:0.4"):
            print(f"  {m:9s} {bruiter(q, qid, m)}")
