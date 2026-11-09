"""Mode observateur de la liste ciblée (docs/17 §18, 06/11/2026) — conteneur jetable, vrai chargeur d'Hermès.

Le réglage `catalogue_observateur_k` (0 = éteint) fait calculer, à chaque consolidation, la sélection que ferait la
recherche message par message, et noter ensuite si les pages existantes choisies par le modèle y figuraient. Ce que l'on
éprouve : éteint, rien n'est écrit ; allumé, le modèle reçoit TOUJOURS la liste complète, le journal note la
sélection et le rattachement ; une panne de l'observateur n'arrête pas la consolidation."""
import importlib, json, re, sys
from pathlib import Path
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))

from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
base = type(p).__module__
C = importlib.import_module(base + ".consolidation")
CFG = importlib.import_module(base + ".config")
OBS = importlib.import_module(base + ".observateur")
TZ = __import__("zoneinfo").ZoneInfo("Europe/Paris")

def lot(m, nom, lignes):
    (m / "raw").mkdir(parents=True, exist_ok=True)
    (m / "raw" / nom).write_text("---\ntype: raw\ndate: 2026-11-06\nouvert_le: 2026-11-06T09:00:00+01:00\n---\n\n## Échanges\n\n"
                                 + "\n".join(lignes) + "\n", encoding="utf-8")
    with (m / "raw" / ".chaine.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"fichier": nom}) + "\n")

def ref(prompt, texte):
    return next(re.match(r"\[([^\]]+)\]", l).group(1) for l in prompt.splitlines() if texte in l and l.startswith("[raw/"))

def premier(messages):
    if "FICHE D'IDENTITÉ" in messages[0]["content"]:
        return '{"fiches": []}'
    s = messages[-1]["content"]
    return json.dumps({"fragments": [{"noeud": "garage_dupont", "nouveau": True, "type_noeud": "entite",
                                      "alias": {"fr": ["garage Dupont"]}, "section": "episodic",
                                      "fait": "Le garage Dupont veut un devis pour jeudi.", "src": [ref(s, "devis pour jeudi")], "conf": 1.0}]})

vu = {}
def second(messages):
    if "FICHE D'IDENTITÉ" in messages[0]["content"]:
        return '{"fiches": []}'
    s = messages[-1]["content"]; vu["prompt"] = s
    return json.dumps({"fragments": [{"noeud": "garage_dupont", "section": "episodic",
                                      "fait": "Le garage Dupont a validé le devis de 450 euros.", "src": [ref(s, "450 euros")], "conf": 1.0}]})

def memoire(nom):
    m = H / nom
    lot(m, "2026-11-06_01.md", ["[09:00 francis] Le garage Dupont veut un devis pour jeudi.", "[09:01 nexa] C'est noté."])
    C.Consolidateur(m, TZ, premier, modele="t", nom_agent="nexa", nom_utilisateur="francis", fiches=False).consolider()
    lot(m, "2026-11-06_02.md", ["[10:00 francis] Le garage Dupont a validé le devis de 450 euros.",
                                "[10:05 francis] Pense à rappeler la carrosserie Martin la semaine prochaine.", "[10:06 nexa] D'accord."])
    return m

print("── 1. le réglage ──")
verif("défaut : observateur éteint", CFG.DEFAUTS["catalogue_observateur_k"] == 0)

print("── 2. éteint : rien n'est écrit ──")
m1 = memoire("m1")
r = C.Consolidateur(m1, TZ, second, modele="t", nom_agent="nexa", nom_utilisateur="francis", fiches=False).consolider()
verif("consolidation normale", r.get("statut") == "ok" and r.get("faits_retenus") == 1, r.get("statut"))
verif("aucun journal d'observation", not (m1 / "telemetrie" / "catalogue_observateur.jsonl").exists())
complet = vu["prompt"].split("CONCEPTS EXISTANTS")[0]

print("── 3. allumé : le modèle reçoit la même liste, le journal note la sélection ──")
m2 = memoire("m2")
r = C.Consolidateur(m2, TZ, second, modele="t", nom_agent="nexa", nom_utilisateur="francis", fiches=False,
                    observateur_k=30).consolider()
verif("consolidation normale", r.get("statut") == "ok" and r.get("faits_retenus") == 1, r.get("statut"))
verif("la liste vue par le modèle est la liste COMPLÈTE, inchangée", vu["prompt"].split("CONCEPTS EXISTANTS")[0] == complet)
lignes = (m2 / "telemetrie" / "catalogue_observateur.jsonl").read_text(encoding="utf-8").splitlines()
x = json.loads(lignes[-1]) if lignes else {}
verif("une ligne par passage", len(lignes) == 1, str(len(lignes)))
verif("messages comptés (3 dans le lot)", x.get("messages") == 3, str(x.get("messages")))
verif("le rattachement à la page existante est noté, et dans la sélection",
      x.get("rattachements") == 1 and x.get("dans_selection") == 1 and x.get("hors_selection") == [], json.dumps(x)[:200])
verif("ni l'utilisateur ni l'agent comptés comme pages", "francis" not in (x.get("hors_selection") or []) and x.get("pages", 0) >= 1)

print("── 4. une panne de l'observateur n'arrête pas la consolidation ──")
m3 = memoire("m3")
OBS.selection = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("panne simulée"))
r = C.Consolidateur(m3, TZ, second, modele="t", nom_agent="nexa", nom_utilisateur="francis", fiches=False,
                    observateur_k=30).consolider()
verif("consolidation normale malgré la panne", r.get("statut") == "ok" and r.get("faits_retenus") == 1, r.get("statut"))
e = json.loads((m3 / "telemetrie" / "catalogue_observateur.jsonl").read_text(encoding="utf-8").splitlines()[-1])
verif("la panne est notée", "panne simulée" in e.get("erreur", ""), json.dumps(e)[:160])

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
