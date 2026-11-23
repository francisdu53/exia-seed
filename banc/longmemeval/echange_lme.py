#!/usr/bin/env python3
"""Banc 17 §30 — LongMemEval, consolidation « un échange par lot » (idée de Francis, 12/11/2026).

Mêmes 100 questions que le §27 (graine 1109, hors abstention), même consigne (consigne de Luna traduite, L1), même
Luna « low » ; seule différence : chaque session est découpée en ÉCHANGES (un tour de l'utilisateur + les réponses de
l'assistant qui suivent), un fichier brut par échange, et UN SEUL lot par appel au modèle.

Deux étapes :
  LOCOMO_ETAPE=consolider  — dans le conteneur de Nexa, par son abonnement (client d'Hermès, aucune clé copiée) ;
                             SHARD=i/n pour répartir les questions entre plusieurs processus ;
  LOCOMO_ETAPE=questions   — conteneur jetable : lecteur et juge de docs/13 (gpt-4o-mini, API), comparaison question
                             par question avec L1 du §27 (lots de 10 000, même consigne, même modèle).
"""
import json, math, os, random, shutil, sys, time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, "/locomo") if Path("/locomo").exists() else None
import commun as K
K.preparer_chemins()
from exia_seed import langues
from exia_seed.consolidation import Consolidateur

UTC = ZoneInfo("UTC"); IMP = ("user", "assistant"); MODELE = "gpt-6-luna"
ICI = Path(__file__).resolve().parent
CONSIGNE_EN = (ICI / "consigne_luna_en.txt").read_text(encoding="utf-8").strip()
ETAPE = os.environ.get("LOCOMO_ETAPE", "consolider")
tous = K.charger_donnees([])
ids = sorted(c["sample_id"] for c in tous if not c["qa"][0].get("abstention"))
SEL = random.Random(1109).sample(ids, 100)
convs = {c["sample_id"]: c for c in tous if c["sample_id"] in set(SEL)}


def fonction_abonnement(journal: Path):
    """Luna par le client d'Hermès et l'abonnement de Nexa (comme sa consolidation de nuit). Journal = cache."""
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
        cle = K.empreinte({"m": MODELE, "msg": messages, "abonnement": 1})
        if cle in cache:
            return cache[cle]["texte"]
        for essai in range(6):
            try:
                t0 = time.monotonic()
                rep = call_llm(task="exia_seed_consolidation", provider=cfg.get("provider") or None, model=MODELE,
                               messages=messages, reasoning_config=parse_reasoning_effort("low"), timeout=300)
                break
            except Exception as e:
                if essai == 5:
                    raise
                print(f"  (nouvel essai {essai + 1} : {str(e)[:120]})", flush=True); time.sleep(30 * (essai + 1))
        texte = extract_content_or_reasoning(rep)
        us = getattr(rep, "usage", None)
        b = us.model_dump() if hasattr(us, "model_dump") else (dict(us) if isinstance(us, dict) else (vars(us) if us is not None else {}))
        b = json.loads(json.dumps(b or {}, default=str))
        x = {"cle": cle, "modele": MODELE, "abonnement": True, "duree_s": round(time.monotonic() - t0, 1),
             "entree": int(b.get("prompt_tokens") or b.get("input_tokens") or 0),
             "entree_cache": int((b.get("prompt_tokens_details") or b.get("input_tokens_details") or {}).get("cached_tokens") or 0),
             "sortie": int(b.get("completion_tokens") or b.get("output_tokens") or 0), "texte": texte,
             "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        cache[cle] = x
        with journal.open("a", encoding="utf-8") as f:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
        return texte
    return appeler


def echanges(tours):
    """Un échange = un tour de l'utilisateur + les tours de l'assistant qui suivent."""
    out = []
    for t in tours:
        if not K.texte_du_tour(t):
            continue
        if not out or K.etiquette(t["speaker"]) != "assistant":
            out.append([])
        out[-1].append(t)
    return out


def consolider(qid, fn):
    racine = K.RUN / "memoires" / qid
    if (racine / "fini.json").exists():
        return
    if racine.exists(): shutil.rmtree(racine)
    langues.fixer(racine, "en"); raw = racine / "raw"; raw.mkdir(parents=True)
    cons = Consolidateur(racine, UTC, fn, modele=MODELE, max_tokens_entree=10000, nom_agent="assistant",
                         nom_utilisateur="user", consigne="adaptee")
    import copy
    cons.masque = copy.copy(cons.masque)
    cons.masque.consigne_consolidation_adaptee = lambda locuteur: CONSIGNE_EN.replace("{LOCUTEUR}", locuteur or "user")
    cons.max_tokens = 1                                   # §30 : un seul lot (un échange) par appel
    par_jour, n_lots = {}, 0
    for n, quand, tours in K.sessions(convs[qid]):
        jour = quand.date().isoformat()
        for ech in echanges(tours):
            par_jour[jour] = par_jour.get(jour, 0) + 1; n_lots += 1
            nom = f"{jour}_{par_jour[jour]:03d}.md"
            lignes = [f"[{quand:%H:%M} {K.etiquette(t['speaker'])}] {K.texte_du_tour(t)}" for t in ech]
            (raw / nom).write_text(f"---\ntype: raw\ndate: {jour}\nlang: en\nsession: {n}\nouvert_le: {quand.isoformat()}+00:00\n---\n\n"
                                   "## Échanges\n\n" + "\n".join(lignes) + "\n", encoding="utf-8")
            with (raw / ".chaine.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps({"fichier": nom}) + "\n")
        for _ in range(400):
            avant = list(cons.lots_en_attente())
            if not avant: break
            r = cons.consolider()
            if r.get("statut") not in ("ok", "vide") or list(cons.lots_en_attente()) == avant: break
    (racine / "fini.json").write_text(json.dumps({"perdus": len(cons.lots_en_attente()), "lots": n_lots}))


if ETAPE == "consolider":
    i, n = (int(x) for x in os.environ.get("SHARD", "0/1").split("/"))
    mes = [q for k, q in enumerate(SEL) if k % n == i]
    fn = fonction_abonnement(K.RUN / f"appels-{i}.jsonl")
    for qid in mes:
        t0 = time.monotonic(); consolider(qid, fn)
        print(qid, "fini", round(time.monotonic() - t0), "s", flush=True)
    sys.exit(0)

# ── étape « questions » : lecteur et juge (API), comparaison avec L1 du §27
from exia_seed.requete import Lecteur
import modele
import repondre_lme as RL
import juger_lme as JL


def repondre(mem, q):
    L = Lecteur(mem, implicites=IMP); dates = K.faits_dates(mem)
    c = L.chercher(q["question"], 10, datetime.fromisoformat(q["instant"]), faits_max=K.BUDGET_FAITS)
    faits = [f["fait"] for x in c.get("resultats", []) for f in x["faits"]]
    faits += [p["fait"] for p in (c.get("pistes") or {}).get("faits", []) if p["fait"] not in faits]
    rep = RL.repondre(RL.FAITS, K.contexte(faits[:K.BUDGET_FAITS], dates), q)
    return JL.juger(q, rep)["label"] == "CORRECT"


ref = json.loads((K.BANC / "runs" / "luna-en-lme" / "bilan.json").read_text())["detail"]
qs = {q["conv"]: q for q in K.questions(list(convs.values()))}
res, perdus, lots = [], 0, 0
for qid in SEL:
    f = json.loads((K.RUN / "memoires" / qid / "fini.json").read_text()); perdus += f["perdus"]; lots += f["lots"]
    res.append(repondre(K.RUN / "memoires" / qid, qs[qid]))
    print(qid, qs[qid].get("type"), res[-1], flush=True)


def mc(a, b):
    s1 = sum(x and not y for x, y in zip(a, b)); s2 = sum(y and not x for x, y in zip(a, b)); m = s1 + s2
    return s1, s2, (min(1, 2 * sum(math.comb(m, k) for k in range(min(s1, s2) + 1)) / 2 ** m) if m else 1)


conso = {"appels": 0, "entree": 0, "entree_cache": 0, "sortie": 0, "duree_s": 0.0}
for j in K.RUN.glob("appels-*.jsonl"):
    for l in j.read_text(encoding="utf-8").splitlines():
        if l.strip():
            x = json.loads(l); conso["appels"] += 1
            for k in ("entree", "entree_cache", "sortie", "duree_s"): conso[k] += x.get(k) or 0
bilan = {"questions": len(res), "echange": round(100 * sum(res) / len(res), 1),
         "L1_lots_10000": ref["L1"] and round(100 * sum(ref["L1"]) / len(ref["L1"]), 1),
         "reference_gpt4o_mini": round(100 * sum(ref["reference"]) / len(ref["reference"]), 1),
         "echange_contre_L1": mc(res, ref["L1"]), "lots_perdus": perdus, "lots": lots,
         "consolidation_abonnement": conso, "depense_api_lecteur_juge": modele.depense()["total"]}
(K.RUN / "bilan.json").write_text(json.dumps({"bilan": bilan, "detail": {"echange": res}}, indent=1))
print(json.dumps(bilan, indent=1))
