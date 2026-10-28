#!/usr/bin/env python3
"""Étape 3 bis (HÔTE) — moteur B : embeddings bge-m3, cosinus, les 12 faits les plus proches (docs/09 §2).

Le modèle d'EXIA GHOST V2.7.x, hors ligne depuis le cache. Les faits sont lus dans les pages (même règle que
graphe._lire : « - fait <!-- métadonnées --> »), sans le paquet exia_seed (il importe Hermès, absent de l'hôte).
Mesure aussi le chargement, la mémoire vive et la latence par requête.

    LOCOMO_BANC=$HOME/banc-locomo LOCOMO_RUN=pilote HF_HUB_OFFLINE=1 \\
        ${PYTHON_EMBEDDINGS:-python3} embeddings.py
"""
from __future__ import annotations

import json
import re
import resource
import sys
import time

import numpy as np

import commun as K

_FAIT = re.compile(r"^- (.*?) <!--.*-->\s*$")


def faits_de(memoire):
    return [m.group(1).strip() for p in sorted((memoire / "pages").glob("*.md"))
            for l in p.read_text(encoding="utf-8").splitlines() for m in [_FAIT.match(l)] if m]


def main() -> int:
    convs = K.charger_donnees(K.selection_du_run())
    qs = K.questions(convs)
    t0 = time.perf_counter()
    from sentence_transformers import SentenceTransformer
    modele = SentenceTransformer("BAAI/bge-m3", device="cpu")
    chargement = time.perf_counter() - t0
    vecteurs, matrices = {}, {}
    fusion = K.RUN / "memoires" / "_fusion"
    for echelle in ("S", "F"):
        if echelle == "F" and not fusion.exists():
            continue
        lignes, lat = [], []
        for q in qs:
            mem = fusion if echelle == "F" else K.RUN / "memoires" / q["conv"]
            if mem not in matrices:
                fs = faits_de(mem)
                neufs = [f for f in fs if f not in vecteurs]
                for f, v in zip(neufs, modele.encode(neufs, normalize_embeddings=True, batch_size=16) if neufs else []):
                    vecteurs[f] = v
                matrices[mem] = (fs, np.stack([vecteurs[f] for f in fs]) if fs else np.zeros((0, 1024)))
            fs, M = matrices[mem]
            t1 = time.perf_counter()
            v = modele.encode([q["question"]], normalize_embeddings=True)[0]
            ordre = np.argsort(-(M @ v))[:K.BUDGET_FAITS] if len(fs) else []
            lat.append((time.perf_counter() - t1) * 1000)
            lignes.append({"id": q["id"], "faits": [fs[i] for i in ordre], "latence_ms": round(lat[-1], 2)})
        K.ecrire_jsonl(K.RUN / "contextes" / f"B_{echelle}.jsonl", lignes)
        lat.sort()
        print(f"  B_{echelle} : {len(lignes)} questions · p50 {lat[len(lat) // 2]:.0f} ms · p95 {lat[int(0.95 * len(lat)) - 1]:.0f} ms", flush=True)
    infra = {"modele": "BAAI/bge-m3", "chargement_s": round(chargement, 1),
             "ram_max_mo": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024), "faits_encodes": len(vecteurs)}
    (K.RUN / "embeddings_infra.json").write_text(json.dumps(infra, indent=1))
    print(infra)
    return 0


if __name__ == "__main__":
    sys.exit(main())
