"""Mémoire vide (27/10/2026) — conteneur jetable, vrai chargeur d'Hermès.

LongMemEval (docs/13 §10) : 74 mémoires sur 500 sans aucun fait (tout ce qu'elles contenaient venait de l'assistant,
écarté par la règle 4). Le moteur plantait (`moteur/fcm.py`, np.max sur un tableau vide) au lieu de rendre « rien ».
Une instance neuve — un nouvel utilisateur, avant sa première consolidation utile — est dans ce cas."""
import importlib, sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))

from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
base = type(p).__module__
G = importlib.import_module(base + ".graphe")
RQ = importlib.import_module(base + ".requete")
R = importlib.import_module(base + ".rappel")
F = importlib.import_module(base + ".moteur.fcm")

print("── 1. le moteur seul ──")
try:
    m = F.FCM([]) if hasattr(F, "FCM") else None
except TypeError:
    m = None
mem = H / "memoire_vide"; (mem / "pages").mkdir(parents=True); (mem / "raw").mkdir()
r = G.calculer(mem, implicites=("user", "assistant"))
verif("le graphe d'une mémoire sans page se calcule", r.get("statut") in ("ok", "vide"), str({k: r.get(k) for k in ("statut", "noeuds", "faits")}))

print("── 2. la recherche et le rappel ──")
try:
    c = RQ.Lecteur(mem, implicites=("user", "assistant")).chercher("what did I buy last week", 10, datetime(2100, 1, 1), faits_max=12)
    verif("memoire_chercher rend un résultat vide, sans exception", not c.get("resultats"), str(c)[:200])
except Exception as e:
    verif("memoire_chercher rend un résultat vide, sans exception", False, repr(e)[:200])
try:
    rp = R.Rappeleur(mem, implicites=("user", "assistant"))
    verif("le rappel se construit sur une mémoire vide", rp is not None)
except Exception as e:
    verif("le rappel se construit sur une mémoire vide", False, repr(e)[:200])

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
