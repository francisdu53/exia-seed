#!/usr/bin/env python3
"""Phase 0 — concurrents à EMBEDDINGS (l'industrie) : la liste classée pour chaque question, avec les mêmes capteurs.

  R    RAG dense : bge-m3 (cosinus) sur le BRUT découpé en tours (deux répliques consécutives, sans recouvrement —
       la granularité « round » que LongMemEval recommande) ; ce que fait l'industrie, sans consolidation.
  Rh   RAG hybride : plein texte (BM25 Okapi, k1 1,2, b 0,75) + bge-m3 sur les mêmes tours, fusion des rangs (RRF, k 60)
       — la recherche hybride que Karpathy suggère pour un wiki qui grandit.
  Rp   bge-m3 sur les SOUVENIRS consolidés (même mémoire que SEED : isole « FCM contre embeddings » ; moteur B d'octobre).
Pas de reranker (décision de Francis du 21/11 : en option seulement).

HÔTE (venv d'EXIA GHOST, bge-m3 en cache local), au plus bas niveau de priorité et sur EVAL_FILS fils (1 par défaut) :
  nice -n 19 env HF_HUB_OFFLINE=1 ${PYTHON_EMBEDDINGS:-python3} fournir_rag.py R lme F test 60
Vecteurs mis en cache sur disque (`vecteurs/`), par empreinte du texte : la construction ne se paie qu'une fois et
l'échelle S réutilise ceux de l'échelle F. Capteurs : chargement du modèle, encodage (temps, nombre), construction par
mémoire, par requête (encodage de la question, recherche dense, plein texte, fusion), déterminisme (deux appels), RAM,
énergie si la machine l'expose.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
CONC, BANC, ECHELLE, JEU, K = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
LIMITE = int(os.environ.get("EVAL_LIMITE", "0"))
sys.path.insert(0, str(ICI)); sys.path.insert(0, str(ICI.parent / "harnais"))
os.environ["LOCOMO_DONNEES"] = str(ICI.parent / "bancs" / "donnees" / ("lme_oracle_locomo.json" if BANC == "lme" else "locomo10.json"))
import commun as KH                                           # noqa: E402
import capteurs as C                                           # noqa: E402
import bruit as BQ                                         # noqa: E402
import echelle as EC                                       # noqa: E402

TOUR = re.compile(r"^\[(\d\d:\d\d) ([^\]]+)\] (.*)$")
FAIT = re.compile(r"^- (.*?) <!-- (.*?) -->\s*$")
MOT = re.compile(r"\w+", re.UNICODE)
H = lambda t: hashlib.sha1(t.encode()).hexdigest()


def date_lisible(d: str) -> str:
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%-d %B %Y")
    except Exception:
        return ""


def tours_du_brut(memoire: Path):
    """Les tours (2 répliques consécutives) de chaque fichier de brut, avec la date et la ligne de la 1re réplique."""
    sortie = []
    for f in sorted((memoire / "raw").glob("*.md")):
        lignes = f.read_text(encoding="utf-8").splitlines()
        date = next((l.split(":", 1)[1].strip() for l in lignes[:12] if l.startswith("date:")), "")
        repliques, dedans = [], False
        for n, l in enumerate(lignes, start=1):
            if l.startswith("## Échanges"):
                dedans = True; continue
            if not dedans or not l.strip() or l.lstrip().startswith("<!--"):
                continue
            m = TOUR.match(l)
            if m:
                repliques.append([n, f"{m.group(2)}: {m.group(3)}"])
            elif repliques:
                repliques[-1][1] += " " + l.strip()
        for k in range(0, len(repliques), 2):
            bloc = repliques[k:k + 2]
            sortie.append({"type": "tour", "texte": "\n".join(r[1] for r in bloc), "date": date_lisible(date),
                           "src": [f.name, bloc[0][0]], "lignes": [r[0] for r in bloc]})
    return sortie


def faits_des_pages(memoire: Path):
    sortie = []
    for p in sorted((memoire / "pages").glob("*.md")):
        for l in p.read_text(encoding="utf-8").splitlines():
            m = FAIT.match(l)
            if m:
                d = re.search(r"(?:^| )dit_le:(\d{4}-\d{2}-\d{2})", m.group(2))
                s = re.search(r"src:raw/([^ :]+):(\d+)", m.group(2))
                sortie.append({"type": "fait", "texte": m.group(1).strip(), "date": date_lisible(d.group(1)) if d else "",
                               "src": [s.group(1), int(s.group(2))] if s else "", "page": p.stem,
                               "refs": [[a, int(b)] for a, b in re.findall(r"src:raw/([^ :]+):(\d+)", m.group(2))]})
    return sortie


class BM25:
    def __init__(self, textes, k1=1.2, b=0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(MOT.findall(t.lower())) for t in textes]
        self.long = [sum(d.values()) for d in self.docs]
        self.moy = sum(self.long) / max(1, len(self.long))
        df = Counter(w for d in self.docs for w in d)
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.inv = defaultdict(list)
        for i, d in enumerate(self.docs):
            for w, c in d.items():
                self.inv[w].append((i, c))

    def chercher(self, requete, k):
        s = defaultdict(float)
        for w in set(MOT.findall(requete.lower())):
            for i, c in self.inv.get(w, ()):
                s[i] += self.idf[w] * c * (self.k1 + 1) / (c + self.k1 * (1 - self.b + self.b * self.long[i] / self.moy))
        return sorted(s.items(), key=lambda x: -x[1])[:k]


class Vecteurs:
    """Cache disque texte → vecteur (bge-m3 normalisé), par banc et par sorte d'unité."""
    def __init__(self, modele, nom):
        self.modele, self.f = modele, ICI / "vecteurs" / f"{nom}.npz"
        self.f.parent.mkdir(exist_ok=True)
        self.v = {}
        autre = self.f.with_name(self.f.name.replace("locomo_", "lme_") if self.f.name.startswith("locomo_") else self.f.name.replace("lme_", "locomo_"))
        for g in (autre, self.f):                       # le banc lui-même en dernier (il l'emporte)
            if g.exists():
                z = np.load(g, allow_pickle=False)
                self.v.update(zip(z["cles"].tolist(), z["m"]))
        self.encodes, self.ns = 0, 0

    def matrice(self, textes):
        manquants = list(dict.fromkeys(t for t in textes if H(t) not in self.v))
        for k in range(0, len(manquants), 64):
            lot = manquants[k:k + 64]
            t0 = time.perf_counter_ns()
            for t, v in zip(lot, self.modele.encode(lot, normalize_embeddings=True, batch_size=16)):
                self.v[H(t)] = v.astype(np.float32)
            self.ns += time.perf_counter_ns() - t0; self.encodes += len(lot)
            if (k // 64) % 20 == 19:
                self.sauver(); print(f"    encodés {self.encodes}/{len(manquants)}", flush=True)
        if manquants:
            self.sauver()
        return np.stack([self.v[H(t)] for t in textes]) if textes else np.zeros((0, 1024), np.float32)

    def sauver(self):
        cles = list(self.v)
        np.savez(self.f.with_suffix(".tmp.npz"), cles=np.array(cles), m=np.stack([self.v[c] for c in cles]))
        os.replace(self.f.with_suffix(".tmp.npz"), self.f)


def main() -> int:
    import torch
    torch.set_num_threads(int(os.environ.get("EVAL_FILS", "1")))
    scelle = json.loads((ICI / "scelle.json").read_text(encoding="utf-8"))
    ids = set(scelle[BANC][JEU]) if JEU in scelle[BANC] else (set(json.loads((ICI / "scelle_verdict.json").read_text(encoding="utf-8"))[BANC]) if JEU == "verdict2" else set(scelle[BANC]["test"][:int(JEU.split("-")[1])]))
    qs = sorted((q for q in KH.questions(json.loads(Path(KH.DONNEES).read_text(encoding="utf-8"))) if q["id"] in ids),
                key=lambda q: (q["conv"], q["id"]))
    if LIMITE:
        qs = qs[:LIMITE]
    for q in qs:                                                # test 2 : question abîmée (EVAL_BRUITQ)
        q["question"] = BQ.bruiter(q["question"], q["id"])
    e0 = C.energie(); t_debut = time.perf_counter()
    ch0 = C.Chrono()
    with ch0.etape("chargement_modele"):
        from sentence_transformers import SentenceTransformer
        modele = SentenceTransformer("BAAI/bge-m3", device="cpu")
        modele.max_seq_length = 512
    ram_modele = C.memoire()
    vect = Vecteurs(modele, f"{BANC}_{'faits' if CONC == 'Rp' else 'tours'}")
    racine = ICI / "memoires" / BANC
    sortie = ICI / "runs" / "candidats" / (os.environ.get("EVAL_SORTIE") or f"{CONC}_{BANC}_{ECHELLE}_{JEU}_{K}.jsonl")
    sortie.parent.mkdir(parents=True, exist_ok=True)
    etat, constructions, lignes = {}, [], []
    err_global = C.Erreurs()
    for n, q in enumerate(qs):
        d = EC.dossier(racine, q["conv"], ECHELLE)
        if d not in etat:
            etat.clear(); ch = C.Chrono(); enc0, ns0 = vect.encodes, vect.ns
            try:
                with ch.etape("lecture"):
                    unites = faits_des_pages(d) if CONC == "Rp" else tours_du_brut(d)
                with ch.etape("vecteurs"):
                    M = vect.matrice([u["texte"] for u in unites])
                bm = None
                if CONC == "Rh":
                    with ch.etape("index_plein_texte"):
                        bm = BM25([u["texte"] for u in unites])
                etat[d] = (unites, M, bm)
                constructions.append({"memoire": d.name, "unites": len(unites), "encodes": vect.encodes - enc0,
                                      "encodage_s": round((vect.ns - ns0) / 1e9, 2), **ch.releve(), "ram": C.memoire()})
            except Exception as e:
                err_global.noter(e, "construction"); etat[d] = None
        if etat.get(d) is None:
            lignes.append({"id": q["id"], "items": [], "erreur": "construction"}); continue
        unites, M, bm = etat[d]
        err = C.Erreurs(); res = []
        for passe in ("froid", "chaud"):
            ch = C.Chrono()
            try:
                with ch.etape("requete"):
                    with ch.etape("encodage_question"):
                        v = modele.encode([q["question"]], normalize_embeddings=True)[0]
                    with ch.etape("recherche_dense"):
                        s = M @ v if len(unites) else np.zeros(0)
                        haut = np.argsort(-s)[:max(K, 100)].tolist()
                    if CONC == "Rh":
                        with ch.etape("plein_texte"):
                            pt = [i for i, _ in bm.chercher(q["question"], max(K, 100))]
                        with ch.etape("fusion"):
                            rrf = defaultdict(float)
                            for liste in (haut, pt):
                                for r, i in enumerate(liste):
                                    rrf[i] += 1 / (60 + r + 1)
                            ordre = [i for i, _ in sorted(rrf.items(), key=lambda x: (-x[1], x[0]))][:K]
                            notes = [round(rrf[i], 5) for i in ordre]
                    else:
                        ordre = haut[:K]; notes = [round(float(s[i]), 5) for i in ordre]
            except Exception as e:
                err.noter(e, passe); ordre, notes = [], []
            res.append((ordre, notes, ch.releve()))
        (ordre, notes, chrono_froid), (ordre2, _, chrono_chaud) = res
        items = [{**unites[i], "note": notes[k]} for k, i in enumerate(ordre)]
        lignes.append({"id": q["id"], "categorie": q.get("categorie"), "type": q.get("type"), "items": items,
                       "capteurs": {"froid": chrono_froid, "chaud": chrono_chaud,
                                    "entonnoir": {"unites": len(unites), "donnes": len(items)},
                                    "deterministe": ordre == ordre2, "tronques": 0,
                                    "saturation": C.saturation(notes), "erreurs": err.releve()}})
        if (n + 1) % 50 == 0:
            print(f"  {n + 1}/{len(qs)}", flush=True)
    duree = time.perf_counter() - t_debut; e1 = C.energie()
    KH.ecrire_jsonl(sortie, lignes)
    man = C.manifeste(bruit=BQ.MODE, memoire=EC.MEM, concurrent=CONC, banc=BANC, echelle=ECHELLE, jeu=JEU, k=K, modele="BAAI/bge-m3 (max_seq 512, CPU)",
                      fils=int(os.environ.get("EVAL_FILS", "1")), chargement=ch0.releve(), ram_apres_modele=ram_modele,
                      questions=len(qs), duree_s=round(duree, 2), encodes_total=vect.encodes,
                      encodage_total_s=round(vect.ns / 1e9, 2), energie_j=round(e1 - e0, 2) if e0 is not None and e1 is not None else None,
                      ram=C.memoire(), constructions=constructions[:50], nb_constructions=len(constructions),
                      erreurs_construction=err_global.releve())
    sortie.with_suffix(".manifeste.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    chaud = [l["capteurs"]["chaud"]["ns"].get("requete", 0) / 1e6 for l in lignes if "capteurs" in l]
    nd = sum(1 for l in lignes if not l.get("capteurs", {}).get("deterministe", True))
    print(f"{sortie.name} : {len(lignes)} q · {sum(len(l['items']) for l in lignes) / max(1, len(lignes)):.1f} items · "
          f"à chaud {C.centiles(chaud)} · non déterministes {nd} · encodés {vect.encodes} en {vect.ns / 1e9:.0f} s · RAM {C.memoire()}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
