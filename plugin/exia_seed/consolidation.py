"""La consolidation — le brut et le registre deviennent des pages (spec §6.2).

UN appel au modèle par lot. Tout le reste est déterministe : sélection des sources, contrôle de
citation, écriture des pages, index, journal, chaîne d'intégrité, git.

    lots de brut fermés + entrées du registre en attente
        │
        ├─ sources numérotées : raw/2026-09-22_01.md:12  |  registre:7807d69e
        ├─ nœuds existants (nom, type, alias) — pour que le modèle réutilise au lieu de dupliquer
        │
        ▼  1 appel LLM (effort bas) → JSON { fragments: [...] }
        │
        ├─ CONTRÔLE DE CITATION (zéro LLM) — un fragment est REJETÉ si :
        │     · il ne cite aucune source, ou une source qu'on ne lui a pas donnée
        │     · un NOMBRE du fait est absent des lignes citées   (un tarif ne s'invente pas)
        │     · un NOM PROPRE du fait est absent des lignes citées
        │     · il ne partage pas assez de mots pleins avec ses sources
        │     · il ne repose QUE sur des paroles de l'agent (jamais confirmées par l'utilisateur)
        │
        ├─ pages : création ou complément, idempotent (un fait déjà présent n'est pas redoublé)
        ├─ raw/.consolide.jsonl · registre.integre.jsonl   (ajout seul)
        ├─ INDEX.md (régénéré) · log.md (ajout seul) · pages/.chaine.jsonl · git commit
        └─ telemetrie/consolidations.jsonl : une ligne par passage

Un seul écrivain : un verrou non bloquant empêche deux consolidations simultanées.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from . import pages as _pages
from . import fiches as _fiches
from . import temps as _temps
from .ingestion import QUI_AVIS
from .registre import Registre
from .util import ajouter_ligne_jsonl, estimer_tokens, maintenant, sha256_fichier

AppelLLM = Callable[[List[Dict[str, str]]], str]

INDEX_FICHE = 110                # caractères de fiche dans INDEX.md : l'index reste à sa taille, la page a le reste
SECTIONS_VALIDES = set(_pages.CLES)
# Mots vides, mots de rôle, séparateur de milliers, consigne au modèle : dans le masque de langue de la
# mémoire (docs/10, `langues/`). Aucune donnée linguistique ici.


def _m(m):
    if m is not None:
        return m
    from . import langues
    return langues.masque(langues.DEFAUT)


# ── outils de texte ─────────────────────────────────────────────────────────
def _mots_pleins(texte: str, m=None) -> List[str]:
    m = _m(m)
    texte = m.re_milliers.sub("", texte or "")          # « 1 200 » est un mot, pas deux (R3, 27/09)
    return [x for x in re.findall(r"[a-zà-ÿ0-9]+", texte.lower())
            if (x.isdigit() or len(x) >= 3) and x not in m.mots_vides]


def _nombres(texte: str, m=None) -> List[str]:
    """Les nombres d'un texte, séparateurs de milliers retirés : « 12 345 € » et « 12345€ » donnent
    tous deux 12345. Défaut trouvé le 27/09 (revue des rejets) : le modèle écrit « 12 345 € » quand
    Francis a écrit « 12345€ » — le contrôle voyait « 38 » et « 512 », et rejetait un fait VRAI."""
    return re.findall(r"\d+(?:[.,]\d+)?", _m(m).re_milliers.sub("", texte or ""))


def _noms_propres(texte: str) -> List[str]:
    """Mots à majuscule hors début de phrase — prénoms, marques, villes."""
    noms = []
    for phrase in re.split(r"(?<=[.!?:;])\s+", (texte or "").strip()):
        mots = re.findall(r"[A-ZÀ-Ý][a-zà-ÿA-ZÀ-Ý-]{2,}", phrase)
        premier = re.match(r"\W*([A-ZÀ-Ý][a-zà-ÿA-ZÀ-Ý-]{2,})", phrase)
        if premier and mots and mots[0] == premier.group(1):
            mots = mots[1:]
        noms.extend(mots)
    return noms


def _plat(texte: str) -> str:
    """Minuscules, trait d'union et apostrophe = espace : « Météo-France » se retrouve dans « météo france ».
    Faux rejet trouvé chez Nexa le 28/10 : Francis tape le nom sans trait d'union, le modèle l'écrit avec."""
    return " ".join(re.split(r"[\s\-‐‑–'’]+", (texte or "").lower()))


def _racine(mot: str) -> str:
    return mot[:5]


class Consolidateur:
    def __init__(self, racine: Path, tz, appel_llm: AppelLLM, *, modele: str = "",
                 max_tokens_entree: int = 40000, nom_agent: str = "assistant", nom_utilisateur: str = "",
                 interlocuteurs=(), fiches: bool = True):
        self.racine = racine
        self.fiches = fiches
        self.tz = tz
        self.appel_llm = appel_llm
        self.modele = modele or "inconnu"
        self.max_tokens = max(4000, int(max_tokens_entree))
        self.nom_agent = nom_agent
        self.nom_utilisateur = nom_utilisateur
        # Conversation entre personnes, sans agent (LoCoMo, docs/09) : nom_agent vide, et la liste des
        # interlocuteurs — implicites comme l'utilisateur dans tout ce qu'ils disent.
        self.interlocuteurs = [n for n in (interlocuteurs or ()) if n]
        from . import langues
        self.masque = langues.de_la_memoire(racine)
        self.raw = racine / "raw"
        self.dossier_pages = racine / "pages"
        self.registre = Registre(racine, tz)
        self._consolide = self.raw / ".consolide.jsonl"
        self._verrou = racine / ".verrou-consolidation"

    # ── ce qui attend ──────────────────────────────────────────────────────
    def lots_en_attente(self) -> List[str]:
        chaine = self.raw / ".chaine.jsonl"
        if not chaine.exists():
            return []
        faits = set()
        if self._consolide.exists():
            faits = {json.loads(l)["fichier"] for l in self._consolide.read_text(encoding="utf-8").splitlines() if l.strip()}
        lots = [json.loads(l)["fichier"] for l in chaine.read_text(encoding="utf-8").splitlines() if l.strip()]
        return [f for f in lots if f not in faits and (self.raw / f).exists()]

    # ── le passage complet ─────────────────────────────────────────────────
    def consolider(self) -> Dict:
        self.racine.mkdir(parents=True, exist_ok=True)
        with open(self._verrou, "a+") as verrou:
            try:
                fcntl.flock(verrou, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {"statut": "deja_en_cours"}
            try:
                return self._consolider()
            finally:
                fcntl.flock(verrou, fcntl.LOCK_UN)

    def _consolider(self) -> Dict:
        t0 = time.monotonic()
        now = maintenant(self.tz)
        lots_attente = self.lots_en_attente()
        notes = self.registre.en_attente()
        if not lots_attente and not notes:
            return {"statut": "rien"}

        # 1. Sources, dans la limite du budget
        sources: Dict[str, Tuple[str, bool]] = {}      # réf → (texte, dit_par_agent)
        ancres: Dict[str, str] = {}                    # réf → moment où la ligne a été dite (R2)
        blocs, lots, budget = [], [], self.max_tokens
        for f in lots_attente:
            lignes = self._lignes_de(f)
            cout = sum(estimer_tokens(t) for _, t in lignes) + 50
            if lots and cout > budget:
                break                                  # le reste au prochain passage
            lots.append(f)
            budget -= cout
            jour_lot, ouverture = self._date_du_lot(f)
            if jour_lot:
                blocs.append(f"── raw/{f} : {self.masque.entete_lot(jour_lot, getattr(self.tz, 'key', ''))}")
            entete_message = ""                        # un message sur plusieurs lignes : l'heure est
            for n, t in lignes:                        # sur la première, les suivantes en héritent
                ref = f"raw/{f}:{n}"
                if re.match(r"\[\d\d:\d\d ", t):
                    entete_message = t
                # Qui parle : l'EN-TÊTE du message, pas la ligne — la 2e ligne d'un message de l'agent est encore
                # l'agent (défaut trouvé le 16/10 ; 0 fait concerné, le filet avait un trou). « systeme » = un avis.
                # Sans agent (conversation entre personnes, docs/10) : personne n'est « l'agent ».
                parleurs = "|".join(re.escape(x) for x in (self.nom_agent, QUI_AVIS) if x)
                sources[ref] = (t, bool(re.match(rf"\[\d\d:\d\d (?:{parleurs})\]", entete_message or t)))
                if jour_lot:
                    ancres[ref] = _temps.dit_le(jour_lot, ouverture, entete_message or t)
                blocs.append(f"[{ref}] {t}")
        for e in notes:
            ref = f"registre:{e['id']}"
            sources[ref] = (e["texte"], False)
            if re.match(r"\d{4}-\d{2}-\d{2}", str(e.get("date") or "")):
                ancres[ref] = str(e["date"])[:16]
            blocs.append(f"[{ref}] ({e['privacy']}) {e['texte']}")

        # Un lot sans aucune ligne de conversation (seulement des repères : consigne « ne note
        # pas ça », compression, ou tout retiré) ne justifie pas un appel au modèle. Défaut trouvé
        # à la revue du 23/09/2026 : la fermeture forcée de 23h55 pouvait produire un tel lot.
        if not any(b.startswith("[") for b in blocs):
            for f in lots:
                ajouter_ligne_jsonl(self._consolide, {"fichier": f, "lot": "vide",
                                                      "ts": now.isoformat(timespec="seconds")})
            self._journaliser_passage(now, lots, notes, [], [], [], 0, 0, t0, statut="vide")
            return {"statut": "vide", "lots": lots}

        existantes = _pages.lister(self.dossier_pages)
        catalogue = "\n".join(
            f"- {p.entete.get('node')} ({p.entete.get('node_type')}) : "
            + ", ".join(a for l in (p.entete.get("aliases") or {}).values() for a in (l or []))
            for p in existantes) or self.masque.textes["aucun"]
        systeme = self.masque.consigne_consolidation(
            avec_agent=bool(self.nom_agent),
            exemple_locuteur=self.nom_utilisateur or (self.interlocuteurs[0].lower() if self.interlocuteurs else ""))
        if self.nom_utilisateur:
            systeme += self.masque.consigne_personnes(self.nom_utilisateur, _pages.slug(self.nom_utilisateur))
        elif self.interlocuteurs:
            systeme += self.masque.consigne_interlocuteurs(self.interlocuteurs)
        # B+ (docs/08 §8) : les concepts existants, avec le début de leur champ lexical, pour être réutilisés
        from . import graphe as _graphe
        thesaurus = _graphe.charger_thesaurus(self.racine)
        T = self.masque.textes
        concepts_txt = "\n".join(f"- {c} : {', '.join((v.get(self.masque.code) or [])[:4])}"
                                 for c, v in sorted((thesaurus.get("concepts") or {}).items())) or T["aucun"]
        messages = [{"role": "system", "content": systeme},
                    {"role": "user", "content": f"{T['noeuds_existants']}\n{catalogue}\n\n{T['concepts_existants']}\n{concepts_txt}"
                                                f"\n\n{T['sources']}\n" + "\n".join(blocs)}]
        tokens_entree = sum(estimer_tokens(m["content"]) for m in messages)

        # 2. L'appel
        reponse = self.appel_llm(messages)
        fragments = self._extraire(reponse)
        nouveaux_concepts = self._concepts_nouveaux(reponse, self.masque)
        concepts_connus = set((thesaurus.get("concepts") or {})) | set(nouveaux_concepts)
        concepts_utilises = set()
        if fragments is None:
            self._journaliser_passage(now, lots, notes, [], [("reponse", "JSON illisible")], [], tokens_entree,
                                      estimer_tokens(reponse or ""), t0, statut="echec_json")
            return {"statut": "echec_json", "extrait": (reponse or "")[:300]}

        # 3. Contrôle, puis écriture
        alias_vers_noeud = _pages.index_alias(existantes)
        par_noeud: Dict[str, _pages.Page] = {p.entete.get("node"): p for p in existantes}
        acceptes, rejetes, creees, cites, dates_retirees = [], [], [], {}, []
        date = now.date().isoformat()
        lot_id = f"{date}_{now.strftime('%H%M%S')}"
        for frag in fragments:
            ok, raison = self._controler(frag, sources)
            if not ok:
                rejetes.append((frag.get("fait", "")[:120], raison))
                continue
            noeud = alias_vers_noeud.get(_pages.slug(frag["noeud"])) or _pages.slug(frag["noeud"])
            page = par_noeud.get(noeud)
            if page is None:
                page = _pages.Page.nouvelle(self.dossier_pages, noeud, frag.get("type_noeud", "concept"),
                                            frag.get("alias") or {}, date, self.modele)
                par_noeud[noeud] = page
                creees.append(noeud)
                for a in [noeud] + [x for l in (frag.get("alias") or {}).values() for x in (l or [])]:
                    alias_vers_noeud[_pages.slug(a)] = noeud
            else:
                page.fusionner_alias(frag.get("alias") or {})
            # R2 — le temps : dit_le par le code, event_time/echeance vérifiés, date en clair ajoutée
            cles = [c for r in frag["src"] for c in self._deplier(str(r)) if c in sources]
            moments = sorted(ancres[c] for c in cles if c in ancres)
            moment = moments[0] if moments else None
            jour = _temps._lire(moment)[0] if moment else None
            cite = " ".join(_temps.sans_horodatage(sources[c][0]) for c in cles)
            quand, retrait_q = _temps.verifier(frag.get("event_time"), cite, jour, self.masque)
            echeance, retrait_e = _temps.verifier(frag.get("echeance"), cite, jour, self.masque)
            for r in (retrait_q, retrait_e):
                if r:
                    dates_retirees.append((frag["fait"][:120], r))
            fait = frag["fait"].rstrip(" .")
            fait = (fait + _temps.suffixe(fait, quand, m=self.masque)
                    + (_temps.suffixe(fait, echeance, self.masque.prefixe_echeance, self.masque) if echeance and echeance != quand else "")
                    + ".")
            meta = {"conf": frag.get("conf"), "src": ",".join(frag["src"]), "dit_le": moment,
                    "event_time": quand, "echeance": echeance,
                    "speaker": frag.get("speaker"),
                    "privacy": frag.get("privacy") if frag.get("privacy") in ("personnel", "confidentiel") else None,
                    "protected": "true" if frag.get("protected") else None, "lot": lot_id}
            # B+ : 1 à 3 concepts, connus ou définis dans ce passage ; un concept sans définition est ignoré
            cs = [c for c in dict.fromkeys(_pages.slug(str(x)) for x in (frag.get("concepts") or [])) if c in concepts_connus][:3]
            if cs:
                meta["concepts"] = ",".join(cs)
                concepts_utilises.update(cs)
            if page.ajouter(frag["section"], fait, meta):
                page.entete["updated"] = date
                prov = page.entete.setdefault("consolidated_from", [])
                for s in frag["src"]:
                    base = s.split(":")[0] + (":" + s.split(":")[1] if s.startswith("registre") else "")
                    if base not in prov:
                        prov.append(base)
                acceptes.append((noeud, frag["section"], fait))
                for s in frag["src"]:
                    if s.startswith("registre:"):
                        cites[s.split(":", 1)[1]] = page.chemin.name
        for p in par_noeud.values():
            if p.chemin.exists() or any(p.sections.values()):
                p.ecrire()
        # Fiches d'identité (docs/12) : les pages touchées par ce passage, réécrites depuis la page ENTIÈRE.
        # Un second appel, court ; une panne laisse les anciennes fiches (partiel > rien).
        rapport_fiches = None
        if self.fiches and acceptes:
            touchees = [par_noeud[n] for n in dict.fromkeys(a[0] for a in acceptes) if n in par_noeud]
            try:
                rf = _fiches.rediger(touchees, self.appel_llm, date, connus=(self.nom_utilisateur, self.nom_agent))
                rapport_fiches = {k: rf[k] for k in ("statut", "demandees", "ecrites", "inchangees", "absentes",
                                                     "appels", "tokens_entree", "tokens_sortie")}
                rapport_fiches["refusees"] = [{"noeud": x[0], "raison": x[1]} for x in rf["refusees"]]
            except Exception as e:
                rapport_fiches = {"statut": "echec", "erreur": f"{type(e).__name__}: {e}"[:200]}

        # 4. Registres d'avancement, index, journal, intégrité
        for f in lots:
            ajouter_ligne_jsonl(self._consolide, {"fichier": f, "lot": lot_id, "ts": now.isoformat(timespec="seconds")})
        for e in notes:
            self.registre.marquer_integre(e["id"], cites.get(e["id"], ""), lot_id)
        self._ecrire_index()
        self._ecrire_log(date, lot_id, lots, notes, acceptes, rejetes, creees)
        # B+ : le thésaurus s'enrichit des concepts nouveaux EFFECTIVEMENT utilisés (un seul écrivain)
        ajouts = {c: v for c, v in nouveaux_concepts.items() if c in concepts_utilises and c not in (thesaurus.get("concepts") or {})}
        if ajouts:
            thesaurus.setdefault("concepts", {}).update(ajouts)
            _graphe.enregistrer_thesaurus(self.racine, thesaurus)
        # Étape 5 : le graphe est recalculé depuis les pages (fonction des pages, zéro appel au modèle).
        # Un échec n'annule pas la consolidation : les pages sont écrites, il sera recalculé au
        # passage suivant (panne = dégradation).
        try:
            from . import graphe as _graphe
            g = _graphe.calculer(self.racine, implicites=(self.nom_utilisateur, self.nom_agent, *self.interlocuteurs))
            graphe_resume = {k: g.get(k) for k in ("statut", "noeuds", "aretes", "duree_ms", "alerte")}
        except Exception as e:
            graphe_resume = {"statut": "echec", "erreur": f"{type(e).__name__}: {e}"[:200]}
        self._chainer_pages(lot_id, now)
        git = self._git_commit(f"consolidation {lot_id} — {len(acceptes)} faits, {len(creees)} nouveaux nœuds")
        rapport = self._journaliser_passage(now, lots, notes, acceptes, rejetes, creees, tokens_entree,
                                            estimer_tokens(reponse or ""), t0, statut="ok", git=git,
                                            dates_retirees=dates_retirees, graphe=graphe_resume, fiches=rapport_fiches)
        return rapport

    # ── contrôle de citation ───────────────────────────────────────────────
    def _controler(self, frag: Dict, sources: Dict[str, Tuple[str, bool]]) -> Tuple[bool, str]:
        fait = str(frag.get("fait") or "").strip()
        if not fait:
            return False, "fait vide"
        if frag.get("section") not in SECTIONS_VALIDES:
            return False, f"section inconnue : {frag.get('section')}"
        if not _pages.slug(str(frag.get("noeud") or "")):
            return False, "nœud absent"
        refs = frag.get("src") or []
        if isinstance(refs, str):
            refs = [refs]
        textes, que_agent = [], True
        for r in refs:
            for cle in self._deplier(str(r)):
                if cle in sources:
                    textes.append(_temps.sans_horodatage(sources[cle][0]))
                    que_agent = que_agent and sources[cle][1]
        if not textes:
            return False, "aucune source valide citée"
        cite = " ".join(textes)
        if que_agent:
            return False, "repose seulement sur des paroles de l'agent"
        m = self.masque
        nombres_cites = set(_nombres(cite, m)) | _temps.nombres_en_lettres(cite, m)
        for n in _nombres(fait, m):
            if n not in nombres_cites:
                return False, f"nombre absent des sources : {n}"
        cite_bas = _plat(cite)
        # Le nom de l'utilisateur et celui de l'agent sont implicites dans tout ce qu'ils disent :
        # « demande à Francis de regrouper les visites » ne cite pas « Francis », et c'est normal.
        # Défaut trouvé sur GPT-6 le 22/09 : la contrainte personnelle était rejetée, donc perdue.
        connus = {n.lower() for n in (self.nom_utilisateur, self.nom_agent, *self.interlocuteurs) if n}
        for nom in _noms_propres(fait):
            if nom.lower() in connus:
                continue
            if _plat(nom) not in cite_bas:
                return False, f"nom propre absent des sources : {nom}"
        # L'utilisateur, l'agent, et les mots qui les désignent sont implicites dans tout ce qui se dit :
        # ils ne comptent ni pour ni contre (D5). Régression trouvée le 27/09 : depuis que R2 retire
        # l'horodatage « [12:20 francis] » des sources, « Francis autorise… » comptait CONTRE le fait.
        implicites = {x.lower() for x in connus} | m.roles
        mots_fait = {x for x in _mots_pleins(fait, m) if x not in implicites}
        racines_cite = {_racine(x) for x in _mots_pleins(cite, m)}
        communs = [x for x in mots_fait if _racine(x) in racines_cite]
        minimum = 1 if len(mots_fait) <= 3 else 2
        if len(communs) < minimum or (mots_fait and len(communs) / len(mots_fait) < 0.4):
            return False, f"trop peu de mots en commun avec les sources ({len(communs)}/{len(mots_fait)})"
        frag["src"] = [str(r) for r in refs]
        return True, ""

    @staticmethod
    def _deplier(ref: str) -> List[str]:
        """`raw/x.md:12-14` → [raw/x.md:12, :13, :14] ; `registre:ab12cd34` → tel quel."""
        ref = ref.strip().strip("[]")
        m = re.match(r"^(raw/[^:]+):(\d+)(?:-(\d+))?$", ref)
        if m:
            a, b = int(m.group(2)), int(m.group(3) or m.group(2))
            if b < a or b - a > 50:
                return []
            return [f"{m.group(1)}:{n}" for n in range(a, b + 1)]
        return [ref] if ref.startswith("registre:") else []

    # ── lecture du brut ────────────────────────────────────────────────────
    def _retraits(self) -> Dict[str, set]:
        """Lignes retirées par l'utilisateur, par fichier — `raw/.retraits.jsonl` fait autorité."""
        sortie: Dict[str, set] = {}
        chemin = self.raw / ".retraits.jsonl"
        if chemin.exists():
            for ligne in chemin.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(ligne)
                    a, b = r["lignes"]
                    sortie.setdefault(r["fichier"], set()).update(range(int(a), int(b) + 1))
                except Exception:
                    continue
        return sortie

    def _date_du_lot(self, fichier: str) -> Tuple[Optional["date"], Optional[str]]:
        """(jour d'ouverture du lot, « HH:MM » d'ouverture) depuis son en-tête ; à défaut, son nom."""
        from datetime import date as _date
        tete = (self.raw / fichier).read_text(encoding="utf-8")[:600]
        m = re.search(r"^date:\s*(\d{4})-(\d{2})-(\d{2})", tete, re.M) or re.match(r"(\d{4})-(\d{2})-(\d{2})", fichier)
        o = re.search(r"^ouvert_le:\s*\S+T(\d\d:\d\d)", tete, re.M)
        try:
            return (_date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None,
                    o.group(1) if o else None)
        except ValueError:
            return None, None

    def _lignes_de(self, fichier: str) -> List[Tuple[int, str]]:
        """Lignes de conversation d'un lot, avec leur numéro RÉEL dans le fichier (1-based).

        Les lignes retirées par l'utilisateur (« oublie ce que je viens de dire », « ne note pas
        ça » rétrospectif) restent dans le fichier mais ne sont jamais montrées au modèle.
        """
        retirees = self._retraits().get(fichier, set())
        sortie, dans_echanges = [], False
        for n, ligne in enumerate((self.raw / fichier).read_text(encoding="utf-8").splitlines(), start=1):
            if ligne.startswith("## Échanges"):
                dans_echanges = True
                continue
            if dans_echanges and ligne.strip() and not ligne.lstrip().startswith("<!--") and n not in retirees:
                sortie.append((n, ligne))
        return sortie

    @staticmethod
    def _extraire(reponse: str) -> Optional[List[Dict]]:
        if not reponse:
            return None
        debut, fin = reponse.find("{"), reponse.rfind("}")
        if debut < 0 or fin <= debut:
            return None
        try:
            donnees = json.loads(reponse[debut:fin + 1])
        except json.JSONDecodeError:
            return Consolidateur._sauver(reponse)
        frags = donnees.get("fragments") if isinstance(donnees, dict) else None
        return [f for f in frags if isinstance(f, dict)] if isinstance(frags, list) else None

    @staticmethod
    def _sauver(reponse: str) -> Optional[List[Dict]]:
        """JSON illisible (sortie coupée par la limite de longueur, ou virgule / guillemet de travers) : on garde les
        fragments COMPLETS écrits avant l'erreur, au lieu de jeter la session entière. Trouvé par LongMemEval le
        27/10/2026 (docs/13 §14.4) : 2 à 6 sessions sur ≈ 380 perdues ainsi, davantage quand la consigne demande plus de
        faits. Les fragments sauvés passent le même contrôle de citation que les autres."""
        m = re.search(r'"fragments"\s*:\s*\[', reponse)
        if not m:
            return None
        dec, pos, sortie = json.JSONDecoder(), m.end(), []
        while True:
            while pos < len(reponse) and reponse[pos] in " \t\r\n,":
                pos += 1
            if pos >= len(reponse) or reponse[pos] != "{":
                break
            try:
                obj, pos = dec.raw_decode(reponse, pos)
            except json.JSONDecodeError:
                break
            if isinstance(obj, dict):
                sortie.append(obj)
        return sortie or None

    @staticmethod
    def _concepts_nouveaux(reponse: str, m=None) -> Dict[str, Dict]:
        """B+ : les concepts nouveaux proposés, avec leur champ lexical (langue de la mémoire ≤ 12, l'autre ≤ 6)."""
        m = _m(m)
        debut, fin = (reponse or "").find("{"), (reponse or "").rfind("}")
        try:
            donnees = json.loads(reponse[debut:fin + 1]) if debut >= 0 and fin > debut else {}
        except json.JSONDecodeError:
            return {}
        sortie = {}
        for c, v in ((donnees.get("concepts_nouveaux") if isinstance(donnees, dict) else None) or {}).items():
            s = _pages.slug(str(c))
            if s and isinstance(v, dict):
                sortie[s] = {m.code: [str(x) for x in (v.get(m.code) or [])][:12], m.autre: [str(x) for x in (v.get(m.autre) or [])][:6]}
        return sortie

    # ── index, journal, intégrité ──────────────────────────────────────────
    def _ecrire_index(self) -> None:
        lignes = [self.masque.textes["index"]]
        for p in _pages.lister(self.dossier_pages):
            n = p.nb_fragments()
            fiche = str(p.entete.get("summary") or "").replace("|", "/")
            alias = ((fiche[:INDEX_FICHE].rsplit(" ", 1)[0] + " …" if len(fiche) > INDEX_FICHE else fiche)
                     or ", ".join(a for l in (p.entete.get("aliases") or {}).values() for a in (l or []))[:80])
            lignes.append(f"| [{p.entete.get('node')}](pages/{p.chemin.name}) | {p.entete.get('node_type')} | {alias} "
                          f"| {n['semantic']}/{n['episodic']}/{n['procedural']}/{n['prospective']} | {p.entete.get('updated')} |")
        (self.racine / "INDEX.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")

    def _ecrire_log(self, date, lot_id, lots, notes, acceptes, rejetes, creees) -> None:
        chemin = self.racine / "log.md"
        T = self.masque.textes
        entete = "" if chemin.exists() else T["log_entete"]
        detail = [T["log_passage"].format(date=date, lot=lot_id),
                  T["log_sources"].format(lots=len(lots), notes=len(notes)),
                  T["log_faits"].format(faits=len(acceptes), noeuds=len(creees))
                  + (f" : {', '.join(creees)}" if creees else ""),
                  T["log_rejets"].format(rejets=len(rejetes))]
        detail += [f"  - « {f} » → {r}" for f, r in rejetes]
        with open(chemin, "a", encoding="utf-8") as fh:
            fh.write(entete + "\n".join(detail) + "\n")

    def _chainer_pages(self, lot_id: str, now) -> None:
        chaine = self.dossier_pages / ".chaine.jsonl"
        self.dossier_pages.mkdir(parents=True, exist_ok=True)
        precedent = "genese"
        if chaine.exists():
            dernieres = chaine.read_text(encoding="utf-8").strip().splitlines()
            if dernieres:
                precedent = json.loads(dernieres[-1])["empreinte"]
        etat = {f.name: sha256_fichier(f) for f in sorted(self.dossier_pages.glob("*.md"))}
        empreinte = "sha256:" + hashlib.sha256(json.dumps([precedent, etat], sort_keys=True).encode()).hexdigest()
        ajouter_ligne_jsonl(chaine, {"lot": lot_id, "ts": now.isoformat(timespec="seconds"),
                                     "pages": etat, "precedent": precedent, "empreinte": empreinte})

    def _git_commit(self, message: str) -> str:
        def git(*args):
            return subprocess.run(["git", "-C", str(self.racine), *args], capture_output=True, text=True, timeout=30)
        try:
            if not (self.racine / ".git").exists():
                git("init", "-q")
                (self.racine / ".gitignore").write_text(
                    ".verrou*\n*.tmp\nraw/.etat.json\nraw/.dernier_tour.json\n", encoding="utf-8")
            # Un arrêt brutal pendant un commit (redémarrage de la passerelle) laisse
            # .git/index.lock : tous les commits suivants échoueraient en silence. On ne le retire
            # que s'il a plus de dix minutes — aucun commit légitime ne dure aussi longtemps.
            verrou_git = self.racine / ".git" / "index.lock"
            if verrou_git.exists() and time.time() - verrou_git.stat().st_mtime > 600:
                verrou_git.unlink()
            git("add", "-A")
            r = git("-c", "user.name=EXIA SEED", "-c", "user.email=exia-seed@localhost", "commit", "-q", "-m", message)
            if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
                return "erreur: " + (r.stderr or r.stdout).strip()[:120]
            return git("rev-parse", "--short", "HEAD").stdout.strip() or "ok"
        except Exception as e:
            return f"git indisponible: {e}"[:120]

    def _journaliser_passage(self, now, lots, notes, acceptes, rejetes, creees, tok_in, tok_out, t0,
                             statut: str, git: str = "", dates_retirees=(), graphe=None, fiches=None) -> Dict:
        rapport = {"ts": now.isoformat(timespec="seconds"), "statut": statut, "modele": self.modele,
                   "langue": f"{self.masque.code}/{self.masque.version}",
                   "lots": lots, "notes": len(notes), "faits_retenus": len(acceptes),
                   "fragments_rejetes": len(rejetes), "noeuds_crees": creees,
                   "tokens_entree_estimes": tok_in, "tokens_sortie_estimes": tok_out,
                   "duree_s": round(time.monotonic() - t0, 1), "git": git,
                   "rejets": [{"fait": f, "raison": r} for f, r in rejetes],
                   "dates_retirees": [{"fait": f, "raison": r} for f, r in dates_retirees],
                   "graphe": graphe, "fiches": fiches}
        dossier = self.racine / "telemetrie"
        dossier.mkdir(parents=True, exist_ok=True)
        ajouter_ligne_jsonl(dossier / "consolidations.jsonl", rapport)
        return rapport


def appel_llm_hermes(effort: str = "low", timeout: float = 300.0) -> AppelLLM:
    """Appel via le client auxiliaire d'Hermès, avec le fournisseur et le modèle PRINCIPAUX de
    l'agent passés explicitement : même lancée hors de la passerelle, la consolidation ne peut pas
    partir sur un autre abonnement."""
    def appeler(messages: List[Dict[str, str]]) -> str:
        from agent.auxiliary_client import call_llm, extract_content_or_reasoning
        from hermes_cli.config import load_config
        from hermes_constants import parse_reasoning_effort
        modele_cfg = (load_config() or {}).get("model") or {}
        rep = call_llm(task="exia_seed_consolidation",
                       provider=modele_cfg.get("provider") or None,
                       model=modele_cfg.get("default") or None,
                       messages=messages, reasoning_config=parse_reasoning_effort(effort), timeout=timeout)
        return extract_content_or_reasoning(rep)
    return appeler


def modele_principal() -> str:
    try:
        from hermes_cli.config import load_config
        return ((load_config() or {}).get("model") or {}).get("default") or ""
    except Exception:
        return ""
