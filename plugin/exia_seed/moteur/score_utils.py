"""
EXIA GHOST V2.3.0 — Score utilities — Famille EXIA CAB

Primitive mathématique : cab_pull(score, target, factor)
Spec complète : exia-ghost-v5-spec/05b_EXIA_CAB.md

Historique :
  V2.2.3 — cab_boost créée pour résoudre la saturation à 1.0 des scores boostés.
  V2.3.0 — Généralisation : cab_boost est un cas particulier de cab_pull (lerp).
            Ajout de cab_penalty et tcab_penalty comme dérivées.
            Backward compat préservée (cab_boost reste un alias).

La primitive cab_pull :
  cab_pull(score, target, factor) = (1 - factor) * score + factor * target

  C'est une interpolation linéaire bornée qui tire un score vers une cible.
  - target=1.0 → boost (cab_boost)
  - target=0.0 → pénalité (cab_penalty)
  - factor=0   → identité (retourne score inchangé)
  - factor=1   → saturation (retourne target)

  Propriétés : monotone, bornée [min(s,t), max(s,t)], continue, self-limiting.
  Coût : 2 mul + 1 add, O(1), sub-microseconde.
"""

from __future__ import annotations

from typing import Union

_Number = Union[int, float]


# ── Primitive ────────────────────────────────────────────

def cab_pull(score: _Number, target: _Number, factor: _Number) -> float:
    """EXIA CAB primitive — tire un score vers une cible avec un poids.

    Formule : (1 - factor) * score + factor * target

    C'est l'interpolation linéaire (lerp) bornée qui unifie cab_boost
    (target=1.0) et cab_penalty (target=0.0) sous une seule opération.

    Args:
        score: valeur courante, attendue dans [0, 1]. Clampée défensivement.
        target: valeur cible vers laquelle tirer, dans [0, 1].
        factor: poids de l'attraction, dans [0, 1].

    Returns:
        Score après traction vers la cible. Garanti dans [min(s,t), max(s,t)].

    Examples:
        >>> round(cab_pull(0.75, 1.0, 0.10), 4)  # boost
        0.775
        >>> round(cab_pull(0.75, 0.0, 0.10), 4)  # penalty
        0.675
        >>> cab_pull(0.50, 1.0, 0.0)              # identity
        0.5
        >>> cab_pull(0.50, 1.0, 1.0)              # saturation
        1.0
    """
    if score < 0.0:
        score = 0.0
    elif score > 1.0:
        score = 1.0
    if target < 0.0:
        target = 0.0
    elif target > 1.0:
        target = 1.0
    if factor <= 0.0:
        return float(score)
    if factor >= 1.0:
        return float(target)
    return float((1.0 - factor) * score + factor * target)


# ── Dérivées ─────────────────────────────────────────────

def cab_boost(score: _Number, factor: _Number) -> float:
    """Boost vers 1.0 — tire le score vers le haut.

    Alias historique V2.2.3 : cab_pull(score, 1.0, factor).
    Utilisé par les 4 boosts du retrieval (BM25, triplet, FCM, entity name).

    Mathematical form: score + (1 - score) * factor

    Args:
        score: current score, expected in [0, 1]. Clamped defensively.
        factor: boost strength in [0, 1]. E.g. 0.10 = advance 10% toward 1.0.

    Returns:
        New score in [0, 1]. Guaranteed >= score when factor > 0.

    Examples:
        >>> round(cab_boost(0.50, 0.10), 4)
        0.55
        >>> round(cab_boost(0.80, 0.10), 4)
        0.82
        >>> round(cab_boost(0.95, 0.10), 4)
        0.955
        >>> cab_boost(0.50, 0.0)
        0.5
    """
    return cab_pull(score, 1.0, factor)


def cab_penalty(score: _Number, factor: _Number) -> float:
    """Pénalité vers 0.0 — tire le score vers le bas.

    Alias sémantique : cab_pull(score, 0.0, factor).
    Base pour les pénalisations spécialisées (T-CAB, ESB futur).

    Mathematical form: score * (1 - factor)

    Args:
        score: current score, expected in [0, 1].
        factor: penalty strength in [0, 1]. E.g. 0.10 = reduce 10% toward 0.0.

    Returns:
        New score in [0, 1]. Guaranteed <= score when factor > 0.

    Examples:
        >>> round(cab_penalty(0.85, 0.10), 4)
        0.765
        >>> round(cab_penalty(0.85, 0.20), 4)
        0.68
        >>> cab_penalty(0.85, 0.0)
        0.85
    """
    return cab_pull(score, 0.0, factor)


def tcab_penalty(
    score: _Number,
    date_count: int,
    lambda_val: _Number,
    max_picks: int = 5,
) -> float:
    """T-CAB (Temporal-CAB) — pénalise les memories sur-représentées par date.

    Calcule un factor progressif basé sur le nombre de fois où la même date
    a déjà été pickée dans le top-k, puis applique cab_penalty.

    factor = lambda_val × min(1.0, date_count / max_picks)

    Progression avec lambda_val=0.20, max_picks=5 :
      pick #1 (count=0) → factor=0.00 → pas de pénalité
      pick #2 (count=1) → factor=0.04 → -4%
      pick #3 (count=2) → factor=0.08 → -8%
      pick #4 (count=3) → factor=0.12 → -12%
      pick #5 (count=4) → factor=0.16 → -16%
      pick #6 (count=5) → factor=0.20 → -20% (saturé)

    Args:
        score: candidate score from retrieval.
        date_count: how many memories from this date are already picked.
        lambda_val: penalty strength [0.0, 0.5]. 0.0 = disabled.
        max_picks: saturation threshold. Default 5.

    Returns:
        Penalized score.

    Examples:
        >>> tcab_penalty(0.85, 0, 0.20)    # no prior picks
        0.85
        >>> round(tcab_penalty(0.85, 3, 0.20), 4)  # 3 prior picks
        0.7480000000000001
        >>> round(tcab_penalty(0.85, 5, 0.20), 4)  # saturated
        0.68
    """
    if lambda_val <= 0.0 or date_count <= 0:
        return float(score) if isinstance(score, float) else float(score)
    factor = lambda_val * min(1.0, date_count / max_picks)
    return cab_pull(score, 0.0, factor)


def esb_penalty(
    score: _Number,
    centrality: _Number,
    lambda_val: _Number,
) -> float:
    """ESB (EXIA Specificity Boost) — pénalise les memories proches du centroïde.

    Combat l'effet centroid des embeddings : les phrases génériques tendent
    à être proches de toutes les queries (cosine élevé sur tout), masquant
    les phrases spécifiques qui répondraient réellement à la question.

    factor = lambda_val × centrality

    Exemples avec lambda_val=0.25 :
      centralité 0.75 (générique) → factor=0.1875 → score × 0.81 (-19%)
      centralité 0.30 (spécifique) → factor=0.075 → score × 0.93 (-7%)
      centralité 0.20 (très spéc.) → factor=0.050 → score × 0.95 (-5%)

    Args:
        score: candidate score from retrieval (cosine brut).
        centrality: cosine(vector, centroid) ∈ [0, 1]. Pre-computed at store().
        lambda_val: penalty strength [0.0, 0.5]. 0.0 = disabled.

    Returns:
        Penalized score.

    Examples:
        >>> round(esb_penalty(0.85, 0.75, 0.25), 4)  # generic → strong penalty
        0.6906
        >>> round(esb_penalty(0.75, 0.30, 0.25), 4)  # specific → mild penalty
        0.6938
        >>> esb_penalty(0.85, 0.0, 0.25)              # zero centrality → no penalty
        0.85
        >>> esb_penalty(0.85, 0.75, 0.0)              # ESB disabled
        0.85
    """
    if lambda_val <= 0.0 or centrality <= 0.0:
        return float(score) if isinstance(score, float) else float(score)
    factor = lambda_val * min(1.0, centrality)
    return cab_pull(score, 0.0, factor)


def isb_penalty(
    score: _Number,
    information_score: _Number,
    lambda_val: _Number,
) -> float:
    """ISB (Information Specificity Boost) — pénalise les mémoires pauvres en information.

    Combat le bruit textuel : les micro-phrases ("Got it, Nate", "Yum!")
    ont un cosine élevé sur tout mais ZÉRO contenu informationnel.
    ESB pénalise par la POSITION (centroïde), ISB pénalise par le CONTENU.

    factor = lambda_val × (1 - information_score)

    Exemples avec lambda_val=0.30 :
      info_score 0.10 (bruit)    → factor=0.27 → score × 0.73 (-27%)
      info_score 0.50 (moyen)    → factor=0.15 → score × 0.85 (-15%)
      info_score 0.90 (riche)    → factor=0.03 → score × 0.97 (-3%)

    Args:
        score: candidate score from retrieval.
        information_score: content richness ∈ [0, 1]. Pre-computed at store().
        lambda_val: penalty strength [0.0, 0.5]. 0.0 = disabled.

    Returns:
        Penalized score.

    Examples:
        >>> round(isb_penalty(0.85, 0.10, 0.30), 4)  # noise → strong penalty
        0.6205
        >>> round(isb_penalty(0.85, 0.90, 0.30), 4)  # rich → mild penalty
        0.8245
        >>> isb_penalty(0.85, 0.50, 0.0)               # ISB disabled
        0.85
    """
    if lambda_val <= 0.0 or information_score >= 1.0:
        return float(score)
    factor = lambda_val * (1.0 - min(1.0, max(0.0, information_score)))
    return cab_pull(score, 0.0, factor)


def cab_lexical(
    bm25_score: _Number,
    target: _Number = 0.65,
    base: _Number = 0.30,
) -> float:
    """CAB-Lexical — score les résultats BM25-only via cab_pull.

    Les résultats trouvés par BM25/FTS5 mais PAS par cosine n'ont pas de
    similarity score. Cette fonction leur attribue un score proportionnel
    à la qualité du match BM25, tiré de base vers target via cab_pull.

    Quality = |bm25_score| / 10 ∈ [0, 1] (plus négatif = meilleur match)

    Exemples avec target=0.65 :
      BM25 -3.5 (moyen)  → quality 0.35 → score 0.42
      BM25 -5.0 (bon)    → quality 0.50 → score 0.48
      BM25 -10  (fort)    → quality 1.00 → score 0.65

    Args:
        bm25_score: raw FTS5 bm25() score (negative, more negative = better).
        target: cab_pull target score for BM25-only results. Tunable.
        base: minimum score (floor). Default 0.30.

    Returns:
        Score in [base, target].
    """
    quality = min(1.0, abs(bm25_score) / 10.0)
    return cab_pull(base, target, quality)
