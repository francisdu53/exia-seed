#!/usr/bin/env python3
"""Banc 8, B+ temps 1 (conteneur, GPT-6) — rattacher chaque fait à 1-3 concepts d'un thésaurus partagé.

Le sens est compilé UNE fois, à l'écriture (philosophie de Karpathy), dans un vocabulaire de concepts qui
porte chacun ses synonymes une seule fois ; chaque concept deviendra un nœud de la FCM (docs/08 §8).
Ici, rattrapage des faits des instantanés du banc (paquets de 50, les concepts existants sont redonnés
au modèle pour qu'il les réutilise). Sortie : thesaurus.json = {"concepts": {slug: {"fr": [...],
"en": [...]}}, "faits": {texte: [slugs]}}.

    python3 banc8_thesaurus.py /opt/data/workspace/banc-6b /opt/data/workspace/banc-8 [plugins]
"""
import json
import re
import sys
from pathlib import Path

SOURCE, SORTIE = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, "/opt/hermes")
sys.path.insert(0, sys.argv[3] if len(sys.argv) > 3 else "/opt/data/plugins")
from exia_seed import graphe as G                                         # noqa: E402
from exia_seed import pages as P                                          # noqa: E402
from exia_seed.consolidation import appel_llm_hermes                      # noqa: E402

PAQUET = 50
SYS = ("Tu construis le THÉSAURUS d'une mémoire personnelle. Pour chaque fait numéroté, donne 1 à 3 CONCEPTS : des "
       "thèmes génériques et réutilisables (exemples : sante, rendez_vous, facturation, client, finances_personnelles, "
       "epargne, courses, site_web, outil_informatique, vehicule, famille, fiscalite), en minuscules_avec_tirets_bas. "
       "RÉUTILISE les concepts existants quand ils conviennent. Un concept n'est PAS un nom propre : les personnes, "
       "clients et entreprises ont déjà leur propre page. Pour chaque concept NOUVEAU, donne 5 à 10 synonymes ou mots "
       "proches en français et 2 à 4 en anglais : les mots qu'on emploierait pour en parler (ex. sante : médecin, docteur, "
       "cabinet médical, consultation, soins, maladie…). Réponds UNIQUEMENT par un objet JSON : "
       '{"faits": {"1": ["concept", ...], ...}, "concepts_nouveaux": {"concept": {"fr": [...], "en": [...]}}}')


def main() -> int:
    textes = []
    for d in sorted((SOURCE / "instantanes").iterdir()):
        for f in G._lire(d)[1]:
            if f["texte"] not in textes:
                textes.append(f["texte"])
    th_f = SORTIE / "thesaurus.json"
    th = json.loads(th_f.read_text(encoding="utf-8")) if th_f.exists() else {"concepts": {}, "faits": {}}
    llm = appel_llm_hermes("low")
    a_faire = [t for t in textes if t not in th["faits"]]
    print(f"{len(textes)} faits distincts, {len(a_faire)} à rattacher", flush=True)
    for k in range(0, len(a_faire), PAQUET):
        lot = a_faire[k:k + PAQUET]
        existants = ", ".join(sorted(th["concepts"])) or "(aucun)"
        liste = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(lot))
        rep = llm([{"role": "system", "content": SYS},
                   {"role": "user", "content": f"CONCEPTS EXISTANTS\n{existants}\n\nFAITS\n{liste}"}])
        m = re.search(r"\{.*\}", rep or "", re.S)
        try:
            d = json.loads(m.group(0)) if m else {}
        except ValueError:
            d = {}
        for slug, al in (d.get("concepts_nouveaux") or {}).items():
            s = P.slug(slug)
            if s and s not in th["concepts"]:
                th["concepts"][s] = {"fr": [str(x) for x in (al or {}).get("fr", [])][:12], "en": [str(x) for x in (al or {}).get("en", [])][:6]}
        for i, cs in (d.get("faits") or {}).items():
            try:
                t = lot[int(i) - 1]
            except (ValueError, IndexError):
                continue
            th["faits"][t] = [P.slug(c) for c in (cs or [])][:3]
        th_f.write_text(json.dumps(th, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  paquet {k // PAQUET + 1} : {len(lot)} faits · {len(th['concepts'])} concepts au total", flush=True)
    orph = [c for cs in th["faits"].values() for c in cs if c not in th["concepts"]]
    print(f"concepts : {len(th['concepts'])} · faits rattachés : {len(th['faits'])}/{len(textes)} · rattachements sans définition : {len(set(orph))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
