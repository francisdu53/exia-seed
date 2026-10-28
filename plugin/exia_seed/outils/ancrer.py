#!/usr/bin/env python3
"""Rattrapage R2 : ajoute `dit_le` aux faits écrits AVANT la révision R2 (26/09/2026).

`dit_le` se retrouve sans rien inventer : c'est la date du lot de la PREMIÈRE source citée, plus
l'heure de sa ligne (ou du message dont elle est la suite). Un fait sans source raw (registre seul)
reçoit la date de l'entrée du registre. On ne touche NI au texte du fait NI à ses dates
event_time/echeance : les vérifier demanderait de relire les phrases avec le modèle.

Idempotent (un fait qui a déjà `dit_le` est laissé), sous le verrou de la consolidation, un commit git.

    python3 /opt/data/plugins/exia_seed/outils/ancrer.py            # simulation : ce qui changerait
    python3 /opt/data/plugins/exia_seed/outils/ancrer.py --ecrire   # écrit
"""
import argparse
import fcntl
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))          # …/plugins
from exia_seed import config as _config                                # noqa: E402
from exia_seed import temps as _temps                                  # noqa: E402

_RE_FAIT = re.compile(r"^(- .*?<!-- )(.*?)( -->)\s*$")


def ancres_du_lot(fichier: Path) -> dict:
    """{numéro de ligne: dit_le} pour un lot de brut."""
    texte = fichier.read_text(encoding="utf-8")
    m = re.search(r"^date:\s*(\d{4})-(\d{2})-(\d{2})", texte, re.M) or re.match(r"(\d{4})-(\d{2})-(\d{2})", fichier.name)
    if not m:
        return {}
    jour = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    o = re.search(r"^ouvert_le:\s*\S+T(\d\d:\d\d)", texte, re.M)
    sortie, entete = {}, ""
    for n, ligne in enumerate(texte.splitlines(), start=1):
        if re.match(r"\[\d\d:\d\d ", ligne):
            entete = ligne
        sortie[n] = _temps.dit_le(jour, o.group(1) if o else None, entete or ligne)
    return sortie


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()
    from hermes_constants import get_hermes_home
    racine = Path(get_hermes_home()) / _config.charger()["dossier"]
    registre = {}
    if (racine / "registre.md").exists():
        # même format que registre._RE_ENTREE : « ## 2026-09-23 14:02 — id · source »
        for m in re.finditer(r"^## (\S+ \S+) — (\S+) · ", (racine / "registre.md").read_text(encoding="utf-8"), re.M):
            registre[m.group(2)] = m.group(1)[:16].replace(" ", "T")
    cache, total, ajoutes, sans = {}, 0, 0, []
    with open(racine / ".verrou-consolidation", "a+") as verrou:
        fcntl.flock(verrou, fcntl.LOCK_EX)                 # attend une consolidation en cours
        for page in sorted((racine / "pages").glob("*.md")):
            lignes, modifie = page.read_text(encoding="utf-8").splitlines(), False
            for i, ligne in enumerate(lignes):
                m = _RE_FAIT.match(ligne)
                if not m:
                    continue
                total += 1
                meta = m.group(2)
                if re.search(r"(^| )dit_le:", meta):
                    continue
                src = re.search(r"(?:^| )src:(\S+)", meta)
                moments = []
                for ref in (src.group(1).split(",") if src else []):
                    r = re.match(r"raw/([^:]+):(\d+)", ref)
                    if r:
                        f = racine / "raw" / r.group(1)
                        if f.exists():
                            cache.setdefault(f, ancres_du_lot(f))
                            if int(r.group(2)) in cache[f]:
                                moments.append(cache[f][int(r.group(2))])
                    elif ref.startswith("registre:") and ref.split(":", 1)[1] in registre:
                        moments.append(registre[ref.split(":", 1)[1]])
                if not moments:
                    sans.append(f"{page.stem} : {ligne[:80]}")
                    continue
                nouveau = re.sub(r"(src:\S+)", rf"\1 dit_le:{min(moments)}", meta, count=1)
                lignes[i] = m.group(1) + nouveau + m.group(3)
                ajoutes += 1; modifie = True
            if modifie and a.ecrire:
                page.write_text("\n".join(lignes) + "\n", encoding="utf-8")
        print(f"{total} faits · {ajoutes} ancrés{'' if a.ecrire else ' (simulation)'} · {len(sans)} sans source datable")
        for s in sans:
            print("  ⚠", s)
        if a.ecrire and ajoutes and (racine / ".git").exists():
            subprocess.run(["git", "-C", str(racine), "add", "-A"], capture_output=True)
            r = subprocess.run(["git", "-C", str(racine), "-c", "user.name=EXIA SEED", "-c", "user.email=exia-seed@localhost", "commit", "-q", "-m",
                                f"R2 : dit_le ajouté à {ajoutes} faits antérieurs"], capture_output=True, text=True)
            print("  git :", "ok" if r.returncode == 0 else r.stderr.strip()[:200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
