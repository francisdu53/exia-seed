"""Les pages — une page par nœud, quatre sections (spec §3.2).

Un nœud FCM = un fichier. La propagation (étape 5) rendra des nœuds ; les nœuds SONT les fichiers :
ni table de correspondance, ni fragments éparpillés à rassembler.

    pages/autoplus-rocheval.md
        ---  en-tête YAML : nœud, type, alias fr/en, dates, provenance, force
        ## Sémantique     faits durables          (oubli τ = 30 j)
        ## Épisodique     ce qui s'est passé      (τ = 7 j)
        ## Procédural     règles de conduite      (τ = 90 j)
        ## Prospectif     intentions, échéances   (jusqu'à l'échéance)

Chaque fragment est une ligne `- fait <!-- métadonnées -->`. Les métadonnées vivent dans le
commentaire : le moteur les lit, un humain lit le fait (spec §4.7 — moteur ≠ contrat).

Seule la consolidation écrit les pages (un seul écrivain). Les pages évoluent ; leur historique
est gardé par git et par pages/.chaine.jsonl.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

# Les quatre sections, dans l'ordre d'écriture. Leurs intitulés (« Sémantique », « Semantic »…) sont dans
# le masque de langue de la mémoire (docs/10) ; la lecture reconnaît ceux de TOUTES les langues.
CLES: List[str] = ["semantic", "episodic", "procedural", "prospective"]


def _titre_vers_cle() -> Dict[str, str]:
    from . import langues
    return {titre: cle for m in langues.tous() for cle, titre in m.sections_page}


def _masque(chemin: Path):
    from . import langues
    return langues.de_la_memoire(chemin.parent.parent)          # …/memoire/pages/x.md → …/memoire
TYPES_NOEUD = ("entite", "concept", "evenement", "etat_agent")
_RE_META = re.compile(r"\s*<!--(.*?)-->\s*$")
# Analyseur YAML compilé (libyaml) quand il existe : 2,6 s → quelques dixièmes pour 2 000 pages
# (mesuré le 26/09, étape 5). Même résultat que safe_load : chargeur « sûr » dans les deux cas.
_YAML = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def slug(noeud: str) -> str:
    """`Autoplus Rocheval` → `autoplus_rocheval` : sans accent, minuscules, tirets bas, 60 caractères max."""
    s = unicodedata.normalize("NFKD", noeud or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return re.sub(r"_+", "_", s)[:60]


def fichier_de(noeud: str) -> str:
    return slug(noeud).replace("_", "-") + ".md"


def _valeur_meta(v) -> str:
    """Valeur de métadonnée sans espace ni fermeture de commentaire : `Francis Babin` → `Francis_Babin`."""
    return re.sub(r"\s+", "_", str(v).replace("-->", "").replace("<!--", "")).strip("_")


def _norm(texte: str) -> str:
    return re.sub(r"\s+", " ", (texte or "").strip().lower())


class Page:
    def __init__(self, chemin: Path, entete: Dict, sections: Dict[str, List[str]]):
        self.chemin = chemin
        self.entete = entete
        self.sections = sections

    # ── lecture ────────────────────────────────────────────────────────────
    @classmethod
    def charger(cls, chemin: Path) -> "Page":
        texte = chemin.read_text(encoding="utf-8")
        entete: Dict = {}
        corps = texte
        if texte.startswith("---\n"):
            fin = texte.find("\n---\n", 4)
            if fin > 0:
                entete = yaml.load(texte[4:fin], Loader=_YAML) or {}
                corps = texte[fin + 5:]
        sections: Dict[str, List[str]] = {cle: [] for cle in CLES}
        courante: Optional[str] = None
        titres = _titre_vers_cle()
        for ligne in corps.splitlines():
            if ligne.startswith("## "):
                courante = titres.get(ligne[3:].strip())
            elif courante and ligne.startswith("- "):
                sections[courante].append(ligne)
        return cls(chemin, entete, sections)

    @classmethod
    def nouvelle(cls, dossier: Path, noeud: str, type_noeud: str, alias: Dict[str, List[str]],
                 date: str, modele: str) -> "Page":
        entete = {
            "node": slug(noeud),
            "node_type": type_noeud if type_noeud in TYPES_NOEUD else "concept",
            "aliases": {k: list(dict.fromkeys(v)) for k, v in (alias or {}).items() if v},
            "created": date, "updated": date,
            "consolidated_from": [], "consolidation_model": modele,
            "strength": 1.0,
        }
        return cls(dossier / fichier_de(noeud), entete, {cle: [] for cle in CLES})

    # ── écriture ───────────────────────────────────────────────────────────
    def contient(self, section: str, fait: str) -> bool:
        cible = _norm(fait)
        return any(_norm(_RE_META.sub("", l[2:])) == cible for l in self.sections.get(section, []))

    def ajouter(self, section: str, fait: str, meta: Dict) -> bool:
        """Ajoute un fragment ; rend False s'il y est déjà (idempotence)."""
        # Un fait vit sur UNE ligne, et ses métadonnées dans un commentaire HTML : un « --> » dans
        # le texte fermerait le commentaire trop tôt, un retour à la ligne couperait le fragment,
        # et un espace dans une valeur (« Francis Babin ») rendrait la relecture `clé:valeur`
        # ambiguë. Défauts trouvés à la revue du 23/09/2026.
        fait = re.sub(r"\s+", " ", (fait or "").replace("-->", "→").replace("<!--", "‹!--")).strip()
        if section not in self.sections or not fait or self.contient(section, fait):
            return False
        champs = " ".join(f"{k}:{_valeur_meta(v)}" for k, v in meta.items() if v not in (None, "", False, []))
        self.sections[section].append(f"- {fait.strip()} <!-- {champs} -->" if champs else f"- {fait.strip()}")
        return True

    def fusionner_alias(self, alias: Dict[str, List[str]]) -> None:
        actuels = self.entete.setdefault("aliases", {})
        for langue, liste in (alias or {}).items():
            actuels[langue] = list(dict.fromkeys((actuels.get(langue) or []) + [a for a in (liste or []) if a]))

    def titre(self) -> str:
        propres = (self.entete.get("aliases") or {}).get(_masque(self.chemin).code) or []
        return propres[0] if propres else self.entete.get("node", "").replace("_", " ").capitalize()

    def ecrire(self) -> None:
        entete = yaml.safe_dump(self.entete, allow_unicode=True, sort_keys=False, width=100).strip()
        blocs = [f"---\n{entete}\n---\n\n# {self.titre()}\n"]
        if self.entete.get("summary"):               # la fiche d'identité, lisible en tête (docs/12) — l'en-tête fait foi
            blocs.append(f"> {self.entete['summary']}\n")
        for cle, titre in _masque(self.chemin).sections_page:
            if self.sections.get(cle):
                blocs.append(f"## {titre}\n" + "\n".join(self.sections[cle]) + "\n")
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.chemin.with_suffix(".md.tmp")
        tmp.write_text("\n".join(blocs), encoding="utf-8")
        tmp.replace(self.chemin)

    def nb_fragments(self) -> Dict[str, int]:
        return {cle: len(self.sections.get(cle, [])) for cle in CLES}


def lister(dossier: Path) -> List[Page]:
    if not dossier.exists():
        return []
    pages = []
    for f in sorted(dossier.glob("*.md")):
        try:
            pages.append(Page.charger(f))
        except Exception:
            continue
    return pages


def index_alias(pages: List[Page]) -> Dict[str, str]:
    """alias normalisé → nœud, pour rattacher un nom déjà connu à son nœud existant."""
    table: Dict[str, str] = {}
    for p in pages:
        noeud = p.entete.get("node", "")
        table[slug(noeud)] = noeud
        for liste in (p.entete.get("aliases") or {}).values():
            for a in liste or []:
                table[slug(a)] = noeud
    return table
