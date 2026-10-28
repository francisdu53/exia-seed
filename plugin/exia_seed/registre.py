"""Le registre — « note ça », disponible tout de suite (spec §6.4).

Décision de Francis, 20/09/2026 : l'agent n'écrit JAMAIS directement dans une page. Deux écrivains
sur les pages = conflits et dérive. Il écrit dans un registre en AJOUT SEUL ; la consolidation
range ensuite chaque entrée dans le bon nœud.

  registre.md              les entrées, lisibles par un humain — jamais réécrit
  registre.integre.jsonl   quelles entrées ont été rangées, et où — jamais réécrit

L'intégration est notée dans un journal à part plutôt que dans le registre lui-même : marquer une
entrée « intégrée » en la modifiant violerait l'ajout seul.

Deux sources alimentent le registre :
  - l'outil `memoire_noter`, appelé par l'agent (sur demande ou de sa propre initiative) ;
  - les écritures de la mémoire native d'Hermès (crochet `on_memory_write`), recopiées ici pour
    que rien de ce que l'agent retient ne reste hors d'EXIA SEED.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from .util import ajouter_ligne_jsonl, maintenant, verrou

_RE_ENTREE = re.compile(r"^## (\S+ \S+) — (\S+) · (\S+)(?: · nœud:(\S+))?$", re.M)


class Registre:
    def __init__(self, racine: Path, tz):
        self.chemin = racine / "registre.md"
        self.integre = racine / "registre.integre.jsonl"
        self._verrou = racine / ".verrou-registre"
        self.tz = tz
        racine.mkdir(parents=True, exist_ok=True)

    def noter(self, texte: str, *, source: str, noeud: str = "", privacy: str = "normal") -> str:
        """Ajoute une entrée ; rend son identifiant (8 caractères, stable)."""
        texte = (texte or "").strip()
        if not texte:
            raise ValueError("texte vide")
        # Une ligne du corps qui commencerait par « ## » serait lue comme une nouvelle entrée, et
        # un « --> » fermerait le commentaire de confidentialité (revue du 23/09/2026).
        texte = "\n".join(("\\" + l) if l.lstrip().startswith("#") else l for l in texte.splitlines())
        texte = texte.replace("-->", "→").replace("<!--", "‹!--")
        if privacy not in ("normal", "personnel", "confidentiel"):
            privacy = "normal"
        noeud = re.sub(r"[^a-z0-9_]", "", (noeud or "").lower())[:60]
        with verrou(self._verrou):
            now = maintenant(self.tz)
            ident = hashlib.sha256(f"{now.isoformat()}|{texte}".encode()).hexdigest()[:8]
            premiere = not self.chemin.exists()
            with open(self.chemin, "a", encoding="utf-8") as f:
                if premiere:
                    from . import langues
                    f.write(langues.de_la_memoire(self.chemin.parent).textes["registre_entete"])
                titre = f"## {now.strftime('%Y-%m-%d %H:%M')} — {ident} · {source}"
                if noeud:
                    titre += f" · nœud:{noeud}"
                f.write(f"\n{titre}\n<!-- privacy:{privacy} -->\n{texte}\n")
        return ident

    def entrees(self) -> List[Dict]:
        """Toutes les entrées, dans l'ordre d'écriture."""
        if not self.chemin.exists():
            return []
        texte = self.chemin.read_text(encoding="utf-8")
        blocs = list(_RE_ENTREE.finditer(texte))
        sortie = []
        for i, m in enumerate(blocs):
            fin = blocs[i + 1].start() if i + 1 < len(blocs) else len(texte)
            corps = texte[m.end():fin].strip()
            pm = re.search(r"<!-- privacy:(\w+) -->", corps)
            corps = re.sub(r"<!-- privacy:\w+ -->\s*", "", corps).strip()
            sortie.append({"id": m.group(2), "date": m.group(1), "source": m.group(3),
                           "noeud": m.group(4) or "", "privacy": pm.group(1) if pm else "normal",
                           "texte": corps})
        return sortie

    def ids_integres(self) -> set:
        if not self.integre.exists():
            return set()
        return {json.loads(l)["id"] for l in self.integre.read_text(encoding="utf-8").splitlines() if l.strip()}

    def en_attente(self) -> List[Dict]:
        faits = self.ids_integres()
        return [e for e in self.entrees() if e["id"] not in faits]

    def marquer_integre(self, ident: str, page: str, lot: str) -> None:
        with verrou(self._verrou):
            ajouter_ligne_jsonl(self.integre, {"id": ident, "page": page, "lot": lot,
                                               "ts": maintenant(self.tz).isoformat(timespec="seconds")})
