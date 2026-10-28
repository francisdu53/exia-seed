#!/usr/bin/env python3
"""Consolidation d'EXIA SEED hors conversation — pour le cron de fin de journée, sans agent.

Ferme le lot de brut ouvert s'il date d'un jour passé (toujours, avec --forcer), puis consolide le
brut et le registre en attente. SILENCIEUX quand tout va bien : un cron sans sortie ne coûte aucun
token et ne notifie personne. Seule une anomalie est imprimée (et donc livrée).

    python3 /opt/data/plugins/exia_seed/outils/consolider.py --forcer     # le cron de 23h55
    python3 /opt/data/plugins/exia_seed/outils/consolider.py --verbeux    # à la main : le rapport
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "/opt/hermes")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))          # …/plugins

from exia_seed import _etiquette, config as _config                     # noqa: E402
from exia_seed.consolidation import Consolidateur, appel_llm_hermes, modele_principal  # noqa: E402
from exia_seed.ingestion import Brut                                     # noqa: E402
from exia_seed.util import fuseau, maintenant                            # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--forcer", action="store_true", help="fermer aussi le lot du jour")
    ap.add_argument("--verbeux", action="store_true", help="afficher le rapport même si tout va bien")
    a = ap.parse_args()

    from hermes_constants import get_hermes_home
    # Le cron tourne dans un processus à part : sans cette ligne, ses journaux n'allaient nulle
    # part (revue du 23/09/2026). Ils rejoignent désormais agent.log et errors.log.
    try:
        from hermes_logging import setup_logging
        setup_logging()
    except Exception:
        pass
    reg = _config.charger()
    tz = fuseau(reg["fuseau"])
    racine = Path(get_hermes_home()) / reg["dossier"]
    agent = _etiquette(reg["nom_agent"]) if reg.get("nom_agent") else ""       # vide : conversation sans agent

    brut = Brut(racine, reg["seuil_lot_tokens"], tz, agent, reg["langue"])
    ouvert = brut.lot_ouvert()
    if ouvert and (a.forcer or ouvert.get("jour") != maintenant(tz).date().isoformat()):
        brut.fermer("fin_de_journee")

    r = Consolidateur(racine, tz, appel_llm_hermes(reg["consolidation_effort"]), modele=modele_principal(),
                      max_tokens_entree=reg["consolidation_max_tokens_entree"], nom_agent=agent,
                      nom_utilisateur=_etiquette(reg["nom_utilisateur"]) if reg.get("nom_utilisateur") else "",
                      interlocuteurs=[_etiquette(n) for n in (reg.get("interlocuteurs") or ())],
                      fiches=bool(reg.get("fiches", True))).consolider()
    if a.verbeux or r.get("statut") not in ("ok", "rien", "vide", "deja_en_cours"):
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
