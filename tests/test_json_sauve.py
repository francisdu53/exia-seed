"""Consolidation : JSON illisible (27/10/2026, docs/13 §14.4) — conteneur jetable, vrai chargeur d'Hermès.

Une réponse du modèle coupée par la limite de longueur, ou avec une virgule de travers, faisait jeter TOUTE la session.
On garde désormais les fragments complets écrits avant l'erreur ; ils passent le contrôle de citation comme les autres."""
import importlib, sys
sys.path.insert(0, "/opt/hermes")
ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))

from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
C = importlib.import_module(type(p).__module__ + ".consolidation").Consolidateur
F = '{"noeud": "jardin", "fait": "%s", "src": ["raw/2023-03-22_01.md:11"]}'
verif("JSON valide : inchangé", C._extraire('{"fragments": [%s, %s]}' % (F % "a", F % "b")) == [{"noeud": "jardin", "fait": x, "src": ["raw/2023-03-22_01.md:11"]} for x in "ab"])
r = C._extraire('{"fragments": [%s, %s, {"noeud": "jardin", "fait": "c", "src": ["raw/2023' % (F % "a", F % "b"))
verif("sortie coupée : les 2 fragments complets sont gardés", r is not None and [x["fait"] for x in r] == ["a", "b"], str(r)[:120])
r = C._extraire('{"fragments": [%s, {"noeud": "x" "fait": "faux"}, %s]}' % (F % "a", F % "b"))
verif("virgule manquante : on garde ce qui précède l'erreur", r is not None and [x["fait"] for x in r] == ["a"], str(r)[:120])
verif("liste vide : liste vide (pas une erreur)", C._extraire('{"fragments": []}') == [])
verif("pas de JSON : None (la session reste un échec)", C._extraire("désolé, je ne peux pas") is None)
verif("aucun fragment complet : None", C._extraire('{"fragments": [{"noeud": "x", "fait": "coupé') is None)
print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
