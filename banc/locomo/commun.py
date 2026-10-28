"""Banc LoCoMo (docs/09) — ce que partagent les étapes : chemins, réglages, données, faits datés.

Rien ici n'appelle de modèle. Les étapes :
    preparer.py   conversations → mémoires EXIA SEED (une par conversation), consolidées session par session
    fusionner.py  les 10 mémoires → une seule (l'échelle « fusionnée »)
    recuperer.py  moteurs A (FCM) et C (plein texte) → contextes (12 faits au plus)
    embeddings.py moteur B (bge-m3) — sur l'HÔTE, comme au banc 8
    repondre.py   A, B, C (contextes) + D (Karpathy pur) + E (tout le contexte) → réponses
    juger.py      juge LoCoMo standard (celui d'EXIA GHOST, permissif) → étiquettes
    bilan.py      tableaux par moteur, échelle, catégorie, tranche (pilote / vérification)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

# ── emplacements (surchargeables : le banc à blanc utilise un autre dossier) ──
BANC = Path(os.environ.get("LOCOMO_BANC", "/banc"))                 # monté depuis $HOME/banc-locomo
DONNEES = Path(os.environ.get("LOCOMO_DONNEES", str(BANC / "donnees" / "locomo10.json")))
RUN = BANC / "runs" / os.environ.get("LOCOMO_RUN", "pilote")
PLUGINS = os.environ.get("LOCOMO_PLUGINS", "/plugins")

# ── réglages du protocole (docs/09 §2, §6) — fixés AVANT la mesure ──
BUDGET_FAITS = 12                    # contexte de A, B, C : 12 faits au plus
PILOTE = ("conv-26", "conv-30")      # §5 : rapportées à part ; les chiffres annoncés portent sur les 8 autres
CAT5_GOLD = "Not mentioned"          # comme EXIA GHOST (eval_locomo.py)
MODELE = os.environ.get("LOCOMO_MODELE", "gpt-4o-mini")
# Prix en $ par million de tokens (entrée, entrée en cache, sortie) — À VÉRIFIER le jour du lancement (§7)
PRIX = {"gpt-4o-mini": (0.15, 0.075, 0.60), "gpt-4.1-mini": (0.40, 0.10, 1.60)}
PLAFOND_USD = float(os.environ.get("LOCOMO_PLAFOND_USD", "20"))   # arrêt local, sous le plafond fixé chez OpenAI
# Interlocuteurs « implicites » (comme l'utilisateur chez Nexa : leur nom n'allume rien). DÉFAUT DU BANC trouvé le 18/10
# (docs/09 §14.5) : dans LoCoMo, celui qui pose la question n'est AUCUN des deux interlocuteurs — « What did Caroline… »
# nomme un sujet comme un autre. Jusqu'au run complet-091 inclus : implicites (LOCOMO_IMPLICITES=1 pour le rejouer).
IMPLICITES = os.environ.get("LOCOMO_IMPLICITES", "0") == "1"
# LongMemEval (docs/13, 27/10/2026) : un UTILISATEUR et son ASSISTANT, comme chez Nexa — speaker_a = l'utilisateur,
# speaker_b = l'agent (règle 4 de la consolidation : ce que dit l'agent n'est retenu que confirmé). LoCoMo : deux humains.
ROLES = os.environ.get("LOCOMO_ROLES", "interlocuteurs")          # « interlocuteurs » (LoCoMo) | « agent » (LongMemEval)
# Fusion : dans LongMemEval, tous les historiques sont ceux d'UN utilisateur (c'est la construction même du jeu) ;
# « user » et « assistant » ne sont pas des homonymes à séparer. LoCoMo : oui (trois « John »).
HOMONYMES = os.environ.get("LOCOMO_HOMONYMES", "1") == "1"


def preparer_chemins() -> None:
    sys.path.insert(0, "/opt/hermes")
    sys.path.insert(0, PLUGINS)


def charger_donnees(selection: Iterable[str] = ()) -> List[Dict]:
    d = json.loads(DONNEES.read_text(encoding="utf-8"))
    sel = set(selection or ())
    return [x for x in d if not sel or x["sample_id"] in sel]


def selection_du_run() -> List[str]:
    f = RUN / "selection.json"
    return json.loads(f.read_text()) if f.exists() else []


def sessions(conv: Dict) -> List[tuple]:
    """[(numéro, datetime, tours)] dans l'ordre."""
    c = conv["conversation"]
    nums = sorted(int(k.split("_")[1]) for k in c if re.fullmatch(r"session_\d+", k))
    return [(n, lire_date(c[f"session_{n}_date_time"]), c[f"session_{n}"]) for n in nums]


def lire_date(s: str) -> datetime:
    """« 1:56 pm on 8 May, 2023 » → datetime(2023, 5, 8, 13, 56)."""
    return datetime.strptime(re.sub(r"\s+", " ", s.strip()), "%I:%M %p on %d %B, %Y")


def texte_du_tour(t: Dict) -> str:
    """Le texte, et la légende d'une photo partagée (format déclaré, docs/09 §3)."""
    txt = (t.get("text") or "").strip()
    if t.get("blip_caption"):
        txt += f" [shares a photo: {t['blip_caption'].strip()}]"
    return re.sub(r"\s+", " ", txt)


def etiquette(nom: str) -> str:
    return re.sub(r"\s+", "_", nom.strip().lower())


def questions(convs: List[Dict]) -> List[Dict]:
    """Toutes les questions, avec leur réponse attendue, leur tranche et l'instant où on les pose (après la
    dernière session : un fait n'est jamais « dit après » la question)."""
    sortie = []
    for conv in convs:
        derniere = sessions(conv)[-1][1]
        for k, q in enumerate(conv["qa"]):
            cat = int(q["category"])
            sortie.append({"id": f"{conv['sample_id']}:{k}", "conv": conv["sample_id"], "categorie": cat,
                           "question": q["question"], "gold": CAT5_GOLD if cat == 5 else str(q.get("answer", "")),
                           "tranche": "pilote" if conv["sample_id"] in PILOTE else "verification",
                           # LongMemEval (docs/13) donne l'instant de la question ; LoCoMo non : après la dernière session
                           "instant": q.get("instant") or derniere.replace(hour=23, minute=59).isoformat(timespec="minutes"),
                           **{c: q[c] for c in ("type", "abstention", "date_question") if c in q}})
    return sortie


def faits_dates(memoire: Path) -> Dict[str, str]:
    """{texte du fait : « 8 May 2023 »} depuis les pages — la date où le fait a été DIT (dit_le)."""
    sortie = {}
    for p in sorted((memoire / "pages").glob("*.md")):
        for l in p.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^- (.*?) <!-- (.*?) -->\s*$", l)
            if m:
                d = re.search(r"(?:^| )dit_le:(\d{4}-\d{2}-\d{2})", m.group(2))
                sortie[m.group(1).strip()] = datetime.strptime(d.group(1), "%Y-%m-%d").strftime("%-d %B %Y") if d else ""
    return sortie


def contexte(faits: List[str], dates: Dict[str, str]) -> str:
    """Le contexte donné au modèle, IDENTIQUE pour A, B et C : un fait par ligne, avec sa date."""
    return "\n".join(f"- [{dates.get(f, '')}] {f}" if dates.get(f) else f"- {f}" for f in faits) or "- (no memories found)"


def ecrire_jsonl(chemin: Path, lignes: Iterable[Dict]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lignes), encoding="utf-8")


def lire_jsonl(chemin: Path) -> List[Dict]:
    return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()] if chemin.exists() else []


def empreinte(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]
