#!/usr/bin/env python3
"""Test 1 (23/11) — mémoires de tailles croissantes pour la courbe d'INTERFÉRENCE (même méthode que l'échelle F).

Reprend fusionner.py (exia-seed/banc/locomo, docs/09 §4) : pages de même nœud fusionnées (les distracteurs se mêlent aux
bons faits), interlocuteurs homonymes de LoCoMo gardés séparés (`john_conv_41`), citations du brut préfixées par la
conversation, thésaurus réuni, INDEX.md régénéré ; puis brut copié avec le même préfixe (comme preparer.py). Le graphe
est calculé ensuite par les fournisseurs, comme pour `_fusion`. Aucun appel au modèle.

  plan        (hôte) groupes de 10 conversations du jeu TEST de LongMemEval (graine 42) → interference/groupes.json + plan.json
  construire  (conteneur Nexa : le paquet importe Hermès) construit chaque mémoire du plan
Mémoires : lme/_g10_XX, _g50_XX, _g200_XX (le groupe XX + des conversations tirées au hasard, emboîtées : celles de
_g50 sont dans _g200) ; lme/_controle et locomo/_controle (tout refusionné : doit redonner `_fusion`) ; locomo/_mixte
(les 10 conversations LoCoMo + les 500 de LongMemEval).
"""
from __future__ import annotations

import json
import random
import re
import shutil
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
MEM = ICI / "memoires"
OUT = ICI / "interference"
TAILLES = (10, 50, 200)
etiquette = lambda nom: re.sub(r"\s+", "_", nom.strip().lower())


def plan() -> int:
    scelle = json.loads((ICI / "scelle.json").read_text(encoding="utf-8"))
    convs_test = sorted({i.rsplit(":", 1)[0] for i in scelle["lme"]["test"]})
    tous = sorted(d.name for d in (MEM / "lme").iterdir() if d.is_dir() and not d.name.startswith("_"))
    assert len(convs_test) == 100 and len(tous) == 500, (len(convs_test), len(tous))
    rnd = random.Random(42)
    melange = convs_test[:]; rnd.shuffle(melange)
    groupes = {f"{g:02d}": sorted(melange[10 * g:10 * g + 10]) for g in range(10)}
    plan_ = []
    for g, membres in groupes.items():
        autres = [c for c in tous if c not in membres]
        random.Random(f"distracteurs-{g}").shuffle(autres)
        for t in TAILLES:
            plan_.append({"cible": f"lme/_g{t}_{g}", "sources": [f"lme/{c}" for c in membres + autres[:t - 10]]})
    plan_.append({"cible": "lme/_controle", "sources": [f"lme/{c}" for c in tous]})
    loc = sorted(d.name for d in (MEM / "locomo").iterdir() if d.is_dir() and not d.name.startswith("_"))
    plan_.append({"cible": "locomo/_controle", "sources": [f"locomo/{c}" for c in loc]})
    plan_.append({"cible": "locomo/_mixte", "sources": [f"locomo/{c}" for c in loc] + [f"lme/{c}" for c in tous]})
    OUT.mkdir(exist_ok=True)
    (OUT / "groupes.json").write_text(json.dumps({"lme": {c: g for g, m in groupes.items() for c in m}}, indent=1), encoding="utf-8")
    (OUT / "plan.json").write_text(json.dumps(plan_, indent=1), encoding="utf-8")
    print(f"{len(plan_)} mémoires prévues ; groupes : {', '.join(f'{g}={len(m)}' for g, m in groupes.items())}")
    return 0


def fusionner(cible: Path, sources: list) -> dict:
    sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, str(ICI / "paquets" / "seed-1.0.0"))
    from zoneinfo import ZoneInfo
    from exia_seed import graphe as G
    from exia_seed import langues
    from exia_seed import pages as P
    from exia_seed.consolidation import Consolidateur
    noms_loc = {c["sample_id"]: [etiquette(c["conversation"][k]) for k in ("speaker_a", "speaker_b")]
                for c in json.loads((ICI.parent / "bancs" / "donnees" / "locomo10.json").read_text(encoding="utf-8"))}
    if cible.exists():
        shutil.rmtree(cible)
    langues.fixer(cible, "en")
    (cible / "pages").mkdir(parents=True)
    (cible / "raw").mkdir()
    noms = {s: (noms_loc[s.name] if s.parent.name == "locomo" else ["user", "assistant"]) for s in sources}
    tous_loc = [n for s in sources if s.parent.name == "locomo" for n in noms[s]]
    homonymes = {n for n in tous_loc if tous_loc.count(n) > 1}       # LongMemEval : un seul « user », jamais renommé
    par_noeud, fusions, concepts, parleurs = {}, 0, {}, []
    for src in sources:
        renommer = {n: f"{n}_{P.slug(src.name)}" for n in noms[src] if n in homonymes} if src.parent.name == "locomo" else {}
        parleurs += [renommer.get(n, n) for n in noms[src]]
        for p in P.lister(src / "pages"):
            n = p.entete.get("node")
            if n in renommer:
                n = p.entete["node"] = renommer[n]
                p.chemin = p.chemin.parent / P.fichier_de(n)
            for cle in P.CLES:
                p.sections[cle] = [re.sub(r"(?<=src:)([^ ]*)", lambda m: re.sub(r"raw/", f"raw/{src.name}_", m.group(1)), l)
                                   for l in p.sections[cle]]
                for ancien, nouveau in renommer.items():
                    p.sections[cle] = [re.sub(rf"(?<=speaker:){re.escape(ancien)}(?![\w])", nouveau, l) for l in p.sections[cle]]
            if n in par_noeud:
                fusions += 1
                q = par_noeud[n]
                q.fusionner_alias(p.entete.get("aliases") or {})
                for cle in P.CLES:
                    q.sections[cle].extend(p.sections[cle])
            else:
                p.chemin = cible / "pages" / p.chemin.name
                par_noeud[n] = p
        th = G.charger_thesaurus(src)
        for c, v in (th.get("concepts") or {}).items():
            d = concepts.setdefault(c, {})
            for lg, mots in v.items():
                d[lg] = list(dict.fromkeys((d.get(lg) or []) + list(mots or [])))
        for f in (src / "raw").glob("*.md"):
            shutil.copy2(f, cible / "raw" / f"{src.name}_{f.name}")
    parleurs = list(dict.fromkeys(parleurs))
    for p in par_noeud.values():
        p.ecrire()
    G.enregistrer_thesaurus(cible, {"concepts": concepts, "faits": {}})
    Consolidateur(cible, ZoneInfo("UTC"), lambda m: "", interlocuteurs=parleurs)._ecrire_index()
    return {"cible": f"{cible.parent.name}/{cible.name}", "conversations": len(sources), "pages": len(par_noeud),
            "pages_fusionnees": fusions, "homonymes": sorted(homonymes), "bruts": sum(1 for _ in (cible / "raw").glob("*.md"))}


def construire() -> int:
    bilan = []
    for x in json.loads((OUT / "plan.json").read_text(encoding="utf-8")):
        r = fusionner(MEM / x["cible"], [MEM / s for s in x["sources"]])
        bilan.append(r); print(json.dumps(r, ensure_ascii=False), flush=True)
    (OUT / "construction.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit({"plan": plan, "construire": construire}[sys.argv[1]]())
