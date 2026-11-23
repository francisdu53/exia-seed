#!/usr/bin/env python3
"""Phase 0 — concurrents EXIA SEED : la liste classée des souvenirs pour chaque question, avec les capteurs.

  S1  `memoire_chercher` (requete.Lecteur, poids du sujet « ancienne » comme chez Nexa) — identique à la 0.9.15
      (contrôle d'équivalence du 20/11) ; code = la 1.0.0 figée (`paquets/seed-1.0.0`).
  S2  la montre 1.0.0 en mode recherche (pas de seuil de silence, pas de continuité, au plus `faits_max`).
Sortie : `runs/candidats/<concurrent>_<banc>_<échelle>_<k>.jsonl` (une ligne par question) + `.manifeste.json`.
Le budget de tokens est appliqué ENSUITE, par `paqueter.py`, de la même façon pour tous les concurrents.

Capteurs par question : temps mur et CPU (requête à froid = premier appel sur une mémoire, avec ses caches paresseux ;
requête à chaud = second appel identique), DÉTERMINISME (les deux appels doivent rendre la même liste), entonnoir,
saturation des notes, troncature (chaque texte rendu doit être le texte complet d'un fait des pages), erreurs comptées.
Construction par mémoire (graphe, rappeleur, lecteur, montre) chronométrée à part.

Conteneur Nexa (le paquet importe Hermès) :
  docker exec -u 10000 -w /opt/data/workspace/banc-cartes/eval nexa /opt/hermes/.venv/bin/python3 \
      fournir_seed.py S2 lme F test 12
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ICI = Path(__file__).resolve().parent
CONC, BANC, ECHELLE, JEU, K = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
PAQUET = os.environ.get("EVAL_PAQUET", "seed-1.0.0")
LIMITE = int(os.environ.get("EVAL_LIMITE", "0"))
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, str(ICI / "paquets" / PAQUET)); sys.path.insert(0, str(ICI))
sys.path.insert(0, str(ICI.parent / "harnais"))
os.environ["LOCOMO_DONNEES"] = str(ICI.parent / "bancs" / "donnees" / ("lme_oracle_locomo.json" if BANC == "lme" else "locomo10.json"))
import commun as KH                                         # noqa: E402
import capteurs as C                                         # noqa: E402
import bruit as BQ                                         # noqa: E402
import echelle as EC                                       # noqa: E402
from exia_seed import graphe as G                            # noqa: E402
from exia_seed import montre as MO                           # noqa: E402
from exia_seed import rappel as R                            # noqa: E402
from exia_seed import requete as Q                           # noqa: E402

TRES_TARD = datetime(2100, 1, 1)
IMPLICITES = ("user", "assistant") if BANC == "lme" else ()
Q.POIDS_SUJET = "ancienne"


def date_lisible(d):
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%-d %B %Y")
    except Exception:
        return ""


def main() -> int:
    scelle = json.loads((ICI / "scelle.json").read_text(encoding="utf-8"))
    ids = set(scelle[BANC][JEU]) if JEU in scelle[BANC] else (set(json.loads((ICI / "scelle_verdict.json").read_text(encoding="utf-8"))[BANC]) if JEU == "verdict2" else set(scelle[BANC]["test"][:int(JEU.split("-")[1])]))
    qs = [q for q in KH.questions(json.loads(Path(KH.DONNEES).read_text(encoding="utf-8"))) if q["id"] in ids]
    qs.sort(key=lambda q: (q["conv"], q["id"]))                 # une mémoire après l'autre (caches)
    if LIMITE:
        qs = qs[:LIMITE]
    for q in qs:                                                # test 2 : question abîmée (EVAL_BRUITQ)
        q["question"] = BQ.bruiter(q["question"], q["id"])
    racine = ICI / "memoires" / BANC
    sortie = ICI / "runs" / "candidats" / (os.environ.get("EVAL_SORTIE") or f"{CONC}_{BANC}_{ECHELLE}_{JEU}_{K}{'' if PAQUET == 'seed-1.0.0' else '_' + PAQUET}.jsonl")
    sortie.parent.mkdir(parents=True, exist_ok=True)
    marque = f".graphe-{PAQUET}"
    etat, constructions, lignes = {}, [], []
    err_global = C.Erreurs()
    e0 = C.energie(); t_debut = time.perf_counter()
    for n, q in enumerate(qs):
        d = EC.dossier(racine, q["conv"], ECHELLE)
        if d not in etat:
            etat.clear()
            ch = C.Chrono()
            try:
                if not (d / marque).exists():
                    with ch.etape("graphe"):
                        G.calculer(d, implicites=IMPLICITES)
                    (d / marque).write_text(PAQUET)
                with ch.etape("rappeleur"):
                    rp = R.Rappeleur(d, implicites=IMPLICITES); m = rp.memoire()
                with ch.etape("moteur"):
                    if CONC == "S1":
                        moteur = Q.Lecteur(d, implicites=IMPLICITES, rappeleur=rp, poids_sujet="ancienne")
                    else:
                        moteur = MO.Montre(rp, continuite=False, seuil=0.0, max=K, garde_fou=10**6)   # comme la production (__init__.py:430)
                index = {f["texte"]: f for f in m.faits}
                etat[d] = (rp, m, moteur, index)
                constructions.append({"memoire": d.name, "faits": len(m.faits), **ch.releve(), "ram": C.memoire()})
            except Exception as e:
                err_global.noter(e, "construction"); etat[d] = None
        if etat.get(d) is None:
            lignes.append({"id": q["id"], "items": [], "erreur": "construction"}); continue
        rp, m, moteur, index = etat[d]
        instant = TRES_TARD if ECHELLE == "F" else datetime.fromisoformat(q["instant"])
        err = C.Erreurs()

        def interroger():
            if CONC == "S1":
                c = moteur.chercher(q["question"], 10, instant, faits_max=K)
                fa = [f["fait"] for y in c.get("resultats", []) for f in y["faits"]]
                fa = (fa + [p["fait"] for p in (c.get("pistes") or {}).get("faits", []) if p["fait"] not in fa])[:K]
                return fa, [], [], {"pages": len(c.get("resultats", [])), "pistes": len((c.get("pistes") or {}).get("faits", []))}
            x = moteur.rappeler(q["question"], instant)
            return ([m.faits[i]["texte"] for i in x["faits"]], x.get("notes", []), x.get("raisons", []),
                    {"allumes": x.get("candidats", 0), "donnes": len(x["faits"])})
        sorties = []
        for passe in ("froid", "chaud"):
            ch = C.Chrono()
            try:
                with ch.etape("requete"):
                    res = interroger()
            except Exception as e:
                err.noter(e, passe); res = (None, [], [], {})
            sorties.append((res, ch.releve()))                  # relevé APRÈS la fin de l'étape
        (textes, notes, raisons, entonnoir), chrono_froid = sorties[0]
        (textes2, *_), chrono_chaud = sorties[1]
        textes = textes or []
        items = []
        for k, t in enumerate(textes):
            f = index.get(t)
            items.append({"type": "fait", "texte": t, "date": date_lisible((f or {}).get("dit_le") or ""),
                          "src": min((f or {}).get("refs") or [""], key=str) if f else "", "page": (f or {}).get("noeud", ""),
                          "refs": sorted([list(r) for r in ((f or {}).get("refs") or ())], key=str),
                          "raison": raisons[k] if k < len(raisons) else ""})
        lignes.append({"id": q["id"], "categorie": q.get("categorie"), "type": q.get("type"), "items": items,
                       "capteurs": {"froid": chrono_froid, "chaud": chrono_chaud, "entonnoir": entonnoir,
                                    "deterministe": textes == (textes2 or []),
                                    "tronques": sum(1 for t in textes if t not in index),
                                    "saturation": C.saturation(notes), "erreurs": err.releve()}})
        if (n + 1) % 50 == 0:
            print(f"  {n + 1}/{len(qs)}", flush=True)
    duree = time.perf_counter() - t_debut; e1 = C.energie()
    KH.ecrire_jsonl(sortie, lignes)
    man = C.manifeste(bruit=BQ.MODE, memoire=EC.MEM, concurrent=CONC, banc=BANC, echelle=ECHELLE, jeu=JEU, k=K, paquet=PAQUET,
                      code_moteur=C.empreinte_dossier(ICI / "paquets" / PAQUET / "exia_seed"),
                      poids_montre=C.empreinte_fichiers([ICI / "paquets" / PAQUET / "exia_seed" / "montre_poids.json"]),
                      questions=len(qs), duree_s=round(duree, 2), energie_j=round(e1 - e0, 2) if e0 is not None and e1 is not None else None,
                      ram=C.memoire(), constructions=constructions, erreurs_construction=err_global.releve())
    sortie.with_suffix(".manifeste.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    nd = sum(1 for l in lignes if not l.get("capteurs", {}).get("deterministe", True))
    ne = sum(sum(l.get("capteurs", {}).get("erreurs", {}).get("par_type", {}).values()) for l in lignes)
    chaud = [l["capteurs"]["chaud"]["ns"].get("requete", 0) / 1e6 for l in lignes if "capteurs" in l]
    print(f"{sortie.name} : {len(lignes)} q · {sum(len(l['items']) for l in lignes) / max(1, len(lignes)):.1f} items · "
          f"à chaud {C.centiles(chaud)} · non déterministes {nd} · erreurs {ne} · RAM {C.memoire()}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
