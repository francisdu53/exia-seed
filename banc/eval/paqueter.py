#!/usr/bin/env python3
"""Phase 0 — le MÊME budget de tokens pour tous les concurrents (PLAN-FCM-EXIA-SEED.md §3, règles d'équité).

Prend la liste classée d'un concurrent (`runs/candidats/*.jsonl`) et construit le bloc de contexte donné au lecteur :
les éléments dans l'ordre du concurrent, chacun ENTIER (jamais coupé), tant que le bloc tient dans le budget ; un élément
trop long est sauté et le suivant essayé (aucun concurrent ne se retrouve à vide s'il a un élément qui tient). Format
identique pour tous : « - [date] texte », lignes de suite indentées ; bloc vide : « - (no memories found) » (comme
commun.contexte). Budget « tout » : tous les éléments, sans coupe (rejeu du protocole « 12 souvenirs » du 20/11).
Compteur fixe o200k (capteurs.Jetons). Hôte :
  ${PYTHON_EMBEDDINGS:-python3} paqueter.py <fichier candidats> <budget>[,<budget>…]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import capteurs as C                                           # noqa: E402

VIDE = "- (no memories found)"
MOTS_OUTILS = set("the a an of to in on and or is are was were do did does what when where who whom which how why with for at by from "
                  "i my me you your it its this that be have has had about after before during did what's whats would could should "
                  "her his him she he they them their there than then into over under also any some".split())


def personnes_connues():
    """Les noms des interlocuteurs des bancs (LoCoMo) — LongMemEval n'a que « user » / « assistant » (pas de nom)."""
    import json as _j
    from pathlib import Path as _P
    d = _P(__file__).resolve().parent.parent / "bancs" / "donnees" / "locomo10.json"
    return {c["conversation"][k].lower() for c in _j.loads(d.read_text(encoding="utf-8")) for k in ("speaker_a", "speaker_b")}


def presenter(question, items, options, personnes, date_question=None):
    """Rouages de PRÉSENTATION (propres à une IA) : `absence` — la question nomme P, mais les passages qui portent sur
    son sujet sont liés à d'autres personnes → on l'écrit en tête du bloc ; `temps` — chaque date devient aussi un écart
    calculé par le code (« 12 days before the question »). Rend (note de tête ou "", éléments éventuellement datés)."""
    import re as _re
    from datetime import datetime as _dt
    note = ""
    q = question.lower()
    nommes = [p for p in personnes if _re.search(rf"\b{_re.escape(p)}\b", q)]
    if ("absence" in options or "faits" in options) and nommes:
        sujet = {w for w in _re.findall(r"[a-z]{3,}", q) if w not in MOTS_OUTILS and w not in personnes}
        lies = set()
        for it in items:
            for l in it["texte"].split("\n"):
                m = _re.match(r"^([A-Za-z][\w ]{0,30}):\s(.*)$", l)
                corps, qui = (m.group(2), {m.group(1).lower()}) if m and it.get("type") == "tour" else (l, set())
                mots = set(_re.findall(r"[a-z]{3,}", corps.lower()))
                if len(mots & sujet) >= max(1, min(2, len(sujet))):
                    lies |= qui | {p for p in personnes if _re.search(rf"\b{_re.escape(p)}\b", corps.lower())}
        absents = [p for p in nommes if p not in lies]
        autres = sorted(lies - set(nommes))
        if absents and autres:
            note = (f"- [note] In these memories, this topic is linked to {', '.join(a.title() for a in autres)}, "
                    f"not to {', '.join(a.title() for a in absents)}.")
            if "faits" in options:                     # parade « faits seuls » : sans le brut, seulement les souvenirs consolidés
                items = [it for it in items if it.get("type") != "tour"]
                note = ""
    if "consigne" in options:                 # RÈGLE DE TÊTE de la mémoire (parade d'abstention) — même texte pour toutes les questions
        note = ("- [memory rule] Each memory says who said or did it. If no memory below shows the person named in the "
                "question saying or doing what is asked, that information is not in memory: say it is not mentioned "
                "instead of guessing.")
    if "regle2" in options:                   # formulation plus fine : s'abstenir quand c'est UNE AUTRE personne, sinon répondre
        note = ("- [memory rule] Each memory says who said or did it. If these memories show only a different person "
                "(not the one named in the question) saying or doing what is asked, answer that it is not mentioned for "
                "that person. If they show the person named, answer from them, even if some details are missing.")
    if "regle3" in options:                   # variante courte
        note = ("- [memory rule] Check who said or did it: if it was someone other than the person in the question, say it "
                "is not mentioned; otherwise answer from these memories.")
    if "temps" in options and date_question:
        dq = date_question
        sortie = []
        for it in items:
            try:
                d = _dt.strptime(it.get("date") or "", "%d %B %Y")
                ecart = (dq.date() - d.date()).days
                it = {**it, "date": f"{it['date']}, {ecart} days before the question" if ecart >= 0 else it["date"]}
            except ValueError:
                pass
            sortie.append(it)
        items = sortie
    return note, items


def ligne(item) -> str:
    t = item["texte"].strip().split("\n")
    tete = f"- [{item['date']}] {t[0]}" if item.get("date") else f"- {t[0]}"
    return "\n".join([tete] + ["  " + x for x in t[1:]])


def paqueter(items, budget, jetons):
    pris, coupes, lignes = [], 0, []
    for k, it in enumerate(items):
        l = ligne(it)
        if budget is not None and jetons("\n".join(lignes + [l])) > budget:
            coupes += 1; continue
        lignes.append(l); pris.append(k)
    bloc = "\n".join(lignes) or VIDE
    return bloc, pris, coupes


def main() -> int:
    src = Path(sys.argv[1])
    budgets = [None if b == "tout" else int(b) for b in sys.argv[2].split(",")]
    pres = [x for x in (sys.argv[3].split(",") if len(sys.argv) > 3 else []) if x]   # rouages de présentation : absence, temps
    jetons = C.Jetons()
    lignes = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    qs, personnes = {}, set()
    if pres:
        import os as _os
        sys.path.insert(0, str(ICI.parent / "harnais"))
        banc = "lme" if "_lme_" in src.name else "locomo"
        _os.environ["LOCOMO_DONNEES"] = str(ICI.parent / "bancs" / "donnees" / ("lme_oracle_locomo.json" if banc == "lme" else "locomo10.json"))
        import commun
        from datetime import datetime as _dt
        qs = {q["id"]: q for q in commun.questions(json.loads(Path(commun.DONNEES).read_text(encoding="utf-8")))}
        personnes = personnes_connues()
    suffixe = ("_P" + "".join(x if x.startswith("regle") else x[0] for x in sorted(pres))) if pres else ""
    for b in budgets:
        nom = f"{src.stem}{suffixe}_B{'tout' if b is None else b}.jsonl"
        sortie = ICI / "runs" / "contextes" / nom
        sortie.parent.mkdir(parents=True, exist_ok=True)
        out, toks, ns, depasse = [], [], [], 0
        for x in lignes:
            t0 = time.perf_counter_ns()
            items = x.get("items", [])
            note = ""
            if pres:
                q = qs.get(x["id"], {})
                dq = None
                try:
                    dq = _dt.fromisoformat(q["instant"])
                except Exception:
                    pass
                note, items = presenter(q.get("question", ""), items, pres, personnes, dq)
            bloc, pris, coupes = paqueter(items, None if b is None else b - (jetons(note) + 1 if note else 0), jetons)
            if note:
                bloc = note + "\n" + bloc
            ns.append(time.perf_counter_ns() - t0)
            n = jetons(bloc); toks.append(n)
            depasse += int(b is not None and n > b)
            out.append({"id": x["id"], "categorie": x.get("categorie"), "type": x.get("type"), "bloc": bloc,
                        "tokens_bloc": n, "items_donnes": len(pris), "items_coupes": coupes,
                        "items_texte": [x["items"][k]["texte"] for k in pris], "paquet_ns": ns[-1]})
        sortie.write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out), encoding="utf-8")
        man = C.manifeste(source=src.name, budget=b, questions=len(out), tokens_bloc=C.centiles(toks),
                          paquet_ms=C.centiles([v / 1e6 for v in ns]), depassements=depasse,
                          vides=sum(1 for o in out if o["bloc"] == VIDE),
                          items_donnes_moy=round(sum(o["items_donnes"] for o in out) / max(1, len(out)), 2))
        sortie.with_suffix(".manifeste.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{nom} : tokens {man['tokens_bloc']} · items {man['items_donnes_moy']} · vides {man['vides']} · dépassements {depasse}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
