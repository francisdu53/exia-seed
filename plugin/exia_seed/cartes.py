"""Cartes thématiques — une FCM = un thème avec ses notions (NOTE-FCM-thematiques.md, 17/11/2026).

EXIA SEED 0.9.16 : construites en mémoire au cache du rappel (lecture seule, rien n'est écrit) ; voie des notions de la montre.

Pour chaque thème (concept du thésaurus), à partir des seuls souvenirs qui lui sont rattachés :
  notions   les mots qui reviennent (≥ 2 souvenirs du thème) ET le distinguent du reste de la mémoire
            (au moins 2 fois plus présents dans le thème que partout) ; classés par information mutuelle
            locale k · log(lift) — « ce que le mot dit du thème » ; 40 au plus (le seuil de division de GHOST).
  liens     deux notions dites dans le même souvenir, au moins 2 fois ; poids k(u,v) / √(k(u)·k(v)).
  accroches chaque souvenir → les notions qu'il contient.
Une notion est un mot ramené au singulier (on retire un s ou un x final : « factures » = « facture »).
Sans modèle, sans vecteur, déterministe.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Dict, Iterable, List

NOTIONS_MAX = 40
NOTION_FAITS_MIN = 2
LIFT_MIN = 2.0
LIEN_FAITS_MIN = 2
MOT_MIN = 4
DISPERSION_MIN = 0.55       # DP de Gries : un mot réparti entre les thèmes comme les souvenirs eux-mêmes
                            # (« indique », « envisage », « doit ») ne caractérise aucun thème


def singulier(w: str) -> str:
    """Racinisation minimale (« S-stemmer ») : le pluriel ne doit pas dédoubler une notion."""
    return w[:-1] if len(w) > MOT_MIN and w[-1] in "sx" else w


def mots(norm: str, vides: set) -> Dict[str, str]:
    """{notion: forme écrite} des mots pleins d'un texte normalisé."""
    out: Dict[str, str] = {}
    for w in norm.split():
        if len(w) >= MOT_MIN and w not in vides and not any(ch.isdigit() for ch in w):
            out.setdefault(singulier(w), w)
    return out


def construire(faits: List[Dict], vides: Iterable[str], tous: bool = False) -> Dict[str, Dict]:
    """{concept: {"faits": [i], "notions": {n: {"k", "lift", "score", "forme"}}, "liens": {n: {m: poids}},
    "accroches": {i: [n]}, "candidats": [...] (si tous)}}."""
    vides = set(vides)
    N = max(1, len(faits))
    docs, formes = [], defaultdict(Counter)
    df: Counter = Counter()
    par_concept: Dict[str, List[int]] = defaultdict(list)
    for i, f in enumerate(faits):
        d = mots(f["norm"], vides)
        docs.append(set(d))
        for n, w in d.items():
            formes[n][w] += 1
        df.update(d.keys())
        for c in dict.fromkeys(f.get("concepts", ())):
            par_concept[c].append(i)
    # Dispersion (Gries 2008) : DP = ½ Σ_c |part du mot dans c − part des souvenirs dans c| ; 0 = partout pareil
    taille = {c: len(ids) for c, ids in par_concept.items()}
    T = sum(taille.values()) or 1
    par_mot: Dict[str, Counter] = defaultdict(Counter)
    for c, ids in par_concept.items():
        for i in ids:
            for n in docs[i]:
                par_mot[n][c] += 1
    dp = {}
    for n, kc in par_mot.items():
        tot = sum(kc.values())
        dp[n] = 0.5 * (sum(abs(v / tot - taille[c] / T) for c, v in kc.items()) + sum(taille[c] / T for c in taille if c not in kc))
    cartes = {}
    for c, ids in par_concept.items():
        nc = len(ids)
        k = Counter(n for i in ids for n in docs[i])
        cand = []
        for n, kn in k.items():
            if kn < NOTION_FAITS_MIN:
                continue
            lift = kn * N / (df[n] * nc)
            if lift < LIFT_MIN or dp[n] < DISPERSION_MIN:
                continue
            cand.append((kn * math.log(lift), n, kn, lift))
        cand.sort(key=lambda t: (-t[0], t[1]))
        garde = cand if tous else cand[:NOTIONS_MAX]
        notions = {n: {"k": kn, "lift": round(lift, 2), "score": round(s, 3), "forme": formes[n].most_common(1)[0][0],
                       "formes": [w for w, _ in formes[n].most_common()]}
                   for s, n, kn, lift in garde[:NOTIONS_MAX]}
        cles = {n for _, n, _, _ in garde}
        co: Counter = Counter()
        accroches = {}
        for i in ids:
            ns = sorted(docs[i] & cles)
            if ns:
                accroches[i] = [n for n in ns if n in notions]
            for a in range(len(ns)):
                for b in range(a + 1, len(ns)):
                    co[(ns[a], ns[b])] += 1
        liens: Dict[str, Dict[str, float]] = defaultdict(dict)
        for (a, b), kab in co.items():
            if kab < LIEN_FAITS_MIN:
                continue
            p = kab / math.sqrt(k[a] * k[b])
            liens[a][b] = liens[b][a] = round(p, 4)
        carte = {"faits": ids, "notions": notions, "liens": dict(liens), "accroches": accroches}
        if tous:
            carte["candidats"] = [(n, kn, round(lift, 2), round(s, 3), formes[n].most_common(1)[0][0]) for s, n, kn, lift in cand]
        cartes[c] = carte
    return cartes


def champs(faits: List[Dict], vides: Iterable[str]) -> Dict[str, List[str]]:
    """Remplace le champ appris (graphe._champs_appris) : les notions de chaque thème, formes écrites."""
    return {c: [v["forme"] for v in x["notions"].values()] for c, x in construire(faits, vides).items()}


def bissection(carte: Dict) -> List[List[str]]:
    """Coupe une carte en deux là où les liens sont les plus faibles (vecteur de Fiedler du laplacien
    normalisé). Sur tous les candidats (une carte qui dépasse 40 notions est celle qu'on diviserait)."""
    import numpy as np
    # la plus grande composante connexe (sinon le vecteur de Fiedler ne fait que séparer les morceaux)
    restants, comp = set(carte["liens"]), []
    while restants:
        pile, vu = [restants.pop()], set()
        while pile:
            a = pile.pop(); vu.add(a)
            for b in carte["liens"].get(a, {}):
                if b in restants:
                    restants.discard(b); pile.append(b)
        comp.append(vu)
    noms = sorted(max(comp, key=len)) if comp else []
    if len(noms) < 6:
        return []
    ix = {n: j for j, n in enumerate(noms)}
    A = np.zeros((len(noms), len(noms)))
    for a in noms:
        for b, p in carte["liens"][a].items():
            A[ix[a], ix[b]] = p
    d = A.sum(1)
    d[d == 0] = 1e-9
    Dm = np.diag(1 / np.sqrt(d))
    L = np.eye(len(noms)) - Dm @ A @ Dm
    _, vec = np.linalg.eigh(L)
    f = Dm @ vec[:, 1]
    return [[n for n in noms if f[ix[n]] < 0], [n for n in noms if f[ix[n]] >= 0]]
