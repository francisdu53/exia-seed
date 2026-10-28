#!/usr/bin/env python3
"""Mesurer les deux mémoires reconsolidées de Nexa (docs/13 §19). Conteneur jetable.

1. Taille : faits, nœuds, arêtes, dépense de consolidation.
2. Couverture : part des messages de Francis (≥ 6 mots, hors avis « systeme ») cités par au moins un fait ; et part
   de ceux qui portent un détail concret (un nombre, ou un nom propre ailleurs qu'en tête de phrase).
3. Questions : 80 messages à détail concret tirés au sort (graine 2710) ; gpt-4o-mini écrit, à partir du SEUL message,
   une question que Francis pourrait poser plus tard et sa réponse ; chaque variante répond avec `memoire_chercher`
   (12 faits datés, consigne « faits » de LongMemEval) ; juge de LongMemEval. Questions écrites UNE fois, mêmes pour
   les deux variantes.

    python3 mesurer.py
"""
import glob, json, os, random, re, sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, "/locomo"); sys.path.insert(0, "/lme"); sys.argv = sys.argv[:1]
import os
os.environ.setdefault("LOCOMO_RUN", "mesures")
import commun as K
K.preparer_chemins()
import modele
from exia_seed import graphe as G
from exia_seed.requete import Lecteur

RUNS = Path(os.environ.get("NEXA_RUNS", "/banc/runs"))       # runs-astra : reconsolidées par GPT-6 Astra (§19.2)
VARIANTES = ("selective", "exhaustive")
ENTETE = re.compile(r"^\[(\d\d:\d\d) ([a-z_]+)\] ?(.*)$")
FAIT = re.compile(r"^- (.*?) <!-- (.*?) -->\s*$")
MAINTENANT = datetime(2026, 10, 27, 21, 0)


def messages_francis(memoire: Path):
    """[(fichier, première ligne, dernière ligne, date, texte)] — un message = son en-tête et ses lignes de suite."""
    sortie = []
    for f in sorted((memoire / "raw").glob("*.md")):
        lignes = f.read_text(encoding="utf-8").splitlines()
        jour = re.search(r"^date: (\S+)", "\n".join(lignes[:8]), re.M)
        courant = None
        for n, l in enumerate(lignes, 1):
            m = ENTETE.match(l)
            if m:
                if courant: sortie.append(courant)
                courant = [f.name, n, n, jour.group(1) if jour else "", m.group(3)] if m.group(2) == "francis" else None
            elif courant is not None and l.strip() and not l.startswith(("<!--", "#", "---")):
                courant[2] = n; courant[4] += " " + l.strip()
        if courant: sortie.append(courant)
    return [tuple(x) for x in sortie if len(x[4].split()) >= 6]


def detail(texte: str) -> bool:
    if re.search(r"\d", texte):
        return True
    mots = re.findall(r"(?<![.!?]\s)(?<!^)\b[A-ZÉÈÀ][a-zéèêàçû]+", texte)
    return bool(mots)


def cites(memoire: Path):
    """{(fichier, ligne)} cités par au moins un fait."""
    c = set()
    for p in (memoire / "pages").glob("*.md"):
        for l in p.read_text(encoding="utf-8").splitlines():
            m = FAIT.match(l)
            if not m: continue
            src = re.search(r"(?:^| )src:(\S+)", m.group(2))
            for ref in (src.group(1).split(",") if src else []):
                r = re.match(r"raw/([^:]+):(\d+)(?:-(\d+))?", ref)
                if r:
                    for k in range(int(r.group(2)), int(r.group(3) or r.group(2)) + 1):
                        c.add((r.group(1), k))
    return c


def main():
    msgs = messages_francis(RUNS / "exhaustive" / "memoire")
    print(f"messages de Francis (≥ 6 mots) : {len(msgs)} · avec détail concret : {sum(detail(m[4]) for m in msgs)}")
    bilan = {}
    for v in VARIANTES:
        mem = RUNS / v / "memoire"
        r = G.calculer(mem, implicites=("francis", "nexa"))
        c = cites(mem)
        couverts = [m for m in msgs if any((m[0], k) in c for k in range(m[1], m[2] + 1))]
        d = [m for m in msgs if detail(m[4])]
        dc = [m for m in couverts if detail(m[4])]
        usd = sum(json.loads(l)["usd"] for l in open(RUNS / v / "appels.jsonl")) if (RUNS / v / "appels.jsonl").exists() else 0
        bilan[v] = {"faits": r.get("faits"), "noeuds": r.get("noeuds"), "aretes": r.get("aretes"), "depense": round(usd, 3),
                    "couverture": round(100 * len(couverts) / len(msgs), 1), "couverture_detail": round(100 * len(dc) / len(d), 1)}
        print(v, json.dumps(bilan[v], ensure_ascii=False))
    # 3. questions
    rng = random.Random(2710)
    tirage = rng.sample([m for m in msgs if detail(m[4])], 80)
    qs = []
    for m in tirage:
        rep = modele.appeler([{"role": "user", "content":
              "Voici un message que Francis a envoyé à son assistante Nexa le " + m[3] + " :\n« " + m[4][:1500] + " »\n\n"
              "Écris UNE question que Francis pourrait poser à Nexa plusieurs semaines plus tard pour vérifier qu'elle "
              "s'en souvient (un détail concret du message : nom, nombre, date, lieu, objet…), et sa réponse courte, tirée "
              "du message SEUL. Réponds uniquement en JSON : {\"question\": \"…\", \"reponse\": \"…\"}"}],
              "question", max_tokens=200, json_seul=True)
        try:
            x = json.loads(rep); qs.append({"msg": m, "question": x["question"], "gold": x["reponse"]})
        except Exception:
            pass
    print(f"questions écrites : {len(qs)}")
    import repondre_lme as RL, juger_lme as JL
    for v in VARIANTES:
        mem = RUNS / v / "memoire"
        L = Lecteur(mem, implicites=("francis", "nexa")); dates = K.faits_dates(mem)
        justes, lignes = 0, []
        for q in qs:
            c = L.chercher(q["question"], 10, MAINTENANT, faits_max=12)
            faits = [f["fait"] for x in c.get("resultats", []) for f in x["faits"]] + [p["fait"] for p in (c.get("pistes") or {}).get("faits", [])]
            qq = {"question": q["question"], "gold": q["gold"], "type": "single-session-user", "date_question": MAINTENANT.strftime("%Y/%m/%d (%a) %H:%M")}
            r = RL.repondre(RL.FAITS, K.contexte(faits[:12], dates), qq)
            j = JL.juger(qq, r)
            justes += j["label"] == "CORRECT"
            lignes.append({"question": q["question"], "gold": q["gold"], "faits": faits[:12], "reponse": r[-300:], "label": j["label"]})
        bilan[v]["questions_justes"] = justes; bilan[v]["questions"] = len(qs)
        K.ecrire_jsonl(RUNS / v / "questions.jsonl", lignes)
        print(v, f"questions : {justes}/{len(qs)}")
    a = {x["question"]: x["label"] == "CORRECT" for x in K.lire_jsonl(RUNS / "selective" / "questions.jsonl")}
    b = {x["question"]: x["label"] == "CORRECT" for x in K.lire_jsonl(RUNS / "exhaustive" / "questions.jsonl")}
    import math
    sa = sum(b[k] and not a[k] for k in a); sb = sum(a[k] and not b[k] for k in a); n = sa + sb
    p = min(1.0, 2 * sum(math.comb(n, k) for k in range(min(sa, sb) + 1)) / 2 ** n) if n else 1
    bilan["apparie"] = {"seul_exhaustive": sa, "seul_selective": sb, "p": round(p, 4)}
    bilan["depense_mesure"] = round(modele.depense()["total"]["usd"], 4)
    (RUNS / "bilan.json").write_text(json.dumps(bilan, indent=1, ensure_ascii=False))
    print(json.dumps(bilan, ensure_ascii=False))


if __name__ == "__main__":
    main()
