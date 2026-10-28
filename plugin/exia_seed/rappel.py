"""Le rappel — étape 6a (docs/06-rappel.md). Du message aux souvenirs, sans aucun appel au modèle.

    message ─► cascade (nom/alias · mot d'alias · plein texte) ─► nœuds d'entrée
            ─► propagation FCM, lue AU-DESSUS DU REPOS ─► nœuds activés
            ─► faits candidats, score cab_pull (le graphe propose, le lexique départage)
            ─► bloc plafonné à 1 200 tokens, ou rien

Phase 1 : le bloc est CALCULÉ et JOURNALISÉ (`memoire/rappel/<date>.jsonl`), jamais injecté.

Tout ce qui est coûteux à construire (moteur, repos, dictionnaires, index plein texte) est gardé en
cache et reconstruit seulement quand le graphe change — charger le moteur coûte 0,5 à 0,9 s à 2 000
nœuds (mesuré à l'étape 5), propager quelques millisecondes.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import threading
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import graphe as _graphe
from .moteur.score_utils import cab_pull
from .util import ajouter_ligne_jsonl, estimer_tokens

PLAFOND_TOKENS = 1200           # invariant de la spec (§6.3) : le bloc est rejoué à chaque tour
SEUIL_NOEUD = 0.05              # activation au-dessus du repos pour qu'un nœud compte
SEUIL_FAIT = 0.35               # score minimal d'un fait — valeur de départ, calibrée au banc 6b
FAITS_PAR_NOEUD = 4             # diversité : un nœud bavard ne remplit pas tout le bloc
MOT_MIN = 5                     # mots d'alias partiels et orphelins : 5 lettres au moins
ACT_ALIAS, ACT_MOT, ACT_MOT_APPROX, ACT_PLEIN_TEXTE = 1.0, 0.6, 0.5, 0.5
GAMMA_COUVERTURE = 2.0          # couvrir la moitié du message ne vaut qu'un quart (premier essai, 26/09)
RACINE = 5                      # comparaison par racine, comme le contrôle de citation (doc 04 §5.2)
ACT_CHAMP = 0.8                 # B+ : activation max d'un concept, × la force du match avec son champ lexical
POIDS_CHAMP_BM25 = 0.4          # B+ : le champ lexical des concepts d'un fait pèse moins que son texte
FTS_MAX = 10
# Mot COURANT d'un alias (docs/12 §9) : il allume le sujet à moitié — ses faits doivent alors ressembler au message
# pour passer le seuil. Un mot DISTINCTIF (écrit avec la fiche : « Valmont ») allume pleinement. 1.0 = comme avant.
# Valeur fixée par le banc du 16/10 sur les deux quinzaines.
POIDS_MOT_COMMUN = 0.5
# Une RÈGLE DE CONDUITE (etat_agent) se rappelle par la SITUATION (« fais-moi une facture » → « vérifier avant envoi »),
# donc par des mots courants ; une entité, par son NOM. Banc du 16/10 : les mots distinctifs appliqués aux règles
# perdaient la plupart des souvenirs utiles perdus. Les règles gardent tous leurs mots d'alias.
TYPES_PAR_SITUATION = ("etat_agent",)
# AMORÇAGE (docs/12 §10) : les sujets du message précédent restent un peu actifs, comme la mémoire de travail. Ils
# s'ajoutent aux indices du message par cab_pull (un « ou » probabiliste : a + b(1 − a)) — deux indices faibles qui
# convergent font un indice fort ; l'amorce SEULE (≤ AMORCE × 0,6) reste sous le seuil : rien n'est resservi sans écho.
AMORCE = 0.5
MOT_DISTINCTIF_MIN = 4          # « exia », « seed », « acme » : un mot distinctif court compte, en correspondance exacte

_VIDES: Dict[str, set] = {}


def _mots_vides(m=None) -> set:
    """Mots vides de la recherche : ceux du masque (normalisés) + ses mots interrogatifs et verbes d'ordre.
    Sans masque : celui d'une mémoire sans `.langue` (le français)."""
    if m is None:
        from . import langues
        m = langues.masque(langues.DEFAUT)
    if m.code not in _VIDES:
        _VIDES[m.code] = {_graphe._norm(x).strip() for x in m.mots_vides} | set(m.mots_vides_recherche)
    return _VIDES[m.code]


def _rac(w: str) -> str:
    """« factures », « facturation » → « factu » : la morphologie ne doit pas cacher le sujet."""
    return w[:RACINE] if len(w) > RACINE else w


def _distance(a: str, b: str, borne: int) -> int:
    """Distance d'édition (Levenshtein), arrêtée dès qu'elle dépasse `borne`."""
    if abs(len(a) - len(b)) > borne:
        return borne + 1
    prec = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cour = [i]
        for j, cb in enumerate(b, 1):
            cour.append(min(prec[j] + 1, cour[j - 1] + 1, prec[j - 1] + (ca != cb)))
        if min(cour) > borne:
            return borne + 1
        prec = cour
    return prec[-1]


class Memoire:
    """Tout ce que le rappel lit, construit une fois par état du graphe."""

    def __init__(self, racine: Path, implicites=()):
        t0 = time.perf_counter()
        self.racine = Path(racine)
        from . import langues
        self.masque = langues.de_la_memoire(self.racine)
        vides = _mots_vides(self.masque)
        self.implicites = {_graphe._pages.slug(x) for x in implicites if x}
        noeuds, self.faits = _graphe._lire(self.racine)
        self.moteur = _graphe.charger_moteur(self.racine)
        # Mémoire vide (aucun nœud) : rien à propager. Le moteur (identique à EXIA GHOST au bit près, on ne le touche
        # pas) plante sur un graphe vide — trouvé par LongMemEval le 27/10/2026 (docs/13 §10 : 74 mémoires sur 500
        # sans aucun fait) ; une instance neuve est dans ce cas.
        self.repos = self.moteur.propagate({}).activations if self.moteur.n_concepts else {}
        # Titre lisible : le premier alias FRANÇAIS de la page (docs/07 — « Dent Repair Pricing » sinon)
        self.titres = {n["noeud"]: n.get("titre") or n["noeud"].replace("_", " ").capitalize() for n in noeuds}
        implicites = self.implicites
        # alias complets (suites de mots) → nœuds ; mots d'alias → nœuds (pour les mentions partielles)
        self.alias: Dict[Tuple[str, ...], set] = defaultdict(set)
        self.mots_alias: Dict[str, set] = defaultdict(set)
        self.mots_courants: set = set()          # (mot, nœud) : mot d'alias courant pour CE nœud (docs/12 §9)
        self.distinctifs_courts: set = set()     # mots distinctifs de 4 lettres : correspondance exacte seulement
        for n in noeuds:
            if n["noeud"] in implicites:
                continue
            # Mot seul (étage 2) : tous les mots des alias, comme avant ; mais quand la page a ses MOTS DISTINCTIFS
            # (écrits avec la fiche, docs/12 §9), les autres mots de ses alias sont COURANTS (« données » de
            # « plateforme de données météo ») et n'allument le sujet qu'à POIDS_MOT_COMMUN.
            # Banc du 16/10 : ne garder QUE les mots distinctifs faisait taire les parasites mais perdait la moitié des
            # souvenirs utiles — dont l'application de courses le 15/10. Le poids continu garde les deux.
            distinctifs = (None if n.get("mots") is None or n.get("type") in TYPES_PAR_SITUATION
                           else {_graphe._norm(x).strip() for x in n["mots"]} - implicites)
            for a in n["alias"]:
                self.alias[tuple(a.split())].add(n["noeud"])
                for m in a.split():
                    if len(m) >= MOT_MIN and m not in vides:
                        self.mots_alias[m].add(n["noeud"])
                        if distinctifs is not None and m not in distinctifs:
                            self.mots_courants.add((m, n["noeud"]))
            for m in distinctifs or ():
                if MOT_DISTINCTIF_MIN <= len(m) < MOT_MIN and m not in vides:
                    self.mots_alias[m].add(n["noeud"]); self.distinctifs_courts.add(m)
        self.long_max = max((len(k) for k in self.alias), default=0)
        self.par_premiere_lettre: Dict[str, List[str]] = defaultdict(list)
        for m in self.mots_alias:
            if m not in self.distinctifs_courts:              # un mot court ne se rapproche pas : « seed » ≠ « seeds »
                self.par_premiere_lettre[m[0]].append(m)
        # plein texte : FTS5 en mémoire, sans accents
        # B+ : champ lexical de chaque concept (en racines) ; un fait est cherchable par son texte ET par
        # le champ de ses concepts — le sens compilé à l'écriture, pas recalculé à chaque question.
        # Champ écrit (thésaurus) + champ appris (les mots de ses propres faits, docs/08 §9)
        self.champs: Dict[str, set] = {n["noeud"]: {_rac(w) for x in n.get("champ", []) + n.get("champ_appris", []) for w in x.split()
                                                   if len(w) >= 3 and w not in vides}
                                      for n in noeuds if n.get("champ")}
        self.champs_texte: Dict[str, str] = {n["noeud"]: " ".join(n.get("champ", []) + n.get("champ_appris", []))
                                             for n in noeuds if n.get("champ")}
        for x in self.faits:
            x["champ"] = " ".join(self.champs_texte.get("concept:" + c, "") for c in x.get("concepts", ()))
        self.fts = sqlite3.connect(":memory:", check_same_thread=False)
        self.fts.execute("create virtual table f using fts5(t, s, tokenize='unicode61 remove_diacritics 2')")
        self.fts.executemany("insert into f(rowid, t, s) values (?, ?, ?)",
                             [(i, x["texte"], x["champ"]) for i, x in enumerate(self.faits)])
        # Rareté des mots (IDF) : un mot présent dans beaucoup de faits pèse peu ; un mot absent de
        # la mémoire pèse le maximum — il montre ce que la mémoire ne sait pas.
        df: Dict[str, int] = defaultdict(int)
        for x in self.faits:
            x["racines"] = {_rac(w) for w in x["norm"].split()}
            x["racines_sem"] = x["racines"] | set().union(*(self.champs.get("concept:" + c, set()) for c in x.get("concepts", ())))
            for w in x["racines"]:
                df[w] += 1
        self.vocabulaire = set(df)
        n = max(1, len(self.faits))
        self.idf = {w: math.log(1 + n / c) for w, c in df.items()}
        self.idf_max = math.log(1 + n)
        # Spécificité d'un concept (29/09, docs/08 §12) : l'IDF appliqué aux concepts. Un concept porté par
        # beaucoup de faits (`facturation`, 35) ne dit presque rien de CHACUN : son champ lexical ne doit
        # pas donner à tous la même note. spec = log(1 + N/n_c) / log(1 + N), dans ]0, 1].
        nc: Dict[str, int] = defaultdict(int)
        for x in self.faits:
            for c in set(x.get("concepts", ())):
                nc[c] += 1
        self.specificite = {c: math.log(1 + n / k) / self.idf_max for c, k in nc.items()}
        # Pour chaque fait : racine du champ → meilleure spécificité parmi ses concepts qui la portent
        for x in self.faits:
            sem: Dict[str, float] = {}
            for c in x.get("concepts", ()):
                s = self.specificite.get(c, 0.0)
                for w in self.champs.get("concept:" + c, ()):
                    if w not in x["racines"] and s > sem.get(w, 0.0):
                        sem[w] = s
            x["sem_spec"] = sem
        # Arêtes et leurs preuves : les « pistes » de memoire_lire (docs/07 D4)
        self.voisins: Dict[str, List[Tuple[str, float, list]]] = defaultdict(list)
        chemin_aretes = self.racine / "graphe" / "aretes.json"
        for x in (json.loads(chemin_aretes.read_text(encoding="utf-8")) if chemin_aretes.exists() else []):
            self.voisins[x["a"]].append((x["b"], x["poids"], x["preuves"]))
            self.voisins[x["b"]].append((x["a"], x["poids"], x["preuves"]))
        for liste in self.voisins.values():
            liste.sort(key=lambda t: (-t[1], t[0]))
        self.fichiers = {n["noeud"]: n["fichier"] for n in noeuds}
        self.fiches = {n["noeud"]: n["fiche"] for n in noeuds if n.get("fiche")}
        self.par_noeud: Dict[str, List[int]] = defaultdict(list)
        for i, x in enumerate(self.faits):
            self.par_noeud[x["noeud"]].append(i)
        self.duree_ms = round((time.perf_counter() - t0) * 1000, 1)


class Rappeleur:
    def __init__(self, racine: Path, implicites=()):
        self.racine = Path(racine)
        self.implicites = implicites
        self._memoire: Optional[Memoire] = None
        self._empreinte = None
        self._verrou = threading.Lock()

    def _etat(self):
        f = self.racine / "graphe" / "aretes.json"
        return f.stat().st_mtime_ns if f.exists() else None

    def memoire(self) -> Optional[Memoire]:
        """La mémoire en cache ; reconstruite seulement si le graphe a changé (D7)."""
        etat = self._etat()
        if etat is None:
            return None
        with self._verrou:
            if self._memoire is None or etat != self._empreinte:
                self._memoire = Memoire(self.racine, self.implicites)
                self._empreinte = etat
            return self._memoire

    def activer(self, m: Memoire, texte: str, seul_texte: bool = False, amorce: Optional[Dict[str, float]] = None) -> Dict:
        """Cascade + propagation, partagées par le rappel (06) et les outils de requête (07).

        Rend les mots pleins, la fonction de couverture, les nœuds d'entrée et leurs étages, les
        orphelins, les faits trouvés par le plein texte, et les nœuds actifs au-dessus du repos."""
        t0 = time.perf_counter()
        norm = _graphe._norm(texte)
        mots = norm.split()
        vides = _mots_vides(m.masque)
        pleins = [w for w in dict.fromkeys(mots) if len(w) >= 3 and w not in vides and not w.isdigit()]

        poids = {}
        for w in pleins:
            poids[_rac(w)] = m.idf.get(_rac(w), m.idf_max)
        total = sum(poids.values()) or 1.0

        def couverture(racines_fait) -> float:
            """Part du texte présente dans un fait, pondérée par la rareté des mots, au carré."""
            return (sum(p for w, p in poids.items() if w in racines_fait) / total) ** GAMMA_COUVERTURE

        entrees: Dict[str, float] = {}
        etages: Dict[str, List[str]] = defaultdict(list)

        def activer(noeud, valeur, etage, indice):
            if valeur > entrees.get(noeud, 0.0):
                entrees[noeud] = valeur
            etages[etage].append(f"{indice}→{noeud}")

        # Étages 0-1 : nom ou alias complet, par suites de mots
        couverts = set()
        for i in (range(0) if seul_texte else range(len(mots))):
            for L in range(1, min(m.long_max, len(mots) - i) + 1):
                for n in m.alias.get(tuple(mots[i:i + L]), ()):
                    activer(n, ACT_ALIAS, "alias", " ".join(mots[i:i + L]))
                    couverts.update(mots[i:i + L])
        # Étage 2 : un mot d'alias seul (« Valmont »), exact ou approché (« Valmon »), partagé
        # entre les nœuds qui le portent — un mot commun à trois nœuds n'en désigne aucun
        for w in ([] if seul_texte else pleins):
            if w in couverts or (len(w) < MOT_MIN and w not in m.distinctifs_courts):
                continue
            if w in m.mots_alias:
                proches, act = [w], ACT_MOT
            else:
                borne = 1 if len(w) <= 7 else 2
                proches = [a for a in m.par_premiere_lettre.get(w[0], ()) if _distance(w, a, borne) <= borne]
                if not proches:
                    continue
                act = ACT_MOT_APPROX
            cibles = set().union(*(m.mots_alias[a] for a in proches))
            for n in cibles:
                commun = all((a, n) in m.mots_courants for a in proches if n in m.mots_alias[a])
                activer(n, act * (POIDS_MOT_COMMUN if commun else 1.0) / len(cibles), "mot_alias", w)
            couverts.add(w)
        # Étage 2 bis (B+) : le champ lexical des concepts. Force GRADUÉE — la part du message (pondérée
        # par la rareté des mots) qui tombe dans le champ du concept : un match fort allume fort.
        if not seul_texte:
            for c, champ in m.champs.items():
                pris = [w for w in poids if w in champ]
                if pris:
                    force = sum(poids[w] for w in pris) / total
                    activer(c, ACT_CHAMP * force, "champ_lexical", "+".join(pris))
        # Étage 3 : filet plein texte sur les faits
        requete = " OR ".join(f'"{w}"' for w in pleins if len(w) >= 4)
        fts_scores: Dict[int, float] = {}
        if requete:
            try:
                lignes = m.fts.execute("select rowid, bm25(f, 1.0, ?) from f where f match ? order by bm25(f, 1.0, ?) limit ?",
                                       (POIDS_CHAMP_BM25, requete, POIDS_CHAMP_BM25, FTS_MAX)).fetchall()
            except sqlite3.OperationalError:
                lignes = []
            # Activation ABSOLUE : la part du texte que le fait couvre, pondérée par la rareté des
            # mots — pas un score relatif au meilleur trouvé, qui ferait toujours un gagnant.
            for rowid, _ in lignes:
                fts_scores[rowid] = couverture(m.faits[rowid]["racines"])
                n = m.faits[rowid]["noeud"]
                if n not in entrees and fts_scores[rowid] > 0:
                    activer(n, ACT_PLEIN_TEXTE * fts_scores[rowid], "plein_texte", str(rowid))
        orphelins = [w for w in pleins if len(w) >= MOT_MIN and w not in couverts and _rac(w) not in m.vocabulaire]
        t_cascade = time.perf_counter()

        # Amorçage : le tour précédent, affaibli, cumulé avec les indices de ce message
        if amorce and not seul_texte:
            for n, v in amorce.items():
                if v > 0 and n in m.fichiers and n not in m.implicites:
                    entrees[n] = cab_pull(entrees.get(n, 0.0), 1.0, AMORCE * min(1.0, v))
                    etages["amorce"].append(f"{v:.2f}→{n}")
        # Propagation, lue au-dessus du repos
        actives: Dict[str, float] = {}
        if entrees and not seul_texte:
            act = m.moteur.propagate(entrees).activations
            for n, v in act.items():
                d = v - m.repos.get(n, 0.0)
                if d >= SEUIL_NOEUD:
                    actives[n] = d
        t_prop = time.perf_counter()
        return {"pleins": pleins, "couverture": couverture, "poids": poids, "total": total,
                "entrees": entrees, "etages": etages,
                "orphelins": orphelins, "fts_scores": fts_scores, "actives": actives,
                "t_cascade": t_cascade - t0, "t_prop": t_prop - t_cascade}

    # ── le rappel ────────────────────────────────────────────────────────
    def rappeler(self, message: str, maintenant: Optional[datetime] = None, mode: str = "complet",
                 amorce: Optional[Dict[str, float]] = None) -> Dict:
        """`mode="plein_texte"` : le même rappel, graphe coupé — seuls les faits trouvés par le plein
        texte, notés par leur seul lexique. C'est le concurrent B du banc 6b : la différence entre
        les deux modes mesure exactement ce qu'apporte le graphe."""
        seul_texte = mode == "plein_texte"
        t0 = time.perf_counter()
        m = self.memoire()
        if m is None:
            return {"statut": "pas_de_graphe", "bloc": ""}
        t_cache = time.perf_counter()
        a = self.activer(m, message, seul_texte, amorce)
        pleins, couverture, entrees, etages = a["pleins"], a["couverture"], a["entrees"], a["etages"]
        orphelins, fts_scores, actives = a["orphelins"], a["fts_scores"], a["actives"]
        t_cascade = t_cache + a["t_cascade"]
        t_prop = t_cascade + a["t_prop"]

        # Choix des faits : cab_pull(activation du nœud, 1, part des mots du message dans le fait)
        jour = (maintenant or datetime.now()).date().isoformat()
        instant = (maintenant or datetime.now()).isoformat(timespec="minutes")
        # Base ABSOLUE : rapportée à l'activation d'un nœud nommé en toutes lettres (injecté à 1,0),
        # et non au plus fort du moment — sinon il y a toujours un gagnant, et jamais de silence.
        # Défaut mesuré au premier essai du 26/09 : « Quel temps fait-il à Brest ? » ramenait 1 160 tokens.
        d_ref = max(1e-6, 1.0 - min(m.repos.values(), default=0.0))
        candidats = []
        sources = ([(m.faits[i]["noeud"], 0.0, [i]) for i in fts_scores] if seul_texte
                   else [(n, d, m.par_noeud.get(n, ())) for n, d in actives.items()])
        for n, d, ids in sources:
            for i in ids:
                f = m.faits[i]
                meta = f["meta"]
                if f["dit_le"] and f["dit_le"][:16] > instant:
                    continue                                    # appris après : pas de triche
                ech = meta.get("echeance")
                if f["section"] == "prospective" and ech and ech[:10] < jour:
                    continue                                    # intention périmée
                lex = couverture(f["racines"])
                if n in m.implicites and lex == 0:
                    continue    # la fiche de l'utilisateur est liée à tout : sans écho du message, rien
                score = cab_pull(min(1.0, d / d_ref), 1.0, lex)
                if score >= SEUIL_FAIT:
                    recence = meta.get("event_time") or f["dit_le"] or ""
                    candidats.append((score, meta.get("protected") == "true", recence,
                                      float(meta.get("conf") or 0), i))
        # Tri déterministe par tris stables successifs (le dernier est le critère principal) :
        # score, puis protected, puis récence, puis confiance, puis ordre des pages.
        candidats.sort(key=lambda c: c[4])
        candidats.sort(key=lambda c: c[3], reverse=True)
        candidats.sort(key=lambda c: c[2], reverse=True)
        candidats.sort(key=lambda c: not c[1])
        candidats.sort(key=lambda c: -round(c[0], 6))
        choisis, par_noeud, tokens = [], defaultdict(int), estimer_tokens(m.masque.textes["rappel_entete"]) + 10
        for score, _, _, _, i in candidats:
            f = m.faits[i]
            if par_noeud[f["noeud"]] >= FAITS_PAR_NOEUD:
                continue
            ligne = _ligne(f, m.masque)
            cout = estimer_tokens(ligne) + (estimer_tokens(m.titres[f["noeud"]]) + 2 if par_noeud[f["noeud"]] == 0 else 0)
            if tokens + cout > PLAFOND_TOKENS:
                continue
            choisis.append((i, round(score, 4)))
            par_noeud[f["noeud"]] += 1
            tokens += cout
        bloc = _bloc(m, [i for i, _ in choisis]) if choisis else ""
        t_fin = time.perf_counter()
        ms = lambda a, b: round((b - a) * 1000, 2)
        return {
            "statut": "ok", "bloc": bloc, "tokens": estimer_tokens(bloc) if bloc else 0,
            "entrees": {n: round(v, 3) for n, v in sorted(entrees.items(), key=lambda x: -x[1])},
            "etages": dict(etages), "orphelins": orphelins,
            "actives": {n: round(v, 3) for n, v in sorted(actives.items(), key=lambda x: -x[1])[:10]},
            "faits": [{"page": m.faits[i]["fichier"], "fait": m.faits[i]["texte"][:90], "score": s} for i, s in choisis],
            "_choisis": choisis,                       # (indice, score) — pour souvenirs(), retiré du journal
            "latence_ms": {"cache": ms(t0, t_cache), "cascade": ms(t_cache, t_cascade),
                           "propagation": ms(t_cascade, t_prop), "choix": ms(t_prop, t_fin),
                           "total": ms(t0, t_fin), "hors_cache": ms(t_cache, t_fin)},
            "cache_reconstruit_ms": m.duree_ms if ms(t0, t_cache) > 1 else 0,
        }

    def journaliser(self, message: str, r: Dict, maintenant: datetime) -> None:
        entree = {"ts": maintenant.isoformat(timespec="seconds"), "message": message[:300],
                  **{k: v for k, v in r.items() if k not in ("bloc", "_choisis")}}
        dossier = self.racine / "rappel"
        dossier.mkdir(parents=True, exist_ok=True)     # défaut trouvé par le test 6a : sans lui, le
        ajouter_ligne_jsonl(dossier / f"{maintenant.date().isoformat()}.jsonl", entree)   # 1er rappel échouait


def souvenirs(m: "Memoire", r: Dict, seuil: float, max_sujets: int, faits_par_sujet: int) -> Dict:
    """Phase 2 (docs/11) — ce qui REMONTE avec le message de Francis, comme chez un humain : d'abord le SUJET
    (« application de liste de courses », et où est sa page), puis un ou deux faits, les règles de conduite
    d'abord. Rien si aucun fait n'atteint le seuil : se taire est une qualité. Construit sur le rappel `r`
    (Rappeleur.rappeler), sans nouveau calcul.

    Banc du 16/10 (docs/11) : le 15/10, « on va préparer la liste de courses » faisait bien remonter la page de
    l'application, mais par des détails (l'ordre des rayons) ; le souvenir utile était le sujet lui-même."""
    groupes: Dict[str, List[tuple]] = defaultdict(list)
    for i, s in r.get("_choisis") or []:
        if s >= seuil:
            groupes[m.faits[i]["noeud"]].append((s, i))
    ordre = sorted(groupes, key=lambda n: (-max(s for s, _ in groupes[n]), n))[:max(0, max_sujets)]
    if not ordre:
        return {"bloc": "", "sujets": [], "faits": 0, "tokens": 0}
    lignes = [m.masque.textes["souvenirs_entete"]]
    n_faits = 0
    for n in ordre:
        fs = sorted(groupes[n], key=lambda t: (m.faits[t[1]]["section"] != "procedural", -t[0], t[1]))[:max(1, faits_par_sujet)]
        lignes.append(f"• {m.titres.get(n, n)} — memoire/pages/{m.fichiers.get(n, '')}")
        if m.fiches.get(n):                                                 # docs/12 : ce que c'est, avant les détails
            lignes.append(f"  {m.fiches[n]}")
        lignes.extend("  – " + _ligne(m.faits[i], m.masque)[2:] for _, i in fs)      # _ligne : « - fait (dit le jj/mm) »
        n_faits += len(fs)
    bloc = "\n".join(lignes)
    return {"bloc": bloc, "sujets": ordre, "faits": n_faits, "tokens": estimer_tokens(bloc)}


def _ligne(f: Dict, masque) -> str:
    d = f["dit_le"]
    quand = masque.textes["rappel_dit_le"].format(jj=d[8:10], mm=d[5:7]) if d and len(d) >= 10 else ""
    return f"- {f['texte']}{quand}"


def _bloc(m: Memoire, indices: List[int]) -> str:
    par_noeud: Dict[str, List[int]] = defaultdict(list)
    for i in indices:
        par_noeud[m.faits[i]["noeud"]].append(i)
    lignes = [m.masque.textes["rappel_entete"]]
    for n, ids in par_noeud.items():
        lignes.append(m.titres[n])
        lignes.extend(_ligne(m.faits[i], m.masque) for i in ids)
    return "\n".join(lignes)
