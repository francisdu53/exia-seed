#!/usr/bin/env python3
"""Régler N sur les jeux de RÉGLAGE scellés (jamais sur le test) — sans aucun token.

Vérité : les répliques-preuves des bancs (preuves.py). Pour chaque question de réglage (LoCoMo conv-26 et conv-30 ;
LongMemEval : les 50 tirées graine 2611), à l'échelle F (la mémoire fusionnée), N allume ses souvenirs et calcule
leurs indices ; un souvenir est « utile » s'il cite une ligne d'une réplique-preuve. Les poids des indices sont ceux
d'une régression logistique (IRLS, pénalité L2 = 1 hors biais) sur toutes ces paires, les deux bancs ensemble.
Ensuite, les réglages des rouages N3 à N5 sont choisis sur une petite grille fixée d'avance, par la part de questions
dont la preuve est dans le bloc au budget B1 (450) — toujours sur le réglage.
Conteneur : … python3 regler_n.py N1|N2   →  poids_N1.json / poids_N2.json (+ réglages_N.json avec la grille)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
ETAGE = sys.argv[1] if len(sys.argv) > 1 and __name__ == "__main__" else "N1"
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, str(ICI / "paquets" / "seed-1.0.0")); sys.path.insert(0, str(ICI))
sys.path.insert(0, str(ICI.parent / "harnais"))
import capteurs as C                                              # noqa: E402
import n as NN                                                    # noqa: E402
import preuves as P                                               # noqa: E402
from paqueter import paqueter                                      # noqa: E402
from exia_seed import rappel as R                                  # noqa: E402

TRES_TARD = datetime(2100, 1, 1)


def questions(banc):
    os.environ["LOCOMO_DONNEES"] = str(ICI.parent / "bancs" / "donnees" / ("lme_oracle_locomo.json" if banc == "lme" else "locomo10.json"))
    import importlib
    import commun
    importlib.reload(commun)
    return commun.questions(json.loads(Path(commun.DONNEES).read_text(encoding="utf-8")))


def cibles(banc, qid, plages, index):
    conv = qid.rsplit(":", 1)[0]
    sortie = []
    for t in P.or_des_questions(banc).get(qid, []):
        pos = [(f, d) for f, d in index.get(P.norm(t), []) if f.startswith(f"{conv}_")]
        if pos:
            sortie.append([(f, d, plages[(f, d)]) for f, d in pos])
    return sortie


def couvre(refs, cib):
    return any(f2 == f and d <= int(ln) <= fin for c in cib for f, d, fin in c for f2, ln in refs)


def ajuster(X, y, l2=1.0, iters=60):
    w = np.zeros(X.shape[1]); masque = np.ones(X.shape[1]); masque[0] = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
        g = X.T @ (p - y) + l2 * masque * w
        H = X.T @ (X * (p * (1 - p))[:, None]) + np.diag(l2 * masque + 1e-6)
        pas = np.linalg.solve(H, g); w -= pas
        if np.abs(pas).max() < 1e-6:
            break
    return w


def auc(s, y):
    o = np.argsort(s); r = np.empty(len(s)); r[o] = np.arange(1, len(s) + 1)
    n1 = y.sum(); n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / max(1, n1 * n0))


def main() -> int:
    scelle = json.loads((ICI / "scelle.json").read_text(encoding="utf-8"))
    cartes = json.loads((ICI / "cartes_ecrites.json").read_text(encoding="utf-8")) if ETAGE != "N1" and (ICI / "cartes_ecrites.json").exists() else None
    etages = () if ETAGE == "N1" else ("N2",)
    lignes, y, essais = [], [], []
    for banc in ("locomo", "lme"):
        imp = ("user", "assistant") if banc == "lme" else ()
        mem = ICI / "memoires" / banc / "_fusion"
        rp = R.Rappeleur(mem, implicites=imp)
        toile = NN.Toile(rp, poids={k: 0.0 for k in NN.TRAITS}, etages=etages, cartes_ecrites=cartes)
        plages, index = P.repliques_du_brut(mem)
        ids = set(scelle[banc]["reglage"])
        for q in (q for q in questions(banc) if q["id"] in ids):
            cib = cibles(banc, q["id"], plages, index)
            if not cib:
                continue
            X, _ = toile._traits_et_candidats(q["question"], TRES_TARD, datetime.fromisoformat(q["instant"]), C.Chrono(), __import__("collections").defaultdict(int))
            for i, x in X.items():
                lignes.append([x[k] for k in NN.TRAITS]); y.append(float(couvre(rp.memoire().faits[i].get("refs") or (), cib)))
            essais.append((banc, q, cib))
    X = np.array(lignes); Y = np.array(y)
    w = ajuster(X, Y)
    poids = {k: round(float(v), 4) for k, v in zip(NN.TRAITS, w)}
    print(f"{ETAGE} : {len(Y)} paires, {int(Y.sum())} utiles ({100 * Y.mean():.2f} %), AUC réglage {auc(X @ w, Y):.3f}")
    print(json.dumps(poids, ensure_ascii=False))
    (ICI / f"poids_{ETAGE}.json").write_text(json.dumps(poids, ensure_ascii=False, indent=1), encoding="utf-8")
    # grille des rouages N3-N5 (réglage seulement), critère : preuve dans le bloc au budget 450
    jetons = C.Jetons()
    grilles = {"N3": [{"inhib": v, "sim_seuil": s} for v in (0.5, 1.0, 2.0, 4.0) for s in (0.5, 0.6)],
               "N4": [{"freres_ecart": e, "freres_parents": p} for e in (-0.5, -1.0, -2.0) for p in (3, 5)],
               "N5": [{"passages": p} for p in (1, 2, 3)]}
    choisis = {}
    toiles = {}
    for etage, grille in grilles.items():
        meilleur = None
        for opt in grille:
            touche = n = 0
            for banc, q, cib in essais:
                imp = ("user", "assistant") if banc == "lme" else ()
                cle = (banc, etage, json.dumps(opt))
                if cle not in toiles:
                    toiles.clear()
                    rp = R.Rappeleur(ICI / "memoires" / banc / "_fusion", implicites=imp)
                    toiles[cle] = NN.Toile(rp, poids, etages=set(etages) | {etage} | ({"N3"} if etage in ("N4", "N5") else set())
                                           | ({"N4"} if etage == "N5" else set()), cartes_ecrites=cartes,
                                           options={**{k: v for e2 in choisis.values() for k, v in e2.items()}, **opt})
                r = toiles[cle].rappeler(q["question"], TRES_TARD, datetime.fromisoformat(q["instant"]), 40, C.Chrono())
                _, pris, _ = paqueter(r["items"], 450, jetons)
                refs = [tuple(x) for k in pris for x in r["items"][k].get("refs") or ()]
                touche += int(couvre(refs, cib)); n += 1
            print(f"  {etage} {opt} : preuve dans le bloc {100 * touche / max(1, n):.1f} % ({n} q)", flush=True)
            if meilleur is None or touche > meilleur[0]:
                meilleur = (touche, opt)
        choisis[etage] = meilleur[1]
    (ICI / f"reglages_{ETAGE}.json").write_text(json.dumps(choisis, ensure_ascii=False, indent=1), encoding="utf-8")
    print("rouages retenus :", choisis)
    return 0


if __name__ == "__main__":
    sys.exit(main())
