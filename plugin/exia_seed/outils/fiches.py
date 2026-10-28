#!/usr/bin/env python3
"""Rattrapage des fiches d'identité (docs/12) — les pages écrites avant les fiches n'en ont pas.

ESSAI À BLANC par défaut : propose une fiche par page, la contrôle, écrit les propositions dans un fichier
JSON à relire — rien ne change dans la mémoire. `--ecrire` pose les fiches acceptées (un commit git les garde).

    python3 …/exia_seed/outils/fiches.py --racine /chemin/memoire --sortie propositions.json   # essai
    python3 …/exia_seed/outils/fiches.py --racine /chemin/memoire --ecrire                     # pose
    --toutes : réécrire aussi les pages qui ont déjà une fiche à jour
"""
import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, "/opt/hermes")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))          # …/plugins

from exia_seed import config as _config, fiches as _fiches, pages as _pages   # noqa: E402
from exia_seed.consolidation import appel_llm_hermes                    # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--racine", required=True, help="dossier mémoire (contient pages/)")
    ap.add_argument("--ecrire", action="store_true", help="poser les fiches (sinon : essai à blanc)")
    ap.add_argument("--toutes", action="store_true", help="aussi les pages déjà à jour")
    ap.add_argument("--sortie", default="", help="fichier JSON des propositions (essai)")
    a = ap.parse_args()
    racine = Path(a.racine)
    pages = _pages.lister(racine / "pages")
    cibles = [p for p in pages if any(p.sections.values())] if a.toutes else _fiches.a_rafraichir(pages)
    reg = _config.charger()
    r = _fiches.rediger(cibles, appel_llm_hermes(reg["consolidation_effort"]), date.today().isoformat(), ecrire=a.ecrire,
                        connus=(reg.get("nom_utilisateur") or "", reg.get("nom_agent") or ""))
    r["pages"] = len(pages)
    if a.sortie:
        Path(a.sortie).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.ecrire and r["ecrites"] and (racine / ".git").exists():
        # même identité que la consolidation : sans elle, git refuse le commit (rattrapage du 16/10, échec silencieux)
        subprocess.run(["git", "-C", str(racine), "add", "-A", "pages"], capture_output=True)
        c = subprocess.run(["git", "-C", str(racine), "-c", "user.name=EXIA SEED", "-c", "user.email=exia-seed@localhost",
                            "commit", "-q", "-m", f"fiches d'identité — {len(r['ecrites'])} pages"], capture_output=True, text=True)
        r["git"] = "ok" if c.returncode == 0 else "erreur: " + (c.stderr or c.stdout).strip()[:160]
    print(json.dumps({k: r.get(k) for k in ("statut", "git", "pages", "demandees", "ecrites", "inchangees", "absentes",
                                        "appels", "tokens_entree", "tokens_sortie")}, ensure_ascii=False))
    for x in r["refusees"]:
        print("REFUSÉE", x[0], "—", x[1], file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
