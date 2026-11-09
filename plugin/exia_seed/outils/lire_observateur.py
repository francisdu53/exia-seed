#!/usr/bin/env python3
"""Bilan du mode observateur de la liste ciblée (docs/17 §18) — LECTURE SEULE.

Pour chaque jour : passages observés, taille de la mémoire, pages sélectionnées, faits rangés dans une page existante,
et la part de ces pages que la sélection contenait (le rappel). Un rappel proche de 100 % dit que n'envoyer que la
sélection au modèle ne lui aurait rien caché.

    python3 /opt/data/plugins/exia_seed/outils/lire_observateur.py [dossier de la mémoire]
"""
import collections
import json
import sys
from pathlib import Path

M = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/data/memoire")
f = M / "telemetrie" / "catalogue_observateur.jsonl"
if not f.exists():
    print("aucune observation pour l'instant :", f); sys.exit(0)
jours = collections.defaultdict(lambda: {"passages": 0, "pannes": 0, "pages": 0, "sel": 0, "ratt": 0, "dans": 0, "hors": collections.Counter(), "ms": 0.0})
for l in f.read_text(encoding="utf-8").splitlines():
    x = json.loads(l); j = jours[x["ts"][:10]]; j["passages"] += 1
    if "erreur" in x:
        j["pannes"] += 1; continue
    j["pages"] = max(j["pages"], x.get("pages", 0)); j["sel"] += x.get("selection_taille", 0)
    j["ratt"] += x.get("rattachements", 0); j["dans"] += x.get("dans_selection", 0); j["ms"] += x.get("duree_ms", 0.0)
    j["hors"].update(x.get("hors_selection") or [])
print(f"{'jour':10} {'passages':>8} {'pannes':>6} {'pages':>6} {'sélection moy.':>14} {'rattachements':>13} {'rappel':>7} {'ms moy.':>8}")
tot = [0, 0]
for d in sorted(jours):
    j = jours[d]; n = max(1, j["passages"] - j["pannes"]); tot[0] += j["dans"]; tot[1] += j["ratt"]
    print(f"{d:10} {j['passages']:>8} {j['pannes']:>6} {j['pages']:>6} {j['sel'] / n:>14.1f} {j['ratt']:>13} "
          f"{(100 * j['dans'] / j['ratt'] if j['ratt'] else 100):>6.1f}% {j['ms'] / n:>8.0f}")
    if j["hors"]:
        print("           hors sélection :", ", ".join(f"{k} ({v})" for k, v in j["hors"].most_common(8)))
print(f"\nrappel cumulé : {tot[0]}/{tot[1]} = {(100 * tot[0] / tot[1] if tot[1] else 100):.1f} %")
