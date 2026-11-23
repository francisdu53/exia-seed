#!/usr/bin/env python3
"""Phase 0 — lecteur et juge COMMUNS à tous les concurrents, avec les vrais tokens et le temps de chaque appel.

Pour chaque question d'un fichier de contextes (`runs/contextes/*.jsonl`) :
  lecteur  Terra, effort « high » — consignes des bancs, inchangées (LoCoMo « QA », LongMemEval « Chain-of-Note »)
  juge     Terra, effort « low » — Mem0 ACCURACY_PROMPT (LoCoMo ; catégorie 5 par la règle d'abstention, sans appel) /
           gabarits LongMemEval
Tokens : l'USAGE renvoyé par l'appel (entrée, sortie raisonnement compris) — plus d'estimation « longueur ÷ 4 ».
Cache par empreinte (modèle, effort, sel, consigne) : une consigne identique n'est jamais facturée deux fois ; le
rapport sépare les appels faits et les appels repris du cache. BRUIT : pour 10 % des questions (empreinte de l'id),
le juge rejuge la même réponse et le lecteur relit le même contexte (sel différent, même consigne envoyée).
Un appel à la fois ; erreurs : 3 reprises espacées ; quota atteint : arrêt propre (code 4), la chaîne reprend plus tard.
Reprise : les questions déjà faites dans la sortie sont sautées.
Conteneur Nexa :
  docker exec -u 10000 -w /opt/data/workspace/banc-cartes/eval nexa /opt/hermes/.venv/bin/python3 lire_juger.py <contextes>
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, str(ICI)); sys.path.insert(0, str(ICI.parent / "harnais"))
SRC = Path(sys.argv[1]) if Path(sys.argv[1]).is_absolute() else ICI / "runs" / "contextes" / sys.argv[1]
BANC = "lme" if "_lme_" in SRC.name else "locomo"
os.environ["LOCOMO_DONNEES"] = str(ICI.parent / "bancs" / "donnees" / ("lme_oracle_locomo.json" if BANC == "lme" else "locomo10.json"))
import commun as KH                                            # noqa: E402

MODELE = os.environ.get("EVAL_MODELE", "gpt-6.1-terra")
EFFORT_LECTEUR, EFFORT_JUGE = os.environ.get("EVAL_EFFORT_LECTEUR", "high"), "low"
CACHE_F = ICI / "runs" / "cache_appels.jsonl"
QUOTA = re.compile(r"usage limit|quota|rate limit|too many requests|429", re.I)
CACHE = {}
if CACHE_F.exists():
    for l in CACHE_F.read_text(encoding="utf-8").splitlines():
        if l.strip():
            e = json.loads(l); CACHE[e["cle"]] = e


def appel_brut(effort: str, contenu: str):
    from agent.auxiliary_client import call_llm, extract_content_or_reasoning
    from hermes_cli.config import load_config
    from hermes_constants import parse_reasoning_effort
    cfg = (load_config() or {}).get("model") or {}
    t0 = time.perf_counter_ns()
    rep = call_llm(task="exia_seed_consolidation", provider=cfg.get("provider") or None, model=MODELE,
                   messages=[{"role": "user", "content": contenu}], reasoning_config=parse_reasoning_effort(effort),
                   timeout=600 if effort == "high" else 300)
    ms = (time.perf_counter_ns() - t0) / 1e6
    u = getattr(rep, "usage", None)
    usage = {"entree": getattr(u, "prompt_tokens", None), "sortie": getattr(u, "completion_tokens", None)} if u else None
    return extract_content_or_reasoning(rep) or "", usage, ms


def appeler(effort: str, contenu: str, sel: str = "") -> dict:
    cle = hashlib.sha256(f"{MODELE}|{effort}|{sel}|{contenu}".encode()).hexdigest()
    if cle in CACHE:
        e = CACHE[cle]
        return {"texte": e["texte"], "usage": e["usage"], "ms": e["ms"], "cache": True}
    for essai in range(4):
        try:
            texte, usage, ms = appel_brut(effort, contenu)
            break
        except Exception as ex:
            msg = f"{type(ex).__name__}: {str(ex)[:300]}"
            if QUOTA.search(msg):
                print(f"QUOTA : {msg}", flush=True); sys.exit(4)
            if essai == 3:
                print(f"ARRÊT : {msg}", flush=True); sys.exit(3)
            time.sleep(60 * (essai + 1))
    e = {"cle": cle, "modele": MODELE, "effort": effort, "texte": texte, "usage": usage, "ms": round(ms, 1),
         "date": time.strftime("%Y-%m-%dT%H:%M:%S")}
    CACHE[cle] = e
    with CACHE_F.open("a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return {"texte": texte, "usage": usage, "ms": round(ms, 1), "cache": False}


def main() -> int:
    if BANC == "locomo":
        from repondre import QA
        from juger import ACCURACY_PROMPT, ABSTENTION
    else:
        from repondre_lme import FAITS
        from juger_lme import gabarit
    qs = {q["id"]: q for q in KH.questions(json.loads(Path(KH.DONNEES).read_text(encoding="utf-8")))}
    ctx = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    sortie = ICI / "runs" / "reponses" / SRC.name
    sortie.parent.mkdir(parents=True, exist_ok=True)
    faits = {json.loads(l)["id"] for l in sortie.read_text(encoding="utf-8").splitlines() if l.strip()} if sortie.exists() else set()

    def lire(q, bloc, sel=""):
        if BANC == "locomo":
            return appeler(EFFORT_LECTEUR, QA.format(context=bloc, question=q["question"]), sel)
        return appeler(EFFORT_LECTEUR, FAITS.format(bloc, q.get("date_question", ""), q["question"]), sel)

    def juger(q, reponse, sel=""):
        if BANC == "locomo":
            if q["categorie"] == 5:
                return ("CORRECT" if ABSTENTION.search(reponse.strip()) else "WRONG"), None
            j = appeler(EFFORT_JUGE, ACCURACY_PROMPT.format(question=q["question"], gold_answer=q["gold"],
                                                             generated_answer=reponse), sel)
            m = re.search(r'"label"\s*:\s*"(CORRECT|WRONG)"', j["texte"] or "")
            return (m.group(1) if m else "UNKNOWN"), j
        j = appeler(EFFORT_JUGE, gabarit(q).format(q["question"], q["gold"], reponse), sel)
        return ("CORRECT" if "yes" in (j["texte"] or "").lower() else "WRONG"), j

    n = 0
    for c in ctx:
        if c["id"] in faits:
            continue
        q = qs[c["id"]]
        lu = lire(q, c["bloc"])
        label, j = juger(q, lu["texte"])
        ligne = {"id": c["id"], "categorie": q.get("categorie"), "type": q.get("type"), "label": label,
                 "reponse": lu["texte"][:600], "lecteur": {k: lu[k] for k in ("usage", "ms", "cache")},
                 "juge": {k: j[k] for k in ("usage", "ms", "cache")} if j else None,
                 "tokens_bloc": c.get("tokens_bloc")}
        if int(hashlib.sha1(c["id"].encode()).hexdigest(), 16) % 10 == 0 and os.environ.get("EVAL_BRUIT", "1") == "1":
            l2, j2 = juger(q, lu["texte"], "rejuge")
            lu3 = lire(q, c["bloc"], "relu")
            l3, j3 = juger(q, lu3["texte"])
            ligne["bruit"] = {"rejuge": l2, "relu": l3,
                              "appels": [x for x in (j2, lu3, j3) if x and not x["cache"]].__len__(),
                              "usage": [x["usage"] for x in (j2, lu3, j3) if x and not x["cache"]]}
        with sortie.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
        n += 1
        if n % 25 == 0:
            print(f"  {n} questions · {sortie.name}", flush=True)
    print(f"FIN {sortie.name} : {n} nouvelles questions", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
