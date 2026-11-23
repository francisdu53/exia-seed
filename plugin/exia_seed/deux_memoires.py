"""0.10.0 (docs/22) — « deux mémoires, une toile » : le rappel automatique lit les SOUVENIRS consolidés et le BRUT.

Réglage `rappel_moteur: deux_memoires` (défaut `ancien` : installer la 0.10.0 ne change rien tant qu'on ne bascule pas ;
revenir = remettre `ancien`). Aucun modèle au rappel. Évalué sur LoCoMo et LongMemEval (docs/22) : prototype de banc
« NA1 », porté ici sans ses rouages écartés par la mesure (cartes écrites, concurrence, frères, passages, désignation,
séance d'abord, mots du temps).

  SOUVENIRS (Toile)  chaque souvenir allumé (plein texte, page nommée ou un mot de son nom, concepts) reçoit la SOMME de
                     ses indices en log-cotes (régression logistique) : rareté BM25, couverture de la question, page
                     nommée, concept (rareté par le « fan »), règle de conduite, fenêtre de temps ; rétroaction : les
                     mots rares des 3 meilleurs souvenirs relancent une 2e recherche.
  BRUT (ToileBrute)  la conversation elle-même, découpée en tours (deux répliques si elles tiennent en 600 caractères,
                     sinon une) : rareté BM25, couverture, personne nommée, fenêtre de temps ; les tours voisins des
                     meilleurs suivent. Jamais les lignes retirées (« oublie ce que je viens de dire »), jamais les
                     3 dernières heures (la conversation est encore sous les yeux de l'agent).
  FUSION             les deux listes réunies par log-cote ; gardé ce qui a au moins `seuil` de chances d'aider, au plus
                     `max`, garde-fou en tokens ; rien de ce qui a été donné dans les 3 dernières heures.
  CORRECTEUR         un mot de la question inconnu de la mémoire (faute de frappe) est remplacé par le mot de la mémoire
                     le plus proche (distance 1 ; 2 pour les mots longs) ; un mot connu n'est jamais touché.
  RÈGLE D'ABSTENTION en tête du bloc : chaque souvenir dit qui l'a dit ; si personne ne l'a dit, ce n'est pas en mémoire.

Les deux voix du brut sont gardées et marquées : les phrases de l'agent portent « (toi) » — on se souvient de ses
propres paroles. Mots sans accents des deux côtés (é → e, ç → c, œ → oe : `graphe._norm`). Ex æquo départagés par un
ordre fixe (même question, même mémoire → mêmes souvenirs, d'un redémarrage à l'autre). Données linguistiques (mois,
« il y a trois jours », textes du bloc) dans les masques de langue.
"""
from __future__ import annotations

import json
import math
import re
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from . import rappel as R
from .graphe import _norm as _plier
from .util import estimer_tokens

POIDS = json.loads(Path(__file__).with_name("deux_memoires_poids.json").read_text(encoding="utf-8"))
TOUR = re.compile(r"^\[(\d\d:\d\d) ([^\]]+)\] (.*)$")


class _Chrono:
    """Temps par étape (ms), pour le journal du rappel."""

    def __init__(self) -> None:
        self.ms: Dict[str, float] = defaultdict(float)

    @contextmanager
    def etape(self, nom: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.ms[nom] += (time.perf_counter() - t0) * 1000


# ── correcteur tiré de la mémoire ────────────────────────────────────────────────────────────────────
def _osa(a: str, b: str, borne: int) -> int:
    """Distance d'édition où deux lettres voisines inversées comptent 1 (« panit » → « paint »), arrêtée au-delà de `borne`."""
    if abs(len(a) - len(b)) > borne:
        return borne + 1
    pp, p = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        c = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            v = min(p[j] + 1, c[j - 1] + 1, p[j - 1] + (a[i - 1] != b[j - 1]))
            if pp is not None and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                v = min(v, pp[j - 2] + 1)
            c[j] = v
        if min(c) > borne:
            return borne + 1
        pp, p = p, c
    return p[-1]


class Correcteur:
    """Un mot de la question dont la RACINE est inconnue de la mémoire (il ne compterait pour rien) est remplacé par le
    mot de la mémoire le plus proche à une faute de frappe près ; à égalité, le plus fréquent, puis l'ordre alphabétique.
    Index par suppressions (SymSpell). Un mot connu n'est jamais touché ; une question sans mot inconnu passe telle quelle."""

    def __init__(self, df: Dict[str, int], mini: int = 5, long_d2: int = 9):
        self.df, self.mini, self.long_d2 = df, mini, long_d2
        self.connues = {R._rac(w) for w in df}
        self.index = defaultdict(list)
        for w in sorted(df):
            if len(w) >= mini - 1 and not w.isdigit():
                for d in {w} | {w[:k] + w[k + 1:] for k in range(len(w))}:
                    self.index[d].append(w)

    @classmethod
    def depuis(cls, textes, mini: int = 5) -> "Correcteur":
        df = defaultdict(int)
        for t in textes:
            for w in set(_plier(t).split()):
                df[w] += 1
        return cls(dict(df), mini=mini)

    def corriger(self, question: str):
        sortie, faites = [], []
        for w in _plier(question).split():
            if len(w) < self.mini or not w.isalpha() or R._rac(w) in self.connues:
                sortie.append(w); continue
            borne = 2 if len(w) >= self.long_d2 else 1
            cands = set()
            for d in {w} | {w[:k] + w[k + 1:] for k in range(len(w))}:
                cands.update(self.index.get(d, ()))
            bons = sorted(x for x in ((_osa(w, c, borne), -self.df[c], c) for c in cands) if x[0] <= borne)
            if bons:
                sortie.append(bons[0][2]); faites.append((w, bons[0][2]))
            else:
                sortie.append(w)
        return (" ".join(sortie) if faites else question), faites


# ── fenêtre de temps (vocabulaire : masque de langue, `fenetre`) ─────────────────────────────────────
def fenetre_de_temps(texte: str, instant: datetime, masque) -> Optional[tuple]:
    """Fenêtre [début, fin) désignée par le message (« en mai 2023 », « la semaine dernière », « il y a trois
    jours »), ou None. Symbolique."""
    v = getattr(masque, "fenetre", None) or {}
    t = _plier(texte)
    an = re.search(r"\b(19|20)\d\d\b", t)
    exclus = v.get("mois_exclus") or {}
    for k, nom in enumerate(masque.mois, start=1):
        nom = _plier(nom).strip()
        if re.search(rf"\b{re.escape(nom)}\b", t) and not (nom in exclus and re.search(exclus[nom], t)):
            y = int(an.group(0)) if an else instant.year - (1 if k > instant.month else 0)
            return datetime(y, k, 1), datetime(y + (k == 12), k % 12 + 1, 1)
    if an:
        return datetime(int(an.group(0)), 1, 1), datetime(int(an.group(0)) + 1, 1, 1)
    j = instant.replace(hour=0, minute=0, second=0, microsecond=0)
    for motif, recul, duree in v.get("relatifs", ()):
        if re.search(motif, t):
            return ((j - timedelta(days=recul), j - timedelta(days=recul) + timedelta(days=duree)) if recul
                    else (j - timedelta(days=duree), j + timedelta(days=1)))
    m = re.search(v["il_y_a"], t) if v.get("il_y_a") else None
    if m:
        nb = v.get("nombres", {}).get(m.group(1)) or (int(m.group(1)) if m.group(1).isdigit() else None)
        u = v.get("unites", {}).get(m.group(2))
        if nb and u:
            c = j - timedelta(days=nb * u)
            return c - timedelta(days=max(1, u // 2)), c + timedelta(days=max(1, u // 2) + 1)
    return None


def _date(masque, iso: str) -> str:
    try:
        return masque.en_clair(datetime.strptime(iso[:10], "%Y-%m-%d").date()) if iso else ""
    except ValueError:
        return ""


# ── SOUVENIRS ────────────────────────────────────────────────────────────────────────────────────────
class Toile:
    def __init__(self, rappeleur, poids: Dict[str, float], options: Optional[Dict] = None):
        self.r, self.m = rappeleur, rappeleur.memoire()
        self.poids = poids
        self.o = {"bm25_max": 100, "concepts_max": 60, "prf_lambda": 1.0, "prf_e": 5, "prf_m": 3, **(options or {})}
        m = self.m
        self.N = max(1, len(m.faits))
        fan = defaultdict(int)
        for f in m.faits:
            for c in f.get("concepts", ()):
                fan[c] += 1
        self.idf_concept = {c: math.log((self.N + 1) / (n + 0.5)) for c, n in fan.items()}
        self.par_concept = defaultdict(list)
        for i, f in enumerate(m.faits):
            for c in f.get("concepts", ()):
                self.par_concept[c].append(i)
        self.idf_concept_max = max(self.idf_concept.values(), default=1.0) or 1.0
        self.df = defaultdict(int)                       # pour la rétroaction : en combien de souvenirs chaque mot
        for f in m.faits:
            for w in sorted(set(re.findall(r"\w{4,}", _plier(f["texte"])))):
                self.df[w] += 1
        self.corr = Correcteur.depuis((f["texte"] for f in m.faits), int(self.o.get("corr_min", 5))) \
            if self.o.get("correcteur", True) else None

    def _fts(self, mots: List[str]) -> Dict[int, float]:
        try:
            return {i: -s for i, s in self.m.fts.execute(
                "select rowid, bm25(f, 1.0, ?) from f where f match ? order by 2, 1 limit ?",
                (R.POIDS_CHAMP_BM25, " OR ".join(f'"{w}"' for w in mots), self.o["bm25_max"]))}
        except Exception:
            return {}

    def rappeler(self, question: str, instant: datetime, k: int, ch: _Chrono, actif,
                 filtre: Optional[datetime] = None) -> List[Dict]:
        """`instant` : maintenant (fenêtre de temps) ; `filtre` : les souvenirs dits après sont ignorés (défaut : instant)."""
        m = self.m
        if self.corr is not None:
            with ch.etape("correcteur"):
                question, faites = self.corr.corriger(question)
            actif["corrections"] += len(faites)
        with ch.etape("traits"):
            a = self.r.activer(m, question)
            nommes = {y.split("→", 1)[1] for y in a["etages"].get("alias", ())}
            un_mot = {y.split("→", 1)[1] for y in a["etages"].get("mot_alias", ())} - nommes
            concepts = {k_[8:]: v for k_, v in a["entrees"].items() if k_.startswith("concept:")}
            fen = fenetre_de_temps(question, instant, m.masque)
        with ch.etape("allumage"):
            mots = [w for w in a["pleins"] if len(w) >= 3]
            bm = self._fts(mots) if mots else {}
            cand = set(bm)
            lam = float(self.o.get("prf_lambda", 0.0))
            if lam > 0 and bm:                          # rétroaction : les mots rares des meilleurs souvenirs
                hauts = sorted(bm, key=lambda i: (-bm[i], i))[:int(self.o["prf_m"])]
                qm = {_plier(w).strip() for w in a["pleins"]}
                tf = defaultdict(float)
                for i in hauts:
                    for w in sorted(set(re.findall(r"\w{4,}", _plier(m.faits[i]["texte"])))):
                        if w not in qm and self.df[w] < 0.05 * self.N:
                            tf[w] += math.log((self.N + 1) / (self.df[w] + 0.5))
                exp = [w for w, _ in sorted(tf.items(), key=lambda x: (-x[1], x[0]))[:int(self.o["prf_e"])]]
                if exp:
                    for i, s2 in self._fts(exp).items():
                        bm[i] = bm.get(i, 0.0) + lam * s2; cand.add(i)
                    actif["retroaction_mots"] += len(exp)
            for n in sorted(nommes | un_mot):
                cand.update(m.par_noeud.get(n, ()))
            if concepts:
                par_c = sorted(((v * self.idf_concept.get(c, 0.0), c) for c, v in concepts.items()), reverse=True)
                pris = []
                for _, c in par_c:
                    pris += self.par_concept.get(c, [])
                    if len(pris) >= self.o["concepts_max"]:
                        break
                cand.update(pris[:self.o["concepts_max"]])
            lim = (filtre or instant).isoformat(timespec="minutes")
            cand = {i for i in cand if not (m.faits[i]["dit_le"] and m.faits[i]["dit_le"][:16] > lim)}
        with ch.etape("note"):
            L = {}
            for i in sorted(cand):
                f = m.faits[i]
                cs = f.get("concepts", ())
                x = {"biais": 1.0, "bm25": math.log1p(bm.get(i, 0.0)), "couverture": a["couverture"](f["racines"]),
                     "nom": float(f["noeud"] in nommes), "un_mot": float(f["noeud"] in un_mot),
                     "concept": max((concepts.get(c, 0.0) * self.idf_concept.get(c, 0.0) / self.idf_concept_max for c in cs), default=0.0),
                     "theme_absent": float(bool(concepts) and bool(cs) and not any(c in concepts for c in cs)),
                     "regle": float(f.get("section") == "procedural"), "temps_dans": 0.0, "temps_hors": 0.0}
                if fen and f["dit_le"]:
                    try:
                        d = datetime.fromisoformat(f["dit_le"][:10])
                        x["temps_dans" if fen[0] <= d < fen[1] else "temps_hors"] = 1.0
                    except ValueError:
                        pass
                L[i] = sum(self.poids.get(c, 0.0) * v for c, v in x.items())
        actif["souvenirs_allumes"] += len(L)
        ordre = sorted(L, key=lambda i: (-L[i], i))[:k]
        return [{"type": "fait", "cle": "f:" + m.faits[i]["texte"], "texte": m.faits[i]["texte"], "note": L[i],
                 "date": _date(m.masque, m.faits[i]["dit_le"] or ""), "page": m.faits[i]["noeud"],
                 "refs": sorted([list(x) for x in (m.faits[i].get("refs") or ())], key=str)} for i in ordre]


# ── BRUT ─────────────────────────────────────────────────────────────────────────────────────────────
class ToileBrute:
    def __init__(self, racine: Path, poids: Dict[str, float], options: Optional[Dict] = None):
        self.poids = poids
        self.o = {"bm25_max": 100, "voisins_parents": 3, "voisins_ecart": -1.0, "taille_max_car": 600, **(options or {})}
        self.tours = []
        retirees = set()                                  # « oublie ce que je viens de dire » : jamais rendu par le brut
        rf = Path(racine) / "raw" / ".retraits.jsonl"
        if rf.exists():
            for l in rf.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(l); a, b = r["lignes"]
                    retirees.update((r["fichier"], x) for x in range(int(a), int(b) + 1))
                except Exception:
                    continue
        self.retirees = len(retirees)
        lim = int(self.o["taille_max_car"])
        for f in sorted((Path(racine) / "raw").glob("*.md")):
            lignes = f.read_text(encoding="utf-8").splitlines()
            date = next((l.split(":", 1)[1].strip() for l in lignes[:12] if l.startswith("date:")), "")
            rep, dedans = [], False
            for n, l in enumerate(lignes, start=1):
                if l.startswith("## Échanges"):                # en-tête écrit par ingestion.py, quelle que soit la langue
                    dedans = True; continue
                if not dedans or not l.strip() or l.lstrip().startswith("<!--"):
                    continue
                m = TOUR.match(l)
                if m:
                    rep.append([n, m.group(2), m.group(3), m.group(1), (f.name, n) in retirees])
                elif rep:
                    rep[-1][2] += " " + l.strip()
            rep = [x for x in rep if not x[4]]
            groupes, k = [], 0                            # deux répliques si elles tiennent ensemble en `lim` caractères
            while k < len(rep):
                n_ = 2 if k + 1 < len(rep) and len(rep[k][2]) + len(rep[k + 1][2]) <= lim else 1
                groupes.append(rep[k:k + n_]); k += n_
            for kk, b in enumerate(groupes):
                texte = "\n".join(f"{x[1]}: {x[2]}" for x in b)
                self.tours.append({"texte": texte, "date": date, "quand": f"{date}T{b[0][3]}", "src": [f.name, b[0][0]],
                                   "lignes": [x[0] for x in b], "locuteurs": {_plier(x[1]).strip() for x in b},
                                   "fichier": f.name, "k": kk,
                                   "rac": [R._rac(w) for w in re.findall(r"\w+", _plier(texte)) if len(w) >= 3]})
        self.par_fichier = defaultdict(dict)
        for i, t in enumerate(self.tours):
            self.par_fichier[t["fichier"]][t["k"]] = i
        n = len(self.tours)
        df = defaultdict(int)
        for t in self.tours:
            for w in set(t["rac"]):
                df[w] += 1
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.long = [len(t["rac"]) for t in self.tours]; self.moy = sum(self.long) / max(1, n)
        self.inv = defaultdict(list)
        for i, t in enumerate(self.tours):
            c = defaultdict(int)
            for w in t["rac"]:
                c[w] += 1
            for w, v in c.items():
                self.inv[w].append((i, v))
        self.locuteurs = {l for t in self.tours for l in t["locuteurs"]} - {_plier(x).strip() for x in self.o.get("implicites", ()) if x}
        self.corr = Correcteur.depuis((t["texte"] for t in self.tours), int(self.o.get("corr_min", 5))) \
            if self.o.get("correcteur", True) else None

    def rappeler(self, question: str, avant: datetime, instant: datetime, masque, k: int, ch: _Chrono, actif) -> List[Dict]:
        """Les tours dits AVANT `avant` (chez l'agent : avant les 3 dernières heures)."""
        if self.corr is not None:
            with ch.etape("correcteur"):
                question, faites = self.corr.corriger(question)
            actif["corrections"] += len(faites)
        lim = avant.isoformat(timespec="minutes")
        with ch.etape("traits"):
            q = [R._rac(w) for w in re.findall(r"\w+", _plier(question)) if len(w) >= 3]
            q = [w for w in dict.fromkeys(q) if w in self.idf]
            nommes = {l for l in self.locuteurs if re.search(rf"\b{re.escape(l)}\b", _plier(question))}
            fen = fenetre_de_temps(question, instant, masque)
        with ch.etape("allumage"):
            s = defaultdict(float)
            for w in q:
                for i, c in self.inv[w]:
                    s[i] += self.idf[w] * c * 2.2 / (c + 1.2 * (0.25 + 0.75 * self.long[i] / self.moy))
            s = {i: v for i, v in s.items() if self.tours[i]["quand"] <= lim}
            cand = dict(sorted(s.items(), key=lambda x: (-x[1], x[0]))[:self.o["bm25_max"]])
        with ch.etape("note"):
            tot = sum(self.idf[w] for w in q) or 1.0
            L = {}
            for i, b in cand.items():
                t = self.tours[i]; rs = set(t["rac"])
                x = {"biais": 1.0, "bm25": math.log1p(b), "couverture": sum(self.idf[w] for w in q if w in rs) / tot,
                     "locuteur": float(bool(nommes & t["locuteurs"])), "temps_dans": 0.0, "temps_hors": 0.0}
                if fen and t["date"]:
                    try:
                        d = datetime.fromisoformat(t["date"][:10])
                        x["temps_dans" if fen[0] <= d < fen[1] else "temps_hors"] = 1.0
                    except ValueError:
                        pass
                L[i] = sum(self.poids.get(c, 0.0) * v for c, v in x.items())
        with ch.etape("voisins"):                          # les tours voisins des meilleurs suivent (le fil de la conversation)
            ordre = sorted(L, key=lambda i: (-L[i], i))
            for i in ordre[:self.o["voisins_parents"]]:
                t = self.tours[i]
                for dk in (-1, 1):
                    j = self.par_fichier[t["fichier"]].get(t["k"] + dk)
                    if j is not None and self.tours[j]["quand"] <= lim and (j not in L or L[j] < L[i] + self.o["voisins_ecart"]):
                        L[j] = L[i] + self.o["voisins_ecart"]
            ordre = sorted(L, key=lambda i: (-L[i], i))[:k]
        actif["tours_allumes"] += len(L)
        return [{"type": "tour", "cle": f"t:{self.tours[i]['src'][0]}:{self.tours[i]['src'][1]}", "texte": self.tours[i]["texte"],
                 "note": L[i], "date": _date(masque, self.tours[i]["date"]), "src": self.tours[i]["src"],
                 "lignes": self.tours[i]["lignes"]} for i in ordre]


# ── le rappel automatique ────────────────────────────────────────────────────────────────────────────
class DeuxMemoires:
    """Le rappel « deux mémoires » d'UNE mémoire : garde l'état de la conversation (ce qui a déjà été donné, le
    message précédent) et reconstruit l'index du brut, en arrière-plan, au plus toutes les `brut_minutes` (il ne lit que ce qui a plus de
    `recul_heures` : un index un peu ancien ne perd rien)."""

    def __init__(self, rappeleur, racine: Path, implicites=(), agent: str = "", options: Optional[Dict] = None):
        self.r, self.racine = rappeleur, Path(racine)
        self.implicites = tuple(x for x in implicites if x)
        self.agent = _plier(agent).strip()
        self.o = {"seuil": 0.05, "max": 10, "garde_fou": 1200, "recul_heures": 3, "brut_minutes": 30, "regle": True,
                  "correcteur": True, "corr_min": 5, **(options or {})}
        self.toile: Optional[Toile] = None
        self.brute: Optional[ToileBrute] = None
        self.brute_t: Optional[datetime] = None
        self._en_cours = False
        self.donnes: List[tuple] = []                     # (instant, clés données)
        self.prec: Optional[tuple] = None                 # (instant, message)

    def _toiles(self, ici: datetime, ch: _Chrono):
        m = self.r.memoire()
        if self.toile is None or self.toile.m is not m:
            with ch.etape("construction_souvenirs"):
                self.toile = Toile(self.r, POIDS["souvenirs"], {"correcteur": self.o["correcteur"], "corr_min": self.o["corr_min"]})
        opts = {"implicites": self.implicites, "correcteur": self.o["correcteur"], "corr_min": self.o["corr_min"]}
        if self.brute is None:                            # la première fois : construit tout de suite (≈ 1 s pour 2 000 tours)
            with ch.etape("construction_brut"):
                self.brute = ToileBrute(self.racine, POIDS["brut"], opts)
            self.brute_t = ici
        elif ici - self.brute_t > timedelta(minutes=float(self.o["brut_minutes"])) and not self._en_cours:
            self._en_cours, self.brute_t = True, ici      # ensuite EN ARRIÈRE-PLAN : le message n'attend pas, l'ancien index sert

            def _reconstruire():
                try:
                    self.brute = ToileBrute(self.racine, POIDS["brut"], opts)
                finally:
                    self._en_cours = False
            threading.Thread(target=_reconstruire, name="exia-seed-brut", daemon=True).start()
        return m

    def _ligne(self, it: Dict, masque) -> str:
        if it["type"] == "fait":
            return f"  – [{it['date']}] {it['texte']}" if it["date"] else f"  – {it['texte']}"
        toi = masque.textes["deux_memoires_toi"]
        parts = []
        for l in it["texte"].split("\n"):
            qui, _, dit = l.partition(": ")
            parts.append(f"{qui} ({toi}): {dit}" if self.agent and _plier(qui).strip() == self.agent else l)
        tete = masque.textes["deux_memoires_conversation"].format(date=it["date"]) if it["date"] else ""
        return f"  – ({tete}) " + " / ".join(parts) if tete else "  – " + " / ".join(parts)

    def rappeler(self, texte: str, ici: datetime) -> Dict:
        t0 = time.perf_counter()
        ch, actif = _Chrono(), defaultdict(int)
        m = self._toiles(ici, ch)
        if m is None:
            return {"bloc": "", "items": [], "candidats": 0, "tokens": 0, "latence_ms": 0.0}
        masque = m.masque
        recul = timedelta(hours=float(self.o["recul_heures"]))
        self.donnes = [(t, ks) for t, ks in self.donnes if ici - t <= recul]
        deja = {k for _, ks in self.donnes for k in ks}
        prec = self.prec[1] if self.prec and ici - self.prec[0] <= timedelta(minutes=30) else ""
        with ch.etape("message"):
            a = self.r.activer(m, texte)
            q = texte if len([w for w in a["pleins"] if len(w) >= 3]) >= 4 or not prec else f"{prec} {texte}"
        self.prec = (ici, texte)
        cands = self.toile.rappeler(q, ici, 30, ch, actif) + self.brute.rappeler(q, ici - recul, ici, masque, 30, ch, actif)
        cands.sort(key=lambda it: (-it["note"], it["cle"]))
        pris, lignes = [], []
        entete = [masque.textes["souvenirs_entete"]] + ([masque.textes["deux_memoires_regle"]] if self.o["regle"] else [])
        for it in cands:
            if 1 / (1 + math.exp(-it["note"])) < float(self.o["seuil"]) or it["cle"] in deja or len(pris) >= int(self.o["max"]):
                continue
            l = self._ligne(it, masque)
            if estimer_tokens("\n".join(entete + lignes + [l])) > int(self.o["garde_fou"]):
                break
            pris.append(it); lignes.append(l)
        self.donnes.append((ici, [it["cle"] for it in pris]))
        bloc = "\n".join(entete + lignes) if pris else ""
        return {"bloc": bloc, "items": pris, "candidats": len(cands), "tokens": estimer_tokens(bloc) if bloc else 0,
                "latence_ms": round((time.perf_counter() - t0) * 1000, 2),
                "etapes_ms": {k: round(v, 2) for k, v in ch.ms.items()}, "actif": dict(actif)}
