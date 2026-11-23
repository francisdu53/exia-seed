"""Capteurs du banc d'évaluation — les MÊMES pour tous les concurrents (PLAN-FCM-EXIA-SEED.md §3 bis).

Bibliothèque standard + `tokenizers` (présent sur l'hôte et dans le conteneur). Rien ici n'appelle de modèle.
  Jetons     compteur de tokens FIXE (o200k, fichier local `o200k_tokenizer.json`, empreinte dans le manifeste)
  Chrono     temps par étape (horloge monotone, ns) + temps CPU du processus, en gestionnaire de contexte
  Erreurs    exceptions comptées par type, jamais avalées en silence (leçon : l'import manquant de GHOST)
  memoire()  pic et courant de la mémoire vive du processus
  energie()  compteur d'énergie matériel (RAPL) quand la machine l'expose, sinon None
  sante()    saturation des notes (le défaut de GHOST), déterminisme (empreinte de sortie)
  manifeste  empreintes du code, des poids, des données, des réglages ; machine ; date (reproductibilité)
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import resource
import socket
import statistics
import time
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ICI = Path(__file__).resolve().parent


class Jetons:
    """Compteur fixe o200k (famille GPT-4o) : le même partout, pour que le budget soit le même pour tous."""
    _t = None

    def __init__(self):
        if Jetons._t is None:
            from tokenizers import Tokenizer
            Jetons._t = Tokenizer.from_file(str(ICI / "o200k_tokenizer.json"))

    def __call__(self, texte: str) -> int:
        return len(Jetons._t.encode(texte or "", add_special_tokens=False).ids)


class _Etape:
    def __init__(self, chrono: "Chrono", nom: str):
        self.c, self.nom = chrono, nom

    def __enter__(self):
        self.t0, self.c0 = time.perf_counter_ns(), time.process_time_ns()
        return self

    def __exit__(self, *exc):
        self.c.ns[self.nom] = self.c.ns.get(self.nom, 0) + time.perf_counter_ns() - self.t0
        self.c.cpu_ns[self.nom] = self.c.cpu_ns.get(self.nom, 0) + time.process_time_ns() - self.c0
        return False


class Chrono:
    """Temps mur et CPU par étape. `with ch.etape("traits"): …` — les étapes s'additionnent si répétées."""
    def __init__(self):
        self.ns: Dict[str, int] = {}
        self.cpu_ns: Dict[str, int] = {}

    def etape(self, nom: str) -> _Etape:
        return _Etape(self, nom)

    def releve(self) -> Dict:
        return {"ns": dict(self.ns), "cpu_ns": dict(self.cpu_ns)}


class Erreurs:
    """Compte chaque exception par type et garde les 3 premières traces ; l'appelant décide de continuer."""
    def __init__(self):
        self.par_type: Counter = Counter()
        self.exemples: List[str] = []

    def noter(self, e: BaseException, ou: str = "") -> None:
        self.par_type[f"{ou}:{type(e).__name__}"] += 1
        if len(self.exemples) < 3:
            self.exemples.append(f"{ou}: {type(e).__name__}: {str(e)[:200]} | "
                                 + " / ".join(traceback.format_exc().strip().splitlines()[-3:]))

    def releve(self) -> Dict:
        return {"par_type": dict(self.par_type), "exemples": self.exemples}


def memoire() -> Dict:
    """Pic (ru_maxrss, Ko sous Linux) et courant (/proc/self/statm) de la mémoire vive du processus, en Mo."""
    pic = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    try:
        courant = int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2**20
    except Exception:
        courant = None
    return {"pic_mo": round(pic, 1), "courant_mo": round(courant, 1) if courant is not None else None}


def energie() -> Optional[float]:
    """Énergie cumulée du paquet CPU en joules (RAPL), ou None si la machine ne l'expose pas (VPS)."""
    f = Path("/sys/class/powercap/intel-rapl:0/energy_uj")
    try:
        return int(f.read_text()) / 1e6
    except Exception:
        return None


def saturation(notes: Iterable[float]) -> Dict:
    """Le défaut de GHOST : tous les candidats reçoivent la même note. Dispersion et part des notes à moins de 1 % du
    maximum (sur les notes > 0). Alerte si ≥ 5 notes et dispersion < 0,01 ou ≥ 90 % collées au maximum."""
    n = [float(x) for x in notes if x is not None]
    if len(n) < 2:
        return {"n": len(n), "ecart_type": None, "part_au_max": None, "alerte": False}
    mx, mn, et = max(n), min(n), statistics.pstdev(n)
    colle = sum(1 for x in n if x >= mx - 0.01 * max(1e-9, abs(mx - mn) + abs(mx))) / len(n)
    return {"n": len(n), "ecart_type": round(et, 5), "part_au_max": round(colle, 3),
            "alerte": len(n) >= 5 and (et < 0.01 or colle >= 0.9)}


def empreinte_obj(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]


def empreinte_fichiers(chemins: Iterable[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(Path(c) for c in chemins):
        if p.is_file():
            h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()[:16]


def empreinte_dossier(d: Path, motif: str = "**/*.py") -> str:
    return empreinte_fichiers(p for p in Path(d).glob(motif) if "__pycache__" not in p.parts)


def machine() -> Dict:
    cpu = ""
    try:
        cpu = next((l.split(":", 1)[1].strip() for l in Path("/proc/cpuinfo").read_text().splitlines()
                    if l.startswith("model name")), "")
    except Exception:
        pass
    return {"hote": socket.gethostname(), "cpu": cpu, "coeurs": os.cpu_count(), "python": platform.python_version(),
            "noyau": platform.release(), "rapl": energie() is not None}


def manifeste(**champs) -> Dict:
    """Manifeste de passage : à écrire à côté de chaque fichier de sortie."""
    return {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "machine": machine(),
            "code_eval": empreinte_dossier(ICI, "*.py"),
            "compteur_tokens": hashlib.sha256((ICI / "o200k_tokenizer.json").read_bytes()).hexdigest()[:16],
            "scelle": hashlib.sha256((ICI / "scelle.json").read_bytes()).hexdigest()[:16]
            if (ICI / "scelle.json").exists() else None, **champs}


def centiles(valeurs: List[float]) -> Dict:
    v = sorted(x for x in valeurs if x is not None)
    if not v:
        return {}
    q = lambda p: v[min(len(v) - 1, int(round(p * (len(v) - 1))))]
    return {"n": len(v), "p50": round(q(0.5), 3), "p90": round(q(0.9), 3), "p99": round(q(0.99), 3),
            "max": round(v[-1], 3), "moy": round(sum(v) / len(v), 3)}
