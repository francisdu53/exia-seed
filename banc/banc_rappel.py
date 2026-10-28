#!/usr/bin/env python3
"""Banc 6b, partie 1 — rejouer les vraies conversations, SANS triche avec le temps, SANS modèle.

Pour chaque message de l'utilisateur dans le brut, la mémoire est reconstituée TELLE QU'ELLE ÉTAIT :
l'instantané git de la dernière consolidation antérieure au message (le dépôt `memoire/` en garde un
par passage). Un fait appris après le message ne peut donc pas servir à y répondre.

Rappels sans appel au modèle :
    A    EXIA SEED complet (cascade + graphe + cab_pull), avec son seuil de silence
    Bk   plein texte seul, À BUDGET ÉGAL : autant de faits que A, les mieux couverts lexicalement
    B5   plein texte seul, les 5 meilleurs faits à chaque message (un RAG classique)
    D    tout donner : toutes les pages de l'instantané     → l'étalon de qualité, et son coût

⚠️ Premier passage (26/09) : B avec le seuil de A ne parlait JAMAIS (0/117) — les messages réels
sont longs, aucun fait n'en couvre assez sans l'aide du graphe. Comparaison déloyale, remplacée par
le budget égal (Bk) et le top-5 (B5), usages standards en recherche d'information.
Le rappel C (« à la Karpathy ») et le juge sont dans banc_juge.py (partie 2, avec modèle).

Lecture seule sur la mémoire : `git archive`, rien n'est modifié.

    python3 banc_rappel.py /opt/data/memoire /opt/data/workspace/banc-6b
"""
import json
import re
import subprocess
import sys
import tarfile
import io
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ICI = Path(__file__).resolve()
sys.path.insert(0, "/opt/hermes")
sys.path.insert(0, str(Path(sys.argv[3]) if len(sys.argv) > 3 else Path("/opt/data/plugins")))
from exia_seed import graphe as G                                        # noqa: E402
from exia_seed import rappel as R                                        # noqa: E402
from exia_seed.util import estimer_tokens                                # noqa: E402

PARIS = ZoneInfo("Europe/Paris")
IMPLICITES = ("francis", "nexa")
UTILISATEUR, AGENT = "francis", "nexa"


def messages(memoire: Path):
    """[(instant Paris naïf, texte du message, réponse de l'agent qui suit)] dans l'ordre."""
    sortie = []
    for f in sorted((memoire / "raw").glob("*.md")):
        texte = f.read_text(encoding="utf-8")
        m = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})", texte, re.M)
        o = re.search(r"^ouvert_le:\s*\S+T(\d\d:\d\d)", texte, re.M)
        if not m:
            continue
        jour = datetime.fromisoformat(m.group(1))
        tours, courant = [], None
        for ligne in texte.split("## Échanges", 1)[-1].splitlines():
            t = re.match(r"^\[(\d\d):(\d\d) (\w+)\] ?(.*)$", ligne)
            if t:
                courant = [t.group(3), f"{t.group(1)}:{t.group(2)}", t.group(4)]
                tours.append(courant)
            elif courant and ligne.strip() and not ligne.lstrip().startswith("<!--"):
                courant[2] += "\n" + ligne
        for k, (qui, hhmm, txt) in enumerate(tours):
            if qui != UTILISATEUR:
                continue
            j = jour + timedelta(days=1) if o and hhmm < o.group(1) else jour
            instant = datetime.fromisoformat(f"{j.date()}T{hhmm}")
            reponse = next((t[2] for t in tours[k + 1:] if t[0] == AGENT), "")
            sortie.append((instant, txt.strip(), reponse.strip()))
    return sortie


def instantanes(memoire: Path):
    """[(epoch, commit)] de la mémoire, dans l'ordre."""
    r = subprocess.run(["git", "-C", str(memoire), "-c", "safe.directory=*", "log", "--reverse", "--format=%H %ct"],
                       capture_output=True, text=True, check=True)
    return [(int(ct), h) for h, ct in (l.split() for l in r.stdout.splitlines())]


def extraire(memoire: Path, commit: str, dossier: Path) -> Path:
    if (dossier / "pages").exists():
        return dossier
    dossier.mkdir(parents=True, exist_ok=True)
    tar = subprocess.run(["git", "-C", str(memoire), "-c", "safe.directory=*", "archive", commit],
                         capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(dossier, members=[x for x in t.getmembers() if x.name.startswith(("pages/", "INDEX.md"))], filter="data")
    (dossier / "raw").mkdir(exist_ok=True)
    G.calculer(dossier, implicites=IMPLICITES)          # le graphe est une fonction des pages (05 D1)
    return dossier


def main() -> int:
    memoire, sortie = Path(sys.argv[1]), Path(sys.argv[2])
    sortie.mkdir(parents=True, exist_ok=True)
    snaps, msgs = instantanes(memoire), messages(memoire)
    rappeleurs, lignes = {}, []
    for n, (instant, texte, reponse) in enumerate(msgs):
        epoch = instant.replace(tzinfo=PARIS).timestamp()
        avant = [h for ct, h in snaps if ct < epoch]
        base = {"n": n, "instant": instant.isoformat(timespec="minutes"), "message": texte[:500],
                "reponse": reponse[:800], "instantane": avant[-1][:7] if avant else None}
        if not avant:
            lignes.append({**base, "memoire": "vide"}); continue
        h = avant[-1]
        if h not in rappeleurs:
            d = extraire(memoire, h, sortie / "instantanes" / h[:7])
            rappeleurs[h] = (R.Rappeleur(d, implicites=IMPLICITES), d)
        rp, d = rappeleurs[h]
        a = rp.rappeler(texte, instant)
        seuil, R.SEUIL_FAIT = R.SEUIL_FAIT, 0.0             # B : tout le classement lexical, sans seuil
        try:
            b = rp.rappeler(texte, instant, mode="plein_texte")
        finally:
            R.SEUIL_FAIT = seuil
        bk, b5 = b["faits"][:len(a["faits"])], b["faits"][:5]
        m = rp.memoire()
        pages_tokens = sum(estimer_tokens(p.read_text(encoding="utf-8")) for p in (d / "pages").glob("*.md"))
        lignes.append({**base, "memoire": {"noeuds": len({f["noeud"] for f in m.faits}), "faits": len(m.faits)},
                       "A": {"faits": [f["fait"] for f in a["faits"]], "tokens": a["tokens"],
                             "latence_ms": a["latence_ms"]["hors_cache"], "entrees": a["entrees"], "orphelins": a["orphelins"]},
                       "Bk": {"faits": [f["fait"] for f in bk], "tokens": sum(estimer_tokens(f["fait"]) for f in bk),
                              "latence_ms": b["latence_ms"]["hors_cache"]},
                       "B5": {"faits": [f["fait"] for f in b5], "tokens": sum(estimer_tokens(f["fait"]) for f in b5),
                              "latence_ms": b["latence_ms"]["hors_cache"]},
                       "D": {"faits": len(m.faits), "tokens": pages_tokens}})
    (sortie / "rejeu.jsonl").write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lignes), encoding="utf-8")

    # Résumé, sans juge
    jouables = [l for l in lignes if l.get("memoire") != "vide"]
    def stats(cle):
        nonvides = [l for l in jouables if l[cle]["faits"]]
        tok = sorted(l[cle]["tokens"] for l in jouables)
        lat = sorted(l[cle]["latence_ms"] for l in jouables)
        return {"blocs_non_vides": f"{len(nonvides)}/{len(jouables)}",
                "tokens_moyens": round(sum(tok) / len(tok)) if tok else 0,
                "tokens_max": tok[-1] if tok else 0,
                "latence_p95_ms": lat[int(0.95 * len(lat)) - 1] if lat else None}
    resume = {"messages": len(lignes), "memoire_vide": len(lignes) - len(jouables), "jouables": len(jouables),
              "instantanes_utilises": len(rappeleurs), "A": stats("A"), "Bk": stats("Bk"), "B5": stats("B5"),
              "D": {"tokens_moyens": round(sum(l["D"]["tokens"] for l in jouables) / max(1, len(jouables))),
                    "tokens_max": max((l["D"]["tokens"] for l in jouables), default=0)},
              "faits_A_absents_de_Bk": sum(len(set(l["A"]["faits"]) - set(l["Bk"]["faits"])) for l in jouables),
              "faits_A_total": sum(len(l["A"]["faits"]) for l in jouables)}
    (sortie / "resume_partie1.json").write_text(json.dumps(resume, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(resume, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
