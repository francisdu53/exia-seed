"""Le moteur de propagation en représentation CREUSE (spec §5.2) — les mêmes calculs que `moteur/fcm.py`, sans matrice pleine.

Pourquoi (docs/13 §14.6, 27/10/2026) : la matrice pleine n × n de `FCMEngine` coûte n² — 202 Mo et 21 ms par recherche à
2 834 nœuds, quand le graphe réel n'a que 0,14 % des liens possibles (11 396 arêtes). D'où le plafond de 2 000 nœuds,
franchi par LongMemEval avec la consolidation exhaustive. Ici, seules les arêtes existent : mémoire et temps en
O(nœuds + arêtes).

Les calculs sont ceux de `FCMEngine.propagate` (EXIA GHOST V2.7.2, gardé identique au bit près dans `moteur/`, et
toujours là pour vérifier) : activation initiale 0, entrées injectées et bornées à [0, 1], au plus 3 itérations de
A ← sigmoïde(W·A) avec λ = 5 et seuil 0,5, les entrées gardant leur valeur (tous les nœuds sont des entrées), arrêt
quand l'écart passe sous 0,001. W est symétrique : W[i, j] = W[j, i] = poids de l'arête. Seul change l'ordre des sommes
(écarts de l'ordre de 1e-15, vérifiés par `tests/test_creux.py` contre le moteur d'origine)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

import numpy as np

LAMBDA = 5.0          # moteur/fcm.py : _LAMBDA
SEUIL = 0.5           # moteur/fcm.py : _sigmoid, x − 0.5
CONVERGENCE = 0.001   # moteur/fcm.py : propagate


@dataclass
class Resultat:
    activations: Dict[str, float]
    iterations: int
    convergence_delta: float
    latency_us: float
    predictions: List[Dict] = field(default_factory=list)


class MoteurCreux:
    """Même interface que `FCMEngine` pour ce qu'EXIA SEED en utilise : `propagate(entrees)`, `n_concepts`."""

    def __init__(self, noms: List[str], aretes: Iterable[Tuple[str, str, float]]):
        self.noms = list(noms)
        self.index = {n: i for i, n in enumerate(self.noms)}
        # Une arête par paire, la DERNIÈRE l'emporte (comme `W[i, j] = W[j, i] = poids` écrit dans l'ordre).
        paires: Dict[Tuple[int, int], float] = {}
        for a, b, poids in aretes:
            i, j = self.index[a], self.index[b]
            paires[(min(i, j), max(i, j))] = float(poids)
        lignes, colonnes, poids = [], [], []
        for (i, j), w in paires.items():
            lignes.append(i); colonnes.append(j); poids.append(w)
            if i != j:                                   # symétrique ; la diagonale une seule fois
                lignes.append(j); colonnes.append(i); poids.append(w)
        self._lignes = np.asarray(lignes, dtype=np.int64)
        self._colonnes = np.asarray(colonnes, dtype=np.int64)
        self._poids = np.asarray(poids, dtype=np.float64)

    @property
    def n_concepts(self) -> int:
        return len(self.noms)

    @property
    def n_aretes(self) -> int:
        return len(self._poids) // 2 if len(self._poids) else 0

    def get_concept_names(self) -> List[str]:
        return list(self.noms)

    def get_weights(self) -> np.ndarray:
        """La matrice pleine W[cible, source], reconstruite À LA DEMANDE — pour l'inspection et les tests seulement
        (mêmes noms que `FCMEngine`) ; la propagation ne s'en sert jamais."""
        W = np.zeros((len(self.noms), len(self.noms)))
        W[self._lignes, self._colonnes] = self._poids
        return W

    def _w_a(self, A: np.ndarray) -> np.ndarray:
        """W · A sans matrice : chaque arête porte poids × activation de sa source vers sa cible."""
        return np.bincount(self._lignes, weights=self._poids * A[self._colonnes], minlength=len(self.noms))

    def propagate(self, inputs: Dict[str, float], max_iter: int = 3) -> Resultat:
        t0 = time.perf_counter_ns()
        n = len(self.noms)
        A = np.zeros(n, dtype=np.float64)
        injectes = [(self.index[k], float(np.clip(v, 0.0, 1.0))) for k, v in inputs.items() if k in self.index]
        for i, v in injectes:
            A[i] = v
        delta, iterations = (1.0 if n else 0.0), 0
        for it in range(max_iter if n else 0):
            A_new = 1.0 / (1.0 + np.exp(-LAMBDA * (self._w_a(A) - SEUIL)))
            for i, v in injectes:
                A_new[i] = v
            delta = float(np.max(np.abs(A_new - A)))
            A = A_new
            iterations = it + 1
            if delta < CONVERGENCE:
                break
        return Resultat(activations={nom: float(A[i]) for i, nom in enumerate(self.noms)}, iterations=iterations,
                        convergence_delta=delta, latency_us=(time.perf_counter_ns() - t0) / 1000.0)
