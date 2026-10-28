#!/usr/bin/env python3
"""Étape 1 — chaque conversation LoCoMo devient une mémoire EXIA SEED (docs/09 §3).

Une session = un fichier brut daté (`raw/2023-05-08_01.md`, en-tête `date`, `ouvert_le`), écrit puis
CONSOLIDÉ aussitôt, dans l'ordre : comme une journée de Nexa, la session suivante voit les nœuds et les
concepts de la précédente. Mémoire en anglais (`.langue` = en), deux interlocuteurs, pas d'agent.
Reprise : une session déjà consolidée n'est pas refaite (et le cache du modèle évite de repayer).

    python3 preparer.py conv-26 conv-30        (sans argument : la sélection du run)
"""
from __future__ import annotations

import json
import sys
from zoneinfo import ZoneInfo

import commun as K

K.preparer_chemins()
from exia_seed import langues                                     # noqa: E402
from exia_seed.consolidation import Consolidateur                 # noqa: E402
import modele                                                     # noqa: E402

UTC = ZoneInfo("UTC")

# Variante de consolidation « exhaustive » (docs/13 §14, 27/10/2026) — BANC SEULEMENT, le dépôt n'est pas changé :
# la règle 3 (« ne retiens que ce qui sera UTILE PLUS TARD ») est remplacée par « garde tout fait de l'utilisateur, avec
# ses détails concrets ». LOCOMO_CONSOLIDATION=exhaustive ; défaut : la consigne d'EXIA SEED telle quelle.
REGLE3 = {"en": ("3. Keep only what will be USEFUL LATER: people, companies, places, prices, work rules, preferences, "
                 "decisions and their reason, notable events, deadlines, intentions. Ignore greetings, small talk, unanswered questions.",
                 "3. Keep EVERY fact the user states about themselves and their world — people, pets, places, possessions, "
                 "purchases, activities, plans, preferences, experiences, health, work — WITH its concrete details (names, "
                 "brands, models, numbers, prices, quantities, colors, dates, durations). A small detail is worth keeping: "
                 "the user may ask about it later. Ignore only greetings, small talk, unanswered questions.")}
# « +categories » (docs/13 §14.2) : la règle 12 (concepts) demande AUSSI la catégorie courante de chaque chose — le mot
# qu'on emploie pour la demander en général : le pont que les embeddings font et que les mots seuls ne font pas
# (diagnostic : « luxury items » ↔ « Gucci handbag »). Exemples de la consigne volontairement ÉTRANGERS aux questions
# examinées (agrafeuse, tulipe, voiture, violoncelle — absents des 200 conversations de développement), pour ne pas souffler les réponses au jeu de développement.
REGLE12 = {"en": ("REUSE existing concepts when they fit.",
                  "Among them, ALWAYS include the everyday CATEGORY of each thing mentioned — the word a person would use to "
                  "ask about it in general (a stapler → office_supply; a tulip → flower; a Toyota Corolla → car; a cello → "
                  "musical_instrument). For a category, the words in \"concepts_nouveaux\" must include its plain names, "
                  "singular and plural (office supply, office supplies…). REUSE existing concepts when they fit.")}
# « +passage » (docs/13 §14.3) : ce qui est dit EN PASSANT (« by the way, I started watering my herb garden today ») est
# un fait au même titre que la demande — diagnostic : ces événements datés sont ceux que les questions de temps visent.
# Ajouté à la fin de la règle 3 exhaustive.
PASSAGE = {"en": " Facts mentioned IN PASSING count as much as the request itself (\"by the way, I…\", \"I just… today\"): what "
                 "the user did, started, finished, bought, fixed, attended or received — each as its own fragment, with WHEN it happened."}
VARIANTE = __import__("os").environ.get("LOCOMO_CONSOLIDATION", "")


def _variante(cons) -> None:
    """27/10/2026 : la consigne exhaustive + « en passant » est devenue celle d'EXIA SEED (masques fr/en, docs/13 §19).
    LOCOMO_CONSOLIDATION=selective rejoue l'ANCIENNE règle 3 (« utile plus tard », `REGLE3_SELECTIVE` du masque) ;
    les anciennes valeurs (exhaustive, +passage, +categories) ne s'appliquent plus : refusées pour ne rien fausser."""
    if not VARIANTE:
        return
    if VARIANTE != "selective":
        raise RuntimeError(f"variante {VARIANTE} : obsolète depuis le 27/10 (la consigne exhaustive est la consigne "
                           "par défaut) — seule « selective » rejoue l'ancienne règle 3")
    import importlib
    ancienne = importlib.import_module(f"exia_seed.langues.{cons.masque.code}").REGLE3_SELECTIVE
    d = cons.masque.consigne_consolidation
    def consigne(*a, **k):
        s = d(*a, **k)
        lignes = [l for l in s.splitlines() if l.startswith("3. ")]
        if len(lignes) != 1:
            raise RuntimeError("variante selective : règle 3 introuvable ou ambiguë dans la consigne")
        return s.replace(lignes[0], ancienne)
    cons.masque = __import__("copy").copy(cons.masque)       # copie : ne touche pas le masque partagé
    cons.masque.consigne_consolidation = consigne

def preparer(conv) -> dict:
    sid = conv["sample_id"]
    c = conv["conversation"]
    a, b = K.etiquette(c["speaker_a"]), K.etiquette(c["speaker_b"])
    racine = K.RUN / "memoires" / sid
    langues.fixer(racine, "en")
    raw = racine / "raw"; raw.mkdir(parents=True, exist_ok=True)
    chaine = raw / ".chaine.jsonl"
    deja = {json.loads(l)["fichier"] for l in (raw / ".consolide.jsonl").read_text().splitlines()} \
        if (raw / ".consolide.jsonl").exists() else set()
    if K.ROLES == "agent":                                # LongMemEval : l'utilisateur et son assistant (docs/13)
        cons = Consolidateur(racine, UTC, lambda m: modele.appeler(m, "consolidation"), modele=K.MODELE,
                             nom_agent=b, nom_utilisateur=a)
    else:
        cons = Consolidateur(racine, UTC, lambda m: modele.appeler(m, "consolidation"), modele=K.MODELE,
                             nom_agent="", nom_utilisateur="", interlocuteurs=[a, b])
    _variante(cons)
    par_jour, bilan = {}, {"sessions": 0, "faits": 0, "rejets": 0, "dates_retirees": 0}
    for n, quand, tours in K.sessions(conv):
        jour = quand.date().isoformat()
        par_jour[jour] = par_jour.get(jour, 0) + 1
        nom = f"{jour}_{par_jour[jour]:02d}.md"
        if nom in deja:
            continue
        lignes = [f"[{quand:%H:%M} {K.etiquette(t['speaker'])}] {K.texte_du_tour(t)}" for t in tours if K.texte_du_tour(t)]
        (raw / nom).write_text(f"---\ntype: raw\ndate: {jour}\nlang: en\nsession: {n}\nouvert_le: {quand.isoformat()}+00:00\n---\n\n"
                               "## Échanges\n\n" + "\n".join(lignes) + "\n", encoding="utf-8")
        dans_chaine = {json.loads(l)["fichier"] for l in chaine.read_text().splitlines()} if chaine.exists() else set()
        if nom not in dans_chaine:                        # reprise après une coupure : pas de doublon
            with chaine.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"fichier": nom}) + "\n")
        r = cons.consolider()
        bilan["sessions"] += 1
        bilan["faits"] += r.get("faits_retenus", 0) or 0
        bilan["rejets"] += r.get("fragments_rejetes", 0) or 0
        bilan["dates_retirees"] += len(r.get("dates_retirees", []) or [])
        if r.get("statut") not in ("ok", "vide"):
            print(f"  ⚠ {sid} session {n} : {r.get('statut')} {str(r.get('extrait', ''))[:120]}", flush=True)
        print(f"  {sid} s{n:<2} {jour} : {r.get('faits_retenus')} faits, {r.get('fragments_rejetes')} rejetés", flush=True)
    return bilan


def main() -> int:
    args = sys.argv[1:]
    fils = 1
    if "--fils" in args:                                  # conversations indépendantes : en parallèle (LongMemEval, 500)
        i = args.index("--fils"); fils = int(args[i + 1]); del args[i:i + 2]
    sel = args or K.selection_du_run()
    K.RUN.mkdir(parents=True, exist_ok=True)
    if args:
        (K.RUN / "selection.json").write_text(json.dumps(sel))

    def un(conv):
        try:
            b = preparer(conv)
        except modele.BudgetDepasse as e:
            print(f"  ⛔ {conv['sample_id']} : {e} — relancer reprend sans repayer", flush=True)
            return False
        print(f"{conv['sample_id']} : {b}", flush=True)
        return True

    convs = K.charger_donnees(sel)
    if fils > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(fils) as ex:
            ok = all(list(ex.map(un, convs)))
    else:
        ok = all(un(c) for c in convs)
    print("dépense :", json.dumps(modele.depense()["total"]))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
