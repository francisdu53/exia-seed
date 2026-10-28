#!/usr/bin/env python3
"""Reconsolider une COPIE de l'historique de Nexa avec une consigne donnée (docs/13 §19). Conteneur jetable.

La mémoire vivante de Nexa n'est jamais lue ici : le lanceur copie au préalable ses lots FERMÉS (`raw/*.md` sauf
`_open`), la chaîne d'intégrité (`raw/.chaine.jsonl`) et le registre (`registre.md`) dans
`/banc/runs/<variante>/memoire` — sans `.consolide.jsonl` ni `registre.integre.jsonl`, pour tout reconsolider.
Réglages de production (francis / nexa, fr, Europe/Paris, 40 000 tokens d'entrée, fiches) ; modèle : gpt-4o-mini par
l'API du banc (`banc/locomo/modele.py`, cache, plafond), le même pour les deux variantes, réponse jusqu'à 8 000 tokens.
REJEU JOUR PAR JOUR, comme les nuits de Nexa (premier essai du 27/10 corrigé : tout l'historique d'un coup, 40 000 tokens
par appel et 2 000 de réponse, ne laissait écrire qu'une poignée de faits pour un mois — 14 pages contre 62 chez elle) :
la chaîne complète est gardée à part (`chaine_complete.jsonl`) et versée dans `raw/.chaine.jsonl` un jour après
l'autre, dans son ordre (l'intégrité est préservée) ; on consolide après chaque jour.

    LOCOMO_RUN=selective  LOCOMO_CONSOLIDATION=selective  python3 reconsolider.py     # l'ancienne règle 3
    LOCOMO_RUN=exhaustive                                 python3 reconsolider.py     # la nouvelle (défaut)
"""
import json, sys
from zoneinfo import ZoneInfo
sys.path.insert(0, "/locomo"); sys.argv = sys.argv[:1]
import commun as K
import preparer as P                                              # _variante (LOCOMO_CONSOLIDATION=selective)
import modele
from exia_seed.consolidation import Consolidateur

racine = K.RUN / "memoire"
cons = Consolidateur(racine, ZoneInfo("Europe/Paris"), lambda m: modele.appeler(m, "consolidation", max_tokens=8000), modele=K.MODELE,
                     max_tokens_entree=40000, nom_agent="nexa", nom_utilisateur="francis", fiches=True)
P._variante(cons)
complete = [l for l in (K.RUN / "chaine_complete.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
deja = {l for l in (racine / "raw" / ".chaine.jsonl").read_text(encoding="utf-8").splitlines()} if (racine / "raw" / ".chaine.jsonl").exists() else set()
jours = []
for l in complete:
    j = json.loads(l)["fichier"][:10]
    if not jours or jours[-1][0] != j:
        jours.append((j, []))
    jours[-1][1].append(l)
tours, faits, rejets = 0, 0, 0
for jour, lignes in jours:
    neuves = [l for l in lignes if l not in deja]
    if neuves:
        with (racine / "raw" / ".chaine.jsonl").open("a", encoding="utf-8") as f:
            f.write("".join(l + "\n" for l in neuves))
        deja.update(neuves)
    bloques = 0
    while cons.lots_en_attente():
        avant = cons.lots_en_attente()
        try:
            r = cons.consolider()
        except modele.BudgetDepasse as e:
            print("⛔", e); sys.exit(2)
        tours += 1
        faits += r.get("faits_retenus", 0) or 0; rejets += r.get("fragments_rejetes", 0) or 0
        if r.get("statut") not in ("ok", "vide"):
            print(f"  {jour} : {r.get('statut')} {str(r.get('extrait', ''))[:120]}", flush=True)
        if cons.lots_en_attente() == avant:
            bloques += 1
            if bloques >= 2:
                print(f"⛔ bloqué sur {avant[:3]} — jour sauté", flush=True); break
    print(f"  {jour} : {tours} passages · {faits} faits · {modele.depense()['total']['usd']:.3f} $", flush=True)
print(json.dumps({"passages": tours, "faits": faits, "rejets": rejets, "reste": len(cons.lots_en_attente()),
                  "depense": round(modele.depense()["total"]["usd"], 4)}))
sys.exit(0)
while True:
    avant = cons.lots_en_attente()
    try:
        r = cons.consolider()
    except modele.BudgetDepasse as e:
        print("⛔", e); break
    tours += 1
    faits += r.get("faits_retenus", 0) or 0; rejets += r.get("fragments_rejetes", 0) or 0
    if r.get("statut") not in ("ok", "vide"):
        print(f"  passage {tours} : {r.get('statut')} {str(r.get('extrait', ''))[:120]}", flush=True)
    if r.get("statut") in ("rien", "deja_en_cours") or not cons.lots_en_attente() or tours > 400:
        break
    if cons.lots_en_attente() == avant:                     # aucun progrès (échec rejoué à l'identique par le cache)
        bloques += 1
        if bloques >= 2:
            print(f"⛔ bloqué sur {avant[:3]} — arrêt", flush=True); break
    if tours % 10 == 0:
        print(f"  {tours} passages · {faits} faits · reste {len(cons.lots_en_attente())} lots · {modele.depense()['total']['usd']:.3f} $", flush=True)
print(json.dumps({"passages": tours, "faits": faits, "rejets": rejets, "reste": len(cons.lots_en_attente()),
                  "depense": round(modele.depense()["total"]["usd"], 4)}))
