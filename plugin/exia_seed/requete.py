"""La requête — étape 7 (docs/07-requete.md). Les outils avec lesquels Nexa interroge son wiki.

L'opération Query du LLM Wiki de Karpathy : Nexa lit INDEX.md, ouvre les pages ; quand le sommaire
ne suffit plus, FCM EXIA prend la place de la recherche par mots-clés ou par vecteurs :

    memoire_chercher(requête)   les sujets pertinents, POURQUOI ils remontent, leurs 2-3 meilleurs faits
    memoire_lire(sujet)         une page, puis ses PISTES : pour chaque sujet lié, les faits qui ont
                                créé le lien (la provenance de l'arête est la piste — le Memex)

Le modèle apporte le sens (il formule une requête courte) ; la FCM apporte la structure. Zéro appel
au modèle, déterministe, < 50 ms. Même moteur que le rappel de l'étape 6 (Rappeleur.activer).
"""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .moteur.score_utils import cab_pull
from .rappel import POIDS_CHAMP_BM25, Rappeleur, _rac
from .util import ajouter_ligne_jsonl, estimer_tokens

BUDGET_LIRE = 1200              # memoire_lire : page + pistes, en tokens
PISTES_MAX, FAITS_PAR_PISTE = 4, 2
BM25_MAX = 60
FAITS_MAX = 12                 # memoire_chercher : faits rendus au plus (pistes comprises)
RESERVE_PISTES = 2             # places gardées pour les pistes associatives du premier sujet
FACTEUR_SENS = 0.8             # B+ : un fait qui répond par le champ lexical de ses concepts, pas par son texte
PISTES_CONCEPT = 3             # B+ : faits d'autres pages, reliés par un concept partagé
# Saturation (docs/09 §14.5-14.7, 18/10) : l'ancienne note cab_pull(activation, 1, couverture) vaut ≈ 1 pour TOUS les
# faits d'un sujet nommé, quelle que soit la question (« les serpents de Jolene » → « la mère de Jolene… »).
# Le sujet dit OÙ chercher, la question dit QUOI prendre : cab_pull(couverture, 1, POIDS_SUJET × activation).
# cab_pull est symétrique : POIDS_SUJET = 1 redonne l'ancienne note exactement ; None aussi (pour comparer).
# 0,25 : vérifié au juge sur LoCoMo (docs/09 §14.7-14.8). Sur la mémoire de Nexa du 23-29/09 (petites pages), il
# coûte 5 souvenirs utiles sur 164 (docs/08 §13) : le choix pour Nexa est à faire avec Francis.
# « eventail » : poids = min(1, budget / faits du sujet) — l'activation se PARTAGE entre les faits du sujet (l'effet
# d'éventail d'Anderson, ACT-R) ; petite page = ancienne note, grande page = pas de saturation. Essayé : compromis.
POIDS_SUJET = 0.25
# Qui a parlé (docs/09 §14.8, 18/10 — Francis : « sinon comment l'agent peut savoir qui a parlé ? ») : chaque fait porte
# son `speaker`. Quand la question nomme une personne qui a parlé, les faits dits par QUELQU'UN D'AUTRE, et qui ne la
# nomment pas, sont tirés vers 0 (« Où Tim est-il allé ? » ne rend plus les randonnées de Joanna).
ATTENUATION_AUTRE = 0.5        # cab_pull(note, 0, ·) ; 0 : le speaker est ignoré
# Les intitulés des sections lues, les messages et les « pourquoi » sont dans le masque de langue (docs/10).


def _date(f: Dict) -> str:
    d = f.get("dit_le") or ""
    return f"{d[8:10]}/{d[5:7]}" if len(d) >= 10 else ""


def _personnes(m) -> set:
    """Les personnes qui ont parlé et qu'il faut nommer : un `speaker` qui a sa page, hors utilisateur et agent
    (implicites — chez Nexa aujourd'hui, presque tout est dit par Francis : rien à afficher, 0 token)."""
    p = getattr(m, "_personnes", None)
    if p is None:
        p = m._personnes = {s for f in m.faits if (s := f["meta"].get("speaker")) and s in m.fichiers and s not in m.implicites}
    return p


def _fait(f: Dict, m=None) -> Dict:
    sortie = {"fait": f["texte"], "dit_le": _date(f)} if _date(f) else {"fait": f["texte"]}
    s = f["meta"].get("speaker")
    if m is not None and s in _personnes(m):
        sortie["dit_par"] = m.titres.get(s, s)
    return sortie


class Lecteur:
    """Les outils de requête. Un par plugin ; lecture seule ; partage le cache du rappel."""

    def __init__(self, racine: Path, implicites=(), rappeleur: Optional[Rappeleur] = None):
        self.racine = Path(racine)
        self.r = rappeleur or Rappeleur(racine, implicites=implicites)

    def _journal(self, outil: str, entree: str, sortie: Dict, t0: float, maintenant: datetime) -> None:
        try:
            dossier = self.racine / "requetes"
            dossier.mkdir(parents=True, exist_ok=True)
            ajouter_ligne_jsonl(dossier / f"{maintenant.date().isoformat()}.jsonl", {
                "ts": maintenant.isoformat(timespec="seconds"), "outil": outil, "entree": entree[:200],
                "sujets": [x.get("sujet") for x in sortie.get("resultats", [])] or ([sortie["sujet"]] if sortie.get("sujet") else []),
                "tokens": sortie.get("tokens"), "latence_ms": round((time.perf_counter() - t0) * 1000, 2)})
        except Exception:
            pass                                               # un journal raté n'empêche pas de répondre

    # ── memoire_chercher ─────────────────────────────────────────────────
    def chercher(self, requete: str, nombre: int = 5, maintenant: Optional[datetime] = None,
                 faits_max: Optional[int] = None) -> Dict:
        """v2 (27/09, docs/08 D7) — le plein texte OUVRE la porte, la FCM vient APRÈS.

        Banc 8 : la v1, réglée pour le rappel à blanc (se taire est une qualité), rendait 42 % des
        souvenirs utiles contre 59 % au plein texte et 62 % aux embeddings. Quand Nexa DEMANDE une
        recherche, se taire devient un défaut. Donc : entrée par BM25 sur tous les faits (60, et non
        les 10 de la cascade), couverture NON élevée au carré, pas de seuil de nœud ; puis la
        propagation FCM classe et ajoute les sujets associés ; puis les PISTES du premier sujet
        (les faits qui créent ses liens) sont jointes — 17 souvenirs utiles que personne d'autre ne
        trouvait au banc."""
        t0 = time.perf_counter()
        maintenant = maintenant or datetime.now()
        m = self.r.memoire()
        if m is None:
            from . import langues
            return {"ok": False, "erreur": langues.de_la_memoire(self.racine).textes["memoire_pas_construite"]}
        T = m.masque.textes
        a = self.r.activer(m, requete)
        entrees, actives = a["entrees"], a["actives"]
        d_ref = max(1e-6, 1.0 - min(m.repos.values(), default=0.0))
        instant = maintenant.isoformat(timespec="minutes")
        # 1. Porte lexicale : BM25 sur les faits (60 premiers)
        bm25_rang: Dict[int, int] = {}
        mots = [w for w in a["pleins"] if len(w) >= 4]
        if mots:
            try:
                lignes = m.fts.execute("select rowid from f where f match ? order by bm25(f, 1.0, ?) limit ?",
                                       (" OR ".join(f'"{w}"' for w in mots), POIDS_CHAMP_BM25, BM25_MAX)).fetchall()
                bm25_rang = {i: k for k, (i,) in enumerate(lignes)}
            except Exception:
                bm25_rang = {}
        # 2. Candidats : sujets touchés par le plein texte, nommés, ou activés par propagation
        candidats = set(actives) | set(entrees) | {m.faits[i]["noeud"] for i in bm25_rang}
        # 3. Crédit de chaque fait, mot par mot de la requête (29/09, docs/08 §12) : 1 si le mot est dans
        #    son TEXTE ; sinon, s'il est dans le champ lexical d'un de ses concepts, FACTEUR_SENS × la
        #    spécificité de ce concept (un concept porté par 35 faits ne distingue aucun d'eux). Additif :
        #    le texte d'abord, le sens en complément — et non plus max(texte, sens), qui mettait à égalité
        #    tous les faits d'un grand concept, devant un fait portant le mot rare de la requête.
        poids, total = a["poids"], a["total"]
        pool = []
        # Ordre FIXE (27/10/2026) : parcourir l'ensemble dans l'ordre de Python changeait, d'un lancement à l'autre,
        # l'ordre des faits à note exactement égale (3 recherches sur 500, docs/13 §16) — une recherche doit se rejouer.
        for n in sorted(candidats):
            faits = [i for i in m.par_noeud.get(n, ()) if not (m.faits[i]["dit_le"] and m.faits[i]["dit_le"][:16] > instant)]
            act = min(1.0, actives.get(n, 0.0) / d_ref)
            for i in faits:
                f = m.faits[i]
                credit = {}
                for w in poids:
                    if w in f["racines"]:
                        credit[w] = 1.0
                    elif w in f["sem_spec"]:
                        credit[w] = FACTEUR_SENS * f["sem_spec"][w]
                if (n in m.implicites and not credit) or (not credit and act <= 0):
                    continue                                 # la fiche de l'utilisateur : seulement l'écho
                pool.append((n, i, act, credit, bm25_rang.get(i, 10 ** 6), f["dit_le"] or ""))
        # 4. Classement des faits : score, puis activation du sujet, rang BM25, les plus récents.
        #    (Essayé le 29/09 : une sélection à rendement décroissant, pour couvrir tous les mots de la
        #    requête. Elle PERD au banc 10 — 157 contre 164 —, le juge préfère la profondeur. Retirée.)
        # Les personnes nommées par la question et qui ont parlé ; les mots qui les nomment
        nommes = {x.split("→", 1)[1] for e in ("alias", "mot_alias") for x in a["etages"].get(e, ())}
        cible = nommes & _personnes(m) if ATTENUATION_AUTRE else set()
        mots_cible = {_rac(w) for al, ns in m.alias.items() if ns & cible for w in al} if cible else set()

        k_budget = max(1, min(int(faits_max or FAITS_MAX), 30))

        def note(c) -> float:
            couv = min(1.0, sum(poids[w] * v for w, v in c[3].items()) / total)
            if POIDS_SUJET is None:
                s = cab_pull(c[2], 1.0, couv)
            else:
                lam = min(1.0, k_budget / max(1, len(m.par_noeud.get(c[0], ())))) if POIDS_SUJET == "eventail" else POIDS_SUJET
                s = cab_pull(couv, 1.0, lam * c[2])
            if cible:
                f = m.faits[c[1]]
                if f["meta"].get("speaker") not in cible and not (mots_cible & f["racines"]):
                    s = cab_pull(s, 0.0, ATTENUATION_AUTRE)
            return s

        budget = max(1, min(int(faits_max or FAITS_MAX), 30))
        nmax = max(1, min(int(nombre or 5), 10))
        classes = sorted(pool, key=lambda c: c[5], reverse=True)                               # récents
        classes.sort(key=lambda c: (-round(note(c), 6), -round(actives.get(c[0], 0.0), 6), c[4]))  # score, activation, BM25
        ordre, sujets, deja = [], [], set()
        for c in classes:
            if len(ordre) >= budget:
                break
            sc, texte = note(c), m.faits[c[1]]["texte"]
            if sc <= 0 or texte in deja or (c[0] not in sujets and len(sujets) >= nmax):
                continue
            if c[0] not in sujets:
                sujets.append(c[0])
            ordre.append((sc, c[0], c[1])); deja.add(texte)
        # 5. Pistes (2 places) : l'association, à partir des faits TROUVÉS ; puis le reste du budget
        principaux = ordre[:max(1, budget - RESERVE_PISTES)]
        pistes_prevues = self._pistes_trouves(m, [i for _, _, i in principaux], sujets, {m.faits[i]["texte"] for _, _, i in principaux},
                                              instant, pool, note)[:RESERVE_PISTES]
        textes_pistes = {p["fait"] for p in pistes_prevues}
        places = budget - len(principaux) - len(pistes_prevues)
        retenus = principaux + [o for o in ordre[len(principaux):] if m.faits[o[2]]["texte"] not in textes_pistes][:max(0, places)]
        choisis = defaultdict(list)
        for sc, n, i in retenus:
            choisis[n].append((sc, i))
        deja = {m.faits[i]["texte"] for _, _, i in retenus}
        resultats = []
        for n in sujets:
            if not choisis[n]:
                continue
            score = choisis[n][0][0]
            if n in entrees and not any(x.endswith("→" + n) for x in a["etages"].get("plein_texte", [])):
                etage = next((e for e, lst in a["etages"].items() if any(x.endswith("→" + n) for x in lst)), "")
                pourquoi = {"alias": T["pourquoi_nomme"], "mot_alias": T["pourquoi_mot_proche"]}.get(etage, T["pourquoi_mots"])
            elif any(m.faits[i]["noeud"] == n for i in bm25_rang):
                pourquoi = T["pourquoi_mots"]
            else:
                source = max(((e, w) for e, w, _ in m.voisins.get(n, ()) if e in entrees or any(m.faits[i]["noeud"] == e for i in bm25_rang)),
                             key=lambda t: t[1], default=None)
                pourquoi = T["pourquoi_lie"].format(titre=m.titres.get(source[0], source[0])) if source else T["pourquoi_associe"]
            resultats.append({"sujet": n, "titre": m.titres.get(n, n), "score": round(score, 3),
                              "pourquoi": pourquoi, "faits": [_fait(m.faits[i], m) for _, i in choisis[n]]})
        sortie = {"ok": True, "requete": requete, "resultats": resultats}
        if resultats:
            pistes = [p for p in pistes_prevues if p["fait"] not in deja]
            if pistes:
                sortie["pistes"] = {"de": m.titres.get(sujets[0], sujets[0]), "faits": pistes}
        else:
            sortie["message"] = T["rien_de_lie"]
        if a["orphelins"]:
            sortie["mots_inconnus"] = a["orphelins"]
        sortie["tokens"] = estimer_tokens(str(sortie))
        self._journal("memoire_chercher", requete, sortie, t0, maintenant)
        return sortie

    def _pistes_trouves(self, m, trouves: List[int], sujets: List[str], exclure: set, instant: str, pool, note) -> List[Dict]:
        """Pistes 29/09 (docs/08 §12) — partir des faits TROUVÉS, pas de toute la page du premier sujet.

        0.7.0 suivait tous les concepts de la page du premier sujet ; quand c'était la fiche de
        l'utilisateur (liée à tout), « mécanicien » menait aux loisirs. Ici : les concepts des faits
        retenus, du plus partagé au plus spécifique ; pour chacun, un fait d'une AUTRE page qui le porte —
        le mieux noté pour la requête s'il est candidat, sinon le plus récent. Puis, s'il reste de la
        place, les faits qui créent les liens du premier sujet qui n'est pas l'utilisateur (le Memex)."""
        pages = {m.faits[i]["noeud"] for i in trouves}
        compte = defaultdict(int)
        for i in trouves:
            for c in m.faits[i].get("concepts", ()):
                compte[c] += 1
        notes = {c[1]: note(c) for c in pool}
        sortie = []
        for c in sorted(compte, key=lambda c: (-compte[c], -m.specificite.get(c, 0.0), c)):
            if len(sortie) >= PISTES_CONCEPT:
                break
            cands = [x for x, f in enumerate(m.faits) if c in f.get("concepts", ()) and f["noeud"] not in pages
                     and f["noeud"] not in m.implicites and f["texte"] not in exclure
                     and not (f["dit_le"] and f["dit_le"][:16] > instant)]
            if cands:
                x = max(cands, key=lambda x: (round(notes.get(x, 0.0), 6), m.faits[x]["dit_le"] or ""))
                exclure.add(m.faits[x]["texte"])
                noeud = m.faits[x]["noeud"]
                sortie.append({"sujet": noeud, "titre": m.titres.get(noeud, noeud), "via": m.titres.get("concept:" + c, c), **_fait(m.faits[x], m)})
        premier = next((s for s in sujets if s not in m.implicites), None)
        if premier:
            sortie += self._pistes(m, premier, exclure, instant)
        return sortie

    def _pistes(self, m, n: str, exclure: set, instant: str) -> List[Dict]:
        """Les faits qui créent les liens de `n` : pour chaque voisin (par force), les faits de SA page
        cités comme preuve de l'arête. Rend [{"sujet", "titre", "fait"}], du lien le plus fort au plus faible.
        (Les pistes par concept, qui partaient ici de toute la page, sont dans `_pistes_trouves` depuis le 29/09.)"""
        sortie = []
        for voisin, poids, preuves in [v for v in m.voisins.get(n, ()) if not v[0].startswith("concept:")][:PISTES_MAX]:
            if voisin in m.implicites:
                continue
            fichier = m.fichiers.get(voisin)
            vus = 0
            for p in preuves:
                for cote in (p, p.get("avec") or {}):
                    if vus >= FAITS_PAR_PISTE or cote.get("page") != fichier or not cote.get("fait"):
                        continue
                    f = next((x for x in m.faits if x["noeud"] == voisin and x["texte"].startswith(cote["fait"][:80])
                              and not (x["dit_le"] and x["dit_le"][:16] > instant)), None)
                    if f and f["texte"] not in exclure:
                        exclure.add(f["texte"]); vus += 1
                        sortie.append({"sujet": voisin, "titre": m.titres.get(voisin, voisin), **_fait(f, m)})
        return sortie

    # ── memoire_lire ─────────────────────────────────────────────────────
    def resoudre(self, m, sujet: str) -> Optional[str]:
        """Nom exact, slug, alias, ou meilleure entrée de la cascade (faute de frappe comprise)."""
        from . import pages as _pages
        s = _pages.slug(sujet)
        if s in m.par_noeud:
            return s
        a = self.r.activer(m, sujet)
        if a["entrees"]:
            return max(a["entrees"].items(), key=lambda t: (t[1], t[0]))[0]
        return None

    def lire(self, sujet: str, maintenant: Optional[datetime] = None) -> Dict:
        t0 = time.perf_counter()
        maintenant = maintenant or datetime.now()
        m = self.r.memoire()
        if m is None:
            from . import langues
            return {"ok": False, "erreur": langues.de_la_memoire(self.racine).textes["memoire_pas_construite"]}
        n = self.resoudre(m, sujet)
        if n is None:
            proches = self.chercher(sujet, 3, maintenant).get("resultats", [])
            return {"ok": False, "erreur": m.masque.textes["aucun_sujet"].format(sujet=sujet),
                    "suggestions": [r["sujet"] for r in proches]}
        instant = maintenant.isoformat(timespec="minutes")
        faits = [i for i in m.par_noeud.get(n, ()) if not (m.faits[i]["dit_le"] and m.faits[i]["dit_le"][:16] > instant)]
        budget = BUDGET_LIRE - 60
        sections = {}
        for cle, titre in m.masque.sections_lecture:     # les plus récents d'abord, jusqu'au budget
            ids = sorted((i for i in faits if m.faits[i]["section"] == cle),
                         key=lambda i: (m.faits[i]["dit_le"] or ""), reverse=True)
            garde = []
            for i in ids:
                cout = estimer_tokens(m.faits[i]["texte"]) + 4
                if cout > budget * 0.75 and garde:
                    break
                garde.append(_fait(m.faits[i], m)); budget -= cout
            if garde:
                sections[titre] = garde
        # Pistes : pour chaque voisin, les faits de SA page qui ont créé le lien (provenance de l'arête)
        pistes, textes_page = [], {m.faits[i]["texte"] for i in faits}
        for voisin, poids, preuves in m.voisins.get(n, ())[:PISTES_MAX]:
            if voisin in m.implicites:
                continue
            fichier = m.fichiers.get(voisin)
            vus, extraits = set(), []
            for p in preuves:
                for cote in (p, p.get("avec") or {}):
                    if cote.get("page") == fichier and cote.get("fait"):
                        complet = next((f["texte"] for f in m.faits if f["noeud"] == voisin and f["texte"].startswith(cote["fait"][:80])), None)
                        if complet and complet not in vus and complet not in textes_page:
                            vus.add(complet); extraits.append(complet)
            if not extraits:                                 # lien « nommé » depuis cette page : le fait le plus récent du voisin
                recents = sorted((i for i in m.par_noeud.get(voisin, ())), key=lambda i: m.faits[i]["dit_le"] or "", reverse=True)
                extraits = [m.faits[i]["texte"] for i in recents[:1]]
            extraits = extraits[:FAITS_PAR_PISTE]
            cout = sum(estimer_tokens(t) for t in extraits) + 8
            if cout > budget:
                break
            budget -= cout
            pistes.append({"sujet": voisin, "titre": m.titres.get(voisin, voisin), "lien": round(poids, 3),
                           "faits": extraits})
        sortie = {"ok": True, "sujet": n, "titre": m.titres.get(n, n), "fiche": m.fiches.get(n, ""),
                  "sections": sections, "pistes": pistes,
                  "nombre_de_faits": len(faits)}
        sortie["tokens"] = estimer_tokens(str(sortie))
        self._journal("memoire_lire", sujet, sortie, t0, maintenant)
        return sortie
