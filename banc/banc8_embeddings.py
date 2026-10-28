#!/usr/bin/env python3
"""Banc 8, temps 2 (HÔTE, environnement d'EXIA GHOST) — le concurrent « embeddings » (docs/08 D2, D6).

bge-m3, le modèle d'embedding qu'utilisait EXIA GHOST V2.7.x, hors ligne depuis le cache. Pour chaque
requête du temps 1 : similarité cosinus requête ↔ chaque fait de l'instantané, sujets classés par leur
meilleur fait, 3 sujets × 3 faits — le budget des autres moteurs. Mesure aussi le chargement et la RAM.

Les pages sont lues ici sans le paquet exia_seed (il importe Hermès, absent de l'hôte) : même règle
que graphe._lire — une ligne « - fait <!-- métadonnées --> » est un fait, le nœud est dans l'en-tête.

    HF_HUB_OFFLINE=1 ${PYTHON_EMBEDDINGS:-python3} banc8_embeddings.py <banc-6b> <banc-8>
"""
import json
import re
import resource
import sys
import time
from pathlib import Path

import numpy as np
import yaml

SOURCE, SORTIE = Path(sys.argv[1]), Path(sys.argv[2])
SUJETS, PAR_SUJET = 3, 3
_META = re.compile(r"\s*<!--(.*?)-->\s*$")


def faits_de(instantane: Path):
    sortie = []
    for f in sorted((instantane / "pages").glob("*.md")):
        t = f.read_text(encoding="utf-8")
        fin = t.find("\n---\n", 4)
        noeud = (yaml.safe_load(t[4:fin]) or {}).get("node") if t.startswith("---\n") and fin > 0 else f.stem
        for l in t[fin + 5:].splitlines():
            if l.startswith("- ") and "<!--" in l:
                sortie.append((str(noeud), _META.sub("", l[2:]).strip()))
    return sortie


def main() -> int:
    requetes = [json.loads(l) for l in (SORTIE / "requetes.jsonl").read_text(encoding="utf-8").splitlines()]
    t0 = time.perf_counter()
    from sentence_transformers import SentenceTransformer
    modele = SentenceTransformer("BAAI/bge-m3", device="cpu")
    chargement = time.perf_counter() - t0
    ram_mo = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    cache_vecteurs, par_instantane, lignes, lat = {}, {}, [], []
    for r in requetes:
        if not r["requete"]:
            lignes.append({"n": r["n"], "embeddings": []}); continue
        s = r["instantane"]
        if s not in par_instantane:
            fs = faits_de(SOURCE / "instantanes" / s)
            neufs = [t for _, t in fs if t not in cache_vecteurs]
            if neufs:
                for t, v in zip(neufs, modele.encode(neufs, normalize_embeddings=True, batch_size=16)):
                    cache_vecteurs[t] = v
            par_instantane[s] = (fs, np.stack([cache_vecteurs[t] for _, t in fs]) if fs else np.zeros((0, 1024)))
        fs, M = par_instantane[s]
        t1 = time.perf_counter()
        q = modele.encode([r["requete"]], normalize_embeddings=True)[0]
        sims = M @ q
        ordre = np.argsort(-sims)
        groupes = {}
        for i in ordre:
            noeud, texte = fs[i]
            if noeud not in groupes and len(groupes) >= SUJETS:
                continue
            groupes.setdefault(noeud, [])
            if len(groupes[noeud]) < PAR_SUJET:
                groupes[noeud].append((texte, float(sims[i])))
            if len(groupes) >= SUJETS and all(len(v) >= PAR_SUJET for v in groupes.values()):
                break
        lat.append((time.perf_counter() - t1) * 1000)
        lignes.append({"n": r["n"], "embeddings": [{"sujet": k, "faits": [t for t, _ in v], "cosinus": [round(c, 3) for _, c in v]}
                                                   for k, v in groupes.items()]})
    (SORTIE / "embeddings.jsonl").write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lignes), encoding="utf-8")
    lat.sort()
    infra = {"modele": "BAAI/bge-m3", "chargement_s": round(chargement, 1), "ram_max_mo": round(ram_mo),
             "faits_encodes": len(cache_vecteurs), "latence_requete_p50_ms": round(lat[len(lat) // 2], 1) if lat else None,
             "latence_requete_p95_ms": round(lat[int(0.95 * len(lat)) - 1], 1) if lat else None}
    (SORTIE / "embeddings_infra.json").write_text(json.dumps(infra, indent=1), encoding="utf-8")
    print(json.dumps(infra, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
