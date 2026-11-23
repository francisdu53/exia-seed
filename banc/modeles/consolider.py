#!/usr/bin/env python3
"""Consolider les six jours avec UN modèle, un passage (docs/17 §3-4). Copies seulement.

Code de production de Nexa (copie figée dans /banc/plugin), consigne de production, 40 000 tokens d'entrée par appel,
réponse jusqu'à 8 000, fiches (second appel), contrôle de citation inchangé. Chaque jour part de son point de départ
(`preparer.py`), copié dans /banc/runs/<modèle>/<passage>/<jour>/memoire ; on consolide jusqu'à épuisement des lots.

- modèles par API : conteneur jetable du banc (`lancer.sh consolider <modèle> <passage>`) ;
- gpt-6-astra : DANS le conteneur de Nexa (`docker exec -u hermes nexa …`), par le client d'Hermès et son abonnement,
  sans copier ses identifiants — comme sa consolidation de nuit, effort « low ». Les compteurs renvoyés sont gardés.

    python3 consolider.py <modèle> <r1|r2>
"""
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

ICI = Path(__file__).resolve().parent
BANC = Path(os.environ.get("BANC", "/banc"))
sys.path.insert(0, str(BANC / "plugin")); sys.path.insert(0, str(ICI))
import appel                                                           # noqa: E402
from exia_seed import consolidation as _C                              # noqa: E402
from exia_seed.consolidation import Consolidateur                      # noqa: E402

# Variante de consigne (docs/17 §10) : la consigne SYSTÈME de production remplacée par un fichier du banc, le reste
# (message utilisateur, contrôle de citation, écriture) inchangé. Sans variable : la consigne de production.
if os.environ.get("BANC_CONSIGNE"):
    _C.PROMPT_SYSTEME = (ICI / os.environ["BANC_CONSIGNE"]).read_text(encoding="utf-8").strip()
if os.environ.get("BANC_EFFORT"):                                       # effort de raisonnement de la variante
    for _m, (_f, _e) in list(appel.MODELES.items()):
        appel.MODELES[_m] = (_f, os.environ["BANC_EFFORT"])

JOURS = tuple(json.loads((BANC / f"{os.environ.get('BANC_PANEL', 'jours')}.json").read_text(encoding="utf-8")))
RUNS = BANC / ("runs-factice" if appel.FACTICE else "runs")   # l'essai à blanc ne touche jamais le vrai banc


def fonction_astra(run: str):
    """La consolidation de nuit de Nexa (appel_llm_hermes « low »), plus la journalisation des compteurs."""
    sys.path.insert(0, "/opt/hermes")
    from agent.auxiliary_client import call_llm, extract_content_or_reasoning
    from hermes_cli.config import load_config
    from hermes_constants import parse_reasoning_effort
    cfg = (load_config() or {}).get("model") or {}
    vus = {}

    def appeler(messages):
        role = "fiches" if "FICHE D'IDENTITÉ" in messages[0]["content"] else "consolidation"
        k = appel.cle("gpt-6-astra", messages, 0, False, run)
        if os.environ.get("BANC_NOUVEL_ESSAI") == "1":           # même règle que les modèles par API (§9.3)
            vus[k] = vus.get(k, 0) + 1
            if vus[k] > 1:
                k = appel.cle("gpt-6-astra", messages, 0, False, f"{run}+essai{vus[k]}")
        deja = appel.en_cache("gpt-6-astra", k)
        if deja:
            return deja["texte"]
        t0 = time.monotonic()
        rep = call_llm(task="exia_seed_consolidation", provider=cfg.get("provider") or None, model=cfg.get("default") or None,
                       messages=messages, reasoning_config=parse_reasoning_effort("low"), timeout=300)
        texte = extract_content_or_reasoning(rep)
        us = getattr(rep, "usage", None)
        brut = us.model_dump() if hasattr(us, "model_dump") else (dict(us) if isinstance(us, dict) else (vars(us) if us is not None else None))
        brut = json.loads(json.dumps(brut, default=str)) if brut is not None else None
        b = brut or {}
        u = {"entree": int(b.get("prompt_tokens") or b.get("input_tokens") or 0),
             "entree_cache": int((b.get("prompt_tokens_details") or b.get("input_tokens_details") or {}).get("cached_tokens") or 0),
             "sortie": int(b.get("completion_tokens") or b.get("output_tokens") or 0)}
        r = (b.get("completion_tokens_details") or b.get("output_tokens_details") or {}).get("reasoning_tokens")
        if r is not None:
            u["raisonnement"] = int(r)
        appel.journaliser("gpt-6-astra", role, k, texte, u, brut, time.monotonic() - t0, run, usd=0.0)   # abonnement : 0 $ réel
        return texte
    return appeler


SORTIE_MAX = int(os.environ.get("BANC_SORTIE_MAX", "8000"))       # 8 000 : protocole ; analyse complémentaire : 32 000
NOUVEL_ESSAI = os.environ.get("BANC_NOUVEL_ESSAI") == "1"          # complémentaire : un échec rappelle VRAIMENT le modèle


def fonction_api(modele: str, run: str):
    vus = {}

    def appeler(messages):
        role = "fiches" if "FICHE D'IDENTITÉ" in messages[0]["content"] else "consolidation"
        tag = run
        if NOUVEL_ESSAI:                     # comme la production : un nouvel essai est un nouvel appel, pas le cache
            k = appel.cle(modele, messages, SORTIE_MAX, False, run)
            vus[k] = vus.get(k, 0) + 1
            tag = run if vus[k] == 1 else f"{run}+essai{vus[k]}"
        return appel.appeler(messages, role, modele=modele, max_tokens=SORTIE_MAX, run=tag)
    return appeler


DEPART = os.environ.get("BANC_DEPART", "depart")           # §22 : depart-K = lots découpés à K tokens
BUDGET = int(os.environ.get("BANC_BUDGET", "40000"))       # §22 : un passage ne prend pas plus de K tokens de brut
CATALOGUE = os.environ.get("BANC_CATALOGUE", "complet")            # docs/17 §12 : « cible » = liste choisie par la FCM
CIBLE_MAX = int(os.environ.get("BANC_CIBLE_MAX", "30"))
IMPLICITES = ("francis", "nexa")
_MSG = re.compile(r"^\[(raw/[^\]]+|registre:[^\]]+)\] ?(.*)$")


def cibler(fn, racine: Path, journal: Path):
    """La liste des nœuds existants réduite à ceux que la recherche fait remonter (docs/17 §12).

    Seul ce que VOIT le modèle change : la résolution des alias (une page nommée par le modèle rejoint la page
    existante) garde la liste complète, comme en production. Une recherche par message (en-tête et lignes de suite),
    même cascade que `memoire_chercher` (nom, alias, mot, champ lexical, plein texte, puis propagation) ; les nœuds
    touchés directement passent avant ceux de la propagation ; au plus CIBLE_MAX, plus l'utilisateur et l'agent."""
    from exia_seed.rappel import Rappeleur
    R = Rappeleur(racine)

    def appeler(messages):
        u = messages[-1]["content"]
        if not u.startswith("NŒUDS EXISTANTS\n") or "\n\nCONCEPTS EXISTANTS\n" not in u:
            return fn(messages)                                        # l'appel « fiches » : inchangé
        tete, reste = u.split("\n\nCONCEPTS EXISTANTS\n", 1)
        lignes = tete.split("\n")[1:]
        sources = reste.split("\n\nSOURCES\n", 1)[-1]
        textes, courant = [], ""
        for l in sources.splitlines():
            m = _MSG.match(l)
            if not m:
                continue
            ref, t = m.groups()
            if ref.startswith("registre:") or re.match(r"\[\d\d:\d\d ", t):
                if courant: textes.append(courant)
                courant = t
            else:
                courant += " " + t
        if courant: textes.append(courant)
        mem = R.memoire()
        score = {}
        if mem is not None:
            for t in textes:
                a = R.activer(mem, t)
                for n, v in a["entrees"].items():
                    score[n] = max(score.get(n, 0.0), 1.0 + v)         # touché directement : d'abord
                for n, v in a["actives"].items():
                    score[n] = max(score.get(n, 0.0), v)
        noeud = lambda l: l[2:].split(" (", 1)[0]
        presents = [noeud(l) for l in lignes if l.startswith("- ")]
        classes = [n for n in sorted(score, key=score.get, reverse=True) if n in presents and n not in IMPLICITES]
        garder = set(classes[:CIBLE_MAX]) | set(IMPLICITES)
        gardees = [l for l in lignes if l.startswith("- ") and noeud(l) in garder] or ["(aucun)"]
        ajouter = {"lignes_completes": len(presents), "lignes_gardees": len(gardees), "messages": len(textes), "candidats": len(classes),
                   "car_complet": len(tete), "car_cible": len("\n".join(gardees)) + 17, "gardes": sorted(garder & set(presents))}
        with journal.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ajouter, ensure_ascii=False) + "\n")
        return fn([*messages[:-1], {"role": "user", "content": "NŒUDS EXISTANTS\n" + "\n".join(gardees)
                                    + "\n\nCONCEPTS EXISTANTS\n" + reste}])
    return appeler


FORMAT = os.environ.get("BANC_FORMAT", "")                  # §26 : « xml » = sections en balises (convention d'Anthropic)
RAPPEL = (ICI / os.environ["BANC_RAPPEL"]).read_text(encoding="utf-8").strip() if os.environ.get("BANC_RAPPEL") else ""


def en_xml(fn):
    """La même matière, organisée à la manière d'Anthropic : chaque partie entre balises, la conversation en dernier,
    puis un rappel des règles clés juste avant la réponse. La consigne système et le contrat de sortie ne changent pas."""
    def appeler(messages):
        u = messages[-1]["content"]
        if not u.startswith("NŒUDS EXISTANTS\n") or "\n\nCONCEPTS EXISTANTS\n" not in u or "\n\nSOURCES\n" not in u:
            return fn(messages)                                        # l'appel « fiches » : inchangé
        noeuds, reste = u[len("NŒUDS EXISTANTS\n"):].split("\n\nCONCEPTS EXISTANTS\n", 1)
        concepts, sources = reste.split("\n\nSOURCES\n", 1)
        x = (f"<noeuds_existants>\n{noeuds}\n</noeuds_existants>\n\n<concepts_existants>\n{concepts}\n</concepts_existants>\n\n"
             f"<conversation>\n{sources}\n</conversation>" + (f"\n\n{RAPPEL}" if RAPPEL else ""))
        return fn([*messages[:-1], {"role": "user", "content": x}])
    return appeler


def main():
    modele, run = sys.argv[1], sys.argv[2]
    fn0 = fonction_astra(run) if modele == "gpt-6-astra" and not appel.FACTICE else fonction_api(modele, run)
    bilan = {}
    for etiq in JOURS:
        racine = RUNS / modele / run / etiq / "memoire"
        if (racine.parent / "fini.json").exists():
            bilan[etiq] = json.loads((racine.parent / "fini.json").read_text(encoding="utf-8")); continue
        if racine.exists():
            shutil.rmtree(racine)
        shutil.copytree(BANC / DEPART / etiq / "memoire", racine)
        (racine.parent / "cible.jsonl").unlink(missing_ok=True)
        fn = cibler(fn0, racine, racine.parent / "cible.jsonl") if CATALOGUE == "cible" else fn0
        fn = en_xml(fn) if FORMAT == "xml" else fn
        if os.environ.get("BANC_CONTEXTE"):               # §29 : les échanges précédents, montrés mais NON citables
            ctx_par_lot = {}
            for l in (racine / "raw" / ".chaine.jsonl").read_text(encoding="utf-8").splitlines():
                if l.strip():
                    e = json.loads(l)
                    if e.get("contexte"):
                        ctx_par_lot[e["fichier"]] = e["contexte"]
            def avec_contexte(messages, _fn=fn, _ctx=ctx_par_lot):
                txt = messages[-1]["content"]
                lots_ici = re.findall(r"── raw/(\S+) :", txt)
                lignes = [x for f in lots_ici for x in _ctx.get(f, [])]
                if lignes and "\nSOURCES\n" in txt:
                    bloc = ("CONTEXTE — les échanges juste avant, DÉJÀ consolidés. Ils servent seulement à comprendre de qui "
                            "et de quoi on parle. N'en tire AUCUN fait et ne les cite JAMAIS : tes faits ne citent que des "
                            "lignes de SOURCES.\n" + "\n".join("› " + x for x in lignes) + "\n\n")
                    txt = txt.replace("\nSOURCES\n", "\n" + bloc + "SOURCES\n", 1)
                    messages = messages[:-1] + [{**messages[-1], "content": txt}]
                    with open(racine.parent / "contexte.jsonl", "a", encoding="utf-8") as j:   # trace : ce qui a été montré
                        j.write(json.dumps({"lots": lots_ici, "lignes_contexte": len(lignes), "debut": lignes[0][:60]}, ensure_ascii=False) + "\n")
                return _fn(messages)
            fn = avec_contexte
        cons = Consolidateur(racine, ZoneInfo("Europe/Paris"), fn, modele=modele, max_tokens_entree=BUDGET,
                             nom_agent="nexa", nom_utilisateur="francis", fiches=True)
        if os.environ.get("BANC_UN_LOT"):                 # §28 : un seul lot (un échange) par appel au modèle
            cons.max_tokens = 1
        passages, bloques, t0 = [], 0, time.monotonic()
        while cons.lots_en_attente() or cons.registre.en_attente():
            avant = (list(cons.lots_en_attente()), len(cons.registre.en_attente()))
            try:
                r = cons.consolider()
            except appel.BudgetDepasse as e:
                print(f"⛔ {e}", flush=True); (RUNS / "ARRET_BUDGET").write_text(str(e)); return 2
            except Exception as e:
                passages.append({"statut": "exception", "erreur": repr(e)[:300]}); bloques += 1
                if bloques >= 2:
                    break
                time.sleep(20); continue
            passages.append({k: r.get(k) for k in ("statut", "faits_retenus", "fragments_rejetes", "lots", "extrait")})
            if (list(cons.lots_en_attente()), len(cons.registre.en_attente())) == avant:
                bloques += 1
                if bloques >= 2:
                    break
        b = {"passages": passages, "perdus": len(cons.lots_en_attente()), "duree_s": round(time.monotonic() - t0, 1),
             "faits_retenus": sum(p.get("faits_retenus") or 0 for p in passages),
             "rejets": sum(p.get("fragments_rejetes") or 0 for p in passages)}
        (racine.parent / "fini.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
        bilan[etiq] = b
        print(f"{modele} {run} {etiq} : {b['faits_retenus']} faits, {b['rejets']} rejets, {b['perdus']} lots perdus, "
              f"{b['duree_s']} s", flush=True)
    (RUNS / modele / run / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
