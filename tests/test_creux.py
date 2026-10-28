"""Moteur creux (27/10/2026, spec §5.2, docs/13 §14.6) — conteneur jetable, vrai chargeur d'Hermès.

`creux.MoteurCreux` doit rendre les MÊMES activations que `moteur/fcm.py` (EXIA GHOST V2.7.2, matrice pleine), à
l'ordre des sommes près — sur des graphes aléatoires creux, avec et sans entrées, arêtes en double, nœud isolé."""
import importlib, sys
import numpy as np
sys.path.insert(0, "/opt/hermes")
ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))

from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
base = type(p).__module__
C = importlib.import_module(base + ".creux")
F = importlib.import_module(base + ".moteur.fcm")

def plein(noms, aretes):
    idx = {n: i for i, n in enumerate(noms)}
    W = np.zeros((len(noms), len(noms)))
    for a, b, w in aretes:
        W[idx[a], idx[b]] = W[idx[b], idx[a]] = w
    return F.FCMEngine("t", [F.FCMConcept(name=n, is_input=True) for n in noms], W)

ecart_max, rangs_ok, essais = 0.0, True, 0
for graine in range(12):
    rng = np.random.default_rng(graine)
    n = int(rng.integers(5, 400))
    noms = [f"n{i}" for i in range(n)]
    m = int(n * rng.uniform(1, 6))
    aretes = [(f"n{rng.integers(n)}", f"n{rng.integers(n)}", float(rng.uniform(0.05, 1))) for _ in range(m)]
    aretes = [(a, b, w) for a, b, w in aretes if a != b]
    aretes += aretes[:3]                                    # arêtes en double : la dernière l'emporte, comme W[i, j] = …
    d, c = plein(noms, aretes), C.MoteurCreux(noms, aretes)
    for entrees in ({}, {noms[0]: 1.0}, {noms[k]: float(rng.uniform()) for k in rng.integers(n, size=4)}, {"inconnu": 1.0}):
        a1, a2 = d.propagate(entrees).activations, c.propagate(entrees).activations
        e = max(abs(a1[k] - a2[k]) for k in noms)
        ecart_max = max(ecart_max, e); essais += 1
        r1 = sorted(noms, key=lambda k: (-round(a1[k], 9), k)); r2 = sorted(noms, key=lambda k: (-round(a2[k], 9), k))
        rangs_ok &= r1[:20] == r2[:20]
verif(f"activations identiques au moteur d'origine ({essais} propagations, 12 graphes)", ecart_max < 1e-12, f"écart max {ecart_max:.1e}")
verif("même classement des 20 premiers nœuds", rangs_ok)
verif("graphe vide : pas d'exception, rien à propager", C.MoteurCreux([], []).propagate({}).activations == {})
iso = C.MoteurCreux(["a", "b", "seul"], [("a", "b", 0.8)])
verif("nœud isolé : activation de repos de la sigmoïde (0,076)", abs(iso.propagate({}).activations["seul"] - 1 / (1 + np.exp(2.5))) < 1e-12)
verif("n_concepts et n_aretes", iso.n_concepts == 3 and iso.n_aretes == 1)

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
