#!/usr/bin/env python3
"""Banc 17 §27 — la consigne de Luna EN ANGLAIS, qualifiée sur LongMemEval (échelle S, une mémoire par question).

100 questions tirées (graine 1109, hors abstention). Pour chacune, sa conversation consolidée session par session dans
une mémoire neuve, comme `preparer.py`, par Luna (effort « low », passages de 10 000 tokens au plus), avec :
  L0 — la consigne anglaise de production du dépôt ;  L1 — la consigne de Luna traduite (`consigne_luna_en.txt`).
Référence : la mémoire du run confirm-lme (gpt-4o-mini, consigne de production) pour les mêmes questions. Puis les
questions, moteur A (`memoire_chercher`), lecteur et juge de docs/13 (gpt-4o-mini), avec le code d'aujourd'hui.

    RUN=luna-en-lme sh lancer.sh luna_en_lme
"""
import json, os, random, shutil, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, "/locomo")
import commun as K
K.preparer_chemins()
from exia_seed import langues
from exia_seed.consolidation import Consolidateur
from exia_seed.requete import Lecteur
import modele
import repondre_lme as RL
import juger_lme as JL

UTC = ZoneInfo("UTC"); IMP = ("user", "assistant")
CONSIGNE_EN = (Path("/lme") / "consigne_luna_en.txt").read_text(encoding="utf-8").strip()
tous = K.charger_donnees([])
ids = sorted(c["sample_id"] for c in tous if not c["qa"][0].get("abstention"))
SEL = random.Random(1109).sample(ids, 100)
convs = {c["sample_id"]: c for c in tous if c["sample_id"] in set(SEL)}


def consolider(qid, variante):
    racine = K.RUN / variante / qid
    if (racine / "fini.json").exists():
        return racine
    if racine.exists(): shutil.rmtree(racine)
    langues.fixer(racine, "en"); raw = racine / "raw"; raw.mkdir(parents=True)
    cons = Consolidateur(racine, UTC, lambda m: modele.appeler(m, "consolidation", modele="gpt-6-luna", max_tokens=32000),
                         modele="gpt-6-luna", max_tokens_entree=10000, nom_agent="assistant", nom_utilisateur="user",
                         consigne="adaptee" if variante == "L1" else "production")
    if variante == "L1":
        import copy
        cons.masque = copy.copy(cons.masque)
        cons.masque.consigne_consolidation_adaptee = lambda locuteur: CONSIGNE_EN.replace("{LOCUTEUR}", locuteur or "user")
    par_jour = {}
    for n, quand, tours in K.sessions(convs[qid]):
        jour = quand.date().isoformat(); par_jour[jour] = par_jour.get(jour, 0) + 1
        nom = f"{jour}_{par_jour[jour]:02d}.md"
        lignes = [f"[{quand:%H:%M} {K.etiquette(t['speaker'])}] {K.texte_du_tour(t)}" for t in tours if K.texte_du_tour(t)]
        (raw / nom).write_text(f"---\ntype: raw\ndate: {jour}\nlang: en\nsession: {n}\nouvert_le: {quand.isoformat()}+00:00\n---\n\n"
                               "## Échanges\n\n" + "\n".join(lignes) + "\n", encoding="utf-8")
        with (raw / ".chaine.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"fichier": nom}) + "\n")
        for _ in range(20):
            avant = list(cons.lots_en_attente())
            if not avant: break
            r = cons.consolider()
            if r.get("statut") not in ("ok", "vide") or list(cons.lots_en_attente()) == avant: break
    (racine / "fini.json").write_text(json.dumps({"perdus": len(cons.lots_en_attente())}))
    return racine


def repondre(mem, q):
    L = Lecteur(mem, implicites=IMP); dates = K.faits_dates(mem)
    c = L.chercher(q["question"], 10, datetime.fromisoformat(q["instant"]), faits_max=K.BUDGET_FAITS)
    faits = [f["fait"] for x in c.get("resultats", []) for f in x["faits"]]
    faits += [p["fait"] for p in (c.get("pistes") or {}).get("faits", []) if p["fait"] not in faits]
    rep = RL.repondre(RL.FAITS, K.contexte(faits[:K.BUDGET_FAITS], dates), q)
    return JL.juger(q, rep)["label"] == "CORRECT"


qs = {q["conv"]: q for q in K.questions(list(convs.values()))}
res = {"reference": [], "L0": [], "L1": []}; perdus = {"L0": 0, "L1": 0}
try:
    for qid in SEL:
        q = qs[qid]
        res["reference"].append(repondre(K.BANC / "runs" / "confirm-lme" / "memoires" / qid, q))
        for v in ("L0", "L1"):
            mem = consolider(qid, v); perdus[v] += json.loads((mem / "fini.json").read_text())["perdus"]
            res[v].append(repondre(mem, q))
        print(qid, q.get("type"), {k: v[-1] for k, v in res.items()}, flush=True)
except modele.BudgetDepasse as e:
    print("⛔", e)
import math
def mc(a, b):
    s1 = sum(x and not y for x, y in zip(a, b)); s2 = sum(y and not x for x, y in zip(a, b)); n = s1 + s2
    return s1, s2, (min(1, 2 * sum(math.comb(n, k) for k in range(min(s1, s2) + 1)) / 2 ** n) if n else 1)
n = len(res["L1"])
bilan = {"questions": n, **{k: round(100 * sum(v[:n]) / max(1, n), 1) for k, v in res.items()}, "lots_perdus": perdus,
         "L1_contre_reference": mc(res["L1"], res["reference"][:n]), "L1_contre_L0": mc(res["L1"], res["L0"][:n]),
         "depense": modele.depense()["total"]}
(K.RUN / "bilan.json").write_text(json.dumps({"bilan": bilan, "detail": res}, indent=1))
print(json.dumps(bilan, indent=1))
