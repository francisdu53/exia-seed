"""Le graphe — étape 5 (docs/05-graphe.md). Relie les pages entre elles, sans aucun appel au modèle.

Le graphe est une FONCTION DES PAGES (D1) : recalculé intégralement à chaque consolidation, de façon
déterministe — mêmes pages, mêmes fichiers, au bit près. Il ne peut pas dériver des pages.

Deux sources de liens (D2), deux preuves vérifiables :
    vécu ensemble   deux faits de nœuds différents citent la même ligne de brut (1,0), ou des
                    lignes du même lot distantes de 1 à 3 (0,5 / distance)
    nommé           un fait du nœud A contient le nom ou un alias du nœud B (0,7)

Poids (D4) — saturation, puis normalisation symétrique (théorie spectrale des graphes) :
    s(a,b) = 1 − exp(−e/κ)          e = somme des preuves de la paire
    w(a,b) = s / √(d(a)·d(b))        d(x) = somme des s de x, plancher 1
Un lien vers un nœud qui touche tout (l'utilisateur) pèse moins qu'un lien vers un nœud rare :
un indice commun à tout le monde n'apprend rien.

Liens symétriques (D3), chacun avec ses preuves (D5). Fichiers texte versionnés avec les pages (D6) :
    graphe/noeuds.json   graphe/aretes.json   graphe/rapport.json
"""
from __future__ import annotations

import json
import math
import re
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import pages as _pages

PREUVE_MEME_LIGNE = 1.0
PREUVE_VOISINE = 0.5            # divisée par la distance en lignes
FENETRE_LIGNES = 3
PREUVE_NOMME = 0.7
PREUVE_CONCEPT = 0.5            # B+ (docs/08 §8) : un fait rattaché à un concept du thésaurus
PREFIXE_CONCEPT = "concept:"
CHAMP_MOTS_PAR_FAIT = 4         # champ lexical VIVANT : les mots les plus rares de chaque fait rattaché
CHAMP_APPRIS_MAX = 40           # plafond par concept (les plus fréquents parmi ses faits d'abord)
KAPPA = 2.0                     # saturation : e = κ donne s = 0,63
ALIAS_MIN = 4                   # un alias plus court (« VW », « BA ») relierait n'importe quoi
# spec §5.2 : 2 000 avec la matrice pleine. Représentation creuse depuis le 27/10/2026 (creux.py) : la mémoire suit les
# arêtes, plus le carré des nœuds ; le plafond devient celui du temps de calcul du graphe (1,4 s à 2 834 nœuds).
PLAFOND_NOEUDS = 20000
ALERTE_PLAFOND = 0.8
PREUVES_LISTEES = 20            # par arête ; le compte total est toujours donné
DECIMALES = 6

_RE_SRC = re.compile(r"(?:^| )src:(\S+)")
_RE_DIT_LE = re.compile(r"(?:^| )dit_le:(\S+)")
_RE_REF = re.compile(r"^raw/([^:]+):(\d+)(?:-(\d+))?$")


_LIGATURES = str.maketrans({"œ": "oe", "Œ": "oe", "æ": "ae", "Æ": "ae", "ß": "ss"})


def _norm(texte: str) -> str:
    """Minuscules, sans accents, ponctuation → espaces : « Ménard » et « menard » se rejoignent.

    Seuls les accents sont retirés ; tout autre signe devient un espace. Défaut trouvé le 29/09 : le
    passage en ASCII EFFAÇAIT l'apostrophe typographique « ’ » (celle qu'écrit le modèle, 184 fois dans
    les pages contre 3 droites) avant qu'elle devienne un espace — « l’encadré » donnait « lencadre »,
    « d’Amandine » « damandine » : invisibles pour la couverture, les alias et les preuves du graphe."""
    t = unicodedata.normalize("NFKD", (texte or "").translate(_LIGATURES))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return " " + re.sub(r"[^a-z0-9]+", " ", t).strip() + " "


def _retraits(racine: Path) -> Dict[str, set]:
    sortie: Dict[str, set] = {}
    chemin = racine / "raw" / ".retraits.jsonl"
    if chemin.exists():
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ligne)
                a, b = r["lignes"]
                sortie.setdefault(r["fichier"], set()).update(range(int(a), int(b) + 1))
            except Exception:
                continue
    return sortie


def charger_thesaurus(racine: Path) -> Dict:
    """Le thésaurus (B+, docs/08 §8) : {"concepts": {slug: {"fr": [...], "en": [...]}}, "faits": {texte: [slugs]}}.

    Chaque concept porte son CHAMP LEXICAL une seule fois ; chaque fait y est rattaché par 1 à 3
    concepts (métadonnée `concepts:` de la page, ou table « faits » du thésaurus)."""
    f = Path(racine) / "thesaurus.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"concepts": {}, "faits": {}}
    except ValueError:
        return {"concepts": {}, "faits": {}}


def enregistrer_thesaurus(racine: Path, thesaurus: Dict) -> None:
    """Écriture atomique du thésaurus — par la consolidation seulement (un seul écrivain)."""
    _ecrire_json(Path(racine) / "thesaurus.json", {"concepts": dict(sorted((thesaurus.get("concepts") or {}).items())),
                                                   "faits": thesaurus.get("faits") or {}})


def _lire(racine: Path):
    """(nœuds dans un ordre stable, faits) depuis les pages — et les concepts du thésaurus (B+)."""
    from . import langues
    masque = langues.de_la_memoire(racine)
    pages = [p for p in _pages.lister(racine / "pages") if p.entete.get("node")]
    pages.sort(key=lambda p: (str(p.entete.get("created") or ""), str(p.entete["node"])))
    retraits = _retraits(racine)
    noeuds, faits = [], []
    for p in pages:
        n = str(p.entete["node"])
        alias = {str(a) for l in (p.entete.get("aliases") or {}).values() for a in (l or []) if a}
        alias.add(n.replace("_", " "))
        # Titre lisible : le premier alias dans la langue de la mémoire (docs/07, docs/10)
        propres = [str(x) for x in ((p.entete.get("aliases") or {}).get(masque.code) or []) if x]
        noeuds.append({"noeud": n, "titre": propres[0] if propres else n.replace("_", " ").capitalize(),
                       "type": p.entete.get("node_type") or "concept",
                       "fichier": p.chemin.name, "fiche": str(p.entete.get("summary") or ""),
                       "mots": [str(x) for x in p.entete["keywords"]] if isinstance(p.entete.get("keywords"), list) else None,
                       "alias": sorted(a for a in {_norm(x).strip() for x in alias} if len(a) >= ALIAS_MIN)})
        for section, lignes in p.sections.items():
            for ligne in lignes:
                m = _pages._RE_META.search(ligne)
                meta = m.group(1) if m else ""
                texte = _pages._RE_META.sub("", ligne[2:]).strip()
                refs = set()
                s = _RE_SRC.search(meta)
                for ref in (s.group(1).split(",") if s else []):
                    r = _RE_REF.match(ref)
                    if not r:
                        continue
                    a, b = int(r.group(2)), int(r.group(3) or r.group(2))
                    for l in range(a, min(b, a + 50) + 1):
                        if l not in retraits.get(r.group(1), set()):
                            refs.add((r.group(1), l))
                d = _RE_DIT_LE.search(meta)
                champs = dict(x.split(":", 1) for x in meta.split() if ":" in x)   # lu par le rappel
                faits.append({"noeud": n, "fichier": p.chemin.name, "section": section, "texte": texte,
                              "norm": _norm(texte), "refs": refs, "dit_le": d.group(1) if d else None,
                              "meta": champs})
    # B+ : les concepts du thésaurus deviennent des nœuds ; chacun porte son champ lexical
    th = charger_thesaurus(racine)
    connus = th.get("concepts") or {}
    for f in faits:
        brut = f["meta"].get("concepts")
        f["concepts"] = [c for c in (brut.split(",") if brut else th.get("faits", {}).get(f["texte"], [])) if c in connus]
    utilises = sorted({c for f in faits for c in f["concepts"]})
    appris = _champs_appris(faits, masque)
    for c in utilises:
        champ = [c.replace("_", " ")] + [str(x) for x in connus[c].get("fr", []) + connus[c].get("en", [])]
        noeuds.append({"noeud": PREFIXE_CONCEPT + c, "titre": c.replace("_", " "), "type": "concept_lexical",
                       "fichier": None, "alias": [],
                       "champ": sorted({_norm(x).strip() for x in champ if _norm(x).strip()}),
                       "champ_appris": appris.get(c, [])})
    return noeuds, faits


def _champs_appris(faits, masque=None) -> Dict[str, List[str]]:
    """Le champ lexical VIVANT (docs/08 §9) : chaque concept apprend le vocabulaire de ses propres faits.

    Pour chaque fait rattaché au concept, ses CHAMP_MOTS_PAR_FAIT mots les plus rares (IDF sur toute la
    mémoire) rejoignent le champ ; on garde les CHAMP_APPRIS_MAX les plus présents parmi les faits du
    concept. Sans modèle, déterministe, et justifiable : un mot est dans le champ parce qu'un fait
    rattaché le contient. Défaut qu'il corrige (banc 8, 26/09) : « chewing-gums catégories têtes de
    gondole » ne trouvait pas `courses`, dont le champ écrit une fois ne contenait ni « gondole » ni
    « caisse » — que les faits de Francis, eux, contenaient."""
    import math
    vides = _mots_vides_graphe(masque)
    docs = [set(w for w in f["norm"].split() if len(w) >= 4 and not w.isdigit() and w not in vides) for f in faits]
    df: Dict[str, int] = defaultdict(int)
    for d in docs:
        for w in d:
            df[w] += 1
    n = max(1, len(docs))
    compte: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for f, d in zip(faits, docs):
        rares = sorted(d, key=lambda w: (df[w], w))[:CHAMP_MOTS_PAR_FAIT]
        for c in f.get("concepts", ()):
            for w in rares:
                if df[w] < n:                                  # un mot présent partout n'apprend rien
                    compte[c][w] += 1
    return {c: [w for w, _ in sorted(m.items(), key=lambda t: (-t[1], df[t[0]], t[0]))[:CHAMP_APPRIS_MAX]]
            for c, m in compte.items()}


def _mots_vides_graphe(masque=None) -> set:
    if masque is None:
        from . import langues
        masque = langues.masque(langues.DEFAUT)
    return {_norm(m).strip() for m in masque.mots_vides}


def _preuve(type_: str, force: float, f: Dict, autre: Optional[Dict] = None, distance: int = 0) -> Dict:
    p = {"type": type_, "force": round(force, DECIMALES), "page": f["fichier"], "fait": f["texte"][:100],
         "lignes": sorted(f"raw/{a}:{b}" for a, b in f["refs"])[:6], "dit_le": f["dit_le"]}
    if autre is not None:
        p["avec"] = {"page": autre["fichier"], "fait": autre["texte"][:100]}
        p["distance"] = distance
    return p


def calculer(racine: Path, ecrire: bool = True, implicites=()) -> Dict:
    """Calcule le graphe depuis les pages ; écrit `graphe/` si `ecrire`. Rend le rapport.

    `implicites` : nœuds de l'utilisateur et de l'agent. Leur nom écrit dans un fait n'est PAS une
    preuve « nommé » — le modèle écrit « Francis a… » dans presque chaque fait. Même logique que le
    contrôle de citation (D5 du doc 04). Mesuré le 26/09 : sans cette règle, francis ↔ liste de
    courses pesait 0,43 sur six seules phrases « Francis a effectué ses courses… ». Les liens
    « vécu ensemble » vers ces nœuds restent : eux sont réels."""
    implicites = {_pages.slug(x) for x in implicites if x}
    t0 = time.perf_counter()
    racine = Path(racine)
    noeuds, faits = _lire(racine)
    if len(noeuds) > PLAFOND_NOEUDS:
        rapport = {"statut": "plafond_depasse", "noeuds": len(noeuds), "plafond": PLAFOND_NOEUDS,
                   "alerte": f"{len(noeuds)} nœuds > plafond {PLAFOND_NOEUDS} : graphe NON recalculé, "
                             "l'ancien reste en place — passer en représentation creuse (spec §5.2)"}
        if ecrire:
            _ecrire_json(racine / "graphe" / "rapport.json", rapport)
        return rapport

    preuves: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)

    # 1. Vécu ensemble — une preuve par paire de faits, à leur plus petite distance. Fenêtre
    #    glissante sur les lignes triées de chaque lot : O(n·k), pas O(n²) (mesuré le 26/09 :
    #    la double boucle coûtait l'essentiel des 7,5 s à 2 000 nœuds).
    par_lot: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    for i, f in enumerate(faits):
        for lot, l in f["refs"]:
            par_lot[lot].append((l, i))
    distance: Dict[Tuple[int, int], int] = {}
    for lot in sorted(par_lot):
        entrees = sorted(par_lot[lot])
        for x, (l, i) in enumerate(entrees):
            y = x + 1
            while y < len(entrees) and entrees[y][0] - l <= FENETRE_LIGNES:
                j = entrees[y][1]
                if faits[i]["noeud"] != faits[j]["noeud"]:
                    paire = (min(i, j), max(i, j))
                    d = entrees[y][0] - l
                    if d < distance.get(paire, FENETRE_LIGNES + 1):
                        distance[paire] = d
                y += 1
    for (i, j), d in sorted(distance.items()):
        f, g = faits[i], faits[j]
        force = PREUVE_MEME_LIGNE if d == 0 else PREUVE_VOISINE / d
        cle = tuple(sorted((f["noeud"], g["noeud"])))
        a_, b_ = (f, g) if f["noeud"] == cle[0] else (g, f)
        preuves[cle].append(_preuve("meme_ligne" if d == 0 else "voisine", force, a_, b_, d))

    # 2. Nommé — un fait de A contient un alias de B. Dictionnaire des alias (suites de mots) ;
    #    chaque fait est parcouru par ses suites de mots, jusqu'à la longueur du plus long alias :
    #    coût proportionnel à la longueur du fait, indépendant du nombre de nœuds (mesuré le 26/09 :
    #    comparer chaque fait à chaque alias coûtait 14 millions de tests à 2 000 nœuds).
    alias_vers: Dict[Tuple[str, ...], set] = defaultdict(set)
    for n in noeuds:
        if n["noeud"] not in implicites:
            for a in n["alias"]:
                alias_vers[tuple(a.split())].add(n["noeud"])
    long_max = max((len(k) for k in alias_vers), default=0)
    for f in faits:
        mots = f["norm"].split()
        cites = set()
        for i in range(len(mots)):
            for L in range(1, min(long_max, len(mots) - i) + 1):
                cites |= alias_vers.get(tuple(mots[i:i + L]), set())
        cites.discard(f["noeud"])
        for n in sorted(cites):
            cle = tuple(sorted((f["noeud"], n)))
            p = _preuve("nomme", PREUVE_NOMME, f)
            p["nomme"] = n
            preuves[cle].append(p)

    # 2 bis. B+ — un fait rattaché à un concept relie sa page au nœud du concept
    for f in faits:
        for c in f.get("concepts", ()):
            cle = tuple(sorted((f["noeud"], PREFIXE_CONCEPT + c)))
            p = _preuve("concept", PREUVE_CONCEPT, f)
            p["concept"] = c
            preuves[cle].append(p)

    # 3. Poids : saturation, puis normalisation symétrique
    e = {c: sum(p["force"] for p in ps) for c, ps in preuves.items()}
    s = {c: 1.0 - math.exp(-v / KAPPA) for c, v in e.items()}
    degre: Dict[str, float] = defaultdict(float)
    for (a, b), v in s.items():
        degre[a] += v
        degre[b] += v
    aretes = []
    for (a, b) in sorted(preuves):
        w = s[(a, b)] / math.sqrt(max(1.0, degre[a]) * max(1.0, degre[b]))
        ps = sorted(preuves[(a, b)], key=lambda p: (-p["force"], p["type"], p["page"], p["fait"]))
        aretes.append({"a": a, "b": b, "poids": round(w, DECIMALES), "saturation": round(s[(a, b)], DECIMALES),
                       "evidence": round(e[(a, b)], DECIMALES), "nb_preuves": len(ps),
                       "preuves": ps[:PREUVES_LISTEES]})

    rapport = _rapport(noeuds, faits, aretes, time.perf_counter() - t0)
    from . import langues
    _m = langues.de_la_memoire(racine)
    rapport["langue"] = f"{_m.code}/{_m.version}"         # avec quelles règles de langue ce graphe a été fait
    if ecrire:
        dossier = racine / "graphe"
        _ecrire_json(dossier / "noeuds.json", noeuds)
        _ecrire_json(dossier / "aretes.json", aretes)
        _ecrire_json(dossier / "rapport.json", rapport)
    return rapport


def _rapport(noeuds, faits, aretes, duree_s: float) -> Dict:
    voisins: Dict[str, set] = defaultdict(set)
    types: Dict[str, int] = defaultdict(int)
    for a_ in aretes:
        voisins[a_["a"]].add(a_["b"])
        voisins[a_["b"]].add(a_["a"])
        for p in a_["preuves"]:
            types[p["type"]] += 1
    noms = [n["noeud"] for n in noeuds]
    isoles = [n for n in noms if n not in voisins]
    # plus grand groupe connexe
    vus, plus_grand = set(), 0
    for n in noms:
        if n in vus:
            continue
        pile, taille = [n], 0
        vus.add(n)
        while pile:
            x = pile.pop(); taille += 1
            for y in voisins[x]:
                if y not in vus:
                    vus.add(y); pile.append(y)
        plus_grand = max(plus_grand, taille)
    n = len(noms)
    deg_max = max(noms, key=lambda x: (len(voisins[x]), x)) if noms else None
    return {"statut": "ok", "noeuds": n, "faits": len(faits), "aretes": len(aretes),
            "densite": round(2 * len(aretes) / (n * (n - 1)), 4) if n > 1 else 0.0,
            "degre_max": {"noeud": deg_max, "voisins": len(voisins[deg_max]) if deg_max else 0},
            "isoles": isoles, "plus_grand_groupe": plus_grand, "preuves_par_type": dict(sorted(types.items())),
            "duree_ms": round(duree_s * 1000, 1), "plafond": PLAFOND_NOEUDS,
            "alerte": (f"{n} nœuds ≥ {int(ALERTE_PLAFOND * 100)} % du plafond"
                       if n >= ALERTE_PLAFOND * PLAFOND_NOEUDS else None)}


def _ecrire_json(chemin: Path, donnees) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin.with_suffix(".tmp")
    tmp.write_text(json.dumps(donnees, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(chemin)


def charger_moteur(racine: Path):
    """Le moteur de propagation construit depuis graphe/ — pour le rappel (étape 6) et la recherche.

    Depuis le 27/10/2026 : représentation CREUSE (`creux.MoteurCreux`, spec §5.2) — les mêmes calculs que `FCMEngine`
    sans la matrice pleine n × n (202 Mo et 21 ms à 2 834 nœuds, docs/13 §14.6). `charger_moteur_plein` garde
    l'ancien chemin pour la vérification (`tests/test_creux.py`)."""
    from .creux import MoteurCreux
    dossier = Path(racine) / "graphe"
    noeuds = json.loads((dossier / "noeuds.json").read_text(encoding="utf-8"))
    aretes = json.loads((dossier / "aretes.json").read_text(encoding="utf-8"))
    return MoteurCreux([n["noeud"] for n in noeuds], ((a_["a"], a_["b"], a_["poids"]) for a_ in aretes))


def charger_moteur_plein(racine: Path):
    """`FCMEngine` (V2.7.2, inchangé) construit depuis graphe/ — la référence de `charger_moteur`.

    Tous les nœuds sont des entrées (`is_input`) : dans ce moteur, seul un nœud d'entrée garde la
    valeur qu'on lui injecte. Matrice symétrique, convention du moteur W[cible, source]."""
    import numpy as np
    from .moteur.fcm import FCMConcept, FCMEngine
    dossier = Path(racine) / "graphe"
    noeuds = json.loads((dossier / "noeuds.json").read_text(encoding="utf-8"))
    aretes = json.loads((dossier / "aretes.json").read_text(encoding="utf-8"))
    index = {n["noeud"]: i for i, n in enumerate(noeuds)}
    W = np.zeros((len(noeuds), len(noeuds)))
    for a_ in aretes:
        i, j = index[a_["a"]], index[a_["b"]]
        W[i, j] = W[j, i] = a_["poids"]
    return FCMEngine("exia_seed", [FCMConcept(name=n["noeud"], is_input=True) for n in noeuds], W)
