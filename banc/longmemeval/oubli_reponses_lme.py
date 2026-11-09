#!/usr/bin/env python3
"""docs/18 §8 — le coût de l'oubli sur les RÉPONSES de LongMemEval (pire cas : aucun rappel entre deux questions).

Pour chaque question dont la mémoire perdrait au moins un fait au jour de la question : la mémoire (confirm-lme,
échelle S) copiée, l'oubli appliqué, le graphe recalculé ; moteur A, lecteur et juge de docs/13 — avant et après
l'oubli, avec le code d'aujourd'hui. Les autres questions ne changent pas.   RUN=oubli-lme sh lancer.sh oubli_reponses_lme
"""
import json, shutil, sys
from datetime import datetime
sys.path.insert(0, "/locomo")
import commun as K
K.preparer_chemins()
from exia_seed import graphe as G
from exia_seed import oubli as O
from exia_seed import pages as P
from exia_seed.requete import Lecteur
import modele
import repondre_lme as RL
import juger_lme as JL

IMP = ("user", "assistant")
import os
TAU = json.loads(os.environ["BANC_TAU"]) if os.environ.get("BANC_TAU") else None      # variante : {"episodic": 30, …}
SRC = K.BANC / "runs" / "confirm-lme" / "memoires"
convs = {c["sample_id"]: c for c in K.charger_donnees(json.loads((K.BANC / "runs" / "confirm-lme" / "selection.json").read_text()))}
qs = {q["conv"]: q for q in K.questions(list(convs.values()))}


def repondre(mem, q):
    L = Lecteur(mem, implicites=IMP); dates = K.faits_dates(mem)
    c = L.chercher(q["question"], 10, datetime.fromisoformat(q["instant"]), faits_max=K.BUDGET_FAITS)
    faits = [f["fait"] for x in c.get("resultats", []) for f in x["faits"]]
    faits += [p["fait"] for p in (c.get("pistes") or {}).get("faits", []) if p["fait"] not in faits]
    rep = RL.repondre(RL.FAITS, K.contexte(faits[:K.BUDGET_FAITS], dates), q)
    return JL.juger(q, rep)["label"] == "CORRECT"


res = []
for qid, q in qs.items():
    src = SRC / qid
    if not (src / "pages").exists():
        continue
    jour = datetime.fromisoformat(q["instant"]).date()
    plan = O.plan(P.lister(src / "pages"), jour, {}, implicites=IMP, tau={**O.TAU, **(TAU or {})})
    if not plan["oublies"]:
        continue
    avant_mem = K.RUN / "avant" / qid; apres_mem = K.RUN / "apres" / qid
    for d in (avant_mem, apres_mem):
        if d.exists(): shutil.rmtree(d)
        shutil.copytree(src, d)
    O.appliquer(apres_mem, plan)
    G.calculer(apres_mem, implicites=IMP)
    try:
        a, b = repondre(avant_mem, q), repondre(apres_mem, q)
    except modele.BudgetDepasse as e:
        print("⛔", e); break
    res.append({"id": qid, "type": q.get("type"), "faits": plan["faits"], "oublies": len(plan["oublies"]), "avant": a, "apres": b})
    print(f"  {qid} {q.get('type')} : {len(plan['oublies'])}/{plan['faits']} oubliés · avant {a} · après {b}", flush=True)
n = len(res)
bilan = {"questions_touchees": n, "justes_avant": sum(r["avant"] for r in res), "justes_apres": sum(r["apres"] for r in res),
         "perdues": sum(r["avant"] and not r["apres"] for r in res), "gagnees": sum(r["apres"] and not r["avant"] for r in res),
         "par_type": {t: {"n": sum(r["type"] == t for r in res), "perdues": sum(r["type"] == t and r["avant"] and not r["apres"] for r in res)}
                      for t in sorted({r["type"] for r in res})},
         "depense": modele.depense()["total"]}
(K.RUN / "bilan.json").write_text(json.dumps({"bilan": bilan, "detail": res}, indent=1))
print(json.dumps(bilan, ensure_ascii=False, indent=1))
