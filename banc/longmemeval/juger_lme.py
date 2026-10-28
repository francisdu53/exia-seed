#!/usr/bin/env python3
"""LongMemEval — le juge OFFICIEL (docs/13) : consignes par type de question et pour l'abstention, MOT POUR MOT
(xiaowu0162/LongMemEval @ 9e0b455, src/evaluation/evaluate_qa.py, get_anscheck_prompt), température 0, 10 tokens,
étiquette = « yes » dans la réponse. UNE passe, comme le dépôt. Seul écart déclaré : GPT-4o-mini au lieu de GPT-4o.

    python3 juger_lme.py [--fils 8]
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "/locomo")
import commun as K                                                # noqa: E402
import modele                                                     # noqa: E402

_DEBUT = ("I will give you a question, a correct answer, and a response from a model. Please answer yes if the response "
          "contains the correct answer. Otherwise, answer no. ")
_ETAPES = ("If the response is equivalent to the correct answer or contains all the intermediate steps to get the correct "
           "answer, you should also answer yes. If the response only contains a subset of the information required by "
           "the answer, answer no. ")
_FIN = "\n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
GABARITS = {   # evaluate_qa.py @ 9e0b455, l. 27-41 — VERBATIM (recomposé par morceaux identiques, vérifié par test)
    "standard": _DEBUT + _ETAPES + _FIN.lstrip(" "),
    "temporal-reasoning": _DEBUT + _ETAPES + "In addition, do not penalize off-by-one errors for the number of days. If the "
        "question asks for the number of days/weeks/months, etc., and the model makes off-by-one errors (e.g., predicting "
        "19 days when the answer is 18), the model's response is still correct. " + _FIN,
    "knowledge-update": _DEBUT + "If the response contains some previous information along with an updated answer, the "
        "response should be considered as correct as long as the updated answer is the required answer." + _FIN,
    "single-session-preference": "I will give you a question, a rubric for desired personalized response, and a response "
        "from a model. Please answer yes if the response satisfies the desired response. Otherwise, answer no. The model "
        "does not need to reflect all the points in the rubric. The response is correct as long as it recalls and utilizes "
        "the user's personal information correctly.\n\nQuestion: {}\n\nRubric: {}\n\nModel Response: {}\n\nIs the model "
        "response correct? Answer yes or no only.",
    "abstention": "I will give you an unanswerable question, an explanation, and a response from a model. Please answer yes "
        "if the model correctly identifies the question as unanswerable. The model could say that the information is "
        "incomplete, or some other information is given but the asked information is not.\n\nQuestion: {}\n\nExplanation: "
        "{}\n\nModel Response: {}\n\nDoes the model correctly identify the question as unanswerable? Answer yes or no only.",
}


def gabarit(q) -> str:
    if q.get("abstention"):
        return GABARITS["abstention"]
    return GABARITS.get(q["type"], GABARITS["standard"])


def juger(q, reponse: str) -> dict:
    rep = modele.appeler([{"role": "user", "content": gabarit(q).format(q["question"], q["gold"], reponse)}],
                         "juge", max_tokens=10)
    return {"label": "CORRECT" if "yes" in (rep or "").lower() else "WRONG", "brut": (rep or "")[:20]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fils", type=int, default=8)
    a = ap.parse_args()
    qs = {q["id"]: q for q in K.questions(K.charger_donnees(K.selection_du_run()))}
    for f in sorted((K.RUN / "reponses").glob("*.jsonl")):
        reps = K.lire_jsonl(f)
        try:
            with ThreadPoolExecutor(a.fils) as ex:
                res = list(ex.map(lambda r: juger(qs[r["id"]], r["reponse"]), reps))
        except modele.BudgetDepasse as e:
            print(f"  ⛔ {e} — arrêt ; relancer reprend sans repayer", flush=True)
            return 2
        K.ecrire_jsonl(K.RUN / "jugements" / f.name, [{"id": r["id"], **x} for r, x in zip(reps, res)])
        print(f"  {f.stem} : {sum(x['label'] == 'CORRECT' for x in res)}/{len(res)}", flush=True)
    print(f"dépense cumulée : {modele.depense()['total']['usd']:.3f} $")
    return 0


if __name__ == "__main__":
    sys.exit(main())
