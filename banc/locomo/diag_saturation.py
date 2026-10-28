#!/usr/bin/env python3
"""Réglage GRATUIT de la note anti-saturation et du speaker (docs/09 §14.7-14.8) — aucun appel au modèle.

Pour chaque variante (POIDS_SUJET, ATTENUATION_AUTRE) : contextes du moteur A (S et F, sans implicites) pour les questions
des conversations données, puis deux mesures sans juge :
  - « réponse présente » : part des mots pleins de la réponse attendue trouvés dans les 12 faits (≥ 0,5 = présente) ;
  - « contextes partagés » : questions dont le contexte est identique à celui d'une autre (la saturation).
    python3 diag_saturation.py RUN conv-26 conv-30
"""
import collections, json, os, re, sys
sys.path.insert(0, "/locomo")
os.environ["LOCOMO_RUN"] = sys.argv[1]
import commun as K
K.preparer_chemins()
from exia_seed import graphe as G, requete as RQ
from exia_seed.requete import Lecteur
import recuperer as RC

convs = sys.argv[2:]
VIDES = set("the a an of in on at to and or for with did does do is was were what when where who how why which her his their"
            " she he they has have had be been that this from by as it its about".split())
def mots(s): return [w for w in re.findall(r"[a-z0-9]+", str(s).lower()) if len(w) >= 3 and w not in VIDES]
qs = [q for q in K.questions(K.charger_donnees(convs)) if q.get("categorie", q.get("category")) != 5]
D = {f"{s['sample_id']}:{k}": x for s in json.load(open(K.DONNEES)) for k, x in enumerate(s["qa"])}
qs = [q for q in qs if D[q["id"]].get("category") != 5]
for c in convs:
    G.calculer(K.RUN / "memoires" / c, implicites=())
def mesurer(nom):
    sortie = {}
    for ech in ("S", "F"):
        lect = {}
        pres = 0; ctx = {}
        for q in qs:
            mem = K.RUN / "memoires" / ("_fusion" if ech == "F" else q["conv"])
            L = lect.setdefault(mem, Lecteur(mem, implicites=()))
            fs = RC.fcm(L, q["question"], RC.TRES_TARD if ech == "F" else __import__("datetime").datetime.fromisoformat(q["instant"]))
            ctx[q["id"]] = tuple(fs)
            rep = mots(D[q["id"]].get("answer", "")); txt = set(mots(" ".join(fs)))
            pres += bool(rep) and sum(w in txt for w in rep) / len(rep) >= 0.5
        cnt = collections.Counter(ctx.values())
        sortie[ech] = (pres, sum(v for v in cnt.values() if v > 1))
        with open(f"/var/sortie/{nom}_{ech}.jsonl", "w") as f:
            for i, v in ctx.items(): f.write(json.dumps({"id": i, "faits": list(v)}, ensure_ascii=False) + "\n")
    print(f"{nom:18s} S: présente {sortie['S'][0]}/{len(qs)} partagés {sortie['S'][1]:3d} | F: présente {sortie['F'][0]}/{len(qs)} partagés {sortie['F'][1]:3d}", flush=True)
VARIANTES = [("ancienne", None, 0.0), ("p0.5", 0.5, 0.0), ("p0.25", 0.25, 0.0), ("p0.1", 0.1, 0.0), ("p0", 0.0, 0.0),
             # §14.8 : lecture du speaker, sur la note retenue (0,25)
             ("eventail", "eventail", 0.5), ("eventail_sans_spk", "eventail", 0.0), ("spk0.25", 0.25, 0.25), ("spk0.5", 0.25, 0.5), ("spk0.75", 0.25, 0.75), ("spk1", 0.25, 1.0)]
if os.environ.get("VARIANTES"):
    VARIANTES = [v for v in VARIANTES if v[0] in os.environ["VARIANTES"].split(",")]
for nom, p, att in VARIANTES:
    RQ.POIDS_SUJET, RQ.ATTENUATION_AUTRE = p, att
    mesurer(nom)
