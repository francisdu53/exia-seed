"""Étape 7 — la requête (docs/07-requete.md). Conteneur jetable, sans réseau, vrai chargeur ET vrai
gestionnaire de mémoire d'Hermès (MemoryManager) : le chemin de production des outils."""
import importlib, json, shutil, sys, time
from datetime import datetime
from pathlib import Path
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); M = H / "memoire"; ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))

from plugins.memory import load_memory_provider
from agent.memory_manager import MemoryManager

print("── 1. le chemin de production : add_provider AVANT initialize_all (défaut du 27/09) ──")
p = load_memory_provider("exia_seed")
mm = MemoryManager()
mm.add_provider(p)                                   # Hermès lit les schémas ICI, plugin non initialisé
verif("les 3 outils sont dans la table d'aiguillage dès l'enregistrement",
      {"memoire_noter", "memoire_chercher", "memoire_lire"} <= mm.get_all_tool_names(), str(mm.get_all_tool_names()))
r = json.loads(mm.handle_tool_call("memoire_chercher", {"requete": "x"}))
verif("appel avant initialisation → réponse propre, pas d'exception", r.get("ok") is False and "pas encore prête" in r.get("erreur", ""), str(r))
mm.initialize_all(session_id="s1", hermes_home=str(H), platform="telegram", agent_context="primary")
r = json.loads(mm.handle_tool_call("memoire_noter", {"texte": "Le carrossier Lebrun est à Pornic."}))
verif("memoire_noter répond par le gestionnaire (c'était « Unknown tool » en production)", r.get("ok") is True, str(r))
verif("…et la note est bien au registre", "Lebrun" in (M / "registre.md").read_text(encoding="utf-8"))

base = type(p).__module__
G = importlib.import_module(base + ".graphe")
P = importlib.import_module(base + ".pages")
T = datetime(2026, 9, 27, 10, 0)

def page(noeud, typ, alias, faits):
    pg = P.Page.nouvelle(M / "pages", noeud, typ, {"fr": alias, "en": [a + " en" for a in alias]}, "2026-09-23", "test")
    for sec, texte, refs, dit in faits:
        pg.ajouter(sec, texte, {"conf": 1.0, "src": ",".join(f"raw/{l}:{n}" for l, n in refs), "dit_le": dit})
    pg.ecrire()

L = "2026-09-24_01.md"
page("autoplus_valmont", "entite", ["Autoplus Valmont"], [
    ("semantic", "Autoplus Valmont est un gros client de débosselage.", [(L, 10)], "2026-09-24T19:00"),
    ("procedural", "Envoyer les factures d'Autoplus Valmont à la comptabilité.", [(L, 20)], "2026-09-24T19:10"),
    ("episodic", "La Polo d'Autoplus Valmont a été débosselée pour 55 euros.", [(L, 40)], "2026-09-24T19:30")])
page("gestion_destinataires", "etat_agent", ["gestion des destinataires"], [
    ("procedural", "Mettre Pascal Ménard en copie des factures.", [(L, 20)], "2026-09-24T19:10")])
page("pascal_menard", "entite", ["Pascal Ménard"], [
    ("semantic", "Pascal Ménard dirige le site d'Autoplus Valmont.", [(L, 10)], "2026-09-24T19:00")])
page("jardinage", "concept", ["jardinage", "potager"], [
    ("semantic", "Le potager est planté de tomates.", [("2026-09-25_01.md", 5)], "2026-09-25T10:00")])
page("francis", "entite", ["Francis"], [
    ("semantic", "Rendez-vous chez le garagiste Martin le 29 septembre.", [(L, 90)], "2026-09-24T20:00"),
    ("semantic", "Francis aime la randonnée.", [(L, 91)], "2026-09-24T20:01")])
G.calculer(M, implicites=("francis", "nexa"))
lire = lambda s: json.loads(mm.handle_tool_call("memoire_lire", {"sujet": s}))
chercher = lambda q, n=5: json.loads(mm.handle_tool_call("memoire_chercher", {"requete": q, "nombre": n}))

print("── 2. memoire_chercher ──")
r = chercher("Autoplus Valmont factures")
sujets = [x["sujet"] for x in r["resultats"]]
verif("sujet nommé en tête, avec « pourquoi : nommé »", sujets and sujets[0] == "autoplus_valmont" and r["resultats"][0]["pourquoi"] == "nommé", str(r["resultats"][:1]))
verif("la règle de destinataires remonte (liée, ou mots en commun)", "gestion_destinataires" in sujets, str(sujets))
verif("chaque sujet porte au plus 3 faits, datés", all(len(x["faits"]) <= 3 and all("dit_le" in f for f in x["faits"]) for x in r["resultats"]))
verif("le fait le mieux couvert passe en tête (factures)", "factures" in r["resultats"][0]["faits"][0]["fait"], r["resultats"][0]["faits"][0]["fait"])
r = chercher("Pascal")
verif("mot d'alias seul (« Pascal »)", r["resultats"] and r["resultats"][0]["sujet"] == "pascal_menard" and r["resultats"][0]["pourquoi"] == "mot proche", str(r["resultats"][:1]))
r = chercher("Valmon")
verif("faute de frappe (« Valmon »)", r["resultats"] and r["resultats"][0]["sujet"] == "autoplus_valmont")
r = chercher("tomates")
verif("plein texte (« tomates » → jardinage)", r["resultats"] and r["resultats"][0]["sujet"] == "jardinage" and r["resultats"][0]["pourquoi"] == "mots en commun")
r = chercher("Autoplus Valmont")
verif("association : un sujet « lié à Autoplus Valmont » sans mot commun", any(x["pourquoi"].startswith("lié à") for x in r["resultats"]), str([(x["sujet"], x["pourquoi"]) for x in r["resultats"]]))
r = chercher("météo Brest")
verif("rien de lié → liste vide et message explicite", r["resultats"] == [] and "Rien de lié" in r.get("message", "") and "brest" in r.get("mots_inconnus", []))
r = chercher("garagiste")
verif("fiche de l'utilisateur : seulement avec écho (garagiste, pas randonnée)", r["resultats"] and all("randonnée" not in f["fait"] for x in r["resultats"] for f in x["faits"]))
verif("nombre respecté", len(chercher("Autoplus Valmont factures", 2)["resultats"]) <= 2)
verif("déterminisme (50 fois)", len({json.dumps(chercher("Autoplus Valmont factures"), sort_keys=True) for _ in range(50)}) == 1)

print("── 3. memoire_lire ──")
r = lire("Autoplus Valmont")
verif("par titre → la page", r.get("sujet") == "autoplus_valmont" and r.get("titre") == "Autoplus Valmont", str(r.get("sujet")))
verif("faits par section, lisibles, sans métadonnées techniques", r["sections"] and "<!--" not in json.dumps(r, ensure_ascii=False) and "src:" not in json.dumps(r, ensure_ascii=False))
verif("tous les faits de la page", r["nombre_de_faits"] == 3 and sum(len(v) for v in r["sections"].values()) == 3)
pistes = {x["sujet"]: x for x in r["pistes"]}
verif("PISTE : la règle Pascal Ménard vient avec la page (provenance de l'arête)",
      "gestion_destinataires" in pistes and any("Pascal" in f for f in pistes["gestion_destinataires"]["faits"]), str(list(pistes)))
verif("pistes rangées par force du lien", [x["lien"] for x in r["pistes"]] == sorted([x["lien"] for x in r["pistes"]], reverse=True))
verif("la fiche de l'utilisateur n'est pas une piste", "francis" not in pistes)
verif("par slug, par faute de frappe", lire("autoplus_valmont").get("sujet") == "autoplus_valmont" and lire("Valmon").get("sujet") == "autoplus_valmont")
r = lire("Tombouctou")
verif("sujet inconnu → erreur claire", r.get("ok") is False and "aucun sujet" in r.get("erreur", ""))
verif("budget : ≤ 1 200 tokens", lire("Autoplus Valmont")["tokens"] <= 1200)

print("── 4. journal, latence ──")
journal = [json.loads(l) for f in (M / "requetes").glob("*.jsonl") for l in f.read_text().splitlines()]
verif("chaque requête est journalisée", len(journal) >= 20 and {"memoire_chercher", "memoire_lire"} <= {j["outil"] for j in journal})
lat = sorted(j["latence_ms"] for j in journal)
verif("latence p95 < 50 ms", lat[int(0.95 * len(lat)) - 1] < 50, f"p95 {lat[int(0.95*len(lat))-1]:.1f} ms")

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
