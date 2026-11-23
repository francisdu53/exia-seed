#!/usr/bin/env python3
"""Étape 5 — le juge, selon le PROTOCOLE DE RÉFÉRENCE de LoCoMo (docs/09 §13).

Recherche sur les concurrents (01/10/2026) : Mem0 a fixé en 2025 le protocole « de fait », repris tel quel par
Zep, MemOS, MemMachine et EverMemOS : consigne du juge Mem0 MOT POUR MOT, GPT-4o-mini, température 0, sortie JSON,
catégorie 5 EXCLUE du score J, F1 de tokens (papier LoCoMo) rapporté à côté.

- Catégories 1-4 : la consigne de Mem0, extraite PAR PROGRAMME de leur dépôt (mem0ai/mem0, commit aae5989e du
  8 juillet 2025, evaluation/metrics/llm_judge.py, ACCURACY_PROMPT) — aucune modification. 3 PASSES (bonne pratique
  de Mem0, MemOS, EverMemOS) : moyenne ± écart-type, et l'étiquette retenue par question à la majorité.
- Catégorie 5 : hors de J ; notée à part par RÈGLE (réponse d'abstention = juste), pendant de la règle du papier
  LoCoMo (« not mentioned » / « no information available »), élargie à « unknown » que demande notre consigne de réponse.
- Historique : v1 = juge d'EXIA GHOST (phrase ajoutée « unknown = correct », appliquée par GPT-4o-mini à TOUTES les
  questions, §12.2) ; v2 = abstention par règle + juge sans la phrase. Archivés : jugements-v1-juge-ghost/, jugements-v2-regle/.

    python3 juger.py [--passes 3] [--fils 8]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import commun as K
import modele

# Mem0, evaluation/metrics/llm_judge.py @ aae5989e — VERBATIM (y compris les apostrophes typographiques et les espaces)
ACCURACY_PROMPT = """
Your task is to label an answer to a question as ’CORRECT’ or ’WRONG’. You will be given the following data:
    (1) a question (posed by one user to another user), 
    (2) a ’gold’ (ground truth) answer, 
    (3) a generated answer
which you will score as CORRECT/WRONG.

The point of the question is to ask about something one user should know about the other user based on their prior conversations.
The gold answer will usually be a concise and short answer that includes the referenced topic, for example:
Question: Do you remember what I got the last time I went to Hawaii?
Gold answer: A shell necklace
The generated answer might be much longer, but you should be generous with your grading - as long as it touches on the same topic as the gold answer, it should be counted as CORRECT. 

For time related questions, the gold answer will be a specific date, month, year, etc. The generated answer might be much longer or use relative time references (like "last Tuesday" or "next month"), but you should be generous with your grading - as long as it refers to the same date or time period as the gold answer, it should be counted as CORRECT. Even if the format differs (e.g., "May 7th" vs "7 May"), consider it CORRECT if it's the same date.

Now it's time for the real question:
Question: {question}
Gold answer: {gold_answer}
Generated answer: {generated_answer}

First, provide a short (one sentence) explanation of your reasoning, then finish with CORRECT or WRONG. 
Do NOT include both CORRECT and WRONG in your response, or it will break the evaluation script.

Just return the label CORRECT or WRONG in a json format with the key as "label".
"""

ABSTENTION = re.compile(r"^\W*(unknown|not mentioned|no information|not specified|not stated|n/?a|none)\b"
                        r"|\b(not mentioned|no information|unknown)\W*$", re.I)


def juger_c14(q, reponse: str, passe: int) -> str:
    rep = modele.appeler([{"role": "user", "content": ACCURACY_PROMPT.format(
        question=q["question"], gold_answer=q["gold"], generated_answer=reponse)}],
        "juge", max_tokens=200, json_seul=True, passe=passe)
    m = re.search(r'"label"\s*:\s*"(CORRECT|WRONG)"', rep or "")
    return m.group(1) if m else "UNKNOWN"


def juger(q, reponse: str, passes: int) -> dict:
    if q["categorie"] == 5:
        return {"label": "CORRECT" if ABSTENTION.search((reponse or "").strip()) else "WRONG", "passes": [], "regle": True}
    labels = [juger_c14(q, reponse, p) for p in range(1, passes + 1)]
    return {"label": Counter(labels).most_common(1)[0][0], "passes": labels, "regle": False}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--passes", type=int, default=3)
    ap.add_argument("--fils", type=int, default=8)
    a = ap.parse_args()
    qs = {q["id"]: q for q in K.questions(K.charger_donnees(K.selection_du_run()))}
    for f in sorted((K.RUN / "reponses").glob("*.jsonl")):
        reps = K.lire_jsonl(f)
        try:
            with ThreadPoolExecutor(a.fils) as ex:
                res = list(ex.map(lambda r: juger(qs[r["id"]], r["reponse"], a.passes), reps))
        except modele.BudgetDepasse as e:
            print(f"  ⛔ {e} — arrêt ; relancer reprend sans repayer", flush=True)
            return 2
        K.ecrire_jsonl(K.RUN / "jugements" / f.name, [{"id": r["id"], **x} for r, x in zip(reps, res)])
        c14 = [x for r, x in zip(reps, res) if qs[r["id"]]["categorie"] != 5]
        print(f"  {f.stem} : J cat. 1-4 = {sum(x['label'] == 'CORRECT' for x in c14)}/{len(c14)} · "
              f"{sum(x['label'] == 'UNKNOWN' for x in c14)} illisibles", flush=True)
    print(f"dépense cumulée : {modele.depense()['total']['usd']:.3f} $")
    return 0


if __name__ == "__main__":
    sys.exit(main())
