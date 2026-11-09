#!/usr/bin/env python3
"""Banc 17 §16 — la règle des mots courts, mesurée sans modèle (gratuit). Rien n'est changé dans EXIA SEED.

Règle (variante du banc, appliquée par remplacement à chaud) : un mot de 2 à 4 lettres compte, en correspondance
EXACTE seulement (aucun rapprochement), s'il n'est pas un mot vide ET (s'il contient un chiffre, ou s'il est un mot du
titre ou d'un alias d'une page existante). Mesures : rappel à K = 20 et 30 par message (comme §15), bruit (pages
touchées directement par message), et la liste des mots courts admis.

    python3 mots_courts.py lme|nexa
"""
import inspect, json, sys
from collections import Counter
from pathlib import Path

JEU = sys.argv[1]
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, "/plugins")          # le plugin du DÉPÔT, pour les deux jeux
from exia_seed import rappel as RP
sys.path.insert(0, "/c")
import rappel_par_message as RM

RM.KS = (20, 30)
ORIGINAL_INIT, ORIGINAL_ACTIVER = RP.Memoire.__init__, RP.Rappeleur.activer
src = inspect.getsource(RP.Rappeleur.activer)
VIEUX = "pleins = [w for w in dict.fromkeys(mots) if len(w) >= 3 and w not in vides and not w.isdigit()]"
NEUF = ("pleins = [w for w in dict.fromkeys(mots) if w not in vides and not w.isdigit() and (len(w) >= 3 or "
        "(len(w) == 2 and (any(c.isdigit() for c in w) or w in m.distinctifs_courts)))]")
assert VIEUX in src
ns = dict(vars(RP)); exec(compile("\n".join(l[4:] for l in src.replace(VIEUX, NEUF).splitlines()), "activer_variante", "exec"), ns)
ACTIVER_VARIANTE = ns["activer"]
ADMIS = Counter()
VIDES_VUS = {}


def init_variante(self, racine, implicites=()):
    ORIGINAL_INIT(self, racine, implicites)
    vides = RP._mots_vides(self.masque) | ({"ai", "va", "as", "ont", "es"} if self.masque.code == "fr" else {"us"})   # formes verbales courtes
    # sigles : écrits en MAJUSCULES (ou avec un chiffre) dans un titre ou un alias d'origine — « BBQ », « PC », « 5K »
    import re as _re
    from exia_seed import pages as _P
    sigles = set()
    for p in _P.lister(Path(racine) / "pages"):
        for l in (p.entete.get("aliases") or {}).values():
            for a0 in (l or []):
                sigles |= {t.lower() for t in _re.findall(r"\b[A-Z0-9]{2,4}\b", str(a0)) if not t.isdigit()}
    VIDES_VUS.update({w: (w in vides) for w in ("ai", "le", "la", "de", "et", "en", "un", "it", "us", "is", "of", "to", "on", "or", "at", "by", "an", "as", "ma", "va")})
    for a, noeuds in self.alias.items():
        for w in a:
            if 2 <= len(w) < RP.MOT_MIN and w not in vides and not w.isdigit():
                if w not in sigles:
                    continue                                   # règle : sigle (majuscules) ou chiffre seulement
                nouveaux = {n for n in noeuds if n not in self.implicites} - self.mots_alias.get(w, set())
                if nouveaux:                                   # aussi quand le sigle désigne déjà une autre page
                    self.mots_alias[w] |= nouveaux; self.distinctifs_courts.add(w); ADMIS[w] += len(nouveaux)


bruit = {}
def compter(activer):
    def f(self, m, texte, *a, **k):
        r = activer(self, m, texte, *a, **k)
        bruit.setdefault("n", []).append(len(r["entrees"]))
        return r
    return f

resultats = {}
for nom, init, act in (("actuelle", ORIGINAL_INIT, ORIGINAL_ACTIVER), ("mots courts", init_variante, ACTIVER_VARIANTE)):
    RP.Memoire.__init__ = init; RP.Rappeleur.activer = compter(act); bruit.clear()
    if JEU == "lme":
        B = Path("/banc/runs"); dep = B / "catalogue-base" / "memoires" / "_fusion"
        cas = [(dep, B / f"catalogue-terra-complet-{i}" / "memoire", "") for i in (1, 2)]; imp = ("user", "assistant")
    else:
        B = Path("/banc"); cas = []
        for panel, runs in (("jours", ("t1", "t2")), ("panel2", ("p2t1", "p2t2"))):
            for j in json.loads((B / f"{panel}.json").read_text()):
                cas += [(B / "depart" / j / "memoire", B / "runs" / "gpt-6.1-terra" / rr / j / "memoire", rr) for rr in runs]
        imp = ("francis", "nexa")
    RM.RATES.clear()
    r = RM.mesurer(cas, RP.Rappeleur, imp)
    r["pages_touchees_directement_par_message"] = round(sum(bruit["n"]) / len(bruit["n"]), 1)
    r["rates_K30"] = sorted({x[1] for x in RM.RATES})
    resultats[nom] = r
print(json.dumps(resultats, ensure_ascii=False, indent=1))
print("mots courts admis (pages concernées) :", len(ADMIS), "mots ;", ", ".join(f"{w}({n})" for w, n in ADMIS.most_common(40)))
print("mots vides reconnus :", VIDES_VUS)
