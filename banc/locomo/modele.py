"""L'appel au modèle du banc LoCoMo — compatible OpenAI, sans dépendance (urllib).

Garde-fous :
- CACHE sur disque (`appels.jsonl` du run) : une relance ne repaie jamais un appel déjà fait ;
- COMPTE RÉEL des tokens (champ `usage` de l'API, cache d'OpenAI compris) et du coût en dollars ;
- ARRÊT LOCAL dès que le coût cumulé atteint LOCOMO_PLAFOND_USD (sous le plafond fixé chez OpenAI) ;
- la clé est lue dans un fichier 600 écrit par Francis (LOCOMO_CLE), jamais affichée, jamais journalisée ;
- MODE FACTICE (LOCOMO_FACTICE=1) : un modèle déterministe, sans réseau ni clé, pour éprouver tout le banc.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List

from commun import MODELE, PLAFOND_USD, PRIX, RUN, BANC, empreinte

FACTICE = os.environ.get("LOCOMO_FACTICE") == "1"
_VERROU = threading.Lock()
_CACHE: Dict[str, Dict] = {}
_CHARGE = False


class BudgetDepasse(RuntimeError):
    pass


def _fichier() -> Path:
    return RUN / ("appels-factices.jsonl" if FACTICE else "appels.jsonl")


def _charger() -> None:
    global _CHARGE
    if not _CHARGE:
        f = _fichier()
        if f.exists():
            for l in f.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    x = json.loads(l)
                    _CACHE[x["cle"]] = x
        _CHARGE = True


def depense() -> Dict:
    """Coût et tokens cumulés du run, par rôle."""
    with _VERROU:
        _charger()
        par = {}
        for x in _CACHE.values():
            r = par.setdefault(x["role"], {"appels": 0, "entree": 0, "entree_cache": 0, "sortie": 0, "usd": 0.0})
            r["appels"] += 1
            r["entree"] += x["entree"]; r["entree_cache"] += x["entree_cache"]; r["sortie"] += x["sortie"]; r["usd"] += x["usd"]
        total = {k: sum(r[k] for r in par.values()) for k in ("appels", "entree", "entree_cache", "sortie", "usd")}
        return {"par_role": par, "total": total}


def _cout(modele: str, entree: int, cache: int, sortie: int) -> float:
    p_in, p_cache, p_out = PRIX[modele]
    return ((entree - cache) * p_in + cache * p_cache + sortie * p_out) / 1e6


def appeler(messages: List[Dict[str, str]], role: str, modele: str = MODELE, max_tokens: int = 2000,
            json_seul: bool = False, passe: int = 0) -> str:
    """Rend le texte de la réponse. `role` : consolidation | page | reponse | juge (compte et mode factice)."""
    cle = empreinte({"m": modele, "msg": messages, "max": max_tokens, "t": 0, **({"json": 1} if json_seul else {}),
                     **({"passe": passe} if passe else {})})
    with _VERROU:
        _charger()
        if cle in _CACHE:
            return _CACHE[cle]["texte"]
        total = sum(x["usd"] for x in _CACHE.values())
        if not FACTICE and total >= PLAFOND_USD:
            raise BudgetDepasse(f"plafond local atteint : {total:.2f} $ ≥ {PLAFOND_USD} $")
    if FACTICE:
        texte, usage = _factice(messages, role), {"prompt_tokens": sum(len(m["content"]) for m in messages) // 4,
                                                  "completion_tokens": 20}
    else:
        texte, usage = _api(messages, modele, max_tokens, json_seul)
    entree = int(usage.get("prompt_tokens", 0))
    cache = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0)
    sortie = int(usage.get("completion_tokens", 0))
    x = {"cle": cle, "role": role, "modele": modele, "entree": entree, "entree_cache": cache, "sortie": sortie,
         "usd": 0.0 if FACTICE else round(_cout(modele, entree, cache, sortie), 6), "texte": texte,
         "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with _VERROU:
        _CACHE[cle] = x
        _fichier().parent.mkdir(parents=True, exist_ok=True)
        with _fichier().open("a", encoding="utf-8") as f:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    return texte


def _api(messages, modele, max_tokens, json_seul=False):
    cle = Path(os.environ.get("LOCOMO_CLE", str(BANC / ".cle-openai"))).read_text().strip()
    corps = json.dumps({"model": modele, "messages": messages, "temperature": 0, "max_tokens": max_tokens,
                        **({"response_format": {"type": "json_object"}} if json_seul else {})}).encode()
    attente = 2.0
    for essai in range(8):
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=corps, method="POST",
                                     headers={"Authorization": f"Bearer {cle}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read().decode())
            return d["choices"][0]["message"]["content"] or "", d.get("usage") or {}
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and essai < 7:
                time.sleep(attente); attente = min(60, attente * 2); continue
            raise RuntimeError(f"API {e.code} : {e.read().decode()[:300]}") from None
        except (urllib.error.URLError, TimeoutError):
            if essai < 7:
                time.sleep(attente); attente = min(60, attente * 2); continue
            raise
    raise RuntimeError("API injoignable")


# ── le modèle factice : déterministe, pour éprouver la plomberie sans rien dépenser ──
def _factice(messages, role) -> str:
    u = messages[-1]["content"]
    if role == "consolidation":
        frags = []
        for ref, qui, texte in re.findall(r"^\[(raw/[^\]]+)\] \[\d\d:\d\d (\w+)\] (.+)$", u, re.M):
            frags.append({"noeud": qui, "nouveau": True, "type_noeud": "entite", "alias": {"en": [qui.capitalize()], "fr": []},
                          "section": "episodic", "fait": texte, "src": [ref], "conf": 1.0, "concepts": []})
        return json.dumps({"fragments": frags, "concepts_nouveaux": {}})
    if role == "page":
        return json.dumps({"pages": re.findall(r"\| \[(\w+)\]", u)[:3]})
    if role == "reponse":
        m = re.search(r"^- (?:\[[^\]]*\] )?(.+)$", u, re.M)
        return " ".join((m.group(1) if m else "Unknown").split()[:6])
    if role == "juge" and "Model Response:" in u:              # juge de LongMemEval (docs/13) : « yes » / « no »
        gold = re.search(r"(?:Correct Answer|Rubric|Explanation): (.*)", u).group(1).lower()
        rep = re.search(r"Model Response: (.*)", u, re.S).group(1).lower()
        return "yes" if any(w in rep for w in re.findall(r"[a-z0-9]{4,}", gold)) else "no"
    if role == "juge":
        gold = re.search(r"Gold answer: (.*)", u).group(1).lower()
        rep = re.search(r"Generated answer: (.*)", u).group(1).lower()      # (même format dans les deux consignes)
        ok = any(w in rep for w in re.findall(r"[a-z0-9]{4,}", gold)) or ("not mentioned" in gold and "unknown" in rep)
        return json.dumps({"label": "CORRECT" if ok else "WRONG"})
    return ""
