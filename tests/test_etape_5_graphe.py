"""Étape 5 — le graphe (docs/05-graphe.md). Conteneur jetable, sans réseau, vrai chargeur d'Hermès."""
import hashlib, importlib, json, random, shutil, sys, time
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
G = importlib.import_module(base + ".graphe")
P = importlib.import_module(base + ".pages")
C = importlib.import_module(base + ".consolidation")
TZ = __import__("zoneinfo").ZoneInfo("Europe/Paris")

def page(racine, noeud, typ, alias, faits, cree="2026-09-23"):
    """faits : [(section, texte, [(lot, ligne)], dit_le)]"""
    pg = P.Page.nouvelle(racine / "pages", noeud, typ, {"fr": alias, "en": []}, cree, "test")
    for sec, texte, refs, dit in faits:
        pg.ajouter(sec, texte, {"conf": 1.0, "src": ",".join(f"raw/{l}:{n}" for l, n in refs), "dit_le": dit})
    pg.ecrire()

def monde(racine):
    """Un petit monde : Autoplus Valmont, Pascal Ménard, facturation, Rocheval, un hub « francis »."""
    if racine.exists():
        shutil.rmtree(racine)
    (racine / "pages").mkdir(parents=True); (racine / "raw").mkdir()
    L = "2026-09-24_01.md"
    page(racine, "autoplus_valmont", "entite", ["Autoplus Valmont"], [
        ("semantic", "Autoplus Valmont est un client régulier.", [(L, 10)], "2026-09-24T19:00"),
        ("procedural", "Les factures d'Autoplus Valmont partent à la comptabilité.", [(L, 20)], "2026-09-24T19:10")])
    page(racine, "pascal_menard", "entite", ["Pascal Ménard"], [
        ("semantic", "Pascal Ménard est le contact des deux sites.", [(L, 10)], "2026-09-24T19:00")])
    page(racine, "facturation", "concept", ["facturation"], [
        ("procedural", "Numéroter les factures à la suite.", [(L, 21)], "2026-09-24T19:11"),
        ("procedural", "La facture 41 a été préparée pour un garage.", [(L, 23)], "2026-09-24T19:12")])
    page(racine, "autoplus_rocheval", "entite", ["Autoplus Rocheval"], [
        ("semantic", "Autoplus Rocheval est le deuxième client.", [(L, 40)], "2026-09-24T19:30"),
        ("semantic", "La Rochevalette n'a rien à voir.", [(L, 60)], "2026-09-24T19:40")])
    page(racine, "francis", "entite", ["Francis"], [
        ("semantic", "Francis a appelé Autoplus Rocheval ce matin.", [(L, 80)], "2026-09-24T20:00"),
        ("semantic", "Francis travaille seul.", [(L, 90)], "2026-09-24T20:10")])
    page(racine, "carrosserie_menard", "entite", ["carrosserie Ménard"], [
        ("semantic", "La carrosserie Ménard est à Pornic.", [(L, 100)], "2026-09-24T20:20")])
    return racine

def aretes(racine):
    return {(a["a"], a["b"]): a for a in json.loads((racine / "graphe" / "aretes.json").read_text(encoding="utf-8"))}

R = monde(M)
print("── 1. déterminisme et reconstruction ──")
r1 = G.calculer(R, implicites=("francis", "nexa"))
f1 = [(R / "graphe" / f).read_bytes() for f in ("noeuds.json", "aretes.json")]
G.calculer(R, implicites=("francis", "nexa"))
f2 = [(R / "graphe" / f).read_bytes() for f in ("noeuds.json", "aretes.json")]
verif("deux calculs → fichiers identiques au bit près", f1 == f2)
shutil.rmtree(R / "graphe"); G.calculer(R, implicites=("francis", "nexa"))
f3 = [(R / "graphe" / f).read_bytes() for f in ("noeuds.json", "aretes.json")]
verif("graphe effacé puis recalculé → identique", f1 == f3)

print("── 2. les deux sources, et leur force ──")
A = aretes(R)
cle = lambda x, y: tuple(sorted((x, y)))
verif("même ligne → lien (Autoplus Valmont — Pascal Ménard)", cle("autoplus_valmont", "pascal_menard") in A)
verif("ligne voisine → lien (Autoplus Valmont — facturation, distance 1)", cle("facturation", "autoplus_valmont") in A)
e_meme = A[cle("autoplus_valmont", "pascal_menard")]["evidence"]
preuves_fact = A[cle("facturation", "autoplus_valmont")]["preuves"]
verif("même ligne (1,0) > voisine à distance 1 (0,5) > distance 3",
      e_meme == 1.0 and any(p["type"] == "voisine" and p["force"] == 0.5 for p in preuves_fact))
verif("au-delà de 3 lignes → aucun lien « vécu » (Rocheval ligne 40, Valmont 20)",
      not any(p["type"] in ("meme_ligne", "voisine") for p in A.get(cle("autoplus_rocheval", "autoplus_valmont"), {"preuves": []})["preuves"]))
verif("« nommé » : un fait de francis cite Autoplus Rocheval → lien", cle("francis", "autoplus_rocheval") in A)
verif("mot entier : « Rochevalette » ne vaut pas « Rocheval »",
      all("Rochevalette" not in p["fait"] for a in A.values() for p in a["preuves"]))
verif("sans accents : alias « carrosserie Ménard » ≠ nœud « Pascal Ménard » (mots entiers)",
      cle("carrosserie_menard", "pascal_menard") not in A)

print("── 3. l'utilisateur est implicite ──")
page(R, "courses", "concept", ["liste de courses"], [
    ("episodic", "Francis a fait ses courses avec la liste.", [("2026-09-25_01.md", 5)], "2026-09-25T10:00")])
G.calculer(R, implicites=("francis", "nexa"))
verif("« Francis a fait ses courses » ne relie pas courses à francis", cle("courses", "francis") not in aretes(R))
G.calculer(R, implicites=())
verif("…alors que sans la règle, il le ferait (contrôle du test)", cle("courses", "francis") in aretes(R))
G.calculer(R, implicites=("francis", "nexa"))

print("── 4. amortissement du hub ──")
H2 = M.parent / "hub"
if H2.exists(): shutil.rmtree(H2)
(H2 / "pages").mkdir(parents=True); (H2 / "raw").mkdir()
for i in range(8):                            # « hub » vécu avec 8 nœuds ; « rare_a » et « rare_b » seulement entre eux
    page(H2, f"n{i}", "concept", [f"sujet{i}"], [("semantic", f"Sujet {i} dit avec le hub.", [("L.md", 10 * i)], None)])
page(H2, "hub", "concept", ["centre"], [("semantic", f"Le hub parle {i}.", [("L.md", 10 * i)], None) for i in range(8)])
page(H2, "rare_a", "concept", ["alpha"], [("semantic", "Alpha dit avec bêta.", [("L.md", 500)], None)])
page(H2, "rare_b", "concept", ["beta"], [("semantic", "Bêta dit avec alpha.", [("L.md", 500)], None)])
G.calculer(H2)
AH = aretes(H2)
w_hub, w_rare = AH[cle("hub", "n0")]["poids"], AH[cle("rare_a", "rare_b")]["poids"]
verif("même preuve (une ligne commune), le lien d'un hub pèse moins", w_hub < w_rare, f"hub {w_hub} < rare {w_rare}")

print("── 5. symétrie, boucles, moteur ──")
m = G.charger_moteur(R)
W = m.get_weights(); noms = m.get_concept_names()
verif("matrice symétrique", (W == W.T).all())
verif("aucune boucle sur soi-même", all(W[i, i] == 0 for i in range(len(noms))))
a0 = next(iter(aretes(R).values()))
verif("W[cible, source] = poids de aretes.json", W[noms.index(a0["a"]), noms.index(a0["b"])] == a0["poids"])
repos = m.propagate({}).activations; act = m.propagate({"autoplus_valmont": 1.0}).activations
verif("propagation : Pascal Ménard s'allume au-dessus du repos, la carrosserie Ménard non",
      act["pascal_menard"] - repos["pascal_menard"] > 0.05 and act["carrosserie_menard"] - repos["carrosserie_menard"] < 0.005)

print("── 6. provenance ──")
toutes = list(aretes(R).values())
verif("toute arête a au moins une preuve", all(a["nb_preuves"] >= 1 and a["preuves"] for a in toutes))
def existe(pr):
    t = (R / "pages" / pr["page"]).read_text(encoding="utf-8")
    return pr["fait"][:60] in t
verif("chaque preuve pointe vers un fait existant (page + texte)", all(existe(pr) for a in toutes for pr in a["preuves"]))
verif("les preuves gardent lignes et dit_le", all(pr["lignes"] and pr.get("dit_le") for a in toutes for pr in a["preuves"] if pr["type"] != "nomme"))

print("── 7. retraits et pages supprimées ──")
(R / "raw" / ".retraits.jsonl").write_text(json.dumps({"fichier": "2026-09-24_01.md", "lignes": [10, 10]}) + "\n")
G.calculer(R, implicites=("francis", "nexa"))
verif("ligne 10 retirée → le lien « même ligne » Valmont — Ménard disparaît", cle("autoplus_valmont", "pascal_menard") not in aretes(R))
(R / "raw" / ".retraits.jsonl").unlink()
(R / "pages" / "autoplus-rocheval.md").unlink(); G.calculer(R, implicites=("francis", "nexa"))
verif("page supprimée → ses liens disparaissent", not any("autoplus_rocheval" in k for k in aretes(R)))

print("── 8. plafond ──")
avant = (R / "graphe" / "aretes.json").read_bytes()
G.PLAFOND_NOEUDS, ancien = 3, G.PLAFOND_NOEUDS
r = G.calculer(R)
G.PLAFOND_NOEUDS = ancien
verif("au-delà du plafond : refus propre, alerte", r["statut"] == "plafond_depasse" and "alerte" in r)
verif("…et l'ancien graphe reste en place", (R / "graphe" / "aretes.json").read_bytes() == avant)

print("── 9. un échec du graphe n'annule pas la consolidation ──")
monde(M)
(M / "raw" / "2026-09-26_01.md").write_text("---\ntype: raw\ndate: 2026-09-26\nouvert_le: 2026-09-26T10:00:00+02:00\n---\n\n## Échanges\n\n[10:00 francis] Le garage Martin de Rocheval veut un devis.\n", encoding="utf-8")
(M / "raw" / ".chaine.jsonl").write_text(json.dumps({"fichier": "2026-09-26_01.md"}) + "\n")
def faux(messages):
    return json.dumps({"fragments": [{"noeud": "garage_martin", "nouveau": True, "type_noeud": "entite",
        "alias": {"fr": ["garage Martin"], "en": []}, "section": "prospective", "fait": "Le garage Martin de Rocheval veut un devis.",
        "src": ["raw/2026-09-26_01.md:9"], "conf": 1.0, "speaker": "francis"}]})
vrai = G.calculer
G.calculer = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("panne simulée"))
r = C.Consolidateur(M, TZ, faux, modele="t", nom_agent="nexa", nom_utilisateur="francis").consolider()
G.calculer = vrai
verif("consolidation réussie malgré la panne du graphe", r.get("statut") == "ok" and (M / "pages" / "garage-martin.md").exists())
verif("la panne est tracée dans la télémétrie", (r.get("graphe") or {}).get("statut") == "echec", str(r.get("graphe")))
(M / "raw" / "2026-09-26_02.md").write_text((M / "raw" / "2026-09-26_01.md").read_text().replace("Martin de Rocheval veut un devis", "Martin rappellera lundi"), encoding="utf-8")
with (M / "raw" / ".chaine.jsonl").open("a") as f: f.write(json.dumps({"fichier": "2026-09-26_02.md"}) + "\n")
r = C.Consolidateur(M, TZ, lambda m: json.dumps({"fragments": []}), modele="t", nom_agent="nexa", nom_utilisateur="francis").consolider()
verif("au passage suivant, le graphe est recalculé et inclut la nouvelle page",
      (r.get("graphe") or {}).get("statut") == "ok" and any(n["noeud"] == "garage_martin" for n in json.loads((M / "graphe" / "noeuds.json").read_text())),
      str(r.get("graphe")))

print("── 10. le moteur n'a pas bougé ──")
fcm = Path(G.__file__).parent / "moteur" / "fcm.py"
verif("moteur/fcm.py = V2.7.2 au bit près (SHA-256)",
      hashlib.sha256(fcm.read_bytes()).hexdigest() == "bb74b91db6c633809b3677ea74be7d22deec7b5d4e68621d4032f8d88dc8931e")

print("── 11. échelle : 2 000 nœuds synthétiques ──")
X = M.parent / "echelle"
if X.exists(): shutil.rmtree(X)
(X / "pages").mkdir(parents=True); (X / "raw").mkdir()
rnd = random.Random(0)
for i in range(2000):
    faits = [("semantic", f"Le sujet {i} parle du thème {rnd.randrange(300)}.", [(f"{rnd.randrange(60):02d}.md", rnd.randrange(400))], "2026-09-24T10:00")
             for _ in range(rnd.randint(1, 6))]
    page(X, f"noeud_{i:04d}", "concept", [f"sujet numero {i}"], faits)
# Plafond provisoire de 2 400 pour éprouver l'alerte à 80 % : depuis le moteur creux (27/10/2026), le vrai plafond
# est 20 000 nœuds — l'alerte ne viendrait qu'à 16 000.
G.PLAFOND_NOEUDS, ancien = 2400, G.PLAFOND_NOEUDS
t0 = time.perf_counter(); r = G.calculer(X); dt = time.perf_counter() - t0
G.PLAFOND_NOEUDS = ancien
verif("2 000 nœuds : calcul < 2 s (prévision)", dt < 2.0, f"{dt:.2f} s · {r['aretes']} arêtes · alerte « {r['alerte']} »")
t0 = time.perf_counter(); m = G.charger_moteur(X); tc = time.perf_counter() - t0
t0 = time.perf_counter(); m.propagate({"noeud_0001": 1.0}); tp = (time.perf_counter() - t0) * 1000
verif("2 000 nœuds : propagation < 50 ms", tp < 50, f"chargement {tc*1000:.0f} ms · propagation {tp:.1f} ms")
verif("alerte à 80 % du plafond", r["alerte"] is not None)

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
