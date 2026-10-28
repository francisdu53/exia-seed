#!/usr/bin/env python3
"""Étape 4 — les réponses (docs/09 §2). Même modèle, même consigne pour tous les moteurs.

- A, B, C : la consigne de réponse d'EXIA GHOST (eval_locomo.py, QA_PROMPT), à UNE adaptation près : les deux
  listes « mémoires de A / mémoires de B » deviennent une seule liste de faits datés — identique pour les trois.
- D, Karpathy pur : 1) le modèle lit INDEX.md et choisit au plus 3 pages ; 2) il lit ces pages et répond.
- E, tout le contexte : la conversation entière, datée (échelle S seulement : en F, plus de 200 000 tokens).
- M, DIAGNOSTIC (ajouté au pilote, docs/09 §12) : TOUTE la mémoire de la conversation (tous ses faits datés). Le
  plafond de ce que la consolidation a gardé : si A, B, C en sont proches, c'est la mémoire qui limite, pas la recherche.

    python3 repondre.py [A B C D E] [--echelles S F] [--fils 8]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import commun as K
import modele

QA = """You are a knowledgeable AI assistant with access to personal memories from two speakers in a conversation.

# INSTRUCTIONS:
1. Carefully analyze ALL provided memories from BOTH speakers. Synthesize information across multiple entries.
2. If memories contain contradictory information, the MOST RECENT memory (by timestamp) is the source of truth.
3. If the question involves relative time references ("last year", "two months ago"), calculate the actual date from the memory timestamp.
4. Your answer must be grounded in the memories. You may use general knowledge to interpret information found in memories.
5. Only say "Unknown" if the memories contain absolutely NO information related to the question. If partial information exists, answer with what you have.
6. CRITICAL: Your final answer MUST be under 5-6 words. No explanations, no justifications. Just the answer.

Memories (with the date each one was said):
{context}

Question: {question}

Answer:"""

CHOIX = """You have a long-term memory organised as a wiki: one page per subject. Below is its index (one row per page:
page name, type, aliases, number of facts, last update). Choose the pages (at most 3) whose content is most useful to
answer the question. Answer ONLY with a JSON object: {{"pages": ["page_name", ...]}}

INDEX
{index}

Question: {question}"""


def repondre(contexte: str, question: str) -> str:
    return modele.appeler([{"role": "user", "content": QA.format(context=contexte, question=question)}], "reponse", max_tokens=60).strip()


def karpathy(memoire, question: str):
    index = (memoire / "INDEX.md").read_text(encoding="utf-8")
    rep = modele.appeler([{"role": "user", "content": CHOIX.format(index=index, question=question)}], "page", max_tokens=100)
    m = re.search(r"\{.*\}", rep or "", re.S)
    try:
        noms = [str(x) for x in (json.loads(m.group(0)).get("pages") or [])][:3] if m else []
    except ValueError:
        noms = []
    dates = K.faits_dates(memoire)
    faits = []
    for n in noms:
        f = memoire / "pages" / (re.sub(r"[^a-z0-9_]", "", n.lower()).replace("_", "-") + ".md")
        if f.exists():
            faits += [x.group(1).strip() for l in f.read_text(encoding="utf-8").splitlines() for x in [re.match(r"^- (.*?) <!--", l)] if x]
    return repondre(K.contexte(faits, dates), question), {"pages": noms, "faits": len(faits)}


def transcription(conv) -> str:
    c = conv["conversation"]
    return "\n".join(f"- [{quand:%-d %B %Y, %-I:%M %p}] {t['speaker']}: {K.texte_du_tour(t)}"
                     for _, quand, tours in K.sessions(conv) for t in tours if K.texte_du_tour(t))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("moteurs", nargs="*", default=["A", "B", "C", "D", "E"])
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
                    texte = K.contexte(ctx[q["id"]], dates_de(mem))
                    return {"id": q["id"], "reponse": repondre(texte, q["question"]), "faits": len(ctx[q["id"]])}
                if moteur == "M":
                    tous = list(dates_de(mem))
                    return {"id": q["id"], "reponse": repondre(K.contexte(tous, dates_de(mem)), q["question"]), "faits": len(tous)}
                if moteur == "D":
                    r, info = karpathy(mem, q["question"])
                    return {"id": q["id"], "reponse": r, **info}
                return {"id": q["id"], "reponse": repondre(transcription(convs[q["conv"]]), q["question"])}

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
