"""Variante : mémoire fusionnée SANS interlocuteurs implicites (graphe + lecteur). Aucun appel au modèle."""
import json, sys
sys.path.insert(0, "/locomo")
import commun as K
K.preparer_chemins()
from pathlib import Path
from exia_seed import graphe as G
from exia_seed.requete import Lecteur
import recuperer as RC
mem = Path("/var/mem")
mode = sys.argv[1]            # "aucun" ou "tous"
fusion = json.loads((K.RUN / "fusion.json").read_text())
imp = () if mode == "aucun" else tuple(fusion["implicites"])
r = G.calculer(mem, implicites=imp)
print("graphe", r.get("statut"), r.get("noeuds"), r.get("aretes"))
L = Lecteur(mem, implicites=imp)
qs = K.questions(K.charger_donnees(K.selection_du_run()))
with open(f"/var/sortie/A_F_{mode}.jsonl", "w") as f:
    for q in qs:
        f.write(json.dumps({"id": q["id"], "faits": RC.fcm(L, q["question"], RC.TRES_TARD)}, ensure_ascii=False) + "\n")
print("questions", len(qs))
