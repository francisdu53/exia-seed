"""Banc 17 §16-17 — la règle des sigles, appliquée à chaud au moteur de recherche (BANC SEULEMENT ; EXIA SEED inchangé).

Un mot de 2 à 4 lettres compte, en correspondance exacte, s'il n'est pas un mot vide et s'il est écrit en majuscules ou
avec un chiffre dans le titre ou un alias d'une page existante (BBQ, PC, SAS, 5K). Formes verbales courtes ajoutées aux
mots vides (fr : ai, va, as, es, ont ; en : us). Mesurée au §16 (`banc/catalogue/mots_courts.py`)."""
import inspect
import re
from pathlib import Path


def appliquer(RP):
    init0 = RP.Memoire.__init__
    src = inspect.getsource(RP.Rappeleur.activer)
    vieux = "pleins = [w for w in dict.fromkeys(mots) if len(w) >= 3 and w not in vides and not w.isdigit()]"
    neuf = ("pleins = [w for w in dict.fromkeys(mots) if w not in vides and not w.isdigit() and (len(w) >= 3 or "
            "(len(w) == 2 and (any(c.isdigit() for c in w) or w in m.distinctifs_courts)))]")
    assert vieux in src, "variante des sigles : la ligne du moteur a changé"
    ns = dict(vars(RP))
    exec(compile("\n".join(l[4:] for l in src.replace(vieux, neuf).splitlines()), "activer_sigles", "exec"), ns)

    def init(self, racine, implicites=()):
        init0(self, racine, implicites)
        vides = RP._mots_vides(self.masque) | ({"ai", "va", "as", "ont", "es"} if self.masque.code == "fr" else {"us"})
        from exia_seed import pages as P
        sigles = set()
        for p in P.lister(Path(racine) / "pages"):
            for l in (p.entete.get("aliases") or {}).values():
                for a0 in (l or []):
                    sigles |= {t.lower() for t in re.findall(r"\b[A-Z0-9]{2,4}\b", str(a0)) if not t.isdigit()}
        for a, noeuds in self.alias.items():
            for w in a:
                if 2 <= len(w) < RP.MOT_MIN and w not in vides and not w.isdigit() and w in sigles:
                    nouveaux = {n for n in noeuds if n not in self.implicites} - self.mots_alias.get(w, set())
                    if nouveaux:
                        self.mots_alias[w] |= nouveaux; self.distinctifs_courts.add(w)

    RP.Memoire.__init__ = init
    RP.Rappeleur.activer = ns["activer"]
