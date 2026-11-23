#!/usr/bin/env python3
"""Régler Nb (la toile sur le BRUT seul, sans modèle) sur les jeux de RÉGLAGE — même méthode que regler_n.py :
régression logistique sur les répliques-preuves (un tour est utile s'il contient une réplique-preuve), puis la
reconstruction (tours voisins) choisie sur une petite grille par la preuve dans le bloc au budget 450. Aucun token.
Conteneur : … python3 regler_nb.py → poids_Nb.json, reglages_Nb.json
"""
import json, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import numpy as np
ICI = Path(__file__).resolve().parent
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, str(ICI / "paquets" / "seed-1.0.0")); sys.path.insert(0, str(ICI))
sys.path.insert(0, str(ICI.parent / "harnais"))
import capteurs as C, n as NN, preuves as P
from paqueter import paqueter
from regler_n import questions, cibles, couvre, ajuster, auc
TRES_TARD = datetime(2100, 1, 1)
TAILLE = int(sys.argv[1]) if len(sys.argv) > 1 else 2          # 2 : tours (Nb) ; 1 : répliques seules (Nb1)
SUFF = "" if TAILLE == 2 else str(TAILLE)
scelle = json.loads((ICI / "scelle.json").read_text(encoding="utf-8"))
jeux, lignes, y = [], [], []
for banc in ("locomo", "lme"):
    mem = ICI / "memoires" / banc / "_fusion"
    toile = NN.ToileBrute(mem, {k: 0.0 for k in NN.TRAITS_B}, {"taille": TAILLE})
    plages, index = P.repliques_du_brut(mem)
    for q in (q for q in questions(banc) if q["id"] in set(scelle[banc]["reglage"])):
        cib = cibles(banc, q["id"], plages, index)
        if not cib:
            continue
        X, _ = toile._traits(q["question"], datetime.fromisoformat(q["instant"]), C.Chrono(), defaultdict(int))
        for i, x in X.items():
            t = toile.tours[i]
            lignes.append([x[k] for k in NN.TRAITS_B]); y.append(float(couvre([(t["fichier"], l) for l in t["lignes"]], cib)))
        jeux.append((banc, q, cib))
X = np.array(lignes); Y = np.array(y); w = ajuster(X, Y)
poids = {k: round(float(v), 4) for k, v in zip(NN.TRAITS_B, w)}
print(f"Nb{SUFF} : {len(Y)} paires, {int(Y.sum())} utiles, AUC réglage {auc(X @ w, Y):.3f}\n{json.dumps(poids)}", flush=True)
(ICI / f"poids_Nb{SUFF}.json").write_text(json.dumps(poids, indent=1), encoding="utf-8")
jetons = C.Jetons(); toiles = {}; meilleur = None
for opt in [{"voisins_ecart": e, "voisins_parents": p, "taille": TAILLE} for e in (-0.5, -1.0, -2.0, -99.0) for p in (3, 5)]:
    ok = n = 0
    for banc, q, cib in jeux:
        cle = (banc, json.dumps(opt))
        if cle not in toiles:
            toiles.clear(); toiles[cle] = NN.ToileBrute(ICI / "memoires" / banc / "_fusion", poids, opt)
        r = toiles[cle].rappeler(q["question"], TRES_TARD, datetime.fromisoformat(q["instant"]), 40, C.Chrono())
        _, pris, _ = paqueter(r["items"], 450, jetons)
        ok += int(couvre([(r["items"][k]["src"][0], l) for k in pris for l in r["items"][k]["lignes"]], cib)); n += 1
    print(f"  {opt} : preuve dans le bloc {100 * ok / n:.1f} % ({n} q)", flush=True)
    if meilleur is None or ok > meilleur[0]:
        meilleur = (ok, opt)
(ICI / f"reglages_Nb{SUFF}.json").write_text(json.dumps({"Nb": meilleur[1]}, indent=1), encoding="utf-8")
print("retenu :", meilleur[1])
