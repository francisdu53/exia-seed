#!/usr/bin/env python3
"""Mesurer les consolidations du banc 17 (docs/17 §5-6). Conteneur jetable ; lecteur, juge et questions : Terra.

1. Coût réel : les compteurs des fournisseurs (journaux `appels/<modèle>.jsonl`), à côté des estimations du code.
2. Qualité : faits retenus, rejets, lots perdus ; couverture des messages de l'utilisateur du jour (≥ 6 mots, hors
   avis « systeme ») cités par au moins un fait ; stabilité entre les deux passages.
3. Questions : les messages du jour à détail concret ; Terra écrit UNE fois, depuis le seul message, une question et sa
   réponse ; chaque mémoire répond avec `memoire_chercher` (12 faits datés, consigne « faits » de LongMemEval) ; juge de
   LongMemEval. Mêmes questions pour tous les modèles.
4. Relecture humaine : 10 faits NOUVEAUX tirés au sort par modèle (passage r1, graine fixe), avec leurs lignes source.
5. Verdict selon les seuils FIGÉS du §6, et un bilan public sans aucune donnée mémorielle.

    python3 mesurer.py
"""
import json
import math
import os
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ICI = Path(__file__).resolve().parent
BANC = Path(os.environ.get("BANC", "/banc"))
sys.path.insert(0, str(BANC / "plugin")); sys.path.insert(0, str(ICI)); sys.path.insert(0, "/locomo"); sys.path.insert(0, "/lme")
import appel                                                           # noqa: E402
import commun as K                                                     # noqa: E402
import repondre_lme as RL                                              # noqa: E402
import juger_lme as JL                                                 # noqa: E402
from exia_seed.requete import Lecteur                                  # noqa: E402

RL.modele = appel; JL.modele = appel                                   # lecteur et juge : Terra, par le module du banc
RUNS = BANC / ("runs-factice" if appel.FACTICE else "runs")
SORTIE = BANC / ("mesures-factices" if appel.FACTICE else os.environ.get("BANC_MESURES", "mesures"))
PASSAGES = tuple(os.environ.get("BANC_PASSAGES", "r1,r2").split(","))   # analyse complémentaire : s1,s2 (Astra : r1,r2)
JOURS = ("C1", "C2", "M1", "M2", "I1", "I2")
PROFIL = {"C1": "calme", "C2": "calme", "M1": "moyen", "M2": "moyen", "I1": "intensif", "I2": "intensif"}
REFERENCE = "gpt-6-astra"
MAINTENANT = datetime(2026, 11, 5, 12, 0)
ENTETE = re.compile(r"^\[(\d\d:\d\d) ([a-z_]+)\] ?(.*)$")
FAIT = re.compile(r"^- (.*?) <!-- (.*?) -->\s*$")
IMPLICITES = ("francis", "nexa")


def messages_utilisateur(memoire: Path):
    """[(fichier, première ligne, dernière ligne, texte)] — un message = son en-tête et ses lignes de suite (≥ 6 mots)."""
    sortie = []
    for f in sorted((memoire / "raw").glob("*.md")):
        courant = None
        for n, l in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            m = ENTETE.match(l)
            if m:
                if courant: sortie.append(courant)
                courant = [f.name, n, n, m.group(3)] if m.group(2) == "francis" else None
            elif courant is not None and l.strip() and not l.startswith(("<!--", "#", "---")):
                courant[2] = n; courant[3] += " " + l.strip()
        if courant: sortie.append(courant)
    return [tuple(x) for x in sortie if len(x[3].split()) >= 6]


def detail(texte: str) -> bool:
    return bool(re.search(r"\d", texte) or re.findall(r"(?<![.!?]\s)(?<!^)\b[A-ZÉÈÀ][a-zéèêàçû]+", texte))


def faits_de(memoire: Path):
    """{texte du fait : (page, métadonnées)}"""
    sortie = {}
    for p in sorted((memoire / "pages").glob("*.md")):
        for l in p.read_text(encoding="utf-8").splitlines():
            m = FAIT.match(l)
            if m:
                sortie[m.group(1)] = (p.name, m.group(2))
    return sortie


def cites(faits) -> set:
    c = set()
    for _, meta in faits.values():
        s = re.search(r"(?:^| )src:(\S+)", meta)
        for ref in (s.group(1).split(",") if s else []):
            r = re.match(r"raw/([^:]+):(\d+)(?:-(\d+))?", ref)
            if r:
                for k in range(int(r.group(2)), int(r.group(3) or r.group(2)) + 1):
                    c.add((r.group(1), k))
    return c


def mcnemar(a, b):
    """p exact, bilatéral, sur les paires discordantes."""
    sa = sum(x and not y for x, y in zip(a, b)); sb = sum(y and not x for x, y in zip(a, b)); n = sa + sb
    return (sa, sb, min(1.0, 2 * sum(math.comb(n, k) for k in range(min(sa, sb) + 1)) / 2 ** n) if n else 1.0)


def questions():
    """Écrites une fois pour toutes (cache : questions.json)."""
    f = SORTIE / "questions.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    qs = []
    for etiq in JOURS:
        for m in [m for m in messages_utilisateur(BANC / "depart" / etiq / "memoire") if detail(m[3])]:
            rep = appel.appeler([{"role": "user", "content":
                  "Voici un message que Francis a envoyé à son assistante Nexa :\n« " + m[3][:1500] + " »\n\n"
                  "Écris UNE question que Francis pourrait poser à Nexa plusieurs semaines plus tard pour vérifier qu'elle "
                  "s'en souvient (un détail concret du message : nom, nombre, date, lieu, objet…), et sa réponse courte, tirée "
                  "du message SEUL. Réponds uniquement en JSON : {\"question\": \"…\", \"reponse\": \"…\"}"}],
                  "question", max_tokens=300, json_seul=True, run="questions")
            try:
                x = json.loads(rep)
                qs.append({"jour": etiq, "msg": list(m[:3]), "question": x["question"], "gold": x["reponse"]})
            except Exception:
                continue
    SORTIE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")
    return qs


def repondre(memoire: Path, qs):
    """La recherche d'abord, à la suite (SQLite ne se partage pas entre fils ; quelques ms) ; puis lecteur et juge en parallèle."""
    L = Lecteur(memoire, implicites=IMPLICITES); dates = K.faits_dates(memoire)
    taches = []
    for q in qs:
        c = L.chercher(q["question"], 10, MAINTENANT, faits_max=12)
        faits = [f["fait"] for x in c.get("resultats", []) for f in x["faits"]] + [p["fait"] for p in (c.get("pistes") or {}).get("faits", [])]
        qq = {"question": q["question"], "gold": q["gold"], "type": "single-session-user",
              "date_question": MAINTENANT.strftime("%Y/%m/%d (%a) %H:%M")}
        taches.append((qq, K.contexte(faits[:12], dates)))
    def un(t):
        qq, ctx = t
        return JL.juger(qq, RL.repondre(RL.FAITS, ctx, qq))["label"] == "CORRECT"
    with ThreadPoolExecutor(8) as ex:
        return list(ex.map(un, taches))


def cout_reel(modele: str, run: str):
    lignes = [x for x in appel._lire(appel._journal(modele)) if (x.get("run") == run or str(x.get("run")).startswith(run + "+")) and x["role"] in ("consolidation", "fiches")]
    tot = {k: sum(x.get(k, 0) or 0 for x in lignes) for k in ("entree", "entree_cache", "ecriture_cache", "sortie", "raisonnement")}
    tot["appels"] = len(lignes)
    tot["usd"] = round(sum(x["usd"] for x in lignes), 4)                       # payé réellement (Astra : abonnement, 0 $)
    tot["usd_equivalent_api"] = round(sum(appel.cout(modele, {**x, "ecriture_cache": x.get("ecriture_cache", 0)}) for x in lignes), 4)
    tot["raisonnement_rapporte"] = any("raisonnement" in x for x in lignes)
    return tot


def estimations(racine: Path):
    e = s = 0
    for etiq in JOURS:
        f = racine / etiq / "memoire" / "telemetrie" / "consolidations.jsonl"
        for l in (f.read_text(encoding="utf-8").splitlines() if f.exists() else []):
            x = json.loads(l); fi = x.get("fiches") or {}
            e += (x.get("tokens_entree_estimes") or 0) + (fi.get("tokens_entree") or 0)
            s += (x.get("tokens_sortie_estimes") or 0) + (fi.get("tokens_sortie") or 0)
    return {"entree": e, "sortie": s}


def main():
    qs = questions()
    print("questions :", len(qs), {j: sum(q["jour"] == j for q in qs) for j in JOURS}, flush=True)
    def passages(m):
        return ("r1", "r2") if m == REFERENCE else PASSAGES
    modeles = [m for m in appel.MODELES if all((RUNS / m / r / j / "fini.json").exists() for r in passages(m) for j in JOURS)]
    print("modèles complets :", modeles, flush=True)
    res = {}
    for m in modeles:
        res[m] = {}
        for r, rr in zip(("r1", "r2"), passages(m)):     # rr : le passage lu sur disque ; r : sa place dans le bilan
            par_jour, justes = {}, []
            for etiq in JOURS:
                mem = RUNS / m / rr / etiq / "memoire"
                fini = json.loads((mem.parent / "fini.json").read_text(encoding="utf-8"))
                avant, apres = faits_de(BANC / "depart" / etiq / "memoire"), faits_de(mem)
                msgs = messages_utilisateur(BANC / "depart" / etiq / "memoire")
                c = cites(apres)
                couverts = sum(any((x[0], k) in c for k in range(x[1], x[2] + 1)) for x in msgs)
                qj = [q for q in qs if q["jour"] == etiq]
                ok = repondre(mem, qj) if qj else []
                justes += ok
                par_jour[etiq] = {"faits_nouveaux": len(set(apres) - set(avant)), "retenus": fini["faits_retenus"],
                                  "rejets": fini["rejets"], "perdus": fini["perdus"], "messages": len(msgs),
                                  "couverts": couverts, "questions": len(qj), "justes": sum(ok)}
            res[m][r] = {"jours": par_jour, "justes_liste": justes, "passage": rr, "cout": cout_reel(m, rr), "estimations": estimations(RUNS / m / rr)}
            t = res[m][r]
            print(f"{m} {r} : {sum(j['retenus'] for j in par_jour.values())} faits, questions {sum(justes)}/{len(justes)}, "
                  f"coût {t['cout']['usd']} $", flush=True)
    # ── agrégats, verdict ──
    def taux(m, cle_num, cle_den):
        v = [sum(res[m][r]["jours"][j][cle_num] for j in JOURS) / max(1, sum(res[m][r]["jours"][j][cle_den] for j in JOURS)) for r in ("r1", "r2")]
        return 100 * sum(v) / 2
    bilan = {"questions": len(qs), "modeles": {}}
    ref = REFERENCE if REFERENCE in res else None
    for m in res:
        q, cv = taux(m, "justes", "questions"), taux(m, "couverts", "messages")
        perdus = sum(res[m][r]["jours"][j]["perdus"] for r in ("r1", "r2") for j in JOURS)
        b = {"questions_pct": round(q, 1), "couverture_pct": round(cv, 1), "passages_perdus": perdus,
             "faits_retenus_moy": sum(res[m][r]["jours"][j]["retenus"] for r in ("r1", "r2") for j in JOURS) / 2,
             "rejets_moy": sum(res[m][r]["jours"][j]["rejets"] for r in ("r1", "r2") for j in JOURS) / 2,
             "stabilite_faits": {r: sum(res[m][r]["jours"][j]["retenus"] for j in JOURS) for r in ("r1", "r2")},
             "par_profil": {p: {"faits_moy": sum(res[m][r]["jours"][j]["retenus"] for r in ("r1", "r2") for j in JOURS if PROFIL[j] == p) / 2,
                                "justes": sum(res[m][r]["jours"][j]["justes"] for r in ("r1", "r2") for j in JOURS if PROFIL[j] == p) / 2,
                                "questions": sum(res[m]["r1"]["jours"][j]["questions"] for j in JOURS if PROFIL[j] == p)}
                            for p in ("calme", "moyen", "intensif")},
             "cout_reel": {r: res[m][r]["cout"] for r in ("r1", "r2")},
             "estimations": {r: res[m][r]["estimations"] for r in ("r1", "r2")}}
        if ref and m != ref:
            b["Q1"] = q >= taux(ref, "justes", "questions") - 5
            b["Q2"] = cv >= taux(ref, "couverts", "messages") - 5
            b["Q4"] = perdus == 0
            b["mcnemar_r1"] = dict(zip(("seul_modele", "seul_astra", "p"), mcnemar(res[m]["r1"]["justes_liste"], res[ref]["r1"]["justes_liste"])))
            b["Q3"] = "relecture de Francis en attente"
        bilan["modeles"][m] = b
    bilan["depense_totale_usd"] = round(appel.depense()["total"]["usd"], 4)
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "bilan.json").write_text(json.dumps({"bilan": bilan, "detail": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    # ── relecture humaine : 10 faits nouveaux par modèle, r1, graine fixe ──
    lignes = ["# Relecture — 10 faits par modèle (privé : faits et sources réels)\n",
              "Pour chaque fait : V (vrai), F (faux), A (mal attribué), D (mal daté).\n"]
    for m in res:
        nouveaux = []
        for etiq in JOURS:
            mem = RUNS / m / passages(m)[0] / etiq / "memoire"; avant = faits_de(BANC / "depart" / etiq / "memoire")
            brut = {f.name: f.read_text(encoding="utf-8").splitlines() for f in (mem / "raw").glob("*.md")}
            for fait, (page, meta) in sorted(faits_de(mem).items()):
                if fait in avant:
                    continue
                s = re.search(r"(?:^| )src:(\S+)", meta); src = []
                for ref in (s.group(1).split(",") if s else []):
                    rr = re.match(r"raw/([^:]+):(\d+)(?:-(\d+))?", ref)
                    if rr and rr.group(1) in brut:
                        src += [brut[rr.group(1)][k - 1] for k in range(int(rr.group(2)), int(rr.group(3) or rr.group(2)) + 1) if k <= len(brut[rr.group(1)])]
                    elif ref.startswith("registre:"):
                        src.append(f"(note du registre {ref[9:]})")
                nouveaux.append((etiq, page, fait, src))
        tirage = random.Random(1705).sample(nouveaux, min(10, len(nouveaux)))
        lignes.append(f"\n## Modèle {chr(65 + list(res).index(m))}\n")
        for i, (etiq, page, fait, src) in enumerate(tirage, 1):
            lignes.append(f"{i}. **{fait}**  \n   _page {page}_  \n" + "".join(f"   > {x}\n" for x in src[:4]) + "   Verdict : ☐ V ☐ F ☐ A ☐ D\n")
    (SORTIE / "relecture.md").write_text("\n".join(lignes), encoding="utf-8")
    (SORTIE / "relecture-cle.json").write_text(json.dumps({chr(65 + i): m for i, m in enumerate(res)}), encoding="utf-8")
    print(json.dumps(bilan, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
