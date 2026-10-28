#!/usr/bin/env python3
"""Banc 10 — optimisation de memoire_chercher sur TOUTES les recherches déjà jugées (docs/08 §12).

Corpus : banc 8 (88 recherches, 23-26/09, instantanés avec le thésaurus du banc) + banc 9 (24 recherches,
27-29/09, instantanés de production). Mêmes requêtes, même budget (9), même juge aveugle ; seuls les faits
jamais jugés passent au juge, et rejoignent l'ensemble des utiles (registre commun à toutes les variantes).

Une variante = un dossier de plugin + des réglages (constantes du module requete). Pour chaque variante,
chaque instantané est recopié et son graphe RECALCULÉ avec le code de la variante (la normalisation du
texte change le graphe).

    python3 banc10_optim.py <nom> <plugins> '{"DECROISSANCE": 1.0}'      (conteneur)
    python3 banc10_optim.py bilan                                         (tableau de toutes les variantes)

⚠️ Aucune de ces recherches n'est une vérification : toutes ont déjà été regardées. La vérification se
fera sur des conversations POSTÉRIEURES à la correction.
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

W = Path("/opt/data/workspace")
ICI = W / "banc-10"
NOM = sys.argv[1]
CORPUS = {"b8": (W / "banc-6b" / "rejeu.jsonl", W / "banc-8" / "requetes.jsonl", W / "banc-8" / "instantanes_bpp",
                 W / "banc-8" / "resultats8_bpp.jsonl", 500_000),
          "b9": (W / "banc-9" / "rejeu.jsonl", W / "banc-9" / "requetes.jsonl", W / "banc-9" / "instantanes",
                 W / "banc-9" / "resultats9.jsonl", 600_000)}
MOTEURS_B8 = ("FCM", "FCM+pistes", "Embeddings", "Plein texte", "FCM v2", "FCM B+", "FCM B++")


def lire(f):
    return [json.loads(l) for l in Path(f).read_text(encoding="utf-8").splitlines() if l.strip()]


def registre():
    f = ICI / "registre.json"
    if f.exists():
        return {k: {"juges": set(v["juges"]), "utiles": set(v["utiles"])} for k, v in json.loads(f.read_text(encoding="utf-8")).items()}
    reg = {}
    for c, (_, _, _, res, _) in CORPUS.items():
        for x in lire(res):
            moteurs = MOTEURS_B8 if c == "b8" else ("FCM B++", "Embeddings", "Plein texte")
            reg[f"{c}:{x['n']}"] = {"juges": set().union(*(set(x.get(k, [])) for k in moteurs)), "utiles": set(x["utiles"])}
    return reg


def enregistrer(reg):
    (ICI / "registre.json").write_text(json.dumps({k: {"juges": sorted(v["juges"]), "utiles": sorted(v["utiles"])} for k, v in reg.items()},
                                                  ensure_ascii=False), encoding="utf-8")


def sous_corpus(c, x):
    if c == "b9":
        return "27-29/09"
    return "26/09" if x["instant"] >= "2026-09-26" else "23-25/09"


def variante() -> int:
    plugins, reglages = sys.argv[2], json.loads(sys.argv[3] if len(sys.argv) > 3 else "{}")
    sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, plugins); sys.path.insert(0, str(W / "banc-8"))
    sys.argv = [sys.argv[0], str(ICI), str(ICI), plugins]                 # banc8_juge : cache dans banc-10
    import banc8_juge as J
    from exia_seed import graphe as G
    from exia_seed import requete as Q
    for k, v in reglages.items():
        assert hasattr(Q, k), k
        setattr(Q, k, v)
    reg = registre()
    sortie, lecteurs = [], {}
    for c, (rejeu_f, req_f, inst, _, decalage) in CORPUS.items():
        rejeu = {x["n"]: x for x in lire(rejeu_f)}
        for r in lire(req_f):
            if not r["requete"]:
                continue
            s = (c, r["instantane"])
            if s not in lecteurs:
                d = ICI / NOM / c / r["instantane"]
                if d.exists():
                    shutil.rmtree(d)
                shutil.copytree(inst / r["instantane"], d, ignore=shutil.ignore_patterns("graphe", "requetes", "rappel"))
                G.calculer(d, implicites=("francis", "nexa"))
                lecteurs[s] = Q.Lecteur(d, implicites=("francis", "nexa"))
            res = lecteurs[s].chercher(r["requete"], 9, datetime.fromisoformat(r["instant"]), faits_max=9)
            faits = [f["fait"] for y in res.get("resultats", []) for f in y["faits"]]
            faits += [p["fait"] for p in (res.get("pistes") or {}).get("faits", []) if p["fait"] not in faits]
            faits = faits[:9]
            cle = f"{c}:{r['n']}"
            nouveaux = [f for f in faits if f not in reg[cle]["juges"]]
            if nouveaux:
                l = rejeu[r["n"]]
                reg[cle]["utiles"] |= J.juger(decalage + r["n"], l["message"], l["reponse"], nouveaux)
                reg[cle]["juges"] |= set(nouveaux)
            sortie.append({"cle": cle, "sous_corpus": sous_corpus(c, r), "requete": r["requete"], "faits": faits})
            print(f"  {cle:7} « {r['requete'][:38]:38} » {len(set(faits) & reg[cle]['utiles'])}/{len(faits)} · {len(nouveaux)} nouveaux", flush=True)
    enregistrer(reg)
    (ICI / f"variante_{NOM}.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in sortie), encoding="utf-8")
    print(f"coût cumulé du juge (banc 10) : {sum(v.get('tokens', 0) for v in J.CACHE.values())} tokens")
    return 0


def bilan() -> int:
    reg = registre()
    fixes = {}
    for c, (_, _, _, res, _) in CORPUS.items():
        for x in lire(res):
            fixes[f"{c}:{x['n']}"] = {"Embeddings": x["Embeddings"], "Plein texte": x["Plein texte"]}
    variantes = {f.stem[len("variante_"):]: {x["cle"]: x for x in lire(f)} for f in sorted(ICI.glob("variante_*.jsonl"))}
    cles = sorted(set.intersection(*(set(v) for v in variantes.values())))
    sc = {k: next(iter(variantes.values()))[k]["sous_corpus"] for k in cles}
    groupes = ["23-25/09", "26/09", "27-29/09", "tout"]
    lignes = {}
    def compte(listes):
        out = {}
        for g in groupes:
            ks = [k for k in cles if g == "tout" or sc[k] == g]
            out[g] = (sum(len(set(listes[k]) & reg[k]["utiles"]) for k in ks), sum(len(listes[k]) for k in ks),
                      sum(1 for k in ks if listes[k] and not set(listes[k]) & reg[k]["utiles"]))
        return out
    for nom, v in variantes.items():
        lignes[nom] = compte({k: v[k]["faits"] for k in cles})
    for e in ("Embeddings", "Plein texte"):
        lignes[e] = compte({k: fixes[k][e] for k in cles})
    tot = {g: sum(len(reg[k]["utiles"]) for k in cles if g == "tout" or sc[k] == g) for g in groupes}
    n = {g: sum(1 for k in cles if g == "tout" or sc[k] == g) for g in groupes}
    print(f"{'':28}" + "".join(f"{g + f' ({n[g]} rech., {tot[g]} utiles)':>30}" for g in groupes))
    for nom, v in lignes.items():
        print(f"{nom:28}" + "".join(f"{f'{u} utiles · préc {u / max(1, p):.0%} · rien {r}':>30}" for u, p, r in (v[g] for g in groupes)))
    (ICI / "bilan10.json").write_text(json.dumps({"recherches": n, "utiles": tot, "lignes": lignes}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    ICI.mkdir(parents=True, exist_ok=True)
    sys.exit(bilan() if NOM == "bilan" else variante())
