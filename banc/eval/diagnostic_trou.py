#!/usr/bin/env python3
"""N0 — le TROU : les questions dont la preuve est trouvée par les embeddings et ratée par la toile (et l'inverse),
au même budget ; pour chacune, la question partage-t-elle des mots pleins avec la réplique-preuve ? (aucun token)
Hôte : python diagnostic_trou.py <toile.jsonl> <embeddings.jsonl> <budget>"""
import json, re, sys
from pathlib import Path
ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI)); sys.path.insert(0, str(ICI.parent / "harnais"))
import preuves as P
A, B, BUD = sys.argv[1], sys.argv[2], int(sys.argv[3])
ra = P.evaluer(ICI / "runs" / "candidats" / A, [BUD])[BUD]["par_question"]
rb = P.evaluer(ICI / "runs" / "candidats" / B, [BUD])[BUD]["par_question"]
banc = "lme" if "_lme_" in A else "locomo"
gold = P.or_des_questions(banc)
os_ = __import__("os"); os_.environ["LOCOMO_DONNEES"] = str(ICI.parent / "bancs" / "donnees" / ("lme_oracle_locomo.json" if banc == "lme" else "locomo10.json"))
import commun
qs = {q["id"]: q for q in commun.questions(json.loads(Path(commun.DONNEES).read_text(encoding="utf-8")))}
VIDES = set("the a an of to in on and or is are was were do did does what when where who which how why with for at by from i my me you your it this that be have has had".split())
mots = lambda t: {w for w in re.findall(r"[a-z]{3,}", t.lower()) if w not in VIDES}
seul_b = [i for i in ra if not ra[i] and rb.get(i)]; seul_a = [i for i in ra if ra[i] and not rb.get(i)]
def communs(i):
    return len(mots(qs[i]["question"]) & set().union(*[mots(t) for t in gold.get(i, [])] or [set()]))
print(f"{A} contre {B} au budget {BUD} : les deux {sum(1 for i in ra if ra[i] and rb.get(i))} · seulement la toile {len(seul_a)} · seulement les embeddings {len(seul_b)} · aucun {sum(1 for i in ra if not ra[i] and not rb.get(i))}")
for nom, l in (("seulement les embeddings", seul_b), ("seulement la toile", seul_a)):
    c = [communs(i) for i in l]
    print(f"  {nom} : mots pleins communs question / preuve — 0 : {sum(1 for x in c if x == 0)} · 1 : {sum(1 for x in c if x == 1)} · ≥ 2 : {sum(1 for x in c if x >= 2)}")
