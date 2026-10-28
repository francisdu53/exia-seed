"""Les enveloppes d'Hermès (docs/12 §5, §8) — ce qu'Hermès ajoute autour d'un message, et ce qu'il en reste à retenir.

Hermès 0.21.3 fait passer par le message « de l'utilisateur » des textes qui n'en sont pas : comptes rendus de
sous-agents et de processus, documents reçus, réponses citées. Leur protocole est en anglais et fixe
(« A background fan-out unit you dispatched… », « Role: leaf   Model: ? ») ; il allumait des sujets par ses mots
(« model » → JEV 42 fois, « subagent », « delegation » → la délégation 22 fois chacun, banc du 16/10).

    est_avis(texte)        compte rendu interne (sous-agent, processus, compaction) — pas une parole de l'utilisateur
    pour_rappel(texte)     le CONTENU à rappeler : but et résultat d'une tâche, nom d'un document ; sans le protocole
    reponse_vocale(…)      une réponse donnée EN VOCAL : le texte prononcé à la place du seul marqueur audio

Les formes sont celles RÉELLES d'Hermès (tools/process_registry_notifications.py, gateway/), pas « tout crochet en
majuscules » : un « [IMPORTANT] … » écrit par Francis reste sa parole, et passe tel quel.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

_RE_AVIS = re.compile(r"^\[(?:ASYNC DELEGATION [A-Z ]+|IMPORTANT: |CONTEXT COMPACTION|CRITICAL — )")
_RE_TACHE = re.compile(r"^--- \S+ TASK \d+/\d+:?\s*(.*?)\s*\((?:status=[^)]*)\)\s*---\s*$")
_RE_DOCUMENT = re.compile(r"^\[The user sent a document: '([^']+)'[^\]]*\]\s*", re.S)
# lignes de protocole d'un compte rendu de délégation : rien à rappeler
_PROTOCOLE = ("A background fan-out unit", "One subagent in a background fan-out", "Dispatched:", "Role:",
              "Original goal:", "Toolsets:", "Live transcript:", "Full live transcript", "Status:")


def est_avis(texte: str) -> bool:
    return bool(_RE_AVIS.match(texte or ""))


def pour_rappel(texte: str) -> str:
    """Le texte sur lequel la mémoire doit se rappeler. Un message ordinaire passe inchangé."""
    t = texte or ""
    if t.startswith("[ASYNC DELEGATION "):
        garde = []
        for ligne in t.splitlines()[1:]:
            s = ligne.strip()
            if not s or s.startswith(_PROTOCOLE):
                continue
            m = _RE_TACHE.match(s)
            garde.append(m.group(1) if m else s)
        return "\n".join(garde)
    if t.startswith("[IMPORTANT: Background process"):
        # « Command: … » dit ce qui tournait ; la suite est sa sortie. La première ligne n'est que le statut.
        lignes = t.splitlines()[1:]
        return "\n".join(l[len("Command:"):].strip() if l.startswith("Command:") else l for l in lignes)
    if est_avis(t):
        return ""                                   # compaction, rechargement, rappel de message : rien à rappeler
    m = _RE_DOCUMENT.match(t)
    if m:                                           # le NOM du document dit son sujet (« 041-2026_AUTOPLUS_VALMONT.pdf »)
        nom = re.sub(r"\.\w{2,4}$", "", m.group(1)).replace("_", " ").replace("-", " ")
        return (nom + "\n" + t[m.end():]).strip()
    return t


# ── Réponses vocales (26/10/2026) ───────────────────────────────────────────────────────────────────────────────
# Quand l'agent répond en vocal, Hermès lui fait renvoyer pour toute réponse « [[audio_as_voice]] » + « MEDIA:<fichier> » :
# le texte prononcé n'existe que dans l'appel de l'outil text_to_speech du tour. Constaté du 23 au 25/10 : 8 réponses
# vocales réduites à leur marqueur dans le brut — ni lues par la consolidation, ni retrouvables. Décision de Francis
# (26/10) : une réponse vocale est traitée comme une réponse écrite (entière dans le brut ; un fait n'en est retenu
# que si l'utilisateur l'a confirmé, comme pour toute parole de l'agent).
_MARQUE_VOCALE = "[[audio_as_voice]]"
OUTIL_VOIX = "text_to_speech"


def _texte_lu(appel: Dict[str, Any]) -> str:
    f = (appel or {}).get("function") or {}
    if f.get("name") != OUTIL_VOIX:
        return ""
    args = f.get("arguments") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return ""
    return str(args.get("text") or "").strip() if isinstance(args, dict) else ""


def reponse_vocale(reponse: str, messages: Optional[List[Dict[str, Any]]], repere: str = "") -> Optional[str]:
    """None si la réponse n'est pas un vocal, ou si le texte prononcé est introuvable (le marqueur reste alors tel quel).
    Sinon : le repère, le texte lu à voix haute pendant le tour (dans l'ordre), puis ce que la réponse disait d'autre."""
    r = (reponse or "").strip()
    if not r.startswith(_MARQUE_VOCALE) or not messages:
        return None
    lus: List[str] = []
    for m in reversed(messages):                    # le tour en cours : tout ce qui suit le dernier message de l'utilisateur
        if m.get("role") == "user":
            break
        if m.get("role") == "assistant":
            lus[:0] = [t for t in map(_texte_lu, m.get("tool_calls") or []) if t]
    if not lus:
        return None
    reste = [l for l in r.splitlines() if l.strip() and not l.strip().startswith((_MARQUE_VOCALE, "MEDIA:"))]
    return "\n".join([repere + "\n".join(lus)] + reste)
