"""L'interface d'un masque de langue. Une langue = une sous-classe qui remplit ces champs.

Inspiré de `BaseMask` d'EXIA GHOST V2.7.2 (`exia/linguistics/base_mask.py`), élargi : EXIA GHOST ne
masquait que la recherche ; ici, tout ce qui dépend d'une langue (lire, dater, compter, consolider,
répondre au modèle) passe par le masque.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Dict, FrozenSet, List, Optional, Pattern, Tuple


class Masque:
    # ── identité ───────────────────────────────────────────────────────────
    code: str = ""                       # ISO 639-1 : « fr », « en » — aussi la clé des alias et du thésaurus
    version: str = "1"                   # tracée dans la télémétrie (une mémoire sait avec quelles règles elle a été faite)
    autre: str = ""                      # la langue « seconde » des alias et des champs lexicaux (fr ↔ en)

    # ── mots ───────────────────────────────────────────────────────────────
    mots_vides: FrozenSet[str] = frozenset()             # contrôle de citation, champ appris, recherche
    mots_vides_recherche: FrozenSet[str] = frozenset()   # en plus, pour la recherche : mots interrogatifs, verbes d'ordre
    roles: FrozenSet[str] = frozenset()                  # mots qui désignent l'utilisateur ou l'agent (implicites, D5)
    re_milliers: Pattern[str] = re.compile(r"(?!)")      # séparateur de milliers, retiré avant de lire un nombre

    # ── temps ──────────────────────────────────────────────────────────────
    jours: List[str] = []                # lundi … dimanche (index = date.weekday())
    mois: List[str] = []                 # janvier … décembre
    mois_variantes: Dict[str, int] = {}  # graphies sans accent, abréviations
    nombres_lettres: Dict[str, int] = {} # « huit » → 8, « midi » → 12
    composes: Dict[str, int] = {}        # « dix-sept » → 17 (cherchés AVANT les simples)
    relatifs: List[Tuple[str, int]] = [] # (« après-demain », 2) … — du plus long au plus court
    semaine_prochaine: Optional[str] = None
    semaine_derniere: Optional[str] = None
    motif_jour_passe: str = r"(?!)"      # regex, {jour} remplacé : « lundi dernier », « last Monday »
    jour_nu_passe: bool = False          # un jour cité seul peut-il désigner le passé ? (fr : non — règle de Francis)
    prefixe_echeance: str = ""

    # ── consignes de mémoire (consignes.py) ────────────────────────────────
    re_retrait_precedent: Pattern[str] = re.compile(r"(?!)")
    re_hors_brut: Pattern[str] = re.compile(r"(?!)")
    re_annonce: Pattern[str] = re.compile(r"(?!)")

    # ── pages, lecture, textes lus par le modèle ou par un humain ─────────
    sections_page: List[Tuple[str, str]] = []
    sections_lecture: List[Tuple[str, str]] = []
    textes: Dict[str, str] = {}

    def __init__(self) -> None:
        alternatives = list(self.composes) + sorted(self.nombres_lettres, key=len, reverse=True)
        # Les composés d'abord (« dix-sept » avant « dix »), puis les simples du plus long au plus court
        self.re_nombres_lettres = re.compile(r"\b(" + "|".join(re.escape(a) for a in alternatives) + r")\b") \
            if alternatives else re.compile(r"(?!)")

    # ── temps : rendu ──────────────────────────────────────────────────────
    def en_clair(self, d: date) -> str:
        raise NotImplementedError

    def date_suffixe(self, d: date, heure: Optional[str]) -> str:
        raise NotImplementedError

    def entete_lot(self, d: date, fuseau: str) -> str:
        raise NotImplementedError

    # ── consolidation : la consigne au modèle ─────────────────────────────
    def consigne_consolidation(self, avec_agent: bool, exemple_locuteur: str) -> str:
        raise NotImplementedError

    def consigne_personnes(self, utilisateur: str, slug: str) -> str:
        """Précision ajoutée quand l'utilisateur est connu (une personne + un agent)."""
        raise NotImplementedError

    def consigne_fiches(self) -> str:
        """Consigne au modèle pour la fiche d'identité et les mots distinctifs de chaque page (docs/12)."""
        raise NotImplementedError

    def consigne_interlocuteurs(self, noms: List[str]) -> str:
        """Précision ajoutée quand la conversation est entre personnes, sans agent."""
        raise NotImplementedError

    def schemas_outils(self, utilisateur: str) -> Dict[str, Dict]:
        raise NotImplementedError
