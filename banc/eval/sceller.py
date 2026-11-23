#!/usr/bin/env python3
"""Phase 0 — SCELLER les jeux AVANT de construire N (PLAN-FCM-EXIA-SEED.md §5 bis, précision 1).

Leçon du 18/11 : un réglage sur ~120 messages se sur-adapte. N ne sera réglé QUE sur les jeux de réglage ; les jeux de
test et de verdict ne servent qu'à mesurer. L'empreinte de ce fichier est notée dans le journal : toute modification
ultérieure se verrait.
  - LongMemEval : échantillon de test = les 100 tirées graine 91 (celles des passages du 20/11) ; réglage = 50 tirées
    graine 2611 parmi les 400 autres ; verdict = les 500 moins le réglage.
  - LoCoMo : échantillon de test = conv-49 (celle des passages du 20/11) ; réglage = conv-26 et conv-30 (les conversations
    « pilote » du protocole docs/09) ; verdict = les 8 autres.
  - Nexa (phase 2) : la RÈGLE est scellée maintenant — messages reçus après le 21/11/2026 23:59 (heure de Paris), jamais
    vus par aucun réglage, tirage graine 2611 ; réglage = les messages déjà jugés (vivier, épreuves e1-e3, m1, m2, f3).
"""
import hashlib
import json
import os
import random
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "harnais"))
DONNEES = ICI.parent / "bancs" / "donnees"


def questions(fichier: str):
    os.environ["LOCOMO_DONNEES"] = str(DONNEES / fichier)
    import importlib
    import commun
    importlib.reload(commun)
    return commun.questions(json.loads((DONNEES / fichier).read_text(encoding="utf-8")))


def main() -> int:
    sortie = ICI / "scelle.json"
    if sortie.exists():
        print("déjà scellé :", hashlib.sha256(sortie.read_bytes()).hexdigest()); return 0
    lme = questions("lme_oracle_locomo.json")
    test_lme = sorted(q["id"] for q in random.Random(91).sample(lme, 100))
    reste = sorted(q["id"] for q in lme if q["id"] not in set(test_lme))
    reglage_lme = sorted(random.Random(2611).sample(reste, 50))
    loc = questions("locomo10.json")
    scelle = {
        "date": "2026-11-21",
        "lme": {"test": test_lme, "reglage": reglage_lme,
                "verdict": sorted(q["id"] for q in lme if q["id"] not in set(reglage_lme))},
        "locomo": {"test": sorted(q["id"] for q in loc if q["conv"] == "conv-49"),
                   "reglage": sorted(q["id"] for q in loc if q["conv"] in ("conv-26", "conv-30")),
                   "verdict": sorted(q["id"] for q in loc if q["conv"] not in ("conv-26", "conv-30"))},
        "nexa": {"regle_test": "messages reçus après 2026-11-21T23:59 Europe/Paris, tirage graine 2611",
                 "reglage": "messages déjà jugés : vivier, épreuves e1-e3, m1, m2, f3"},
    }
    sortie.write_text(json.dumps(scelle, ensure_ascii=False, indent=1), encoding="utf-8")
    for b in ("lme", "locomo"):
        print(b, {k: len(v) for k, v in scelle[b].items()})
    print("empreinte :", hashlib.sha256(sortie.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
