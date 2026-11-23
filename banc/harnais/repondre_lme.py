#!/usr/bin/env python3
"""LongMemEval — les réponses (docs/13). Même modèle, même consigne pour tous les moteurs de faits.

Consigne : celle du dépôt de LongMemEval (xiaowu0162/LongMemEval @ 9e0b455, src/generation/run_generation.py),
MOT POUR MOT, version « faits extraits » avec raisonnement pas à pas (Chain-of-Note, la lecture recommandée par le
papier) pour A, B, C, M ; version « historique » pour E. « Current Date » = la date officielle de la question.
    A, B, C : 12 faits datés (contextes du banc LoCoMo) · M : toute la mémoire de la question (S) · E : ses sessions (S)

    python3 repondre_lme.py [A B C M E] [--echelles S F] [--fils 8]
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "/locomo")
import commun as K                                                # noqa: E402
import modele                                                     # noqa: E402

# run_generation.py @ 9e0b455, l. 65 et l. 55 — VERBATIM
FAITS = ('I will give you several facts extracted from history chats between you and a user. Please answer the question '
         'based on the relevant facts. Answer the question step by step: first extract all the relevant information, and '
         'then reason over the information to get the answer.\n\n\nHistory Chats:\n\n{}\n\nCurrent Date: {}\nQuestion: {}\n'
         'Answer (step by step):')
HISTOIRE = ('I will give you several history chats between you and a user. Please answer the question based on the relevant '
            'chat history. Answer the question step by step: first extract all the relevant information, and then reason over '
            'the information to get the answer.\n\n\nHistory Chats:\n\n{}\n\nCurrent Date: {}\nQuestion: {}\nAnswer (step by step):')
MAX_SORTIE = 800                                                  # gen_length du dépôt avec --cot true


def repondre(gabarit: str, contexte: str, q) -> str:
    return modele.appeler([{"role": "user", "content": gabarit.format(contexte, q["date_question"], q["question"])}],
                          "reponse", max_tokens=MAX_SORTIE).strip()


def historique(conv) -> str:
    """Les sessions de la question, datées, dans l'ordre (format « nl » du dépôt)."""
    blocs = []
    for _, quand, tours in K.sessions(conv):
        lignes = "\n".join(f"{t['speaker']}: {t['text'].strip()}" for t in tours)
        blocs.append(f"Session Date: {quand:%Y/%m/%d (%a) %H:%M}\nSession Content:\n{lignes}")
    return "\n\n".join(blocs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("moteurs", nargs="*", default=["A", "B", "C", "M", "E"])
    ap.add_argument("--echelles", nargs="*", default=["S", "F"])
    ap.add_argument("--fils", type=int, default=8)
    a = ap.parse_args()
    convs = {c["sample_id"]: c for c in K.charger_donnees(K.selection_du_run())}
    qs = K.questions(list(convs.values()))
    fusion = K.RUN / "memoires" / "_fusion"
    dates = {}

    def dates_de(mem):
        if mem not in dates:
            dates[mem] = K.faits_dates(mem)
        return dates[mem]

    for moteur in a.moteurs:
        for echelle in a.echelles:
            if echelle == "F" and (moteur in "EM" or not fusion.exists()):
                continue
            ctx = {}
            if moteur in "ABC":
                f = K.RUN / "contextes" / f"{moteur}_{echelle}.jsonl"
                if not f.exists():
                    print(f"  ({f.name} absent : {moteur}_{echelle} sauté)"); continue
                ctx = {x["id"]: x["faits"] for x in K.lire_jsonl(f)}

            def un(q):
                mem = fusion if echelle == "F" else K.RUN / "memoires" / q["conv"]
                if moteur in "ABC":
                    return {"id": q["id"], "reponse": repondre(FAITS, K.contexte(ctx[q["id"]], dates_de(mem)), q),
                            "faits": len(ctx[q["id"]])}
                if moteur == "M":
                    tous = list(dates_de(mem))
                    return {"id": q["id"], "reponse": repondre(FAITS, K.contexte(tous, dates_de(mem)), q), "faits": len(tous)}
                return {"id": q["id"], "reponse": repondre(HISTOIRE, historique(convs[q["conv"]]), q)}

            try:
                with ThreadPoolExecutor(a.fils) as ex:
                    lignes = list(ex.map(un, qs))
            except modele.BudgetDepasse as e:
                print(f"  ⛔ {e} — arrêt ({moteur}_{echelle}) ; relancer reprend sans repayer", flush=True)
                return 2
            K.ecrire_jsonl(K.RUN / "reponses" / f"{moteur}_{echelle}.jsonl", lignes)
            print(f"  {moteur}_{echelle} : {len(lignes)} réponses · dépense cumulée {modele.depense()['total']['usd']:.3f} $", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
