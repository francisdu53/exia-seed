#!/usr/bin/env python3
"""Banc 17 §13 — la liste des nœuds ciblée par la recherche, à GRANDE échelle (LongMemEval fusionnée).

Départ : la mémoire fusionnée de 460 conversations (run `catalogue-base`, ≈ 2 100 pages), SANS les 40 questions tirées
(`donnees/tirage-catalogue-0511.json`, graine 1105, hors abstention). On y consolide, l'une après l'autre et session
par session, les conversations de ces 40 questions — comme une mémoire qui grandit. Deux conditions, seule change la
liste des nœuds existants que voit le modèle :
- `complet` : toute la liste (la production). La sélection que ferait la recherche est CALCULÉE et journalisée, pas
  appliquée — pour mesurer son rappel ;
- `cible` : les 30 pages au plus que la recherche fait remonter, plus l'utilisateur et l'assistant (même règle qu'au §12).
La résolution des alias garde la liste complète dans les deux cas. Puis les 40 questions, moteur A à l'échelle F,
même lecteur et même juge que docs/13.

    RUN=catalogue-complet-1 python3 catalogue_lme.py complet
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, "/locomo")
import commun as K                                                # noqa: E402

K.preparer_chemins()
from exia_seed import langues                                     # noqa: E402
from exia_seed.consolidation import Consolidateur                 # noqa: E402
from exia_seed import rappel as _RP                               # noqa: E402
from exia_seed.rappel import Rappeleur                            # noqa: E402
from exia_seed.requete import Lecteur                             # noqa: E402
import modele                                                     # noqa: E402
import repondre_lme as RL                                         # noqa: E402
import juger_lme as JL                                            # noqa: E402

CIBLE_MAX = 30
import os                                                         # noqa: E402
import time                                                       # noqa: E402
if os.environ.get("LOCOMO_SIGLES") == "1":                        # §17 : la règle des sigles (§16), banc seulement
    import variante_sigles
    variante_sigles.appliquer(_RP)
ABONNEMENT = os.environ.get("LOCOMO_ABONNEMENT") == "1"            # §17 : la consolidation par l'abonnement de Nexa
ETAPE = os.environ.get("LOCOMO_ETAPE", "tout")                    # consolider (conteneur de Nexa) | questions (API) | tout
# §14 : le modèle de CONSOLIDATION seul change (Terra) ; lecteur et juge restent ceux de docs/13 (gpt-4o-mini)
CONSO = os.environ.get("LOCOMO_MODELE_CONSOLIDATION", K.MODELE)
SORTIE = int(os.environ.get("LOCOMO_SORTIE_CONSOLIDATION", "2000"))
IMPLICITES = ("user", "assistant")
BASE = K.BANC / "runs" / "catalogue-base" / "memoires" / "_fusion"
TIRAGE = K.BANC / "donnees" / "tirage-catalogue-0511.json"
TRES_TARD = datetime(2100, 1, 1)
_MSG = re.compile(r"^\[(raw/[^\]]+|registre:[^\]]+)\] ?(.*)$")


def selectionner(R: Rappeleur, sources: str):
    """Les nœuds que la recherche fait remonter pour les messages du lot, classés (touchés d'abord, puis propagation)."""
    textes, courant = [], ""
    for l in sources.splitlines():
        m = _MSG.match(l)
        if not m:
            continue
        ref, t = m.groups()
        if ref.startswith("registre:") or re.match(r"\[\d\d:\d\d ", t):
            if courant: textes.append(courant)
            courant = t
        else:
            courant += " " + t
    if courant: textes.append(courant)
    mem = R.memoire(); score = {}
    if mem is not None:
        for t in textes:
            a = R.activer(mem, t)
            for n, v in a["entrees"].items():
                score[n] = max(score.get(n, 0.0), 1.0 + v)
            for n, v in a["actives"].items():
                score[n] = max(score.get(n, 0.0), v)
    return sorted(score, key=score.get, reverse=True), len(textes)


def par_message(R: Rappeleur, sources: str, presents: set, k: int):
    """§17 : chaque message cherché SEUL ; les k meilleures pages de chacun, réunies (pas de séquentiel)."""
    textes, courant = [], ""
    for l in sources.splitlines():
        m = _MSG.match(l)
        if not m:
            continue
        ref, t = m.groups()
        if ref.startswith("registre:") or re.match(r"\[\d\d:\d\d ", t):
            if courant: textes.append(courant)
            courant = t
        else:
            courant += " " + t
    if courant: textes.append(courant)
    mem = R.memoire(); garder, candidats = set(), set()
    if mem is not None:
        for t in textes:
            a = R.activer(mem, t); loc = {}
            for n, v in a["entrees"].items():
                if n in presents: loc[n] = max(loc.get(n, 0.0), 1.0 + v)
            for n, v in a["actives"].items():
                if n in presents: loc[n] = max(loc.get(n, 0.0), v)
            candidats |= set(loc)
            garder |= set(sorted(loc, key=loc.get, reverse=True)[:k])
    return garder, len(candidats), len(textes)


def enveloppe(fn, racine: Path, condition: str, journal: Path, etat: dict):
    R = Rappeleur(racine, implicites=IMPLICITES)
    T = langues.de_la_memoire(racine).textes
    tete_n, tete_c, tete_s = T["noeuds_existants"] + "\n", "\n\n" + T["concepts_existants"] + "\n", "\n\n" + T["sources"] + "\n"

    def appeler(messages):
        u = messages[-1]["content"]
        if not u.startswith(tete_n) or tete_c not in u:
            return fn(messages)                                        # l'appel des fiches : inchangé
        tete, reste = u.split(tete_c, 1)
        lignes = tete.split("\n")[1:]
        noeud = lambda l: l[2:].split(" (", 1)[0]
        presents = [noeud(l) for l in lignes if l.startswith("- ")]
        p = set(presents)
        if condition == "message":
            g, n_cand, n_msg = par_message(R, reste.split(tete_s, 1)[-1], p - set(IMPLICITES), CIBLE_MAX)
            classes = [None] * n_cand
            garder = g | set(IMPLICITES)
        else:
            classes, n_msg = selectionner(R, reste.split(tete_s, 1)[-1])
            classes = [n for n in classes if n in p and n not in IMPLICITES]
            garder = set(classes[:CIBLE_MAX]) | set(IMPLICITES)
        gardees = [l for l in lignes if l.startswith("- ") and noeud(l) in garder] or [T["aucun"]]
        with journal.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"question": etat["q"], "lignes_completes": len(presents), "candidats": len(classes),
                                "lignes_gardees": len(gardees), "messages": n_msg, "car_complet": len(tete),
                                "car_cible": len(tete_n) + len("\n".join(gardees)), "gardes": sorted(garder & p)},
                               ensure_ascii=False) + "\n")
        if condition in ("cible", "message"):
            messages = [*messages[:-1], {"role": "user", "content": tete_n + "\n".join(gardees) + tete_c + reste}]
        return fn(messages)
    return appeler


def fonction_abonnement(journal: Path):
    """Terra par le client d'Hermès et l'abonnement de Nexa (comme sa consolidation de nuit, docs/17 §11.2), sans
    copier ses identifiants. Journal au format de `modele.py` (cache : une reprise ne redemande rien)."""
    sys.path.insert(0, "/opt/hermes")
    from agent.auxiliary_client import call_llm, extract_content_or_reasoning
    from hermes_cli.config import load_config
    from hermes_constants import parse_reasoning_effort
    cfg = (load_config() or {}).get("model") or {}
    cache = {}
    if journal.exists():
        for l in journal.read_text(encoding="utf-8").splitlines():
            if l.strip():
                x = json.loads(l); cache[x["cle"]] = x

    def appeler(messages):
        cle = K.empreinte({"m": CONSO, "msg": messages, "abonnement": 1})
        if cle in cache:
            return cache[cle]["texte"]
        for essai in range(6):
            try:
                rep = call_llm(task="exia_seed_consolidation", provider=cfg.get("provider") or None, model=CONSO,
                               messages=messages, reasoning_config=parse_reasoning_effort(os.environ.get("LOCOMO_EFFORT", "low")),
                               timeout=300)
                break
            except Exception as e:
                if essai == 5:
                    raise
                print(f"  (nouvel essai {essai + 1} : {str(e)[:120]})", flush=True); time.sleep(30 * (essai + 1))
        texte = extract_content_or_reasoning(rep)
        us = getattr(rep, "usage", None)
        b = us.model_dump() if hasattr(us, "model_dump") else (dict(us) if isinstance(us, dict) else (vars(us) if us is not None else {}))
        b = json.loads(json.dumps(b or {}, default=str))
        x = {"cle": cle, "role": "consolidation", "modele": CONSO, "abonnement": True,
             "entree": int(b.get("prompt_tokens") or b.get("input_tokens") or 0),
             "entree_cache": int((b.get("prompt_tokens_details") or b.get("input_tokens_details") or {}).get("cached_tokens") or 0),
             "sortie": int(b.get("completion_tokens") or b.get("output_tokens") or 0), "usd": 0.0, "texte": texte,
             "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        cache[cle] = x
        with journal.open("a", encoding="utf-8") as f:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
        return texte
    return appeler


def main() -> int:
    condition = sys.argv[1]
    assert condition in ("complet", "cible", "message")
    ids = json.loads(TIRAGE.read_text())["ids"]
    convs = {c["sample_id"]: c for c in K.charger_donnees(ids)}
    racine = K.RUN / "memoire"
    if not racine.exists():
        shutil.copytree(BASE, racine)
    raw = racine / "raw"; raw.mkdir(exist_ok=True)
    chaine = raw / ".chaine.jsonl"
    deja = {json.loads(l)["fichier"] for l in (raw / ".consolide.jsonl").read_text().splitlines()} \
        if (raw / ".consolide.jsonl").exists() else set()
    etat = {"q": ""}
    base_fn = fonction_abonnement(K.RUN / "appels.jsonl") if ABONNEMENT else \
        (lambda m: modele.appeler(m, "consolidation", modele=CONSO, max_tokens=SORTIE))
    fn = enveloppe(base_fn, racine, condition, K.RUN / "liste.jsonl", etat)
    cons = Consolidateur(racine, ZoneInfo("UTC"), fn, modele=CONSO, nom_agent="assistant", nom_utilisateur="user")
    bilan = {"sessions": 0, "faits": 0, "rejets": 0, "statuts": {}}
    for qid in (ids if ETAPE != "questions" else ()):                   # l'ordre du tirage : le même pour toutes les conditions
        etat["q"] = qid
        par_jour = {}
        for n, quand, tours in K.sessions(convs[qid]):
            jour = quand.date().isoformat()
            par_jour[jour] = par_jour.get(jour, 0) + 1
            nom = f"{qid}_{jour}_{par_jour[jour]:02d}.md"
            if nom in deja:
                continue
            lignes = [f"[{quand:%H:%M} {K.etiquette(t['speaker'])}] {K.texte_du_tour(t)}" for t in tours if K.texte_du_tour(t)]
            (raw / nom).write_text(f"---\ntype: raw\ndate: {jour}\nlang: en\nsession: {n}\nouvert_le: {quand.isoformat()}+00:00\n---\n\n"
                                   "## Échanges\n\n" + "\n".join(lignes) + "\n", encoding="utf-8")
            dans = {json.loads(l)["fichier"] for l in chaine.read_text().splitlines()} if chaine.exists() else set()
            if nom not in dans:
                with chaine.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"fichier": nom}) + "\n")
            try:
                r = cons.consolider()
            except modele.BudgetDepasse as e:
                print(f"⛔ {e}", flush=True); return 2
            bilan["sessions"] += 1; bilan["faits"] += r.get("faits_retenus") or 0; bilan["rejets"] += r.get("fragments_rejetes") or 0
            bilan["statuts"][r.get("statut")] = bilan["statuts"].get(r.get("statut"), 0) + 1
            print(f"  {condition} {qid} s{n} : {r.get('statut')} {r.get('faits_retenus')} faits", flush=True)
    perdus = len(cons.lots_en_attente())
    f_conso = K.RUN / "bilan-consolidation.json"
    if bilan["sessions"]:                                              # garde le bilan des consolidations faites
        anc = json.loads(f_conso.read_text()) if f_conso.exists() else {"sessions": 0, "faits": 0, "rejets": 0, "statuts": {}}
        for k in ("sessions", "faits", "rejets"):
            anc[k] += bilan[k]
        for k, v in bilan["statuts"].items():
            anc["statuts"][k] = anc["statuts"].get(k, 0) + v
        f_conso.write_text(json.dumps(anc, ensure_ascii=False, indent=1))
    if ETAPE == "consolider":
        print(json.dumps({"consolidation": json.loads(f_conso.read_text()) if f_conso.exists() else bilan, "perdus": perdus}), flush=True)
        return 0
    if f_conso.exists():
        bilan.update({k: v for k, v in json.loads(f_conso.read_text()).items()})
    # les 40 questions, moteur A à l'échelle F (docs/13), lecteur et juge de LongMemEval
    qs = K.questions(list(convs.values()))
    L = Lecteur(racine, implicites=IMPLICITES); dates = K.faits_dates(racine)
    res = []
    for q in qs:
        c = L.chercher(q["question"], 10, TRES_TARD, faits_max=K.BUDGET_FAITS)
        faits = [f["fait"] for x in c.get("resultats", []) for f in x["faits"]]
        faits += [p["fait"] for p in (c.get("pistes") or {}).get("faits", []) if p["fait"] not in faits]
        rep = RL.repondre(RL.FAITS, K.contexte(faits[:K.BUDGET_FAITS], dates), q)
        res.append({"id": q["conv"], "juste": JL.juger(q, rep)["label"] == "CORRECT"})
    bilan.update({"perdus": perdus, "justes": sum(r["juste"] for r in res), "questions": len(res), "detail": res,
                  "depense": modele.depense()["total"]})
    (K.RUN / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in bilan.items() if k != "detail"}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
