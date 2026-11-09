#!/usr/bin/env python3
"""§14.2 — pourquoi la recherche classe mal les pages que Terra choisit (diagnostic, sans modèle)."""
import re, sys, json
from collections import defaultdict, Counter
sys.path.insert(0, "/locomo"); sys.path.insert(0, "/lme")
import commun as K
K.preparer_chemins()
from exia_seed.rappel import Rappeleur
import catalogue_lme as C
import comparer_catalogue_lme as Z
Z.RUNS = K.BANC / "runs"; Z.BASE = Z.RUNS / "catalogue-base" / "memoires" / "_fusion"
noeud = {p.name: Z.noeud_de(p) for p in (Z.BASE / "pages").glob("*.md")}
presents = set(noeud.values()) - set(C.IMPLICITES)
R = Rappeleur(Z.BASE, implicites=C.IMPLICITES); mem = R.memoire()
run = Z.RUNS / "catalogue-terra-complet-1"; m = run / "memoire"; pg = Z.pages(m)
ratt = defaultdict(set)
for page, lignes in pg.items():
    if page in noeud and noeud[page] not in C.IMPLICITES:
        for f, _ in lignes:
            x = Z.RAW_Q.match(f)
            if x: ratt[x.group(1)].add(noeud[page])
etage_des_rates, etage_top, n_direct, par_msg_rang, unions = Counter(), Counter(), [], [], defaultdict(list)
for q, choisies in ratt.items():
    textes = []
    for f in sorted((m / "raw").glob(f"{q}_*.md")):
        cour = ""
        for l in f.read_text(encoding="utf-8").splitlines():
            if re.match(r"\[\d\d:\d\d ", l):
                if cour: textes.append(cour)
                cour = l
            elif cour and l.strip(): cour += " " + l
        if cour: textes.append(cour)
    score, etage, rang_msg = {}, {}, defaultdict(lambda: 10**6)
    for t in textes:
        a = R.activer(mem, t)
        loc = {}
        for et, lst in a["etages"].items():
            for e in lst:
                n = e.split("→", 1)[1]
                v = 1.0 + a["entrees"].get(n, 0)
                if v > score.get(n, 0): score[n], etage[n] = v, et
                if n in presents: loc[n] = max(loc.get(n, 0), v)
        for n, v in a["actives"].items():
            if v > score.get(n, 0): score[n], etage[n] = v, "propagation"
            if n in presents: loc[n] = max(loc.get(n, 0), v)
        for i, n in enumerate(sorted(loc, key=loc.get, reverse=True)):
            rang_msg[n] = min(rang_msg[n], i)
    for k in (5, 10, 30):
        unions[k].append(sum(1 for n, r in rang_msg.items() if r < k))
    unions["messages"].append(len(textes))
    classes = [n for n in sorted(score, key=score.get, reverse=True) if n in presents]
    n_direct.append(sum(1 for n in classes if score[n] >= 1.0))
    for n in classes[:30]: etage_top[etage[n]] += 1
    for n in choisies:
        r = classes.index(n) if n in classes else None
        if r is None or r >= 30:
            etage_des_rates[etage.get(n, "jamais")] += 1
        par_msg_rang.append(rang_msg[n])
print("pages touchées DIRECTEMENT par lot (score ≥ 1) : moyenne", round(sum(n_direct) / len(n_direct)), "max", max(n_direct))
print("comment les 30 premières sont entrées :", dict(etage_top))
print("comment entrent les pages choisies par Terra mais hors des 30 :", dict(etage_des_rates))
tot = len(par_msg_rang)
for k in (5, 10, 30):
    print(f"part des pages choisies dans le top {k} d'AU MOINS UN message : {100 * sum(r < k for r in par_msg_rang) / tot:.1f} %")
for k, v in unions.items():
    print(f"union par question, {k} : moyenne {sum(v) / len(v):.0f}, max {max(v)}")
