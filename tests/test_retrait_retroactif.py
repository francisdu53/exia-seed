"""Retrait rétroactif (14/11/2026) — conteneur jetable, vrai chargeur d'Hermès.

« Oublie ce que je viens de dire » ne faisait qu'empêcher la consolidation FUTURE des lignes visées : si leur lot était déjà
consolidé, les faits restaient. Désormais, au début de chaque passage (sous le verrou), les faits qui citent une ligne
retirée sont retirés de leur page, inscrits au registre `oublis/` (raison « retrait ») et restaurables."""
import importlib, json, shutil, sys, tempfile
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, "/opt/hermes")
ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))

from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
base = type(p).__module__
C = importlib.import_module(base + ".consolidation").Consolidateur
oubli = importlib.import_module(base + ".oubli")
TZ = ZoneInfo("Europe/Paris")
LOT = "2026-11-10_01.md"
LIGNES = ["---", "type: raw", "date: 2026-11-10", "lang: fr", "ouvert_le: 2026-11-10T09:00:00+01:00", "---", "", "## Échanges", "",
          "[09:01 francis] Le garage Dupont veut un devis de 1200 euros pour jeudi prochain.",      # 10
          "[09:01 nexa] C'est noté pour le garage Dupont.",                                         # 11
          "[09:10 francis] Ma voiture personnelle est une Polo rouge de deux mille douze.",         # 12
          "[09:10 nexa] Bien noté pour ta Polo."]                                                   # 13


def factice(messages):
    if "SOURCES" not in messages[-1]["content"]:
        return "{}"
    frs = [{"noeud": "garage_dupont", "nouveau": True, "type_noeud": "entite", "alias": {"fr": ["Dupont"], "en": []},
            "section": "semantic", "fait": "Le garage Dupont veut un devis de 1200 euros pour jeudi prochain",
            "src": [f"raw/{LOT}:10"], "conf": 1.0, "speaker": "francis", "concepts": []},
           {"noeud": "francis", "nouveau": False, "type_noeud": "entite", "section": "semantic",
            "fait": "Ma voiture personnelle est une Polo rouge de deux mille douze", "src": [f"raw/{LOT}:12"],
            "conf": 1.0, "speaker": "francis", "concepts": []}]
    return json.dumps({"fragments": frs, "concepts_nouveaux": {}}, ensure_ascii=False)


r = Path(tempfile.mkdtemp(prefix="retrait-")); (r / "raw").mkdir(); (r / "pages").mkdir()
(r / ".langue").write_text("fr\n", encoding="utf-8")
(r / "raw" / LOT).write_text("\n".join(LIGNES) + "\n", encoding="utf-8")
(r / "raw" / ".chaine.jsonl").write_text(json.dumps({"fichier": LOT, "sha256": "x", "precedent": "genese"}) + "\n", encoding="utf-8")
print("── réglage éteint (défaut, 15/11) : l'ancien comportement — le fait déjà consolidé reste ──")
r0 = Path(tempfile.mkdtemp(prefix="retrait-off-")); (r0 / "raw").mkdir(); (r0 / "pages").mkdir()
(r0 / ".langue").write_text("fr\n", encoding="utf-8")
(r0 / "raw" / LOT).write_text("\n".join(LIGNES) + "\n", encoding="utf-8")
(r0 / "raw" / ".chaine.jsonl").write_text(json.dumps({"fichier": LOT, "sha256": "x", "precedent": "genese"}) + "\n", encoding="utf-8")
c0 = C(r0, TZ, factice, modele="essai", nom_agent="nexa", nom_utilisateur="francis", fiches=False)
c0.consolider()
with open(r0 / "raw" / ".retraits.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps({"fichier": LOT, "lignes": [12, 13]}) + "\n")
res0 = c0.consolider()
verif("éteint : rien n'est retiré", res0.get("statut") == "rien" and "Polo" in "\n".join(x.read_text(encoding="utf-8") for x in (r0 / "pages").glob("*.md")), str(res0))
shutil.rmtree(r0)

print("── réglage allumé ──")
c = C(r, TZ, factice, modele="essai", nom_agent="nexa", nom_utilisateur="francis", fiches=False, retrait_retroactif=True)
c.consolider()
texte = lambda: "\n".join(x.read_text(encoding="utf-8") for x in (r / "pages").glob("*.md"))
verif("avant : les deux faits sont dans la mémoire", "Polo" in texte() and "Dupont" in texte())

print("── un retrait arrive APRÈS la consolidation du lot ──")
with open(r / "raw" / ".retraits.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps({"fichier": LOT, "lignes": [12, 13], "qui": "francis", "consigne": "retrait_precedent", "ts": "2026-11-10T09:11:00+01:00"}) + "\n")
res = c.consolider()
verif("le passage applique le retrait même sans lot en attente", res.get("statut") == "retrait" and res.get("faits_retires") == 1, str(res))
verif("le fait qui cite la ligne retirée a disparu", "Polo" not in texte())
verif("les autres faits sont intacts", "Dupont" in texte())
journal = list((r / "oublis").glob("*.jsonl"))
lignes = [json.loads(l) for f in journal for l in f.read_text(encoding="utf-8").splitlines()]
verif("inscrit au registre oublis/ avec la raison « retrait »", any(x.get("raison") == "retrait" and "Polo" in x.get("ligne", "") for x in lignes), str(lignes)[:160])
verif("tracé dans le journal de la mémoire", "retrait |" in (r / "log.md").read_text(encoding="utf-8"))
verif("le brut reste intact (chaîne d'intégrité)", (r / "raw" / LOT).read_text(encoding="utf-8") == "\n".join(LIGNES) + "\n")
res2 = c.consolider()
verif("un retrait n'est appliqué qu'une fois", res2.get("statut") == "rien", str(res2))
page = next(x.get("page") for x in lignes if x.get("raison") == "retrait")
verif("restaurable (oubli.restaurer)", oubli.restaurer(r, page, "Ma voiture") == 1 and "Polo" in texte())

print("── un retrait sur des lignes jamais consolidées : rien à retirer, rien de cassé ──")
with open(r / "raw" / ".retraits.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps({"fichier": "2026-11-11_01.md", "lignes": [10, 11]}) + "\n")
res3 = c.consolider()
verif("aucun fait retiré", res3.get("faits_retires") == 0 and "Dupont" in texte(), str(res3))
shutil.rmtree(r)
print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
