#!/usr/bin/env python3
"""Rapport automatique d'un ensemble de passages (PLAN-FCM-EXIA-SEED.md §3 bis) — un capteur que personne ne lit ne
sert à rien : ce rapport est la seule lecture prévue des capteurs.

Pour chaque passage (concurrent × banc × échelle × budget) dont les réponses existent :
  qualité      exactitude (toutes catégories ; LoCoMo : J sur les catégories 1-4, comme Mem0, et l'abstention cat. 5 à part)
               avec intervalle de confiance à 95 % (bootstrap, graine fixe) ; par catégorie / type
  comparaison  test apparié (McNemar exact) contre les concurrents de référence, sur les mêmes questions
  tokens       bloc de contexte (o200k) ; lecteur et juge : entrée / sortie (usage renvoyé par l'appel) ; facturés (hors
               cache) ; TOKENS PAR BONNE RÉPONSE
  temps        rappel à chaud / à froid, mise au budget, lecteur, juge ; BOUT À BOUT (rappel + budget + lecteur) ;
               MS PAR BONNE RÉPONSE ; construction des index ; énergie si la machine l'expose
  ressources   pic de mémoire vive ; éléments donnés ; entonnoir
  santé        non-déterminisme, erreurs, troncatures, saturation des notes, blocs vides, dépassements du budget,
               bruit du juge (rejugement) et du lecteur (relecture)
Hôte : python3 rapport.py [motif de nom] [références séparées par des virgules, défaut S2,R]
"""
from __future__ import annotations

import json
import math
import random
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ICI = Path(__file__).resolve().parent
RUNS = ICI / "runs"
NOM = re.compile(r"^(?P<c>[^_]+)_(?P<b>lme|locomo)_(?P<e>[SF])_(?P<j>[^_]+)_(?P<k>\d+)(?:_(?P<p>[^_]+))?_B(?P<B>\w+)\.jsonl$")


def lire(p: Path):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def cent(v):
    v = sorted(x for x in v if x is not None)
    if not v:
        return {}
    q = lambda p: v[min(len(v) - 1, int(round(p * (len(v) - 1))))]
    return {"p50": round(q(.5), 1), "p90": round(q(.9), 1), "p99": round(q(.99), 1), "max": round(v[-1], 1)}


def ic95(bons, n, graine=1):
    if n == 0:
        return (None, None)
    r = random.Random(graine); x = [1] * bons + [0] * (n - bons)
    s = sorted(sum(r.choice(x) for _ in range(n)) / n for _ in range(2000))
    return (round(100 * s[49], 1), round(100 * s[1949], 1))


def mcnemar(a: dict, b: dict):
    """p exact bilatéral sur les paires discordantes (questions communes)."""
    communs = set(a) & set(b)
    x = sum(1 for i in communs if a[i] and not b[i]); y = sum(1 for i in communs if b[i] and not a[i])
    n = x + y
    if n == 0:
        return x, y, 1.0
    k = min(x, y)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n * 2
    return x, y, round(min(1.0, p), 4)


def passage(f: Path):
    m = NOM.match(f.name)
    rep = lire(f)
    ctx = {c["id"]: c for c in lire(RUNS / "contextes" / f.name)}
    cand_nom = re.sub(r"_P[a-z0-9]+$", "", f.name.rsplit("_B", 1)[0]) + ".jsonl"
    cand = {c["id"]: c for c in lire(RUNS / "candidats" / cand_nom)}
    man_c = json.loads((RUNS / "candidats" / cand_nom.replace(".jsonl", ".manifeste.json")).read_text()) \
        if (RUNS / "candidats" / cand_nom.replace(".jsonl", ".manifeste.json")).exists() else {}
    bons = {r["id"]: r["label"] == "CORRECT" for r in rep}
    hors5 = [r for r in rep if r.get("categorie") != 5]
    cat5 = [r for r in rep if r.get("categorie") == 5]
    u = lambda r, qui, k: ((r.get(qui) or {}).get("usage") or {}).get(k) or 0
    facture = lambda r, qui: 0 if not r.get(qui) or r[qui].get("cache") else u(r, qui, "entree") + u(r, qui, "sortie")
    tok_lect = [u(r, "lecteur", "entree") + u(r, "lecteur", "sortie") for r in rep]
    tok_juge = [u(r, "juge", "entree") + u(r, "juge", "sortie") for r in rep]
    rappel_chaud = [cand[r["id"]]["capteurs"]["chaud"]["ns"].get("requete", 0) / 1e6 for r in rep if "capteurs" in cand.get(r["id"], {})]
    rappel_froid = [cand[r["id"]]["capteurs"]["froid"]["ns"].get("requete", 0) / 1e6 for r in rep if "capteurs" in cand.get(r["id"], {})]
    bout = []
    for r in rep:
        c = cand.get(r["id"], {}).get("capteurs")
        if c and r.get("lecteur") and not r["lecteur"].get("cache"):
            bout.append(c["chaud"]["ns"].get("requete", 0) / 1e6 + ctx.get(r["id"], {}).get("paquet_ns", 0) / 1e6 + r["lecteur"]["ms"])
    ok = sum(bons.values()); n = len(rep)
    sante = defaultdict(int)
    for c in cand.values():
        k = c.get("capteurs", {})
        sante["non_deterministes"] += int(k.get("deterministe") is False)
        sante["erreurs"] += sum(k.get("erreurs", {}).get("par_type", {}).values()) + int("erreur" in c)
        sante["tronques"] += k.get("tronques", 0)
        sante["saturation_alertes"] += int(k.get("saturation", {}).get("alerte", False))
    sante["blocs_vides"] = sum(1 for c in ctx.values() if c["bloc"] == "- (no memories found)")
    sante["depassements_budget"] = sum(1 for c in ctx.values() if m["B"] != "tout" and c["tokens_bloc"] > int(m["B"]))
    bruit = [r["bruit"] for r in rep if r.get("bruit")]
    par_cat = defaultdict(lambda: [0, 0])
    for r in rep:
        cle = str(r.get("categorie")) if m["b"] == "locomo" else (r.get("type") or "?")
        par_cat[cle][0] += r["label"] == "CORRECT"; par_cat[cle][1] += 1
    return {
        "nom": f.name, "concurrent": m["c"], "banc": m["b"], "echelle": m["e"], "jeu": m["j"], "k": int(m["k"]),
        "budget": m["B"], "n": n, "exactitude": round(100 * ok / n, 1) if n else None, "ic95": ic95(ok, n),
        "J_cat1_4": round(100 * sum(r["label"] == "CORRECT" for r in hors5) / len(hors5), 1) if m["b"] == "locomo" and hors5 else None,
        "abstention_cat5": round(100 * sum(r["label"] == "CORRECT" for r in cat5) / len(cat5), 1) if cat5 else None,
        "par_categorie": {k: f"{v[0]}/{v[1]}" for k, v in sorted(par_cat.items())},
        "tokens": {"bloc_moy": round(sum(c["tokens_bloc"] for c in ctx.values()) / max(1, len(ctx)), 1),
                   "lecteur_moy": round(sum(tok_lect) / max(1, n), 1), "juge_moy": round(sum(tok_juge) / max(1, n), 1),
                   "lecteur_sortie_moy": round(sum(u(r, "lecteur", "sortie") for r in rep) / max(1, n), 1),
                   "factures": sum(facture(r, "lecteur") + facture(r, "juge") for r in rep)
                   + sum(sum((x or {}).get("entree", 0) + (x or {}).get("sortie", 0) for x in b.get("usage", [])) for b in bruit),
                   "par_bonne_reponse": round(sum(tok_lect) / ok, 1) if ok else None},
        "temps_ms": {"rappel_chaud": cent(rappel_chaud), "rappel_froid": cent(rappel_froid),
                     "lecteur": cent([r["lecteur"]["ms"] for r in rep if r.get("lecteur") and not r["lecteur"].get("cache")]),
                     "bout_a_bout": cent(bout),
                     "ms_par_bonne_reponse": round(sum(bout) / max(1, len(bout)) * n / ok, 1) if ok and bout else None},
        "ressources": {"ram_pic_mo": (man_c.get("ram") or {}).get("pic_mo"), "duree_s": man_c.get("duree_s"),
                       "energie_j": man_c.get("energie_j"), "encodage_s": man_c.get("encodage_total_s"),
                       "items_donnes_moy": round(sum(c["items_donnes"] for c in ctx.values()) / max(1, len(ctx)), 2)},
        "sante": dict(sante),
        "bruit": {"n": len(bruit), "juge_accord": round(100 * sum(1 for b, r in zip(bruit, [r for r in rep if r.get("bruit")]) if b["rejuge"] == r["label"]) / len(bruit), 1) if bruit else None,
                  "lecteur_accord": round(100 * sum(1 for b, r in zip(bruit, [r for r in rep if r.get("bruit")]) if b["relu"] == r["label"]) / len(bruit), 1) if bruit else None},
        "_bons": bons,
    }


def main() -> int:
    motif = sys.argv[1] if len(sys.argv) > 1 else ""
    refs = (sys.argv[2] if len(sys.argv) > 2 else "S2,R").split(",")
    ps = [passage(f) for f in sorted((RUNS / "reponses").glob("*.jsonl")) if NOM.match(f.name) and motif in f.name]
    groupes = defaultdict(list)
    for p in ps:
        groupes[(p["banc"], p["echelle"], p["jeu"], p["budget"])].append(p)
    L = [f"# Rapport d'évaluation — {datetime.now().strftime('%d/%m/%Y %H:%M')}", "",
         "Lecteur Terra « high », juge Terra « low » (abonnement) — chiffres NON comparables aux classements publics.", ""]
    for (b, e, j, B), g in sorted(groupes.items()):
        L += [f"## {b} · échelle {e} · jeu {j} · budget {B}", "",
              "| Concurrent | n | Exactitude [IC 95] | J cat.1-4 | Bloc (tok) | Lecteur (tok) | Tok / bonne rép. | Rappel à chaud p50 / p99 (ms) | Bout à bout p50 / p99 (ms) | RAM pic (Mo) | Santé |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for p in sorted(g, key=lambda p: p["concurrent"]):
            s = p["sante"]; alertes = ", ".join(f"{k} {v}" for k, v in s.items() if v) or "ok"
            L.append(f"| {p['concurrent']} | {p['n']} | {p['exactitude']} [{p['ic95'][0]}-{p['ic95'][1]}] | {p['J_cat1_4'] if p['J_cat1_4'] is not None else '—'} "
                     f"| {p['tokens']['bloc_moy']} | {p['tokens']['lecteur_moy']} | {p['tokens']['par_bonne_reponse']} "
                     f"| {p['temps_ms']['rappel_chaud'].get('p50')} / {p['temps_ms']['rappel_chaud'].get('p99')} "
                     f"| {p['temps_ms']['bout_a_bout'].get('p50')} / {p['temps_ms']['bout_a_bout'].get('p99')} "
                     f"| {p['ressources']['ram_pic_mo']} | {alertes} |")
        L.append("")
        for ref in refs:
            r = next((p for p in g if p["concurrent"] == ref), None)
            if not r:
                continue
            for p in g:
                if p is r:
                    continue
                x, y, pv = mcnemar(p["_bons"], r["_bons"])
                L.append(f"- {p['concurrent']} contre {ref} : {x} gagnées seul / {y} perdues seul — p = {pv}")
        L.append("")
        for p in sorted(g, key=lambda p: p["concurrent"]):
            L.append(f"- {p['concurrent']} : par catégorie {p['par_categorie']} · bruit {p['bruit']} · tokens facturés {p['tokens']['factures']} "
                     f"· lecteur {p['temps_ms']['lecteur']} · ms/bonne rép. {p['temps_ms']['ms_par_bonne_reponse']} · ressources {p['ressources']}")
        L.append("")
    sortie = ICI / "rapports" / f"rapport_{motif or 'tout'}_{datetime.now().strftime('%Y%m%d-%H%M')}.md"
    sortie.parent.mkdir(exist_ok=True)
    sortie.write_text("\n".join(L), encoding="utf-8")
    sortie.with_suffix(".json").write_text(json.dumps([{k: v for k, v in p.items() if k != "_bons"} for p in ps],
                                                      ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(L)); print(f"\n→ {sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
