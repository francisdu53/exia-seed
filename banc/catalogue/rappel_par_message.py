#!/usr/bin/env python3
"""Banc 17 §15 — rappel de la recherche MESSAGE PAR MESSAGE selon K (pages gardées par message). Sans modèle, gratuit.

Référence : les pages qui existaient au départ et dans lesquelles Terra, avec la liste COMPLÈTE, a rangé un fait
nouveau (hors utilisateur et agent). Pour chaque session (un fichier brut), chaque message est cherché seul (même
cascade que `memoire_chercher`) sur la mémoire de départ ; on garde les K meilleures pages de chaque message, et l'on
mesure la part des pages de référence retrouvées et la taille de la liste envoyée (union par session).

    python3 rappel_par_message.py lme|nexa
"""
import json, re, sys
from collections import defaultdict
from pathlib import Path

JEU = sys.argv[1] if len(sys.argv) > 1 else ""
KS = (5, 10, 15, 20, 30)
RATES = []
FAIT = re.compile(r"^- (.*?) <!-- (.*?) -->\s*$")
ENTETE = re.compile(r"^\[(\d\d:\d\d) ([a-z_]+)\] ?(.*)$")


def faits(mem):
    """{page : {texte du fait : fichiers bruts cités}}"""
    out = {}
    for p in (mem / "pages").glob("*.md"):
        d = {}
        for l in p.read_text(encoding="utf-8").splitlines():
            m = FAIT.match(l)
            if m:
                s = re.search(r"(?:^| )src:(\S+)", m.group(2))
                d[m.group(1)] = {re.match(r"raw/([^:]+):", r).group(1) for r in (s.group(1).split(",") if s else []) if re.match(r"raw/([^:]+):", r)}
        out[p.name] = d
    return out


def noeud_de(p):
    m = re.search(r"^node: (.+)$", p.read_text(encoding="utf-8"), re.M)
    return m.group(1).strip() if m else p.stem


def messages(f):
    out, cour = [], None
    for l in f.read_text(encoding="utf-8").splitlines():
        m = ENTETE.match(l)
        if m:
            if cour: out.append(cour)
            cour = l
        elif cour is not None and l.strip() and not l.startswith(("<!--", "#", "---")):
            cour += " " + l.strip()
    if cour: out.append(cour)
    return out


def mesurer(cas, Rappeleur, implicites):
    """cas : [(départ, mémoire du run, nom du run)] → rappel et taille par K."""
    tot = {k: [0, 0, []] for k in KS}
    caches = {}
    for depart, mem, _ in cas:
        f0, f1 = faits(depart), faits(mem)
        noeud = {p.name: noeud_de(p) for p in (depart / "pages").glob("*.md")}
        presents = set(noeud.values()) - set(implicites)
        ref = defaultdict(set)                                  # fichier brut → pages de départ choisies
        for page, d in f1.items():
            if page in noeud and noeud[page] not in implicites:
                for texte, fichiers in d.items():
                    if texte not in f0.get(page, {}):
                        for fi in fichiers:
                            if (mem / "raw" / fi).exists():
                                ref[fi].add(noeud[page])
        if str(depart) not in caches:
            R = Rappeleur(depart, implicites=implicites); caches[str(depart)] = (R, R.memoire())
        R, m = caches[str(depart)]
        for fi, choisies in ref.items():
            rang = defaultdict(lambda: 10 ** 6)
            for t in messages(mem / "raw" / fi):
                a = R.activer(m, t); loc = {}
                for n, v in a["entrees"].items():
                    if n in presents: loc[n] = max(loc.get(n, 0), 1.0 + v)
                for n, v in a["actives"].items():
                    if n in presents: loc[n] = max(loc.get(n, 0), v)
                for i, n in enumerate(sorted(loc, key=loc.get, reverse=True)):
                    rang[n] = min(rang[n], i)
            for n in choisies:
                if rang[n] >= 30:
                    RATES.append((fi[:40], n, rang[n] if rang[n] < 10 ** 6 else None))
            for k in KS:
                tot[k][0] += sum(rang[n] < k for n in choisies); tot[k][1] += len(choisies)
                tot[k][2].append(sum(1 for r in rang.values() if r < k))
    return {f"K{k}": {"rappel_pct": round(100 * a / max(1, b), 1), "pages_envoyees_moy": round(sum(c) / max(1, len(c)), 1),
                      "pages_envoyees_max": max(c or [0]), "references": b} for k, (a, b, c) in tot.items()}


def main():
    if JEU == "lme":
        sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, "/plugins")
        from exia_seed.rappel import Rappeleur
        B = Path("/banc/runs"); dep = B / "catalogue-base" / "memoires" / "_fusion"
        # un seul départ pour tous ; on remplace la mémoire de départ par celle du run, privée de ses fichiers nouveaux : approx.
        r = mesurer([(dep, B / f"catalogue-terra-complet-{i}" / "memoire", f"terra-complet-{i}") for i in (1, 2)], Rappeleur, ("user", "assistant"))
        print("LongMemEval :", r["K30"])
        for x in RATES: print("  raté", x)
    else:
        sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, "/banc/plugin")
        from exia_seed.rappel import Rappeleur
        B = Path("/banc")
        cas = []
        for panel, runs in (("jours", ("t1", "t2")), ("panel2", ("p2t1", "p2t2"))):
            for j in json.loads((B / f"{panel}.json").read_text()):
                for rr in runs:
                    cas.append((B / "depart" / j / "memoire", B / "runs" / "gpt-6.1-terra" / rr / j / "memoire", rr))
        r = mesurer(cas, Rappeleur, ("francis", "nexa"))
        print("Nexa (53 à 83 pages), Terra liste complète, 12 journées × 2 :", json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
