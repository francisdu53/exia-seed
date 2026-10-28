"""Petits outils partagés : temps, hachage, verrou, écriture atomique."""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def fuseau(nom: str):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(nom)
    except Exception:
        return timezone.utc


def maintenant(tz) -> datetime:
    return datetime.now(tz)


def estimer_tokens(texte: str) -> int:
    """Estimation sans tokeniseur : ~4 caractères par token (français). Sert aux seuils, pas à la facture."""
    return math.ceil(len(texte or "") / 4)


def sha256_fichier(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(65536), b""):
            h.update(bloc)
    return "sha256:" + h.hexdigest()


@contextlib.contextmanager
def verrou(chemin: Path) -> Iterator[None]:
    """Verrou inter-processus : la passerelle et une commande `hermes` peuvent écrire en même temps."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def lire_json(chemin: Path, defaut: Any) -> Any:
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:
        return defaut


def ecrire_json(chemin: Path, donnees: Any) -> None:
    """Écriture atomique : un plantage en plein milieu ne laisse jamais un fichier à moitié écrit."""
    tmp = chemin.with_suffix(chemin.suffix + ".tmp")
    tmp.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, chemin)


def ajouter_ligne_jsonl(chemin: Path, donnees: Any) -> None:
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(json.dumps(donnees, ensure_ascii=False) + "\n")
