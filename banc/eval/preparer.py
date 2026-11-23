#!/usr/bin/env python3
"""Phase 0 — préparer les mémoires du banc d'évaluation (PLAN-FCM-EXIA-SEED.md §5).

Copie les mémoires DÉJÀ consolidées (aucune reconsolidation) des passages de référence, sans toucher aux originaux :
  LoCoMo        $HOME/banc-locomo/runs/confirm-092/memoires        (10 conversations + _fusion)
  LongMemEval   $HOME/banc-longmemeval/runs/confirm-lme/memoires   (500 mémoires + _fusion)
puis REMPLIT le brut des mémoires fusionnées (vide jusqu'ici : fusionner.py créait le dossier sans le remplir), avec le
même préfixe que les citations (`raw/<source>_<fichier>`), et vérifie que chaque citation `src:raw/<f>:<ligne>` pointe une
ligne qui existe (capteur « citations résolues »). Hôte, bibliothèque standard seulement.
    python3 preparer.py            → eval/memoires/{locomo,lme}/…  +  eval/preparation.json
"""
import json
import re
import shutil
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
SOURCES = {"locomo": Path("$HOME/banc-locomo/runs/confirm-092/memoires"),
           "lme": Path("$HOME/banc-longmemeval/runs/confirm-lme/memoires")}
CITE = re.compile(r"src:raw/([^ :]+):(\d+)")


def lignes_brut(dossier: Path) -> dict:
    return {f.name: len(f.read_text(encoding="utf-8").splitlines()) for f in (dossier / "raw").glob("*.md")}


def verifier_citations(memoire: Path) -> dict:
    nb = {f: n for f, n in lignes_brut(memoire).items()}
    total = ok = 0
    manquantes = []
    for p in (memoire / "pages").glob("*.md"):
        for m in CITE.finditer(p.read_text(encoding="utf-8")):
            total += 1
            if m.group(1) in nb and 1 <= int(m.group(2)) <= nb[m.group(1)]:
                ok += 1
            elif len(manquantes) < 5:
                manquantes.append(f"{p.name}: raw/{m.group(1)}:{m.group(2)}")
    return {"citations": total, "resolues": ok, "part": round(ok / total, 4) if total else None, "exemples_manquants": manquantes}


def main() -> int:
    rapport = {}
    for banc, src in SOURCES.items():
        cible = ICI / "memoires" / banc
        if cible.exists():
            print(f"{banc} : déjà préparé ({cible}) — rien recopié"); continue
        shutil.copytree(src, cible, ignore=shutil.ignore_patterns(".graphe-du-jour", "__pycache__"))
        fusion = cible / "_fusion"
        n = 0
        for m in sorted(d for d in cible.iterdir() if d.is_dir() and d.name != "_fusion"):
            for f in (m / "raw").glob("*.md"):
                shutil.copy2(f, fusion / "raw" / f"{m.name}_{f.name}"); n += 1
        rapport[banc] = {"memoires": sum(1 for d in cible.iterdir() if d.is_dir() and d.name != "_fusion"),
                         "bruts_relies_a_la_fusion": n, "citations_fusion": verifier_citations(fusion),
                         "citations_par_memoire": {}}
        part = [verifier_citations(m) for m in sorted(cible.iterdir()) if m.is_dir() and m.name != "_fusion"]
        rapport[banc]["citations_par_memoire"] = {"citations": sum(x["citations"] for x in part),
                                                  "resolues": sum(x["resolues"] for x in part)}
        print(banc, json.dumps(rapport[banc], ensure_ascii=False))
    (ICI / "preparation.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
