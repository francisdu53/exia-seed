#!/usr/bin/env python3
"""Étape 2 — l'échelle « fusionnée » (docs/09 §4) : les mémoires des conversations réunies en UNE.

- Interlocuteurs HOMONYMES (« John » parle dans conv-41, conv-43 et conv-47 : trois personnes) : leurs pages
  restent SÉPARÉES (`john_conv_41`…, alias « John » gardé). Les fusionner ferait d'eux une seule personne, et
  ne fausserait que la FCM (qui raisonne sur les pages) — pas les embeddings (qui ne lisent que des faits).
- Les autres pages de même nom (« hiking » dans deux conversations) : FUSIONNÉES en une page, comme l'aurait fait une
  seule mémoire qui aurait tout vécu — les distracteurs se mêlent aux bons faits. Le nombre de fusions est compté.
- Références au brut préfixées par la conversation (`raw/conv-26_2023-05-08_01.md:12`) : deux conversations
  n'ont rien « vécu ensemble » ; sans ce préfixe, deux lignes de même numéro créeraient de fausses arêtes.
- Le `speaker` des faits d'un homonyme est renommé comme sa page (`speaker:john_conv_41`) : trois personnes, trois
  identités — comme le ferait un identifiant de canal en multi-utilisateur (décision de Francis, 18/10).
- Thésaurus : union des concepts, union de leurs champs lexicaux. Graphe recalculé (interlocuteurs implicites
  seulement si LOCOMO_IMPLICITES=1, docs/09 §14.5). INDEX.md régénéré. Aucun appel au modèle.

    python3 fusionner.py
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from zoneinfo import ZoneInfo

import commun as K

K.preparer_chemins()
from exia_seed import graphe as G                                 # noqa: E402
from exia_seed import langues                                     # noqa: E402
from exia_seed import pages as P                                  # noqa: E402
from exia_seed.consolidation import Consolidateur                 # noqa: E402

FUSION = "_fusion"


def main() -> int:
    sources = sorted(d for d in (K.RUN / "memoires").iterdir() if d.is_dir() and d.name != FUSION)
    cible = K.RUN / "memoires" / FUSION
    if cible.exists():
        shutil.rmtree(cible)
    langues.fixer(cible, "en")
    (cible / "pages").mkdir(parents=True)
    (cible / "raw").mkdir()
    par_noeud, fusions, concepts = {}, 0, {}
    convs = {c["sample_id"]: c for c in K.charger_donnees([s.name for s in sources])}
    noms = {sid: [K.etiquette(c["conversation"][k]) for k in ("speaker_a", "speaker_b")] for sid, c in convs.items()}
    tous = [n for v in noms.values() for n in v]
    homonymes = {n for n in tous if tous.count(n) > 1} if K.HOMONYMES else set()
    parleurs = []
    for src in sources:
        renommer = {n: f"{n}_{P.slug(src.name)}" for n in noms.get(src.name, []) if n in homonymes}
        parleurs += [renommer.get(n, n) for n in noms.get(src.name, [])]
        for p in P.lister(src / "pages"):
            n = p.entete.get("node")
            if n in renommer:                                   # un interlocuteur homonyme : sa propre page
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
    parleurs = list(dict.fromkeys(parleurs))                 # LongMemEval : « user », « assistant » une seule fois
    for p in par_noeud.values():
        p.ecrire()
    G.enregistrer_thesaurus(cible, {"concepts": concepts, "faits": {}})
    Consolidateur(cible, ZoneInfo("UTC"), lambda m: "", interlocuteurs=parleurs)._ecrire_index()
    r = G.calculer(cible, implicites=tuple(parleurs) if K.IMPLICITES else ())
    bilan = {"conversations": len(sources), "pages": len(par_noeud), "pages_fusionnees": fusions,
             "interlocuteurs_homonymes": sorted(homonymes), "implicites": parleurs if K.IMPLICITES else [], "interlocuteurs": parleurs,
             "faits": r.get("faits"), "noeuds": r.get("noeuds"), "aretes": r.get("aretes"), "concepts": len(concepts),
             "graphe_ms": r.get("duree_ms"), "statut_graphe": r.get("statut")}
    (K.RUN / "fusion.json").write_text(json.dumps(bilan, indent=1))
    print(json.dumps(bilan, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
