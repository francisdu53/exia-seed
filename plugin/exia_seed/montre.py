"""Le rappel « montre » — plan 1.0 d'EXIA SEED (NOTE-FCM-thematiques §10 ; Francis, 19/11/2026).

  Rouage 1  ce sont les SOUVENIRS qui s'allument (plein texte sur toute la mémoire, notions des cartes FCM, pages
            nommées, pages activées par le graphe) ; une page n'est là que parce qu'un de ses souvenirs l'est ;
  Rouage 2  chaque souvenir a SA note, la chance d'être utile, faite d'une seule primitive : cab_pull vers 1 pour chaque
            voix présente, cab_pull vers 0 pour chaque voix attendue absente (poids appris, montre_poids.json) ;
  Rouage 3  le choix : note ≥ SEUIL, au plus MAX souvenirs, les tokens seulement comme garde-fou ; silence sinon ;
  Rouage 4  la continuité : un souvenir déjà donné plus tôt dans la conversation n'est pas redonné (Hermès rejoue les
            blocs : Nexa l'a encore sous les yeux) ; un message trop court pour dire son sujet (« oui, vas-y ») s'aide du
            message précédent ;
  Rouage 5  chaque souvenir arrive entier, avec la raison qui l'a fait remonter.
Aucun modèle de langage, aucun vecteur. Mesures (EXIA SEED 0.9.16) : NOTE-FCM-thematiques §10, docs/21.
"""
from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict

from . import cartes as _cartes
from . import graphe as _graphe
from . import requete as _requete
from .util import estimer_tokens

SEUIL = 0.20          # au moins une chance sur cinq d'être utile (la 0.9.15 : ≈ 22 % de ses souvenirs le sont)
MAX = 10              # Francis, 19/11 : « une dizaine c'est bien »
GARDE_FOU = 1200      # tokens du bloc (invariant de la spec, docs/06)
BM25_MAX = 60
NOTIONS_MAX = 30
PAGES_GRAPHE = 5
POIDS = json.loads((Path(__file__).with_name("montre_poids.json")).read_text(encoding="utf-8"))
VOIX = ("nom", "un_mot", "mots", "bm25", "fcm", "notion", "graphe", "regle", "vecu")
ABSENCES = ("mots", "notion", "fcm")


def cab_pull(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _note(x: Dict[str, float], absences: bool = True, poids: Dict = None) -> float:
    P = poids or POIDS
    s = P["fuite"]
    for k in P["voix"]:
        s = cab_pull(s, 1.0, P["voix"][k] * x.get(k, 0.0))
    for k in (ABSENCES if absences else ()):
        if k in ("fcm", "notion") and not x.get("_themes", True):
            continue          # voix ATTENDUE seulement si le souvenir a un thème : une mémoire sans thésaurus ne se tait pas
        s = cab_pull(s, 0.0, P["absences"][k] * (1.0 - x[k]))
    return s


class Montre:
    def __init__(self, rappeleur, implicites=("francis", "nexa"), **options):
        self.r = rappeleur
        self.implicites = implicites
        self._etat = None
        # interrupteurs (recherche des trous : on retire un rouage, on remesure)
        # F3 (20/11) : la voix FORCE — « ce qui a servi se renforce » ; `forces` : texte du souvenir → force apprise
        self.poids = options.pop("poids", POIDS)
        self.forces = options.pop("forces", None)
        self.o = {"bm25": True, "notions": True, "pages": True, "graphe": True, "vecu": True, "absences": True,
                  "continuite": True, "seuil": SEUIL, "max": MAX, "garde_fou": GARDE_FOU, **options}

    def _prepare(self, m):
        if self._etat is None or self._etat[0] is not m:
            vides = _graphe._mots_vides_graphe(m.masque) | {_graphe._norm(x).strip() for x in m.masque.mots_vides_recherche}
            cartes = _cartes.construire(m.faits, vides)
            inv = {}
            for c, x in cartes.items():
                d = defaultdict(list)
                for i, ns in x["accroches"].items():
                    for v in ns:
                        d[v].append(i)
                inv[c] = d
            self._etat = (m, cartes, inv, vides)
        return self._etat

    def rappeler(self, message: str, maintenant: datetime, deja=(), precedent: str = "") -> Dict:
        """ROUAGE 4, la continuité : `deja` = souvenirs déjà donnés plus tôt dans la conversation (Hermès les rejoue, Nexa
        les a encore sous les yeux : on ne les redonne pas) ; `precedent` = le message précédent (< 30 min), qui sert
        d'indice quand celui-ci est trop court pour dire son sujet seul (« oui, vas-y »)."""
        self.r._memo_activer = {}
        try:
            if self.o["continuite"] and precedent:
                m = self.r.memoire()
                if m is not None and len(self.r.activer(m, message)["pleins"]) < 4:
                    message = precedent + "\n" + message
            return self._rappeler(message, maintenant, set(deja) if self.o["continuite"] else set())
        finally:
            self.r._memo_activer = None

    def _rappeler(self, message: str, maintenant: datetime, deja=frozenset()) -> Dict:
        t0 = time.perf_counter()
        m = self.r.memoire()
        vide = {"bloc": "", "faits": [], "notes": [], "tokens": 0, "latence_ms": 0.0}
        if m is None:
            return vide
        _, cartes, inv, vides = self._prepare(m)
        instant = maintenant.isoformat(timespec="minutes")
        a = self.r.activer(m, message)
        mq = set(_cartes.mots(_graphe._norm(message), vides))
        nommes = {y.split("→", 1)[1] for y in a["etages"].get("alias", ())}
        un_mot = {y.split("→", 1)[1] for y in a["etages"].get("mot_alias", ())} - nommes
        fcm = {k[8:]: v for k, v in a["entrees"].items() if k.startswith("concept:")}
        fcm_max = max(fcm.values(), default=0.0) or 1.0
        d_ref = max(1e-6, 1.0 - min(m.repos.values(), default=0.0))
        poids, total = a["poids"], a["total"]
        # ── rouage 1 : les souvenirs qui s'allument ─────────────────────────────────────
        cand = {}
        rang = {}
        mots = [w for w in a["pleins"] if len(w) >= 4]
        if mots and self.o["bm25"]:
            try:
                for k, (i,) in enumerate(m.fts.execute("select rowid from f where f match ? order by bm25(f, 1.0, ?) limit ?",
                                                        (" OR ".join(f'"{w}"' for w in mots), _requete.POIDS_CHAMP_BM25, BM25_MAX))):
                    rang[i] = k; cand[i] = None
            except Exception:
                pass
        best, nbn = {}, defaultdict(int)
        for c, carte in cartes.items():
            act = {}
            for u in mq:
                if u in carte["notions"]:
                    act[u] = 1.0
                for v, w in carte["liens"].get(u, {}).items():
                    if v not in mq and w > act.get(v, 0.0):
                        act[v] = w
            for v, x in act.items():
                for i in inv[c].get(v, ()):
                    nbn[i] += 1
                    if x > best.get(i, 0.0):
                        best[i] = x
        if self.o["notions"]:
            for _, _, i in sorted(((b, nbn[i], i) for i, b in best.items() if b >= 0.3), key=lambda t: (-t[0], -t[1], t[2]))[:NOTIONS_MAX]:
                cand[i] = None
        pages = (set(nommes) | set(un_mot) if self.o["pages"] else set()) | \
                ({n for n, _ in sorted(a["actives"].items(), key=lambda t: -t[1])[:PAGES_GRAPHE]} if self.o["graphe"] else set())
        for n in pages:
            for i in m.par_noeud.get(n, ()):
                cand[i] = None
        # ── voix de chaque souvenir allumé ─────────────────────────────────────────
        V = {}
        for i in cand:
            f = m.faits[i]
            if f["dit_le"] and f["dit_le"][:16] > instant:
                continue
            cov = math.sqrt(a["couverture"](f["racines"]))
            if f["noeud"] in m.implicites and cov == 0:
                continue                                    # la page de l'utilisateur : seulement par écho
            n = f["noeud"]
            V[i] = {"nom": float(n in nommes), "un_mot": float(n in un_mot), "mots": min(1.0, cov / 0.3),
                    "bm25": 1.0 / (1 + rang[i]) if i in rang else 0.0,
                    "fcm": max((fcm.get(c, 0.0) for c in f.get("concepts", ())), default=0.0) / fcm_max,
                    "notion": best.get(i, 0.0), "graphe": min(1.0, a["actives"].get(n, 0.0) / d_ref),
                    "regle": float(f["section"] == "procedural"), "vecu": 0.0, "_cov": cov,
                    "_themes": bool(f.get("concepts")),
                    "force": (self.forces(f["texte"]) if self.forces else 0.0)}
        # le VÉCU : dit en même temps (ou nommé par) un souvenir ANCRÉ — page nommée, assez du message, ou notion dite
        ancres = {i for i, x in V.items() if x["nom"] or x["_cov"] >= 0.15 or x["notion"] >= 1.0}
        debut = defaultdict(list)
        for i in V:
            debut[m.faits[i]["texte"][:100]].append(i)
        lien_de = {}
        for n in ({m.faits[i]["noeud"] for i in ancres} if self.o["vecu"] else ()):
            for _, _, preuves in m.voisins.get(n, ()):
                for pr in preuves:
                    xs = [x for x in debut.get((pr.get("fait") or "")[:100], []) if x in ancres]
                    if pr.get("type") in ("meme_ligne", "voisine") and pr.get("avec"):
                        ys = debut.get((pr["avec"].get("fait") or "")[:100], [])
                        for x in xs:
                            for y in ys:
                                if y != x and pr.get("force", 0.5) > V[y]["vecu"]:
                                    V[y]["vecu"] = min(1.0, pr.get("force", 0.5)); lien_de[y] = x
                    elif pr.get("type") == "nomme" and pr.get("nomme"):
                        for x in xs:
                            for y in m.par_noeud.get(pr["nomme"], ()):
                                if y in V and y != x and 0.4 > V[y]["vecu"]:
                                    V[y]["vecu"] = 0.4; lien_de[y] = x
        # ── rouage 2 : la note ; rouage 3 : le choix ────────────────────────────────────
        notes = sorted(((_note(x, self.o["absences"], self.poids), i) for i, x in V.items() if i not in deja), key=lambda t: (-t[0], t[1]))
        choisis = [(s, i) for s, i in notes if s >= self.o["seuil"]][:self.o["max"]]
        # ── rouage 5 : la présentation, chaque souvenir avec sa raison ─────────────────────────
        if not choisis:
            return {**vide, "latence_ms": round((time.perf_counter() - t0) * 1000, 2), "candidats": len(V)}
        from .rappel import _ligne

        def raison(i):
            x, f = V[i], m.faits[i]
            n = f["noeud"]
            tirages = sorted(((self.poids["voix"][k] * x.get(k, 0.0), k) for k in self.poids["voix"]), reverse=True)
            k = tirages[0][1]
            if k == "nom":
                return f"tu as nommé « {m.titres.get(n, n)} »"
            if k == "un_mot":
                return f"un mot de « {m.titres.get(n, n)} »"
            if k == "vecu" and i in lien_de:
                return f"dit en même temps que « {m.faits[lien_de[i]]['texte'][:60]}… »"
            if k == "fcm":
                c = max(f.get("concepts", ()), key=lambda c: fcm.get(c, 0.0), default="")
                return f"même FCM : {c.replace('_', ' ')}"
            if k == "notion":
                return "notion de ton message"
            if k == "regle":
                return "règle de travail"
            if k == "force":
                return "t’a déjà servi"
            communs = sorted((w for w in poids if w in f["racines"]), key=lambda w: -poids[w])[:3]
            return "mots en commun : " + ", ".join(communs) if communs else "lié au sujet"

        par_page, ordre_pages = defaultdict(list), []
        for s, i in choisis:
            n = m.faits[i]["noeud"]
            if n not in par_page:
                ordre_pages.append(n)
            par_page[n].append(i)
        lignes, tok = [m.masque.textes["souvenirs_entete"]], 0
        retenus = []
        for n in ordre_pages:
            entete = [f"• {m.titres.get(n, n)} — memoire/pages/{m.fichiers.get(n, '')}"] + ([f"  {m.fiches[n]}"] if m.fiches.get(n) else [])
            corps = []
            for i in par_page[n]:
                l = "  – " + _ligne(m.faits[i], m.masque)[2:] + f" — pourquoi : {raison(i)}"
                if estimer_tokens("\n".join(lignes + entete + corps + [l])) > self.o["garde_fou"]:
                    break
                corps.append(l); retenus.append(i)
            if corps:
                lignes += entete + corps
        bloc = "\n".join(lignes) if retenus else ""
        return {"bloc": bloc, "faits": retenus, "notes": [round(s, 3) for s, i in choisis if i in retenus],
                "raisons": [raison(i) for i in retenus],
                "tokens": estimer_tokens(bloc) if bloc else 0, "candidats": len(V),
                "latence_ms": round((time.perf_counter() - t0) * 1000, 2)}
