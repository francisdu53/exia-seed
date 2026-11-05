"""Consigne adaptée et modèle de consolidation (05/11/2026, docs/17 §11) — conteneur jetable, vrai chargeur d'Hermès.

Deux réglages : `consolidation_modele` (vide = le modèle principal de l'agent) et `consolidation_consigne`
(« production » par défaut, ou « adaptee », la consigne écrite pour un petit modèle). Ce que l'on éprouve : sans
réglage, rien ne change ; la consigne adaptée part bien au modèle, avec le même contrat de sortie ; une conversation
entre personnes garde la consigne de production ; une langue sans variante aussi."""
import importlib, inspect, json, sys
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
L = importlib.import_module(base + ".langues")

print("── 1. les réglages ──")
verif("défauts : modèle principal, consigne de production",
      CFG.DEFAUTS["consolidation_modele"] == "" and CFG.DEFAUTS["consolidation_consigne"] == "production")
verif("appel_llm_hermes accepte un modèle de consolidation", "modele" in inspect.signature(C.appel_llm_hermes).parameters)

def memoire(nom):
    m = H / nom; (m / "raw").mkdir(parents=True)
    (m / "raw" / "2026-11-05_01.md").write_text("---\ntype: raw\ndate: 2026-11-05\nouvert_le: 2026-11-05T09:00:00+01:00\n---\n\n"
        "## Échanges\n\n[09:00 francis] Le garage Dupont veut un devis pour jeudi.\n[09:01 nexa] C'est noté.\n", encoding="utf-8")
    (m / "raw" / ".chaine.jsonl").write_text(json.dumps({"fichier": "2026-11-05_01.md"}) + "\n", encoding="utf-8")
    return m

def systeme_envoye(nom, **k):
    vu = {}
    def faux(messages):
        if "FICHE D'IDENTITÉ" not in messages[0]["content"]:
            vu["s"] = messages[0]["content"]
        return '{"fragments": [], "concepts_nouveaux": {}}'
    C.Consolidateur(memoire(nom), __import__("zoneinfo").ZoneInfo("Europe/Paris"), faux, modele="t", fiches=False, **k).consolider()
    return vu.get("s", "")

print("── 2. la consigne envoyée au modèle ──")
fr = L.masque("fr")
prod = systeme_envoye("m1", nom_agent="nexa", nom_utilisateur="francis")
adap = systeme_envoye("m2", nom_agent="nexa", nom_utilisateur="francis", consigne="adaptee")
verif("sans réglage : la consigne de production", prod.startswith(fr.consigne_consolidation(True, "francis")[:200]))
verif("« adaptee » : la consigne adaptée (but, méthode, fidélité)", "LE BUT" in adap and "MÉTHODE" in adap and "FIDÉLITÉ AUX SOURCES" in adap)
verif("même contrat de sortie (le format JSON est identique)",
      adap.split("FORMAT")[1].split("}}")[0] == prod.split("FORMAT")[1].split("}}")[0], adap.split("FORMAT")[1][:120])
verif("le nom de l'utilisateur reste ajouté à la consigne adaptée", "francis" in adap.split("FORMAT")[-1] or "« francis »" in adap)
pers = systeme_envoye("m3", nom_agent="", interlocuteurs=("anna", "marc"), consigne="adaptee")
verif("conversation entre personnes : la consigne de production reste", "LE BUT" not in pers and pers != "")
en = L.masque("en")
verif("langue sans variante (anglais) : la consigne de production",
      en.consigne_consolidation_adaptee("user") == en.consigne_consolidation(True, "user"))

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
