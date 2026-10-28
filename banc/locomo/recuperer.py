#!/usr/bin/env python3
"""Étape 3 — moteurs A (FCM EXIA, 0.9.0) et C (plein texte) : 12 faits au plus par question (docs/09 §2).

La requête est la question elle-même. Deux échelles : S (la mémoire de la conversation) et F (la mémoire
fusionnée). Aucun appel au modèle.

- A : `memoire_chercher` tel que Nexa l'utilise (Lecteur.chercher, pistes comprises), budget 12 faits.
- C : BM25 PUR sur le TEXTE des faits (colonne t de l'index FTS5), les 12 meilleurs — sans le champ lexical
  des concepts, qui est un apport d'EXIA SEED (aux bancs 8-10, le « plein texte » le lisait aussi : déclaré).

En F, aucun fait n'est écarté comme « dit après la question » : les conversations n'ont pas les mêmes dates.

    python3 recuperer.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime

import commun as K

K.preparer_chemins()
from exia_seed import rappel as R                                 # noqa: E402
from exia_seed.requete import Lecteur                             # noqa: E402
from exia_seed import requete as RQ                               # noqa: E402
import os                                                         # noqa: E402
# Variantes du moteur A (docs/09 §14.7-14.8) : LOCOMO_POIDS_SUJET (« ancienne » = l'ancienne note), LOCOMO_ATTENUATION
if os.environ.get("LOCOMO_POIDS_SUJET"):
    RQ.POIDS_SUJET = None if os.environ["LOCOMO_POIDS_SUJET"] == "ancienne" else float(os.environ["LOCOMO_POIDS_SUJET"])
if os.environ.get("LOCOMO_ATTENUATION"):
    RQ.ATTENUATION_AUTRE = float(os.environ["LOCOMO_ATTENUATION"])
from exia_seed import graphe as G                                 # noqa: E402

TRES_TARD = datetime(2100, 1, 1)


def bm25(lecteur: Lecteur, question: str):
    m = lecteur.r.memoire()
    if m is None:                                            # mémoire vide (LongMemEval, docs/13 §11) : rien à chercher
        return []
    vides = R._mots_vides(m.masque)
    mots = [w for w in dict.fromkeys(G._norm(question).split()) if len(w) >= 3 and w not in vides and not w.isdigit()]
    if not mots:
        return []
    try:
        lignes = m.fts.execute("select rowid from f where f match ? order by bm25(f, 1.0, 0.0) limit ?",
                               (" OR ".join(f't:"{w}"' for w in mots), K.BUDGET_FAITS)).fetchall()
    except Exception:
        return []
    return [m.faits[i]["texte"] for (i,) in lignes]


def fcm(lecteur: Lecteur, question: str, instant: datetime):
    c = lecteur.chercher(question, 10, instant, faits_max=K.BUDGET_FAITS)
    faits = [f["fait"] for x in c.get("resultats", []) for f in x["faits"]]
    faits += [p["fait"] for p in (c.get("pistes") or {}).get("faits", []) if p["fait"] not in faits]
    return faits[:K.BUDGET_FAITS]


def main() -> int:
    convs = K.charger_donnees(K.selection_du_run())
    parleurs = {c["sample_id"]: (K.etiquette(c["conversation"]["speaker_a"]), K.etiquette(c["conversation"]["speaker_b"])) for c in convs}
    f = K.RUN / "fusion.json"                                # en F : les noms tels que la fusion les a écrits
    tous_parleurs = tuple(json.loads(f.read_text())["implicites"]) if f.exists() else tuple(p for v in parleurs.values() for p in v)
    if not K.IMPLICITES:                                     # docs/09 §14.5 : aucun interlocuteur implicite
        parleurs = {c: () for c in parleurs}
        tous_parleurs = ()
        for c in parleurs:                                   # graphe de chaque conversation recalculé sans eux
            G.calculer(K.RUN / "memoires" / c, implicites=())
    qs = K.questions(convs)
    fusion = K.RUN / "memoires" / "_fusion"
    lecteurs = {}
    for echelle in ("S", "F"):
        if echelle == "F" and not fusion.exists():
            print("  (pas de mémoire fusionnée : échelle F sautée)"); continue
        sorties = {"A": [], "C": []}
        for q in qs:
            mem = fusion if echelle == "F" else K.RUN / "memoires" / q["conv"]
            if mem not in lecteurs:
                lecteurs[mem] = Lecteur(mem, implicites=tous_parleurs if echelle == "F" else parleurs[q["conv"]])
            L = lecteurs[mem]
            instant = TRES_TARD if echelle == "F" else datetime.fromisoformat(q["instant"])
            t0 = time.perf_counter(); fa = fcm(L, q["question"], instant); ta = (time.perf_counter() - t0) * 1000
            t0 = time.perf_counter(); fc = bm25(L, q["question"]); tc = (time.perf_counter() - t0) * 1000
            sorties["A"].append({"id": q["id"], "faits": fa, "latence_ms": round(ta, 2)})
            sorties["C"].append({"id": q["id"], "faits": fc, "latence_ms": round(tc, 2)})
        for moteur, lignes in sorties.items():
            K.ecrire_jsonl(K.RUN / "contextes" / f"{moteur}_{echelle}.jsonl", lignes)
            lat = sorted(l["latence_ms"] for l in lignes)
            print(f"  {moteur}_{echelle} : {len(lignes)} questions · {sum(len(l['faits']) for l in lignes) / max(1, len(lignes)):.1f} faits "
                  f"en moyenne · p50 {lat[len(lat) // 2]:.1f} ms · p95 {lat[int(0.95 * len(lat)) - 1]:.1f} ms", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
