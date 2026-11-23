#!/usr/bin/env python3
"""Phase 1, rouage N2 — la consolidation ÉCRIT les cartes : « le sens se paie une fois, à l'écriture ».

Pour chaque souvenir d'une mémoire, le modèle de consolidation de Nexa (Terra, effort « low ») écrit :
  themes  un chemin de 2 à 4 thèmes, du général au précis (« food › vegetables › carrots ») — les FCM imbriquées ;
  termes  jusqu'à 8 mots qu'on emploierait pour chercher ce souvenir et qui ne sont PAS dans son texte (synonymes,
          catégories générales, sortes plus précises, mots du quotidien liés).
Rien n'est inventé sur les faits : seulement des mots pour le retrouver. Par lots de 30 souvenirs, regroupés par page.
Cache par texte du souvenir (`cartes_ecrites.json`) : la fusion et les mémoires par conversation partagent les textes.
Tokens réels de chaque appel journalisés (`journaux/cartes_usage.jsonl`) : c'est le coût d'ÉCRITURE de N2.
Conteneur : … python3 ecrire_cartes.py memoires/locomo/_fusion memoires/lme/_fusion [--limite N]
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, str(ICI / "paquets" / "seed-1.0.0")); sys.path.insert(0, str(ICI))
import lire_juger as LJ                                           # noqa: E402  (appel avec usage réel, reprises, quota)

FAIT = re.compile(r"^- (.*?) <!--.*-->\s*$")
CONSIGNE = """You maintain the associative index of a personal memory. For each memory below, write:
- "themes": a path of 2 to 4 themes from general to specific that the memory belongs to, as short common nouns
  (examples: ["food", "vegetables", "carrots"]; ["work", "invoices", "payment terms"]; ["family", "children", "school"]).
- "terms": up to 8 words or short phrases someone could use later when looking for this memory and that are NOT already
  in its text: synonyms, general categories, more specific kinds, related everyday words.
Write in the language of the memory. Do not add facts. Answer with JSON only, one entry per id:
{"1": {"themes": [...], "terms": [...]}, "2": {...}}

Page: {page}
Memories:
{souvenirs}"""
LOT = 30


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    limite = int(sys.argv[sys.argv.index("--limite") + 1]) if "--limite" in sys.argv else 0
    args = [a for a in args if not a.isdigit()]
    f_cartes = ICI / "cartes_ecrites.json"
    cartes = json.loads(f_cartes.read_text(encoding="utf-8")) if f_cartes.exists() else {}
    usage_f = ICI / "journaux" / "cartes_usage.jsonl"
    par_page = defaultdict(list)
    for a in args:
        for p in sorted((ICI / a / "pages").glob("*.md")):
            titre = next((l[2:].strip() for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("# ")), p.stem)
            for l in p.read_text(encoding="utf-8").splitlines():
                m = FAIT.match(l)
                if m and m.group(1).strip() not in cartes:
                    par_page[titre].append(m.group(1).strip())
    lots, cour, titre_cour = [], [], []
    for titre, faits in par_page.items():
        for t in dict.fromkeys(faits):
            cour.append((titre, t))
            if len(cour) >= LOT:
                lots.append(cour); cour = []
    if cour:
        lots.append(cour)
    if limite:
        lots = lots[:limite]
    print(f"{sum(len(l) for l in lots)} souvenirs à cartographier en {len(lots)} appels ({len(cartes)} déjà faits)", flush=True)
    for k, lot in enumerate(lots):
        pages = sorted({t for t, _ in lot})
        contenu = CONSIGNE.replace("{page}", " / ".join(pages)).replace(
            "{souvenirs}", "\n".join(f"{j + 1}. {t}" for j, (_, t) in enumerate(lot)))
        r = LJ.appeler("low", contenu, sel="cartes")
        texte = r["texte"] or ""
        try:
            d = json.loads(texte[texte.find("{"):texte.rfind("}") + 1])
        except Exception:
            d = {}
        ok = 0
        for j, (_, t) in enumerate(lot):
            e = d.get(str(j + 1)) or {}
            th = [str(x) for x in e.get("themes", [])][:4]; te = [str(x) for x in e.get("terms", [])][:8]
            if th or te:
                cartes[t] = {"themes": th, "termes": te}; ok += 1
        with usage_f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"lot": k, "souvenirs": len(lot), "ecrits": ok, "usage": r["usage"], "ms": r["ms"],
                                 "cache": r["cache"], "date": time.strftime("%Y-%m-%dT%H:%M:%S")}) + "\n")
        if k % 10 == 9 or k == len(lots) - 1:
            tmp = f_cartes.with_suffix(".tmp"); tmp.write_text(json.dumps(cartes, ensure_ascii=False), encoding="utf-8")
            tmp.replace(f_cartes)
            print(f"  {k + 1}/{len(lots)} appels · {len(cartes)} souvenirs cartographiés", flush=True)
    print("FIN-CARTES", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
