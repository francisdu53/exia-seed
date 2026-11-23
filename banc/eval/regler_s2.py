#!/usr/bin/env python3
"""TÉMOIN S2r — la montre 1.0.0 RÉAJUSTÉE sur les mêmes jeux de réglage que N (aucun token).

Pourquoi : N1 est réglé sur les jeux de réglage des bancs (anglais), la montre l'avait été sur la mémoire française de
Nexa. Sans ce témoin, un écart N1 / S2 pourrait venir du seul réglage. On garde l'architecture de la montre (cab_pull,
voix et absences) et on cherche ses poids par montée coordonnée, directement sur le critère : la part des questions de
RÉGLAGE dont la preuve est dans le bloc au budget 450 (critère plus favorable encore à la montre que la vraisemblance).
Poids bornés à [0, 1] (cab_pull). Deux tours ; multiplicateurs 0 / 0,5 / 1,5 / 2,5 et valeur 1.
Conteneur : … python3 regler_s2.py → poids_S2r.json (copié dans paquets/seed-1.0.0-S2r pour fournir_seed.py)
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, str(ICI / "paquets" / "seed-1.0.0")); sys.path.insert(0, str(ICI))
sys.path.insert(0, str(ICI.parent / "harnais"))
import capteurs as C                                              # noqa: E402
import preuves as P                                               # noqa: E402
from paqueter import paqueter                                      # noqa: E402
from regler_n import questions, cibles, couvre                     # noqa: E402
from exia_seed import montre as MO, rappel as R                    # noqa: E402

TRES_TARD = datetime(2100, 1, 1)


def main() -> int:
    scelle = json.loads((ICI / "scelle.json").read_text(encoding="utf-8"))
    jetons = C.Jetons()
    jeux = []
    for banc in ("locomo", "lme"):
        imp = ("user", "assistant") if banc == "lme" else ()
        mem = ICI / "memoires" / banc / "_fusion"
        rp = R.Rappeleur(mem, implicites=imp); m = rp.memoire()
        mo = MO.Montre(rp, continuite=False, seuil=0.0, max=40, garde_fou=10**6)
        plages, index = P.repliques_du_brut(mem)
        ids = set(scelle[banc]["reglage"])
        qs = [(q, cibles(banc, q["id"], plages, index)) for q in questions(banc) if q["id"] in ids]
        jeux.append((mo, m, [(q, c) for q, c in qs if c]))

    def score(poids):
        ok = n = 0
        for mo, m, qs in jeux:
            mo.poids = poids
            for q, cib in qs:
                x = mo.rappeler(q["question"], TRES_TARD)
                items = [{"texte": m.faits[i]["texte"], "date": ""} for i in x["faits"]]
                _, pris, _ = paqueter(items, 450, jetons)
                refs = [tuple(r) for k in pris for r in (m.faits[x["faits"][k]].get("refs") or ())]
                ok += int(couvre(refs, cib)); n += 1
        return ok / max(1, n)

    P0 = copy.deepcopy(MO.POIDS)
    meilleur, best = P0, score(P0)
    print(f"départ (poids 1.0.0) : preuve dans le bloc {100 * best:.1f} %", flush=True)
    cles = [("fuite", None)] + [("voix", k) for k in P0["voix"]] + [("absences", k) for k in P0["absences"]]
    for tour in range(2):
        for g, k in cles:
            v0 = meilleur[g] if k is None else meilleur[g][k]
            for mult in (0.0, 0.5, 1.5, 2.5):
                essai = copy.deepcopy(meilleur)
                v = min(1.0, max(0.0, v0 * mult if v0 > 0 else (0.1 if mult else 0.0)))
                if k is None:
                    essai[g] = max(1e-4, v)
                else:
                    essai[g][k] = v
                s = score(essai)
                if s > best + 1e-9:
                    best, meilleur = s, essai
                    print(f"  tour {tour + 1} · {g}.{k} = {v:.4f} → {100 * best:.1f} %", flush=True)
    (ICI / "poids_S2r.json").write_text(json.dumps(meilleur, ensure_ascii=False, indent=1), encoding="utf-8")
    cible = ICI / "paquets" / "seed-1.0.0-S2r"
    if cible.exists():
        shutil.rmtree(cible)
    shutil.copytree(ICI / "paquets" / "seed-1.0.0", cible, ignore=shutil.ignore_patterns("__pycache__"))
    (cible / "exia_seed" / "montre_poids.json").write_text(json.dumps(meilleur, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"S2r : preuve dans le bloc (réglage) {100 * best:.1f} % — poids dans poids_S2r.json et paquets/seed-1.0.0-S2r")
    return 0


if __name__ == "__main__":
    sys.exit(main())
