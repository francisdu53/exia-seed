"""L'appel aux modèles du banc 17 (docs/17) — OpenAI, Anthropic, Mistral, sans dépendance (urllib). 05/11/2026.

Même interface que `banc/locomo/modele.py` (`appeler`, `depense`, `BudgetDepasse`) : le lecteur et le juge de LongMemEval
s'y branchent sans changement. Garde-fous repris de ce module :
- CACHE sur disque (un journal par modèle) : une relance ne repaie jamais un appel déjà fait ; le passage (`run`) fait
  partie de la clé, pour que le second passage soit un VRAI second appel ;
- COMPTES RÉELS renvoyés par chaque fournisseur (entrée, cache lu, cache écrit, sortie, raisonnement s'il est donné), le
  champ `usage` brut gardé à côté ; un compteur absent reste absent ;
- ARRÊT LOCAL dès que le coût cumulé de TOUT le banc atteint BANC_PLAFOND_USD (10 $) ;
- les clés sont lues dans des fichiers 600, jamais affichées, jamais journalisées ;
- MODE FACTICE (BANC_FACTICE=1) : réponses déterministes, sans réseau ni clé, pour éprouver tout le banc.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

BANC = Path(os.environ.get("BANC", "/banc"))
FACTICE = os.environ.get("BANC_FACTICE") == "1"
PLAFOND_USD = float(os.environ.get("BANC_PLAFOND_USD", "10"))
TERRA = "gpt-6.1-terra"                       # écrit les questions, lit et juge — le même pour tous (docs/17 §5.3)

# Tarifs officiels relevés le 05/11/2026, USD par million : entrée, entrée en cache (lecture), sortie (docs/17 §4)
PRIX = {"gpt-6-astra": (10.0, 1.0, 50.0), "gpt-6.1-terra": (1.0, 0.05, 5.0), "gpt-6-luna": (0.10, 0.01, 0.50),
        "claude-haiku-5-5": (0.10, 0.01, 0.50), "mistral-small-2603": (0.15, 0.015, 0.60),
        "mistral-large-4-0": (0.70, 0.07, 2.10)}
# fournisseur et effort de raisonnement pour CONSOLIDER (production : « low ») ; Small 4 n'a que none / high
MODELES = {"gpt-6-astra": ("hermes", "low"), "gpt-6.1-terra": ("openai", "low"), "gpt-6-luna": ("openai", "low"),
           "claude-haiku-5-5": ("anthropic", "low"), "mistral-small-2603": ("mistral", "none"),
           "mistral-large-4-0": ("mistral", "low")}
ROLES_SANS_RAISONNEMENT = {"question", "reponse", "juge"}   # Terra lecteur et juge : effort « none », sortie suffisante

_VERROU = threading.Lock()


class BudgetDepasse(RuntimeError):
    pass


def _journal(modele: str) -> Path:
    return BANC / "appels" / (f"{modele}{'-factice' if FACTICE else ''}.jsonl")


def _lire(f: Path) -> List[Dict]:
    if not f.exists():
        return []
    sortie = []
    for l in f.read_text(encoding="utf-8").splitlines():
        try:
            sortie.append(json.loads(l))
        except ValueError:                    # une ligne en cours d'écriture par un autre fil : ignorée, relue au prochain tour
            continue
    return sortie


def depense() -> Dict:
    """Coût et tokens cumulés de tout le banc, par modèle et par rôle (relu sur disque : plusieurs processus)."""
    par = {}
    for f in sorted((BANC / "appels").glob("*.jsonl")) if (BANC / "appels").exists() else []:
        if FACTICE != f.stem.endswith("-factice"):
            continue
        for x in _lire(f):
            r = par.setdefault(f"{x['modele']}/{x['role']}", {"appels": 0, "entree": 0, "entree_cache": 0, "sortie": 0, "usd": 0.0})
            r["appels"] += 1
            r["entree"] += x["entree"]; r["entree_cache"] += x["entree_cache"]; r["sortie"] += x["sortie"]; r["usd"] += x["usd"]
    total = {k: sum(r[k] for r in par.values()) for k in ("appels", "entree", "entree_cache", "sortie", "usd")}
    return {"par": par, "total": total}


def cle(modele: str, messages, max_tokens: int, json_seul: bool, run: str) -> str:
    brut = json.dumps({"m": modele, "msg": messages, "max": max_tokens, "json": json_seul, "run": run},
                      ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(brut.encode()).hexdigest()


def en_cache(modele: str, k: str) -> Optional[Dict]:
    for x in _lire(_journal(modele)):
        if x["cle"] == k:
            return x
    return None


def cout(modele: str, u: Dict) -> float:
    p_in, p_cache, p_out = PRIX[modele]
    hors_cache = max(0, u["entree"] - u["entree_cache"] - u.get("ecriture_cache", 0))
    return (hors_cache * p_in + u["entree_cache"] * p_cache + u.get("ecriture_cache", 0) * p_in * 1.25
            + u["sortie"] * p_out) / 1e6


def journaliser(modele: str, role: str, k: str, texte: str, u: Dict, brut, duree: float, run: str, usd: Optional[float] = None) -> Dict:
    x = {"cle": k, "modele": modele, "role": role, "run": run, **u, "usage_brut": brut, "duree_s": round(duree, 2),
         "usd": 0.0 if FACTICE else round(cout(modele, u) if usd is None else usd, 6), "texte": texte,
         "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with _VERROU:
        _journal(modele).parent.mkdir(parents=True, exist_ok=True)
        with _journal(modele).open("a", encoding="utf-8") as f:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    return x


def appeler(messages: List[Dict[str, str]], role: str, modele: str = TERRA, max_tokens: int = 8000,
            json_seul: bool = False, passe: int = 0, run: str = "r1") -> str:
    """Rend le texte de la réponse. `role` : consolidation | fiches | question | reponse | juge."""
    k = cle(modele, messages, max_tokens, json_seul, run)
    deja = en_cache(modele, k)
    if deja:
        return deja["texte"]
    total = depense()["total"]["usd"]
    if not FACTICE and total >= PLAFOND_USD:
        raise BudgetDepasse(f"plafond local atteint : {total:.2f} $ ≥ {PLAFOND_USD} $")
    t0 = time.monotonic()
    if FACTICE:
        texte, u, brut = _factice(messages, role), {"entree": sum(len(m["content"]) for m in messages) // 4,
                                                    "entree_cache": 0, "sortie": 20}, None
    else:
        fournisseur = MODELES.get(modele, ("openai", "low"))[0]
        effort = "none" if role in ROLES_SANS_RAISONNEMENT else MODELES.get(modele, ("", "low"))[1]
        sortie_max = max(max_tokens, 1000) if role in ROLES_SANS_RAISONNEMENT else max_tokens
        texte, u, brut = {"openai": _openai, "anthropic": _anthropic, "mistral": _mistral}[fournisseur](
            messages, modele, sortie_max, effort, json_seul)
    journaliser(modele, role, k, texte, u, brut, time.monotonic() - t0, run)
    return texte


# ── fournisseurs ─────────────────────────────────────────────────────────────
def _cles_ghost() -> Dict[str, str]:
    env = {}
    for l in Path(os.environ.get("BANC_CLES", "/cles/ghost.env")).read_text(encoding="utf-8").splitlines():
        l = l.strip().removeprefix("export ")
        if "=" in l and not l.startswith("#"):
            a, b = l.split("=", 1)
            env[a.strip()] = b.strip().strip('"').strip("'")
    return env


def _post(url: str, corps: Dict, entetes: Dict) -> Dict:
    donnees = json.dumps(corps).encode()
    attente = 2.0
    for essai in range(8):
        req = urllib.request.Request(url, data=donnees, method="POST", headers={"Content-Type": "application/json", **entetes})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            corps_err = e.read().decode("utf-8", "replace")[:400]
            if e.code in (408, 409, 429) or e.code >= 500:
                time.sleep(attente); attente = min(60, attente * 2); continue
            raise RuntimeError(f"HTTP {e.code} : {corps_err}")
        except (urllib.error.URLError, TimeoutError) as e:
            time.sleep(attente); attente = min(60, attente * 2); last = e
    raise RuntimeError("échec après 8 essais")


def _openai(messages, modele, max_tokens, effort, json_seul):
    cle_api = Path(os.environ.get("BANC_CLE_OPENAI", "/cle-openai")).read_text().strip()
    corps = {"model": modele, "messages": messages, "max_completion_tokens": max_tokens, "reasoning_effort": effort,
             **({"response_format": {"type": "json_object"}} if json_seul else {})}
    d = _post("https://api.openai.com/v1/chat/completions", corps, {"Authorization": f"Bearer {cle_api}"})
    us = d.get("usage") or {}
    u = {"entree": int(us.get("prompt_tokens") or 0),
         "entree_cache": int((us.get("prompt_tokens_details") or {}).get("cached_tokens") or 0),
         "sortie": int(us.get("completion_tokens") or 0)}
    r = (us.get("completion_tokens_details") or {}).get("reasoning_tokens")
    if r is not None:
        u["raisonnement"] = int(r)
    return (d["choices"][0]["message"].get("content") or ""), u, us


def _anthropic(messages, modele, max_tokens, effort, json_seul):
    cle_api = _cles_ghost()["EXIA_ANTHROPIC_API_KEY"]
    systeme = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    autres = [m for m in messages if m["role"] != "system"]
    corps = {"model": modele, "max_tokens": max_tokens, "messages": autres,
             **({"system": systeme} if systeme else {}),
             **({"output_config": {"effort": effort}} if effort and effort != "none" else {})}
    if effort == "none":                      # Haiku 5.5 : réflexion désactivable à effort « high » ou moins
        corps["thinking"] = {"type": "disabled"}
    d = _post("https://api.anthropic.com/v1/messages", corps, {"x-api-key": cle_api, "anthropic-version": "2023-06-01"})
    us = d.get("usage") or {}
    lu, ecrit = int(us.get("cache_read_input_tokens") or 0), int(us.get("cache_creation_input_tokens") or 0)
    u = {"entree": int(us.get("input_tokens") or 0) + lu + ecrit, "entree_cache": lu, "ecriture_cache": ecrit,
         "sortie": int(us.get("output_tokens") or 0)}          # la réflexion est comprise dans output_tokens
    texte = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    if d.get("stop_reason") == "refusal":
        texte = ""
    return texte, u, us


def _mistral(messages, modele, max_tokens, effort, json_seul):
    cle_api = _cles_ghost()["EXIA_MISTRAL_API_KEY"]
    corps = {"model": modele, "messages": messages, "max_tokens": max_tokens,
             **({"reasoning_effort": effort} if effort else {}),
             **({"response_format": {"type": "json_object"}} if json_seul else {})}
    d = _post("https://api.mistral.ai/v1/chat/completions", corps, {"Authorization": f"Bearer {cle_api}"})
    us = d.get("usage") or {}
    u = {"entree": int(us.get("prompt_tokens") or 0),
         "entree_cache": int((us.get("prompt_tokens_details") or {}).get("cached_tokens") or 0),
         "sortie": int(us.get("completion_tokens") or 0)}
    contenu = d["choices"][0]["message"].get("content") or ""
    if isinstance(contenu, list):            # certains modèles rendent des blocs (texte, raisonnement)
        contenu = "".join(b.get("text", "") for b in contenu if isinstance(b, dict) and b.get("type") == "text")
    return contenu, u, us


# ── mode factice : déterministe, pour éprouver la mécanique sans réseau ───────────────
def _factice(messages, role) -> str:
    texte = "\n".join(m["content"] for m in messages)
    if role == "fiches" or "FICHE D'IDENTITÉ" in texte[:4000]:
        return '{"fiches": {}}'
    if role == "consolidation":
        m = re.search(r"^\[(raw/[^\]]+)\] \[\d\d:\d\d francis\] (.{20,200})$", texte, re.M)
        if not m:
            return '{"fragments": []}'
        fait = m.group(2).strip()
        return json.dumps({"fragments": [{"noeud": "francis", "section": "episodic", "fait": fait, "src": [m.group(1)],
                                          "conf": 1.0, "speaker": "francis"}]}, ensure_ascii=False)
    if role == "question":
        return '{"question": "Que disait ce message ?", "reponse": "un détail"}'
    if role == "juge":
        return "yes"
    return "Réponse factice."
