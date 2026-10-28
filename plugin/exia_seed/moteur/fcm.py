"""
EXIA GHOST V5 — Fuzzy Cognitive Maps Engine

Moteur de propagation FCM vectorisé (NumPy).
Propagation: A_new = sigmoid(W @ A_current)
Sigmoid: 1 / (1 + exp(-lambda * (x - 0.5))) avec lambda=5

Refs:
  - Doc 06 §5 : FCM architecture, catalogue Nexa
  - Doc 14 §3.3 : FCMPropagationTrace
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np


# ═══════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════

@dataclass
class FCMConcept:
    """Noeud d'une FCM."""
    name: str
    activation: float = 0.0     # [0, 1]
    is_input: bool = False
    is_output: bool = False
    anchor_phrases: List[str] = field(default_factory=list)  # [CP9] semantic seeding
    # V2.5.0 Sprint K0: BM25-matchable search terms (English) for FCM spreading.
    # When the FCM propagation activates this concept, semantic._fcm_spreading_search
    # uses these terms for the BM25 search instead of the raw concept name (which
    # may be in French, like "joie" or "intensite_emotionnelle", and match nothing
    # in an EN corpus). Falls back to [name] if empty.
    # Ref: EXIA_GHOST_SPEC/09B_FCM_EXIA_FORMULATION_MATHEMATIQUE.md §Q_F7
    search_terms: List[str] = field(default_factory=list)


@dataclass
class FCMResult:
    """Résultat d'une propagation FCM."""
    activations: Dict[str, float]       # concept_name -> activation finale
    iterations: int
    convergence_delta: float
    latency_us: float                   # microsecondes
    predictions: List[dict]             # futures taguées depuis les concepts output


# ═══════════════════════════════════════════════════════════
# SIGMOID
# ═══════════════════════════════════════════════════════════

_LAMBDA = 5.0

def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Sigmoid FCM vectorisée: 1 / (1 + exp(-λ * (x - 0.5)))."""
    return 1.0 / (1.0 + np.exp(-_LAMBDA * (x - 0.5)))


# ═══════════════════════════════════════════════════════════
# FCM ENGINE
# ═══════════════════════════════════════════════════════════

class FCMEngine:
    """Moteur de propagation Fuzzy Cognitive Map.

    Graphe dirigé pondéré de concepts avec propagation vectorisée.
    Target: <100μs par propagation pour 50 noeuds.
    """

    def __init__(self, name: str, concepts: List[FCMConcept], weights: np.ndarray,
                 domain_phrases: Optional[List[str]] = None,
                 boost_map: Optional[Dict[str, str]] = None):
        n = len(concepts)
        if weights.shape != (n, n):
            raise ValueError(
                f"Weight matrix shape {weights.shape} != ({n}, {n})"
            )
        self._name = name
        self._concepts = list(concepts)
        self._weights = weights.astype(np.float64)
        # Index rapide name -> position
        self._index: Dict[str, int] = {c.name: i for i, c in enumerate(concepts)}
        # Masques pré-calculés
        self._input_mask = np.array([c.is_input for c in concepts], dtype=bool)
        self._output_mask = np.array([c.is_output for c in concepts], dtype=bool)
        self._output_names = [c.name for c in concepts if c.is_output]
        # Ancres de domaine : phrases décrivant le domaine (pré-encodées au boot)
        self._domain_phrases = domain_phrases or []
        self._domain_anchors: List[np.ndarray] = []  # vecteurs encodés
        # Boost map : output_concept → action (pour délibération génétique)
        self._boost_map: Dict[str, str] = boost_map or {}
        # [CP9] Concept anchors : concept_name → encoded vectors (set at boot)
        self._concept_anchors: Dict[str, List[np.ndarray]] = {}
        # Phase D: activation counters for lifecycle decisions
        self._activation_count: int = 0
        self._total_interactions: int = 0
        # V2.2.2 Phase 2 Lot 2A — FCM dynamics forensics (class-level cumulative)
        self._propagate_calls_total: int = 0
        self._propagate_iteration_capped_total: int = 0  # # of times iter == max_iter
        self._propagate_iterations_sum: int = 0           # cumulative iterations
        self._addnode_failed_collision_total: int = 0
        self._addnode_failed_full_total: int = 0

    @property
    def domain_phrases(self) -> List[str]:
        return self._domain_phrases

    @property
    def domain_anchors(self) -> List[np.ndarray]:
        return self._domain_anchors

    def set_domain_anchors(self, anchors: List[np.ndarray]):
        """Set pre-encoded domain anchor vectors (called at boot)."""
        self._domain_anchors = anchors

    @property
    def boost_map(self) -> Dict[str, str]:
        """Mapping output_concept → action pour boost délibération."""
        return self._boost_map

    # ── CP9 : Concept anchors ──────────────────────────────

    def set_concept_anchors(self, concept_name: str, anchors: List[np.ndarray]):
        """Set pre-encoded anchor vectors for an input concept (called at boot)."""
        self._concept_anchors[concept_name] = anchors

    @property
    def concept_anchors(self) -> Dict[str, List[np.ndarray]]:
        """concept_name → list of encoded anchor vectors."""
        return self._concept_anchors

    def get_input_concepts_with_anchors(self) -> List[str]:
        """Return names of input concepts that have anchor vectors."""
        return [name for name in self._concept_anchors if name in self._index]

    def get_telemetry_snapshot(self) -> Dict[str, int]:
        """V2.4.1 Phase 0 — Expose FCM dynamics counters (silent before this fix).

        Keys returned (prefixed by FCM name in global collector):
          fcm.<name>.propagate_calls_total            — # of propagate() calls
          fcm.<name>.propagate_iteration_capped_total — # of times iter == max_iter
          fcm.<name>.propagate_iterations_sum         — cumulative iterations
          fcm.<name>.addnode_failed_collision_total   — # of sprout collisions
          fcm.<name>.addnode_failed_full_total        — # of sprout when full
          fcm.<name>.activation_count                 — # of activations (Phase D lifecycle)
          fcm.<name>.total_interactions               — # of total interactions
        """
        return {
            "propagate_calls_total": self._propagate_calls_total,
            "propagate_iteration_capped_total": self._propagate_iteration_capped_total,
            "propagate_iterations_sum": self._propagate_iterations_sum,
            "addnode_failed_collision_total": self._addnode_failed_collision_total,
            "addnode_failed_full_total": self._addnode_failed_full_total,
            "activation_count": self._activation_count,
            "total_interactions": self._total_interactions,
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def n_concepts(self) -> int:
        return len(self._concepts)

    def get_concept_names(self) -> List[str]:
        """Retourne la liste des noms de concepts."""
        return [c.name for c in self._concepts]

    def get_weights(self) -> np.ndarray:
        """Retourne une copie de la matrice de poids."""
        return self._weights.copy()

    def set_weights(self, weights: np.ndarray) -> None:
        """Replace weight matrix (for loading persisted user weights).

        Args:
            weights: New weight matrix — must match current shape.

        Raises:
            ValueError: If shape doesn't match.
        """
        if weights.shape != self._weights.shape:
            raise ValueError(
                f"Shape mismatch: expected {self._weights.shape}, got {weights.shape}"
            )
        self._weights = weights.copy()

    def get_w_sym(self) -> np.ndarray:
        """Return symmetric decomposition: W_sym = (W + W^T) / 2."""
        return (self._weights + self._weights.T) / 2.0

    # ── Phase D: Activation tracking ─────────────────────

    def record_activation(self, was_active: bool) -> None:
        """Record whether this FCM was activated in an interaction."""
        self._total_interactions += 1
        if was_active:
            self._activation_count += 1

    @property
    def activation_rate(self) -> float:
        """Activation rate over recorded period."""
        if self._total_interactions == 0:
            return 0.0
        return self._activation_count / self._total_interactions

    def reset_activation_stats(self) -> None:
        """Reset counters (called after monthly evaluation)."""
        self._activation_count = 0
        self._total_interactions = 0

    def propagate(self, inputs: Dict[str, float], max_iter: int = 3) -> FCMResult:
        """Propage les activations à travers la FCM.

        Args:
            inputs: {concept_name: activation_value} pour les concepts d'entrée
            max_iter: nombre max d'itérations (défaut 3, V1.0 budget)

        Returns:
            FCMResult avec activations finales, timing et prédictions
        """
        # V2.2.2 Phase 2 Lot 2A: count propagate calls
        self._propagate_calls_total += 1
        t0 = time.perf_counter_ns()

        n = len(self._concepts)
        # Vecteur d'activation initial
        A = np.array([c.activation for c in self._concepts], dtype=np.float64)

        # Injecter les entrées
        for name, value in inputs.items():
            idx = self._index.get(name)
            if idx is not None:
                A[idx] = np.clip(value, 0.0, 1.0)

        W = self._weights
        convergence_delta = 1.0
        iterations = 0

        for i in range(max_iter):
            A_new = _sigmoid(W @ A)
            # Les concepts input gardent leur valeur injectée
            for name, value in inputs.items():
                idx = self._index.get(name)
                if idx is not None and self._concepts[idx].is_input:
                    A_new[idx] = np.clip(value, 0.0, 1.0)

            convergence_delta = float(np.max(np.abs(A_new - A)))
            A = A_new
            iterations = i + 1
            if convergence_delta < 0.001:
                break

        t1 = time.perf_counter_ns()
        latency_us = (t1 - t0) / 1000.0

        # V2.2.2 Phase 2 Lot 2A: track iteration cap + cumulative iterations
        self._propagate_iterations_sum += iterations
        if iterations >= max_iter and convergence_delta >= 0.001:
            # Capped: did max_iter without converging
            self._propagate_iteration_capped_total += 1

        # Construire le dict d'activations
        activations = {c.name: float(A[i]) for i, c in enumerate(self._concepts)}

        # Prédictions depuis les concepts output
        predictions = []
        for name in self._output_names:
            idx = self._index[name]
            predictions.append({
                "concept": name,
                "activation": float(A[idx]),
                "confidence": float(min(A[idx], 1.0 - convergence_delta)),
            })

        return FCMResult(
            activations=activations,
            iterations=iterations,
            convergence_delta=convergence_delta,
            latency_us=latency_us,
            predictions=predictions,
        )

    def add_node(self, name: str, is_input: bool = True, is_output: bool = False,
                 anchor_phrases: list = None, initial_weights: dict = None) -> bool:
        """Add a new concept node to this FCM (Phase C: Node Sprouting).

        Resizes the weight matrix from n×n to (n+1)×(n+1).
        Existing weights are preserved. New row/column initialized
        from initial_weights dict or zeros.

        Args:
            name: Concept name (must not already exist)
            is_input: Can receive external activation (concept seeding)
            is_output: Produces predictions
            anchor_phrases: Phrases for concept seeding (CP9)
            initial_weights: {existing_concept_name: weight_value}

        Returns:
            True if added, False if name already exists or FCM is full (50 nodes)
        """
        # Check name doesn't already exist
        if name in self._index:
            # V2.2.2 Phase 2 Lot 2A: count name collisions
            self._addnode_failed_collision_total += 1
            return False

        # Hard limit: 50 nodes per FCM
        n = len(self._concepts)
        if n >= 50:
            # V2.2.2 Phase 2 Lot 2A: count FCM-full rejections
            self._addnode_failed_full_total += 1
            return False

        # Create new concept
        new_concept = FCMConcept(
            name=name,
            activation=0.0,
            is_input=is_input,
            is_output=is_output,
            anchor_phrases=anchor_phrases or [],
        )

        # Resize weight matrix: (n)×(n) → (n+1)×(n+1)
        new_weights = np.zeros((n + 1, n + 1), dtype=np.float64)
        new_weights[:n, :n] = self._weights

        # Fill new row/column from initial_weights
        if initial_weights:
            for existing_name, weight_value in initial_weights.items():
                idx = self._index.get(existing_name)
                if idx is not None:
                    clamped = np.clip(weight_value, -1.0, 1.0)
                    # existing → new (new row, column = existing index)
                    new_weights[n, idx] = clamped
                    # new → existing (existing row, column = new index)
                    new_weights[idx, n] = clamped

        # Update internal state
        self._concepts.append(new_concept)
        self._weights = new_weights
        self._index[name] = n

        # Rebuild masks
        self._input_mask = np.array([c.is_input for c in self._concepts], dtype=bool)
        self._output_mask = np.array([c.is_output for c in self._concepts], dtype=bool)
        self._output_names = [c.name for c in self._concepts if c.is_output]

        # Set concept anchors if provided
        if anchor_phrases and is_input:
            self.set_concept_anchors(name, [])  # placeholder, caller encodes

        return True

    def update_weight(self, from_concept: str, to_concept: str, delta: float):
        """Met à jour un poids (apprentissage Hebbien, Phase 6).

        Clampe le résultat dans [-1, 1].
        """
        i_from = self._index.get(from_concept)
        i_to = self._index.get(to_concept)
        if i_from is None:
            raise KeyError(f"Unknown concept: {from_concept}")
        if i_to is None:
            raise KeyError(f"Unknown concept: {to_concept}")
        self._weights[i_to, i_from] = np.clip(
            self._weights[i_to, i_from] + delta, -1.0, 1.0
        )

    def to_dict(self) -> dict:
        """Sérialise la FCM en dict (persistance JSON)."""
        d = {
            "name": self._name,
            "concepts": [
                {
                    "name": c.name,
                    "activation": c.activation,
                    "is_input": c.is_input,
                    "is_output": c.is_output,
                    **({"anchor_phrases": c.anchor_phrases} if c.anchor_phrases else {}),
                }
                for c in self._concepts
            ],
            "weights": self._weights.tolist(),
        }
        if self._boost_map:
            d["boost_map"] = self._boost_map
        if self._domain_phrases:
            d["domain_phrases"] = self._domain_phrases
        d["activation_count"] = self._activation_count
        d["total_interactions"] = self._total_interactions
        return d

    @classmethod
    def from_dict(cls, data: dict) -> FCMEngine:
        """Désérialise une FCM depuis un dict."""
        concepts = [
            FCMConcept(
                name=c["name"],
                activation=c.get("activation", 0.0),
                is_input=c.get("is_input", False),
                is_output=c.get("is_output", False),
                anchor_phrases=c.get("anchor_phrases", []),
                search_terms=c.get("search_terms", []),  # V2.5.0 Sprint K0
            )
            for c in data["concepts"]
        ]
        weights = np.array(data["weights"], dtype=np.float64)
        boost_map = data.get("boost_map", {})
        domain_phrases = data.get("domain_phrases", [])
        fcm = cls(name=data["name"], concepts=concepts, weights=weights,
                  domain_phrases=domain_phrases, boost_map=boost_map)
        fcm._activation_count = data.get("activation_count", 0)
        fcm._total_interactions = data.get("total_interactions", 0)
        return fcm
