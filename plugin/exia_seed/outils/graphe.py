#!/usr/bin/env python3
"""Le graphe d'EXIA SEED à la demande — calcul, voisins d'un nœud, propagation (étape 5).

    python3 /opt/data/plugins/exia_seed/outils/graphe.py                       # rapport du graphe actuel
    python3 /opt/data/plugins/exia_seed/outils/graphe.py --calculer            # recalcule depuis les pages
    python3 /opt/data/plugins/exia_seed/outils/graphe.py --voisins autoplus_valmont
    python3 /opt/data/plugins/exia_seed/outils/graphe.py --propager autoplus_valmont

`--propager` montre l'activation AU-DESSUS DU REPOS : au repos, le moteur FCM de V2.7.2 fait
flotter chaque nœud vers 0,08-0,11 (plancher de sa sigmoïde) ; seul l'écart compte.
Le calcul se fait sous le verrou de la consolidation : jamais deux écrivains.
"""
import argparse
import fcntl
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))          # …/plugins
from exia_seed import config as _config                                # noqa: E402
from exia_seed import graphe as _graphe                                # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--calculer", action="store_true")
    ap.add_argument("--voisins")
    ap.add_argument("--propager")
    a = ap.parse_args()
    from hermes_constants import get_hermes_home
    reg = _config.charger()
    racine = Path(get_hermes_home()) / reg["dossier"]
    implicites = (reg.get("nom_utilisateur"), reg.get("nom_agent"))
    if a.calculer or not (racine / "graphe" / "aretes.json").exists():
        with open(racine / ".verrou-consolidation", "a+") as verrou:
            fcntl.flock(verrou, fcntl.LOCK_EX)
            r = _graphe.calculer(racine, implicites=implicites)
    else:
        r = json.loads((racine / "graphe" / "rapport.json").read_text(encoding="utf-8"))
    if not (a.voisins or a.propager):
        print(json.dumps(r, ensure_ascii=False, indent=1))
    if a.voisins:
        aretes = json.loads((racine / "graphe" / "aretes.json").read_text(encoding="utf-8"))
        liste = sorted(((x["b"] if x["a"] == a.voisins else x["a"], x) for x in aretes
                        if a.voisins in (x["a"], x["b"])), key=lambda t: -t[1]["poids"])
        print(f"{a.voisins} : {len(liste)} voisin(s)")
        for v, x in liste:
            types = sorted({p["type"] for p in x["preuves"]})
            print(f"  {x['poids']:.3f}  {v:34} {x['nb_preuves']} preuve(s) : {', '.join(types)}")
            print(f"         ex. « {x['preuves'][0]['fait'][:90]} »")
    if a.propager:
        m = _graphe.charger_moteur(racine)
        repos = m.propagate({}).activations
        act = m.propagate({a.propager: 1.0}).activations
        ecarts = sorted(((n, act[n] - repos[n]) for n in act if n != a.propager), key=lambda t: -t[1])
        print(f"propagation depuis {a.propager} — activation au-dessus du repos :")
        for n, v in ecarts:
            if v > 0.005:
                print(f"  +{v:.3f}  {n}")
        print(f"  ({sum(1 for _, v in ecarts if v <= 0.005)} nœud(s) sans écart notable)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
