#!/usr/bin/env python3
"""LongMemEval (version nettoyée) → le format du banc LoCoMo (docs/13). Sur l'hôte, sans dépendance, sans modèle.

Une question = une « conversation » : ses sessions (datées, triées), entre `user` (speaker_a) et `assistant`
(speaker_b), et sa question, avec l'instant où elle est posée (`question_date`), son type et l'abstention (`_abs`).
Rien n'est reformulé : les tours sont recopiés tels quels.

    python3 convertir.py longmemeval_oracle.json lme_oracle_locomo.json
"""
import json
import re
import sys
from datetime import datetime


def date_lme(s: str) -> datetime:
    """« 2023/05/20 (Sat) 02:21 » → datetime."""
    return datetime.strptime(re.sub(r"\s*\(\w+\)\s*", " ", s.strip()), "%Y/%m/%d %H:%M")


def date_locomo(d: datetime) -> str:
    return f"{int(d.strftime('%I'))}:{d:%M} {d.strftime('%p').lower()} on {d.day} {d:%B}, {d.year}"


def main(entree: str, sortie: str) -> int:
    d = json.load(open(entree, encoding="utf-8"))
    out = []
    for q in d:
        sess = sorted(zip(q["haystack_dates"], q["haystack_session_ids"], q["haystack_sessions"]), key=lambda x: date_lme(x[0]))
        conv = {"speaker_a": "user", "speaker_b": "assistant"}
        for n, (quand, sid, tours) in enumerate(sess, 1):
            conv[f"session_{n}_date_time"] = date_locomo(date_lme(quand))
            conv[f"session_{n}"] = [{"speaker": t["role"], "dia_id": f"{sid}:{k}", "text": t["content"]}
                                    for k, t in enumerate(tours) if (t.get("content") or "").strip()]
        out.append({"sample_id": q["question_id"], "conversation": conv,
                    "qa": [{"question": q["question"], "answer": str(q["answer"]), "category": 1,
                            # instant de RECHERCHE : 43 questions ont une session datée après elles, le même jour ou le
                            # lendemain (au plus 23 h 19, défaut du jeu). A filtre par date, B non : on prend le plus
                            # tardif, pour ne pas pénaliser A sur un artefact. La consigne garde la date officielle.
                            "instant": max(date_lme(q["question_date"]), date_lme(sess[-1][0])).isoformat(timespec="minutes"),
                            "date_question": q["question_date"], "type": q["question_type"],
                            "abstention": q["question_id"].endswith("_abs"),
                            "evidence": q.get("answer_session_ids", [])}]})
    json.dump(out, open(sortie, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(out)} questions, {sum(len([k for k in o['conversation'] if re.fullmatch(r'session_\d+', k)]) for o in out)} sessions → {sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
