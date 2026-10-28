"""Étape 8 — B++ en production (docs/08 §8-10) : thésaurus de concepts, champ lexical vivant, budget loyal.
Conteneur jetable, sans réseau, vrai chargeur d'Hermès."""
import importlib, json, subprocess, sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); M = H / "memoire"; ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))

from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
p.initialize("s1", hermes_home=str(H), platform="telegram", agent_context="primary")
base = type(p).__module__
G = importlib.import_module(base + ".graphe"); C = importlib.import_module(base + ".consolidation")
Q = importlib.import_module(base + ".requete")
TZ = __import__("zoneinfo").ZoneInfo("Europe/Paris"); T = datetime(2026, 9, 28, 10, 0)

print("── 1. la consolidation rattache aux concepts ──")
(M / "raw").mkdir(parents=True, exist_ok=True)
(M / "raw" / "2026-09-27_01.md").write_text("""---
type: raw
date: 2026-09-27
ouvert_le: 2026-09-27T09:00:00+02:00
---

## Échanges

[09:00 francis] J'ai rendez-vous chez le garagiste Martin mardi à 10h.
[09:01 francis] Hugo a rendez-vous chez le carrossier Sophie jeudi.
[09:02 francis] Pour la liste, les chewing-gums vont aux têtes de gondole près des caisses.
[09:03 francis] Mets le lait dans le rayon frais de la liste.
[09:04 francis] Autoplus Valmont veut sa facture 42.
""", encoding="utf-8")
(M / "raw" / ".chaine.jsonl").write_text(json.dumps({"fichier": "2026-09-27_01.md"}) + "\n")
def faux(messages):
    assert "CONCEPTS EXISTANTS" in messages[1]["content"]
    F = [
     {"noeud": "francis", "nouveau": True, "type_noeud": "entite", "alias": {"fr": ["Francis"], "en": []}, "section": "prospective",
      "fait": "Rendez-vous chez le garagiste Martin mardi à 10h.", "src": ["raw/2026-09-27_01.md:9"], "conf": 1.0, "concepts": ["entretien", "rendez_vous"]},
     {"noeud": "hugo", "nouveau": True, "type_noeud": "entite", "alias": {"fr": ["Hugo"], "en": []}, "section": "prospective",
      "fait": "Hugo a rendez-vous chez le carrossier Sophie jeudi.", "src": ["raw/2026-09-27_01.md:10"], "conf": 1.0, "concepts": ["entretien", "rendez_vous", "equipe", "trop"]},
     {"noeud": "liste_courses", "nouveau": True, "type_noeud": "concept", "alias": {"fr": ["liste de courses"], "en": []}, "section": "procedural",
      "fait": "Les chewing-gums vont aux têtes de gondole près des caisses.", "src": ["raw/2026-09-27_01.md:11"], "conf": 1.0, "concepts": ["courses"]},
     {"noeud": "liste_courses", "section": "procedural", "fait": "Le lait va dans le rayon frais de la liste.",
      "src": ["raw/2026-09-27_01.md:12"], "conf": 1.0, "concepts": ["courses", "fantome"]},
     {"noeud": "autoplus_valmont", "nouveau": True, "type_noeud": "entite", "alias": {"fr": ["Autoplus Valmont"], "en": []}, "section": "prospective",
      "fait": "Autoplus Valmont veut sa facture 42.", "src": ["raw/2026-09-27_01.md:13"], "conf": 1.0, "concepts": ["facturation"]}]
    return json.dumps({"fragments": F, "concepts_nouveaux": {
        "entretien": {"fr": ["entretien", "mécanicien", "garagiste", "carrossier", "atelier", "révision"], "en": ["maintenance"]},
        "rendez_vous": {"fr": ["rendez-vous", "créneau", "agenda"], "en": ["appointment"]},
        "courses": {"fr": ["courses", "liste de courses", "supermarché", "rayons"], "en": ["groceries"]},
        "facturation": {"fr": ["facture", "facturation"], "en": ["invoice"]},
        "equipe": {"fr": ["équipe", "collègue"], "en": ["team"]},
        "inutile": {"fr": ["jamais utilisé"], "en": []}}}, ensure_ascii=False)
r = C.Consolidateur(M, TZ, faux, modele="t", nom_agent="nexa", nom_utilisateur="francis").consolider()
verif("passage réussi", r.get("statut") == "ok", str(r.get("statut")))
hugo = (M / "pages" / "hugo.md").read_text(encoding="utf-8")
verif("métadonnée concepts écrite, 3 au plus", "concepts:entretien,rendez_vous,equipe" in hugo and "trop" not in hugo, hugo[-160:])
lait = (M / "pages" / "liste-courses.md").read_text(encoding="utf-8")
verif("un concept sans définition (« fantome ») est ignoré", "fantome" not in lait and "concepts:courses" in lait)
th = json.loads((M / "thesaurus.json").read_text(encoding="utf-8"))
verif("thésaurus : les concepts utilisés, pas « inutile »", {"entretien", "courses", "facturation", "equipe"} <= set(th["concepts"]) and "inutile" not in th["concepts"])
verif("le champ lexical est gardé une seule fois, au concept", "garagiste" in th["concepts"]["entretien"]["fr"])

print("── 2. le graphe : concepts en nœuds, champ vivant ──")
noeuds = {n["noeud"]: n for n in json.loads((M / "graphe" / "noeuds.json").read_text(encoding="utf-8"))}
verif("les concepts sont des nœuds", "concept:entretien" in noeuds and noeuds["concept:entretien"]["type"] == "concept_lexical")
verif("champ appris : « gondole » vient du fait rattaché à courses", "gondole" in noeuds["concept:courses"]["champ_appris"], str(noeuds["concept:courses"]["champ_appris"]))
aretes = {(a["a"], a["b"]) for a in json.loads((M / "graphe" / "aretes.json").read_text(encoding="utf-8"))}
verif("lien page ↔ concept (hugo ↔ santé)", ("concept:entretien", "hugo") in aretes)
f1 = (M / "graphe" / "noeuds.json").read_bytes(); G.calculer(M, implicites=("francis", "nexa"))
verif("déterminisme", f1 == (M / "graphe" / "noeuds.json").read_bytes())

print("── 3. la recherche : le sens, le champ vivant, le budget ──")
L = Q.Lecteur(M, implicites=("francis", "nexa"))
r = L.chercher("mécanicien", 5, T)
tous = [f["fait"] for x in r.get("resultats", []) for f in x["faits"]] + [f["fait"] for f in (r.get("pistes") or {}).get("faits", [])]
verif("« mécanicien » trouve le garagiste par le champ de `entretien` (aucun mot commun)", any("garagiste" in t for t in tous), str(tous))
verif("…et enrichit : le rendez-vous de Hugo, par le même concept", any("Hugo" in t for t in tous), str(tous))
r = L.chercher("gondole", 5, T)
tous = [f["fait"] for x in r.get("resultats", []) for f in x["faits"]] + [f["fait"] for f in (r.get("pistes") or {}).get("faits", [])]
verif("champ vivant : « gondole » ramène aussi l'autre fait de `courses` (le lait)", any("lait" in t for t in tous), str(tous))
r = L.chercher("entretien rendez-vous facture courses", 9, T, faits_max=4)
n_faits = sum(len(x["faits"]) for x in r["resultats"]) + len((r.get("pistes") or {}).get("faits", []))
verif("budget : faits_max respecté (4)", n_faits <= 4, str(n_faits))
verif("rien de lié → silence (météo Brest)", L.chercher("météo Brest", 5, T)["resultats"] == [])

print("── 4. le rattrapage des faits existants ──")
page = M / "pages" / "autoplus-valmont.md"
t = page.read_text(encoding="utf-8").replace(" concepts:facturation", "")
page.write_text(t, encoding="utf-8")
graine = H / "graine.json"
graine.write_text(json.dumps({"concepts": th["concepts"], "faits": {"Autoplus Valmont veut sa facture 42.": ["facturation"]}}, ensure_ascii=False))
outil = Path(G.__file__).parent / "outils" / "concepts.py"
s = subprocess.run([sys.executable, str(outil), "--graine", str(graine)], capture_output=True, text=True, env={"HERMES_HOME": str(H), "PATH": "/usr/bin:/bin"})
verif("simulation : 1 fait sans concept, connu de la graine, rien écrit", "1 faits sans concept · 1 connus" in s.stdout and "concepts:" not in page.read_text(), s.stdout[:160] + s.stderr[-200:])
avant = page.read_text(encoding="utf-8")
s = subprocess.run([sys.executable, str(outil), "--graine", str(graine), "--ecrire"], capture_output=True, text=True, env={"HERMES_HOME": str(H), "PATH": "/usr/bin:/bin"})
apres = page.read_text(encoding="utf-8")
verif("écriture : la métadonnée est ajoutée", "concepts:facturation" in apres, s.stdout[-200:] + s.stderr[-200:])
th2 = json.loads((M / "thesaurus.json").read_text(encoding="utf-8"))
verif("le thésaurus garde les concepts déjà créés (santé, courses…)", {"entretien", "courses", "equipe", "facturation"} <= set(th2["concepts"]), str(sorted(th2["concepts"])))
verif("…le texte du fait n'a pas bougé", [l.split("<!--")[0] for l in avant.splitlines()] == [l.split("<!--")[0] for l in apres.splitlines()])
s = subprocess.run([sys.executable, str(outil), "--graine", str(graine)], capture_output=True, text=True, env={"HERMES_HOME": str(H), "PATH": "/usr/bin:/bin"})
verif("idempotent : plus rien à rattacher", "0 faits sans concept" in s.stdout, s.stdout[:120])

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
