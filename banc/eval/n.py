"""N — « deux mémoires, une toile » : PROTOTYPE DE BANC de la nouvelle approche (PLAN-FCM-EXIA-SEED.md §2 et §4).

Rien de ceci n'est dans EXIA SEED. Lit le wiki avec les mêmes briques que la montre 1.0.0 (rappel.Memoire : souvenirs,
racines, concepts, citations ; Rappeleur.activer : mots pleins et leur rareté, alias, concepts allumés ; index plein
texte), puis applique SES rouages, activables un par un (échelons de la phase 1) :

  ① TRAITS      la question allume des traits : mots (rareté), page nommée ou un mot de son nom, concepts (rareté par le
                « fan » : un concept relié à beaucoup de souvenirs pèse peu), fenêtre de temps (« last week », « in May
                2023 »…), et (N2) les cartes et termes ÉCRITS par la consolidation.
  ② CLÉS        chaque souvenir allumé reçoit la SOMME de ses indices en log-cotes (régression logistique : chaque
                indice ajoute la force de sa preuve, rien ne sature ; la probabilité n'apparaît qu'à la fin) ; poids
                appris sur les jeux de RÉGLAGE seulement (`regler_n.py`), avec les répliques-preuves comme vérité.
  N3 CONCURRENCE  un souvenir presque identique à un souvenir mieux placé (même page) est freiné ; l'ancienne version
                d'un fait cède devant la plus récente.
  N4 RECONSTRUCTION les souvenirs gagnants rallument leurs « frères » du même épisode (cités à ≤ 3 lignes de brut).
  N5 PASSAGES   les premiers souvenirs ouvrent leur passage de brut (la réplique citée et sa voisine), placé juste après.

Capteurs : temps mur et CPU par étape (traits, allumage, note, concurrence, reconstruction, passages) ; compteurs
d'ACTIVITÉ de chaque rouage (un rouage à 0 sur tout un passage = alerte « jamais exécuté »).
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

TRAITS = ("biais", "bm25", "couverture", "nom", "un_mot", "concept", "theme_absent", "regle", "temps_dans",
          "temps_hors", "sens", "sens_couverture")
MOIS = {m: k + 1 for k, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                         "september", "october", "november", "december"])}
MOIS.update({m: k + 1 for k, m in enumerate(["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout",
                                              "septembre", "octobre", "novembre", "decembre"])})
TOUR = re.compile(r"^\[(\d\d:\d\d) ([^\]]+)\] (.*)$")


_NORM = None


def _plier(texte: str) -> str:
    """Minuscules SANS ACCENTS (é → e, ç → c, œ → oe), ponctuation → espaces : la règle de toute la mémoire
    (`graphe._norm`, déjà suivie par les souvenirs). Défaut trouvé le 23/11 : le côté brut ne pliait que la casse —
    « detecte » (Francis écrit souvent sans accents) ne retrouvait pas « détecte » (Nexa, les souvenirs)."""
    global _NORM
    if _NORM is None:
        from exia_seed import graphe as _g
        _NORM = _g._norm
    return _NORM(texte)


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
    """Le correcteur tiré de la MÉMOIRE elle-même (23/11, test « question abîmée ») : un mot de la question dont la RACINE
    est inconnue de la mémoire (il ne compterait pour rien) est remplacé par le mot de la mémoire le plus proche à une
    faute de frappe près (lettre oubliée, en trop, voisine, deux lettres inversées : distance 1 ; 2 pour les mots longs) ;
    à égalité, le plus fréquent dans la mémoire, puis l'ordre alphabétique (déterministe). Index par suppressions
    (SymSpell). Un mot connu n'est jamais touché ; une question sans mot inconnu passe telle quelle. Aucun modèle."""

    def __init__(self, df: Dict[str, int], rac, mini: int = 4, long_d2: int = 9):
        self.df, self.rac, self.mini, self.long_d2 = df, rac, mini, long_d2
        self.connues = {rac(w) for w in df}
        self.index = defaultdict(list)
        for w in sorted(df):
            if len(w) >= mini - 1 and not w.isdigit():
                for d in {w} | {w[:k] + w[k + 1:] for k in range(len(w))}:
                    self.index[d].append(w)

    def corriger(self, question: str):
        mots = _plier(question).split()
        sortie, faites = [], []
        for w in mots:
            if len(w) < self.mini or not w.isalpha() or self.rac(w) in self.connues:
                sortie.append(w); continue
            borne = 2 if len(w) >= self.long_d2 else 1
            cands = set()
            for d in {w} | {w[:k] + w[k + 1:] for k in range(len(w))}:
                cands.update(self.index.get(d, ()))
            bons = sorted(((_osa(w, c, borne), -self.df[c], c) for c in cands), key=lambda x: x[:3])
            bons = [x for x in bons if x[0] <= borne]
            if bons:
                sortie.append(bons[0][2]); faites.append((w, bons[0][2]))
            else:
                sortie.append(w)
        return (" ".join(sortie) if faites else question), faites


def _correcteur(textes, rac, o):
    if not o.get("correcteur"):
        return None
    df = defaultdict(int)
    for t in textes:
        for w in set(_plier(t).split()):
            df[w] += 1
    return Correcteur(dict(df), rac, mini=int(o.get("corr_min", 4)), long_d2=int(o.get("corr_long", 9)))


_TEMPS_MOTIFS = (r"\b(19|20)\d\d\b", r"\byesterday\b|\bhier\b", r"\blast week\b|semaine derniere", r"\blast month\b|mois dernier",
                 r"\blast year\b|annee derniere|an dernier", r"\bthis week\b|cette semaine", r"\bthis month\b|\bce mois\b",
                 r"\b(\d+|a|one|two|three|four|five|six)\s+(day|week|month|year)s?\s+ago\b", r"\bil y a (\d+) (jour|semaine|mois|an)s?\b")


def sans_mots_du_temps(texte: str) -> str:
    """La question SANS les expressions que `fenetre_de_temps` sait lire (« two weeks ago », « en février », « hier ») :
    elles règlent la fenêtre de dates (traits temps_dans / temps_hors) et ne doivent plus aussi chercher des mots dans le
    texte — le diagnostic du 23/11 : « two », « weeks », « ago » faisaient gagner des souvenirs étrangers (50 / 88)."""
    t = _plier(texte)
    for nom in MOIS:
        if not (nom == "may" and re.search(r"\bmay (i|we|you|he|she|they)\b", t)):
            t = re.sub(rf"\b{nom}\b", " ", t)
    for motif in _TEMPS_MOTIFS:
        t = re.sub(motif, " ", t)
    return t


def fenetre_de_temps(texte: str, instant: datetime):
    """Fenêtre [début, fin) désignée par la question, ou None. Symbolique, anglais et français."""
    t = _plier(texte)
    an = re.search(r"\b(19|20)\d\d\b", t)
    for nom, k in MOIS.items():
        if re.search(rf"\b{nom}\b", t) and not (nom == "may" and re.search(r"\bmay (i|we|you|he|she|they)\b", t)):
            y = int(an.group(0)) if an else instant.year - (1 if k > instant.month else 0)
            d = datetime(y, k, 1)
            return d, datetime(y + (k == 12), k % 12 + 1, 1)
    if an:
        return datetime(int(an.group(0)), 1, 1), datetime(int(an.group(0)) + 1, 1, 1)
    j = instant.replace(hour=0, minute=0, second=0, microsecond=0)
    regles = [(r"\byesterday\b|\bhier\b", 1, 1), (r"\blast week\b|semaine derniere", 7, 7),
              (r"\blast month\b|mois dernier", 31, 31), (r"\blast year\b|annee derniere|an dernier", 366, 366),
              (r"\bthis week\b|cette semaine", 0, 7), (r"\bthis month\b|ce mois", 0, 31)]
    for motif, recul, duree in regles:
        if re.search(motif, t):
            return (j - timedelta(days=recul), j - timedelta(days=recul) + timedelta(days=duree)) if recul else (j - timedelta(days=duree), j + timedelta(days=1))
    m = re.search(r"\b(\d+|a|one|two|three|four|five|six)\s+(day|week|month|year)s?\s+ago\b|il y a (\d+) (jour|semaine|mois|an)", t)
    if m:
        nb = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}.get(m.group(1) or "", None)
        nb = nb or int(m.group(1) or m.group(3))
        u = {"day": 1, "jour": 1, "week": 7, "semaine": 7, "month": 30, "mois": 30, "year": 365, "an": 365}[m.group(2) or m.group(4)]
        c = j - timedelta(days=nb * u)
        return c - timedelta(days=max(1, u // 2)), c + timedelta(days=max(1, u // 2) + 1)
    return None


class Toile:
    """La toile de N pour UNE mémoire. `etages` ⊂ {"N2", "N3", "N4", "N5"} (N1 toujours)."""

    def __init__(self, rappeleur, poids: Dict[str, float], etages=(), cartes_ecrites: Optional[Dict] = None,
                 options: Optional[Dict] = None):
        from exia_seed import rappel as R
        self.R, self.r = R, rappeleur
        self.m = rappeleur.memoire()
        self.poids, self.etages = poids, set(etages)
        self.o = {"bm25_max": 100, "concepts_max": 60, "sens_max": 60, "freres_parents": 5, "freres_lignes": 3,
                  "freres_ecart": -1.0, "passages": 3, "inhib": 2.0, "sim_seuil": 0.6, **(options or {})}
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
        # épisodes : (fichier de brut) → [(ligne, i)] — pour les frères (N4) ; brut pour les passages (N5)
        self.par_fichier = defaultdict(list)
        for i, f in enumerate(m.faits):
            for fi, ln in f.get("refs") or ():
                self.par_fichier[fi].append((int(ln), i))
        self.brut_cache = {}
        self.corr = _correcteur((f["texte"] for f in m.faits), R._rac, self.o)
        self.seances_du_fait = [{fi for fi, _ in (f.get("refs") or ())} for f in m.faits]
        self.fichiers_de = defaultdict(set)                # racine → séances citées par les souvenirs qui la portent
        for i, f in enumerate(m.faits):
            for w in f["racines"]:
                self.fichiers_de[w] |= self.seances_du_fait[i]
        # cartes écrites par la consolidation (N2) : traits « sens » = racines des thèmes imbriqués et des termes
        self.sens, self.inv_sens, self.idf_sens = {}, defaultdict(set), {}
        if "N2" in self.etages and cartes_ecrites:
            from exia_seed import cartes as _cartes, graphe as _graphe
            vides = R._mots_vides(m.masque)
            for i, f in enumerate(m.faits):
                e = cartes_ecrites.get(f["texte"])
                if not e:
                    continue
                mots = " ".join(e.get("themes", []) + e.get("termes", []))
                rac = {R._rac(w) for w in re.findall(r"\w+", _graphe._norm(mots)) if len(w) >= 3 and w not in vides}
                self.sens[i] = rac
                for w in rac:
                    self.inv_sens[w].add(i)
            self.idf_sens = {w: math.log((self.N + 1) / (len(s) + 0.5)) for w, s in self.inv_sens.items()}

    # ── ① + ② ──────────────────────────────────────────────────────────────────────────────────────
    def _traits_et_candidats(self, question: str, instant_filtre: datetime, instant_reel: datetime, ch, actif):
        m, R = self.m, self.R
        with ch.etape("traits"):
            fen = fenetre_de_temps(question, instant_reel)
            a = self.r.activer(m, sans_mots_du_temps(question) if (fen is not None and self.o.get("temps_mots")) else question)
            nommes = {y.split("→", 1)[1] for y in a["etages"].get("alias", ())}
            un_mot = {y.split("→", 1)[1] for y in a["etages"].get("mot_alias", ())} - nommes
            concepts = {k[8:]: v for k, v in a["entrees"].items() if k.startswith("concept:")}
            q_rac = {R._rac(w) for w in a["pleins"] if len(w) >= 3}
            poids_q = {R._rac(w): a["poids"].get(w, 0.0) for w in a["pleins"] if len(w) >= 3}
            total_q = sum(poids_q.values()) or 1.0
        actif["traits_mots"] += len(q_rac); actif["traits_pages"] += len(nommes) + len(un_mot)
        actif["traits_concepts"] += len(concepts); actif["traits_temps"] += int(fen is not None)
        with ch.etape("allumage"):
            cand, bm = set(), {}
            mots = [w for w in a["pleins"] if len(w) >= 3]
            if mots:
                try:
                    for i, s in m.fts.execute("select rowid, bm25(f, 1.0, ?) from f where f match ? order by 2 limit ?",
                                              (R.POIDS_CHAMP_BM25, " OR ".join(f'"{w}"' for w in mots), self.o["bm25_max"])):
                        bm[i] = -s; cand.add(i)
                except Exception:
                    pass
            lam = float(self.o.get("prf_lambda", 0.0))
            if lam > 0 and bm:                           # RÉTROACTION : les mots rares des meilleurs souvenirs → 2e passe
                if not hasattr(self, "_df"):
                    self._df = defaultdict(int)
                    for f in m.faits:
                        for w in set(re.findall(r"\w{4,}", _plier(f["texte"]))):
                            self._df[w] += 1
                hauts = sorted(bm, key=lambda i: -bm[i])[:int(self.o.get("prf_m", 3))]
                qm = {_plier(w).strip() for w in a["pleins"]}
                tf = defaultdict(float)
                for i in hauts:
                    for w in set(re.findall(r"\w{4,}", _plier(m.faits[i]["texte"]))):
                        if w not in qm and self._df[w] < 0.05 * self.N:
                            tf[w] += math.log((self.N + 1) / (self._df[w] + 0.5))
                exp = [w for w, _ in sorted(tf.items(), key=lambda x: -x[1])[:int(self.o.get("prf_e", 5))]]
                if exp:
                    try:
                        for i, s2 in m.fts.execute("select rowid, bm25(f, 1.0, ?) from f where f match ? order by 2 limit ?",
                                                   (R.POIDS_CHAMP_BM25, " OR ".join(f'"{w}"' for w in exp), self.o["bm25_max"])):
                            bm[i] = bm.get(i, 0.0) + lam * -s2; cand.add(i)
                    except Exception:
                        pass
                    actif["retroaction_mots"] += len(exp)
            for n in nommes | un_mot:
                cand.update(m.par_noeud.get(n, ()))
            if concepts:
                par_c = sorted(((v * self.idf_concept.get(c, 0.0), c) for c, v in concepts.items()), reverse=True)
                pris = []
                for _, c in par_c:
                    pris += self.par_concept.get(c, [])
                    if len(pris) >= self.o["concepts_max"]:
                        break
                cand.update(pris[:self.o["concepts_max"]])
            sens_q = {}
            if self.sens:
                sens_q = {w: self.idf_sens[w] for w in q_rac if w in self.idf_sens}
                score = defaultdict(float)
                for w, v in sens_q.items():
                    for i in self.inv_sens[w]:
                        score[i] += v
                cand.update(i for i, _ in sorted(score.items(), key=lambda x: -x[1])[:self.o["sens_max"]])
                actif["traits_sens"] += len(sens_q)
            cov, ws = {}, float(self.o.get("seance", 0.0))
            if ws > 0 and poids_q:                          # LA SÉANCE D'ABORD (souvenirs groupés par la séance qu'ils citent)
                cov = defaultdict(float)
                for w, p in poids_q.items():
                    for fi in self.fichiers_de.get(w, ()):
                        cov[fi] += p / total_q
                if int(self.o.get("seance_recrue", 0)):
                    hautes = sorted(cov.items(), key=lambda x: (-x[1], x[0]))[:int(self.o["seance_recrue"])]
                    for fi, _ in hautes:
                        for _ln, i in self.par_fichier.get(fi, ()):
                            if i not in cand and q_rac & set(m.faits[i]["racines"]):
                                cand.add(i); actif["seance_recrues"] += 1
            filtre = instant_filtre.isoformat(timespec="minutes")
            cand = {i for i in cand if not (m.faits[i]["dit_le"] and m.faits[i]["dit_le"][:16] > filtre)}
        actif["allumes"] += len(cand)
        with ch.etape("note"):
            X = {}
            for i in cand:
                f = m.faits[i]
                cs = f.get("concepts", ())
                x = {"biais": 1.0, "bm25": math.log1p(bm.get(i, 0.0)),
                     "couverture": a["couverture"](f["racines"]),
                     "nom": float(f["noeud"] in nommes), "un_mot": float(f["noeud"] in un_mot),
                     "concept": max((concepts.get(c, 0.0) * self.idf_concept.get(c, 0.0) / self.idf_concept_max for c in cs), default=0.0),
                     "theme_absent": float(bool(concepts) and bool(cs) and not any(c in concepts for c in cs)),
                     "regle": float(f.get("section") == "procedural"), "temps_dans": 0.0, "temps_hors": 0.0,
                     "sens": 0.0, "sens_couverture": 0.0}
                if fen and f["dit_le"]:
                    try:
                        d = datetime.fromisoformat(f["dit_le"][:10])
                        x["temps_dans" if fen[0] <= d < fen[1] else "temps_hors"] = 1.0
                    except ValueError:
                        pass
                if sens_q and i in self.sens:
                    pr = sum(v for w, v in sens_q.items() if w in self.sens[i])
                    x["sens"] = pr / (sum(sens_q.values()) or 1.0)
                    x["sens_couverture"] = sum(poids_q.get(w, 0.0) for w in q_rac if w in self.sens[i] or w in f["racines"]) / total_q
                X[i] = x
            L = {i: sum(self.poids.get(k, 0.0) * v for k, v in x.items()) for i, x in X.items()}
            if cov:
                for i in L:
                    X[i]["seance"] = max((cov.get(fi, 0.0) for fi in self.seances_du_fait[i]), default=0.0)
                    L[i] += ws * X[i]["seance"]
        return X, L

    # ── N3 ────────────────────────────────────────────────────────────────────────────────────────
    def _concurrence(self, ordre, L, actif):
        m, garde, sortie = self.m, [], []
        for i in ordre:
            ri = m.faits[i]["racines"]
            pire = 0.0
            for j in garde[:30]:
                if m.faits[j]["noeud"] != m.faits[i]["noeud"]:
                    continue
                rj = m.faits[j]["racines"]
                sim = len(ri & rj) / max(1, len(ri | rj))
                if sim >= self.o["sim_seuil"]:
                    plus_recent = (m.faits[i]["dit_le"] or "") > (m.faits[j]["dit_le"] or "")
                    pire = max(pire, sim * (0.5 if plus_recent else 1.0))
            if pire:
                L[i] -= self.o["inhib"] * pire; actif["freines"] += 1
            garde.append(i)
        return sorted(ordre, key=lambda i: -L[i])

    # ── N4 ────────────────────────────────────────────────────────────────────────────────────────
    def _freres(self, ordre, L, actif):
        m = self.m
        ajouts = {}
        for i in ordre[:self.o["freres_parents"]]:
            for fi, ln in m.faits[i].get("refs") or ():
                for ln2, j in self.par_fichier.get(fi, ()):
                    if j != i and abs(ln2 - int(ln)) <= self.o["freres_lignes"]:
                        v = L[i] + self.o["freres_ecart"]
                        if j not in L or v > L[j]:
                            if v > ajouts.get(j, -1e9):
                                ajouts[j] = v
        for j, v in ajouts.items():
            if j not in L:
                actif["freres_ajoutes"] += 1
            else:
                actif["freres_releves"] += 1
            L[j] = max(L.get(j, -1e9), v)
        return sorted(L, key=lambda i: -L[i])

    # ── N5 ────────────────────────────────────────────────────────────────────────────────────────
    def _passage(self, i):
        f = self.m.faits[i]
        refs = sorted(f.get("refs") or (), key=lambda r: (r[0], int(r[1])))
        if not refs:
            return None
        fi, ln = refs[0][0], int(refs[0][1])
        if fi not in self.brut_cache:
            p = self.r.racine / "raw" / fi
            self.brut_cache[fi] = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
        lignes = self.brut_cache[fi]
        tours = [(n, l) for n, l in enumerate(lignes, start=1) if TOUR.match(l)]
        k = max((x for x, (n, _) in enumerate(tours) if n <= ln), default=None)
        if k is None:
            return None
        pris = tours[max(0, k - 1):k + 1] if k > 0 else tours[k:k + 2]
        texte = "\n".join(f"{TOUR.match(l).group(2)}: {TOUR.match(l).group(3)}" for _, l in pris)
        return {"type": "passage", "texte": "(conversation) " + texte, "date": "", "refs": [[fi, n] for n, _ in pris],
                "src": [fi, pris[0][0]]}

    def rappeler(self, question: str, instant_filtre: datetime, instant_reel: datetime, k: int, ch) -> Dict:
        actif = defaultdict(int)
        if self.corr is not None:
            with ch.etape("correcteur"):
                question, faites = self.corr.corriger(question)
            actif["corrections"] += len(faites)
        X, L = self._traits_et_candidats(question, instant_filtre, instant_reel, ch, actif)
        ordre = sorted(L, key=lambda i: -L[i])
        if "N3" in self.etages:
            with ch.etape("concurrence"):
                ordre = self._concurrence(ordre, L, actif)
        if "N4" in self.etages:
            with ch.etape("reconstruction"):
                ordre = self._freres(ordre, L, actif)
        ordre = ordre[:k]
        m = self.m
        items = []
        with ch.etape("passages"):
            vus = set()
            for r, i in enumerate(ordre):
                f = m.faits[i]
                d = f["dit_le"] or ""
                try:
                    dl = datetime.strptime(d[:10], "%Y-%m-%d").strftime("%-d %B %Y") if d else ""
                except ValueError:
                    dl = ""
                items.append({"type": "fait", "texte": f["texte"], "date": dl, "page": f["noeud"],
                              "refs": sorted([list(x) for x in (f.get("refs") or ())], key=str), "note": round(L[i], 3)})
                if "N5" in self.etages and r < self.o["passages"]:
                    p = self._passage(i)
                    if p and tuple(map(tuple, p["refs"])) not in vus:
                        vus.add(tuple(map(tuple, p["refs"]))); items.append(p); actif["passages"] += 1
        notes = [L[i] for i in ordre]          # log-cotes : c'est leur dispersion que lit le capteur de saturation
        return {"items": items, "notes": notes, "X": {i: X.get(i) for i in ordre}, "actif": dict(actif),
                "entonnoir": {"allumes": len(L), "donnes": len(ordre)}}


# ══ Nb — la même toile directement sur le BRUT : aucune consolidation, aucun modèle (« la consolidation est-elle
#    nécessaire ? », Francis 21/11). Unité = le tour (deux répliques), comme le RAG brut ; traits : mots (rareté BM25,
#    couverture), interlocuteur nommé, fenêtre de temps ; reconstruction : les tours voisins des meilleurs.
TRAITS_B = ("biais", "bm25", "couverture", "locuteur", "temps_dans", "temps_hors")


class ToileBrute:
    def __init__(self, racine: Path, poids: Dict[str, float], options: Optional[Dict] = None):
        from exia_seed import rappel as R
        self.R, self.poids = R, poids
        self.o = {"bm25_max": 100, "voisins_parents": 5, "voisins_ecart": -0.5, "taille": 2, **(options or {})}
        pas = int(self.o["taille"])                         # 2 = tour (deux répliques) ; 1 = la réplique seule
        self.tours = []                                    # {texte, date, quand, src, lignes, locuteurs, rac, fichier, k}
        retirees = set()                                   # « oublie ce que je viens de dire » : jamais rendu par le brut
        rf = Path(racine) / "raw" / ".retraits.jsonl"
        if rf.exists():
            import json as _json
            for l in rf.read_text(encoding="utf-8").splitlines():
                try:
                    r = _json.loads(l); a, b = r["lignes"]
                    retirees.update((r["fichier"], x) for x in range(int(a), int(b) + 1))
                except Exception:
                    continue
        self.retirees = len(retirees)
        for f in sorted((Path(racine) / "raw").glob("*.md")):
            lignes = f.read_text(encoding="utf-8").splitlines()
            date = next((l.split(":", 1)[1].strip() for l in lignes[:12] if l.startswith("date:")), "")
            rep, dedans = [], False
            for n, l in enumerate(lignes, start=1):
                if l.startswith("## Échanges"):
                    dedans = True; continue
                if not dedans or not l.strip() or l.lstrip().startswith("<!--"):
                    continue
                m = TOUR.match(l)
                if m:
                    rep.append([n, m.group(2), m.group(3), m.group(1), (f.name, n) in retirees])
                elif rep:
                    rep[-1][2] += " " + l.strip()
            rep = [x for x in rep if not x[4]]
            groupes, k = [], 0                             # « taille » 0 = ADAPTATIF : deux répliques si elles sont courtes
            while k < len(rep):
                if pas == 0:
                    lim = int(self.o.get("taille_max_car", 600))
                    n_ = 2 if k + 1 < len(rep) and len(rep[k][2]) + len(rep[k + 1][2]) <= lim else 1
                else:
                    n_ = pas
                groupes.append((k, rep[k:k + n_])); k += n_
            for kk, (k, b) in enumerate(groupes):
                texte = "\n".join(f"{x[1]}: {x[2]}" for x in b)
                self.tours.append({"texte": texte, "date": date, "quand": f"{date}T{b[0][3]}", "src": [f.name, b[0][0]], "lignes": [x[0] for x in b],
                                   "locuteurs": {_plier(x[1]).strip() for x in b}, "fichier": f.name, "k": kk,
                                   "rac": [R._rac(w) for w in re.findall(r"\w+", _plier(texte)) if len(w) >= 3]})
        self.par_fichier = defaultdict(dict)
        self.par_ligne = {}                                # (fichier, ligne d'une réplique) → tour : pour la DÉSIGNATION
        for i, t in enumerate(self.tours):
            self.par_fichier[t["fichier"]][t["k"]] = i
            for ln in t["lignes"]:
                self.par_ligne[(t["fichier"], ln)] = i
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
        self.locuteurs = {l for t in self.tours for l in t["locuteurs"]} - {_plier(x).strip() for x in self.o.get("implicites", ())}
        self.corr = _correcteur((t["texte"] for t in self.tours), R._rac, self.o)
        self.fichiers_de = defaultdict(set)                # racine → séances (fichiers du brut) qui la contiennent
        for t in self.tours:
            for w in set(t["rac"]):
                self.fichiers_de[w].add(t["fichier"])

    def _traits(self, question, instant_reel, ch, actif, limite: Optional[datetime] = None):
        with ch.etape("traits"):
            fen = fenetre_de_temps(question, instant_reel)
            qt = sans_mots_du_temps(question) if (fen is not None and self.o.get("temps_mots")) else _plier(question)
            q = [self.R._rac(w) for w in re.findall(r"\w+", qt) if len(w) >= 3]
            q = [w for w in dict.fromkeys(q) if w in self.idf]
            nommes = {l for l in self.locuteurs if re.search(rf"\b{re.escape(l)}\b", _plier(question))}
        actif["traits_mots"] += len(q); actif["traits_locuteurs"] += len(nommes); actif["traits_temps"] += int(fen is not None)
        with ch.etape("allumage"):
            def bm(mots, poids=1.0, s=None):
                s = s if s is not None else defaultdict(float)
                for w in mots:
                    for i, c in self.inv[w]:
                        s[i] += poids * self.idf[w] * c * 2.2 / (c + 1.2 * (0.25 + 0.75 * self.long[i] / self.moy))
                return s
            s = bm(q)
            lam = float(self.o.get("prf_lambda", 0.0))
            if lam > 0 and s:                            # RÉTROACTION : complétion par les meilleurs tours (sans modèle)
                hauts = sorted(s, key=lambda i: -s[i])[:int(self.o.get("prf_m", 3))]
                tf = defaultdict(float)
                for i in hauts:
                    for w in self.tours[i]["rac"]:
                        if w not in q:
                            tf[w] += self.idf.get(w, 0.0)
                exp = [w for w, _ in sorted(tf.items(), key=lambda x: -x[1])[:int(self.o.get("prf_e", 5))]]
                s = bm(exp, lam, s); actif["retroaction_mots"] += len(exp)
            if self.o.get("strict") and nommes:            # parade « abstention » : la question nomme quelqu'un → seulement SES répliques
                s = {i: v for i, v in s.items() if nommes & self.tours[i]["locuteurs"]}
                actif["strict_filtres"] += 1
            if limite is not None:                         # seulement le brut d'AVANT (chez Nexa : avant les 3 dernières heures)
                lim = limite.isoformat(timespec="minutes")
                s = {i: v for i, v in s.items() if self.tours[i]["quand"] <= lim}
            cov, ws = {}, float(self.o.get("seance", 0.0))
            if ws > 0 and q:                                # LA SÉANCE D'ABORD : part de la question couverte par la séance entière
                tot_s = sum(self.idf[w] for w in q) or 1.0
                cov = defaultdict(float)
                for w in q:
                    for fi in self.fichiers_de[w]:
                        cov[fi] += self.idf[w] / tot_s
            cand = dict(sorted(s.items(), key=lambda x: -x[1])[:self.o["bm25_max"]])
            if cov and int(self.o.get("seance_recrue", 0)):  # les tours des meilleures séances entrent même hors du top BM25
                hautes = {fi for fi, _ in sorted(cov.items(), key=lambda x: (-x[1], x[0]))[:int(self.o["seance_recrue"])]}
                for i, v in s.items():
                    if self.tours[i]["fichier"] in hautes and i not in cand:
                        cand[i] = v; actif["seance_recrues"] += 1
        actif["allumes"] += len(cand)
        with ch.etape("note"):
            tot = sum(self.idf[w] for w in q) or 1.0
            X, L = {}, {}
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
                X[i] = x; L[i] = sum(self.poids.get(k, 0.0) * v for k, v in x.items())
                if cov:
                    x["seance"] = cov.get(t["fichier"], 0.0); L[i] += ws * x["seance"]
        return X, L

    def rappeler(self, question, instant_filtre, instant_reel, k, ch, designes: Optional[Dict] = None):
        """`designes` : {(fichier, ligne) : log-cote du souvenir qui la cite} — le SOUVENIR DÉSIGNE SON BRUT :
        un tour cité gagne `design_bonus` ; un tour cité mais non trouvé par ses mots entre à (log-cote du souvenir +
        `design_ajout`) ; `design_seul` = cascade pure (aucune recherche du brut par ses propres mots)."""
        actif = defaultdict(int)
        if self.corr is not None:
            with ch.etape("correcteur"):
                question, faites = self.corr.corriger(question)
            actif["corrections"] += len(faites)
        lim_t = None if instant_filtre.year >= 2100 else instant_filtre
        if self.o.get("design_seul"):
            X, L = {}, {}
        else:
            X, L = self._traits(question, instant_reel, ch, actif, lim_t)
        lim = instant_filtre.isoformat(timespec="minutes")
        if designes:
            with ch.etape("designation"):
                vus = {}
                for (fi, ln), lf in designes.items():
                    i = self.par_ligne.get((fi, int(ln)))
                    if i is not None and self.tours[i]["quand"] <= lim:
                        vus[i] = max(vus.get(i, -1e9), lf)
                for i, lf in vus.items():
                    if i in L:
                        L[i] += self.o.get("design_bonus", 0.0); actif["tours_designes_releves"] += 1
                    else:
                        L[i] = lf + self.o.get("design_ajout", -1.0); actif["tours_designes_ajoutes"] += 1
        ordre = sorted(L, key=lambda i: -L[i])
        with ch.etape("reconstruction"):
            for i in ordre[:self.o["voisins_parents"]]:
                t = self.tours[i]
                for dk in (-1, 1):
                    j = self.par_fichier[t["fichier"]].get(t["k"] + dk)
                    if j is not None and self.tours[j]["quand"] <= lim and (j not in L or L[j] < L[i] + self.o["voisins_ecart"]):
                        actif["voisins_ajoutes" if j not in L else "voisins_releves"] += 1
                        L[j] = L[i] + self.o["voisins_ecart"]
            ordre = sorted(L, key=lambda i: -L[i])[:k]
        items = []
        for i in ordre:
            t = self.tours[i]
            try:
                dl = datetime.strptime(t["date"][:10], "%Y-%m-%d").strftime("%-d %B %Y") if t["date"] else ""
            except ValueError:
                dl = ""
            items.append({"type": "tour", "texte": t["texte"], "date": dl, "src": t["src"], "lignes": t["lignes"],
                          "note": round(L[i], 3)})
        return {"items": items, "notes": [L[i] for i in ordre], "X": {i: X.get(i) for i in ordre},
                "actif": dict(actif), "entonnoir": {"allumes": len(X), "donnes": len(ordre)}}
