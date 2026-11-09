#!/usr/bin/env python3
"""Banc 17 §12 — la liste complète des nœuds contre la liste ciblée par la recherche, à la consolidation.

Même modèle (Terra), même consigne adaptée, mêmes journées ; seule la liste des nœuds existants vue par le modèle
change. On compare, sur les deux panels (12 journées, deux passages chacun) : bonnes réponses, couverture, lots perdus,
doublons probables, et les tokens d'entrée réels. Conteneur jetable (`lancer.sh comparer`). Agrégats seulement dans le
bilan ; la liste des doublons probables (noms de pages) reste dans le dossier privé du banc.

Doublon probable : une page NOUVELLE d'un passage, dont la majorité des lignes citées sont rangées, dans l'autre
condition, dans une page qui existait déjà au départ. Le bruit se mesure de la même façon entre les deux passages de
la liste complète.
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("BANC_PANEL", "jours")
import mesurer as M                                                    # noqa: E402

BANC, RUNS, appel = M.BANC, M.RUNS, M.appel
TERRA = "gpt-6.1-terra"
PANELS = {"jours": {"complet": ("t1", "t2"), "cible": ("k1", "k2"), "mesures": "mesures-terra-T"},
          "panel2": {"complet": ("p2t1", "p2t2"), "cible": ("p2k1", "p2k2"), "mesures": "mesures-panel2"}}
SORTIE = BANC / "mesures-catalogue"


def pages(mem: Path) -> dict:
    """{page : lignes de brut citées}"""
    out = {}
    for p in (mem / "pages").glob("*.md"):
        out[p.name] = M.cites({k: v for k, v in M.faits_de(mem).items() if v[0] == p.name})
    return out


def doublons(mem_a: Path, mem_b: Path, depart: Path):
    """Pages nouvelles de A dont la majorité des lignes citées vont, dans B, dans une page existant au départ."""
    existantes = {p.name for p in (depart / "pages").glob("*.md")}
    pa, pb = pages(mem_a), pages(mem_b)
    ligne_b = {}
    for page, lignes in pb.items():
        for l in lignes:
            ligne_b.setdefault(l, set()).add(page)
    out = []
    for page, lignes in pa.items():
        if page in existantes or not lignes:
            continue
        vers = Counter(q for l in lignes for q in ligne_b.get(l, ()) if q in existantes)
        if vers:
            cible, n = vers.most_common(1)[0]
            if n * 2 > len(lignes):
                out.append((page, cible))
    return out


def main():
    bilan, prive = {}, {}
    for panel, cfg in PANELS.items():
        M.JOURS = tuple(json.loads((BANC / f"{panel}.json").read_text(encoding="utf-8")))
        M.SORTIE = BANC / cfg["mesures"]
        qs = M.questions()                                             # déjà écrites : aucun appel
        res = {}
        for cond in ("complet", "cible"):
            res[cond] = []
            for rr in cfg[cond]:
                justes, couverts, messages, perdus, nouvelles, faits = [], 0, 0, 0, 0, 0
                for etiq in M.JOURS:
                    mem = RUNS / TERRA / rr / etiq / "memoire"
                    depart = BANC / "depart" / etiq / "memoire"
                    fini = json.loads((mem.parent / "fini.json").read_text(encoding="utf-8"))
                    msgs = M.messages_utilisateur(depart)
                    c = M.cites(M.faits_de(mem))
                    couverts += sum(any((x[0], k) in c for k in range(x[1], x[2] + 1)) for x in msgs)
                    messages += len(msgs); perdus += fini["perdus"]; faits += fini["faits_retenus"]
                    nouvelles += len({p.name for p in (mem / "pages").glob("*.md")} - {p.name for p in (depart / "pages").glob("*.md")})
                    qj = [q for q in qs if q["jour"] == etiq]
                    justes += M.repondre(mem, qj) if qj else []
                cible = [json.loads(l) for etiq in M.JOURS
                         for l in ((RUNS / TERRA / rr / etiq / "cible.jsonl").read_text(encoding="utf-8").splitlines()
                                   if (RUNS / TERRA / rr / etiq / "cible.jsonl").exists() else [])]
                res[cond].append({"passage": rr, "justes": justes, "couverts": couverts, "messages": messages,
                                  "perdus": perdus, "faits": faits, "pages_nouvelles": nouvelles, "cout": M.cout_reel(TERRA, rr),
                                  "liste": {"passages": len(cible), "lignes_completes": sum(x["lignes_completes"] for x in cible),
                                            "lignes_gardees": sum(x["lignes_gardees"] for x in cible),
                                            "car_complet": sum(x["car_complet"] for x in cible),
                                            "car_cible": sum(x["car_cible"] for x in cible)}})
                print(f"{panel} {cond} {rr} : {sum(justes)}/{len(justes)} justes, couverture {couverts}/{messages}, "
                      f"{faits} faits, {nouvelles} pages nouvelles, {perdus} perdus", flush=True)
        # doublons : cible contre complet (même rang de passage), et le bruit complet contre complet
        d = {"bruit": [], "cible": []}
        for etiq in M.JOURS:
            dep = BANC / "depart" / etiq / "memoire"
            m = {rr: RUNS / TERRA / rr / etiq / "memoire" for rr in cfg["complet"] + cfg["cible"]}
            c1, c2 = cfg["complet"]; k1, k2 = cfg["cible"]
            d["bruit"] += [(etiq,) + x for x in doublons(m[c1], m[c2], dep) + doublons(m[c2], m[c1], dep)]
            d["cible"] += [(etiq,) + x for x in doublons(m[k1], m[c1], dep) + doublons(m[k2], m[c2], dep)]
        prive[panel] = d
        bilan[panel] = {"res": res, "doublons": {k: len(v) for k, v in d.items()}}

    def taux(cond, cle_n, cle_d):
        v = [sum(bilan[p]["res"][cond][i][cle_n] if cle_n != "justes" else sum(bilan[p]["res"][cond][i]["justes"]) for p in PANELS)
             / max(1, sum(bilan[p]["res"][cond][i][cle_d] if cle_d != "questions" else len(bilan[p]["res"][cond][i]["justes"]) for p in PANELS))
             for i in (0, 1)]
        return round(100 * sum(v) / 2, 1)
    q = {c: taux(c, "justes", "questions") for c in ("complet", "cible")}
    cv = {c: taux(c, "couverts", "messages") for c in ("complet", "cible")}
    perdus = sum(r["perdus"] for p in PANELS for r in bilan[p]["res"]["cible"])
    db = {k: sum(bilan[p]["doublons"][k] for p in PANELS) for k in ("bruit", "cible")}
    a = [x for p in PANELS for i in (0, 1) for x in bilan[p]["res"]["cible"][i]["justes"]]
    b = [x for p in PANELS for i in (0, 1) for x in bilan[p]["res"]["complet"][i]["justes"]]
    tok = {c: sum(r["cout"]["entree"] for p in PANELS for r in bilan[p]["res"][c]) for c in ("complet", "cible")}
    usd = {c: round(sum(r["cout"]["usd"] for p in PANELS for r in bilan[p]["res"][c]), 3) for c in ("complet", "cible")}
    liste = {k: sum(r["liste"][k] for p in PANELS for r in bilan[p]["res"]["cible"])
             for k in ("passages", "lignes_completes", "lignes_gardees", "car_complet", "car_cible")}
    verdict = {"questions_pct": q, "couverture_pct": cv, "doublons_probables": db, "lots_perdus_cible": perdus,
               "mcnemar_cible_contre_complet": dict(zip(("seul_cible", "seul_complet", "p"), M.mcnemar(a, b))),
               "tokens_entree_reels": tok, "usd_consolidation": usd, "liste_ciblee": liste,
               "C1": q["cible"] >= q["complet"] - 5, "C2": cv["cible"] >= cv["complet"] - 5,
               "C3": perdus == 0, "C4": db["cible"] <= db["bruit"] + 2,
               "depense_totale_banc_usd": round(appel.depense()["total"]["usd"], 4)}
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "bilan.json").write_text(json.dumps({"verdict": verdict, "detail": bilan}, ensure_ascii=False, indent=1), encoding="utf-8")
    (SORTIE / "doublons-prive.json").write_text(json.dumps(prive, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(verdict, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
