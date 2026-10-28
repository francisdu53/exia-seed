#!/usr/bin/env python3
"""Étape 5 bis (HÔTE, nltk) — le F1 de tokens du PAPIER LoCoMo, indépendant de tout juge (docs/09 §13).

Fonctions recopiées de snap-research/locomo, task_eval/evaluation.py (normalize_answer, f1_score, f1) : réponse et
référence normalisées (minuscules, ponctuation, articles), racinisées (Porter), F1 du recouvrement ; catégorie 1 :
F1 partiel par sous-réponse (séparées par des virgules) ; catégorie 3 : référence coupée au premier « ; » ;
catégorie 5 : 1 si la réponse contient « not mentioned » ou « no information available » (règle du papier).

    LOCOMO_BANC=$HOME/banc-locomo LOCOMO_RUN=pilote ${PYTHON_EMBEDDINGS:-python3} f1.py
"""
from __future__ import annotations

import string
import sys
from collections import Counter

import numpy as np
import regex
from nltk.stem import PorterStemmer

import commun as K

ps = PorterStemmer()


def normalize_answer(s):                                   # verbatim, evaluation.py
    s = s.replace(',', "")

    def remove_articles(text):
        return regex.sub(r'\b(a|an|the|and)\b', ' ', text)

    def white_space_fix(text):
        return ' '.join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        return ''.join(ch for ch in text if ch not in exclude)

    def lower(text):
        return text.lower()

    return white_space_fix(remove_articles(remove_punc(lower(s))))


def f1_score(prediction, ground_truth):                    # verbatim, evaluation.py
    prediction_tokens = [ps.stem(w) for w in normalize_answer(prediction).split()]
    ground_truth_tokens = [ps.stem(w) for w in normalize_answer(ground_truth).split()]
    common = Counter(prediction_tokens) & Counter(ground_truth_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0
    precision = 1.0 * num_same / len(prediction_tokens)
    recall = 1.0 * num_same / len(ground_truth_tokens)
    return (2 * precision * recall) / (precision + recall)


def f1(prediction, ground_truth):                          # verbatim, evaluation.py (catégorie 1)
    predictions = [p.strip() for p in prediction.split(',')]
    ground_truths = [g.strip() for g in ground_truth.split(',')]
    return np.mean([max([f1_score(prediction, gt) for prediction in predictions]) for gt in ground_truths])


def score(q, sortie: str) -> float:                        # eval_question_answering, evaluation.py
    reponse = str(q["gold"])
    if q["categorie"] == 3:
        reponse = reponse.split(';')[0].strip()
    if q["categorie"] in (2, 3, 4):
        return float(f1_score(sortie, reponse))
    if q["categorie"] == 1:
        return float(f1(sortie, reponse))
    return 1.0 if ('no information available' in sortie.lower() or 'not mentioned' in sortie.lower()) else 0.0


def main() -> int:
    qs = {q["id"]: q for q in K.questions(K.charger_donnees(K.selection_du_run()))}
    for f in sorted((K.RUN / "reponses").glob("*.jsonl")):
        lignes = [{"id": r["id"], "f1": round(score(qs[r["id"]], r["reponse"] or ""), 4)} for r in K.lire_jsonl(f)]
        K.ecrire_jsonl(K.RUN / "f1" / f.name, lignes)
        c14 = [l["f1"] for l in lignes if qs[l["id"]]["categorie"] != 5]
        print(f"  {f.stem} : F1 cat. 1-4 = {100 * sum(c14) / max(1, len(c14)):.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
