#!/usr/bin/env python3
"""Banc 17 §14.2 — rappel de la recherche selon le nombre de pages gardées (K). Sans modèle, gratuit.

Pour chaque passage « complet » (gpt-4o-mini : catalogue-complet-*, Terra : catalogue-terra-complet-*) : les faits
rangés dans une page qui existait au départ (hors utilisateur et assistant), par question. Pour chaque question, la
recherche du §13 est rejouée sur la mémoire de DÉPART avec les sessions de la question (approximation : la mémoire du
banc a grandi entre-temps), et l'on compte la part des pages réellement choisies par le modèle qui figurent dans les K
premières. Conteneur jetable (`lancer.sh rappel_k_lme`).
"""
import json
import re
import sys
from collections import defaultdict

sys.path.insert(0, "/locomo"); sys.path.insert(0, "/lme")
import commun as K                                                # noqa: E402
K.preparer_chemins()
from exia_seed.rappel import Rappeleur                            # noqa: E402
import catalogue_lme as C                                         # noqa: E402
import comparer_catalogue_lme as Z                                # noqa: E402

Z.RUNS = K.BANC / "runs"; Z.BASE = Z.RUNS / "catalogue-base" / "memoires" / "_fusion"
KS = (30, 60, 100, 200, 400)


def main():
    noeud = {p.name: Z.noeud_de(p) for p in (Z.BASE / "pages").glob("*.md")}
    presents = set(noeud.values()) - set(C.IMPLICITES)
    R = Rappeleur(Z.BASE, implicites=C.IMPLICITES)
    classement = {}
    out = {}
    for prefixe in ("catalogue", "catalogue-terra"):
        for i in (1, 2):
            run = Z.RUNS / f"{prefixe}-complet-{i}"
            mem = run / "memoire"
            pg = Z.pages(mem)
            ratt = defaultdict(set)
            for page, lignes in pg.items():
                if page in noeud and noeud[page] not in C.IMPLICITES:
                    for f, _ in lignes:
                        m = Z.RAW_Q.match(f)
                        if m:
                            ratt[m.group(1)].add(noeud[page])
            for q in ratt:
                if q not in classement:
                    src = []
                    for f in sorted((mem / "raw").glob(f"{q}_*.md")):
                        src += [f"[raw/{f.name}:{n}] {l}" for n, l in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)]
                    ordre, _ = C.selectionner(R, "\n".join(src))
                    classement[q] = [n for n in ordre if n in presents]
            total = sum(len(v) for v in ratt.values())
            out[run.name] = {"rattachements": total, **{f"K{k}": round(100 * sum(len(v & set(classement[q][:k])) for q, v in ratt.items()) / max(1, total), 1) for k in KS},
                             "jamais_trouve": round(100 * sum(len(v - set(classement[q])) for q, v in ratt.items()) / max(1, total), 1)}
            print(run.name, out[run.name], flush=True)
    (Z.RUNS / "catalogue-rappel-k.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
