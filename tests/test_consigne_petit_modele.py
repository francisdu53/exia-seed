"""La consigne pour un petit modèle (docs/20, 08/11/2026) — conteneur jetable, vrai chargeur d'Hermès.

`consolidation_consigne: petit_modele` envoie la consigne qualifiée pour GPT-6 Luna et Claude Haiku 5.5 : la consigne
adaptée, plus la règle absolue et le travail message par message, au caractère près celle du banc. Une langue sans
variante retombe sur la consigne adaptée (puis de production)."""
import importlib, sys
from pathlib import Path
sys.path.insert(0, "/opt/hermes")
ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))
from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed"); base = type(p).__module__
L = importlib.import_module(base + ".langues"); C = importlib.import_module(base + ".consolidation")
fr, en = L.masque("fr"), L.masque("en")
pm = fr.consigne_consolidation_petit_modele("francis")
verif("la règle absolue et le travail message par message sont là", "RÈGLE ABSOLUE" in pm and "MESSAGE PAR MESSAGE" in pm)
verif("placés avant la méthode", pm.index("RÈGLE ABSOLUE") < pm.index("MÉTHODE"))
verif("même contrat de sortie que la consigne adaptée",
      pm.split("FORMAT")[-1] == fr.consigne_consolidation_adaptee("francis").split("FORMAT")[-1])
verif("l'exemple n'utilise qu'un nom inventé", "Budgeo" in pm)
pe = en.consigne_consolidation_petit_modele("user")
verif("anglais : la variante qualifiée (docs/20 §7), même contrat de sortie que la consigne de production",
      "ABSOLUTE RULE" in pe and "MESSAGE BY MESSAGE" in pe and pe.split("FORMAT")[-1] == en.consigne_consolidation(True, "user").split("FORMAT")[-1],
      pe.split("FORMAT")[-1][:100])
vu = {}
def faux(messages):
    if "FICHE D'IDENTITÉ" not in messages[0]["content"]:
        vu["s"] = messages[0]["content"]
    return '{"fragments": [], "concepts_nouveaux": {}}'
M = Path("/opt/data/m"); (M / "raw").mkdir(parents=True)
(M / "raw" / "2026-11-08_01.md").write_text("---\ntype: raw\ndate: 2026-11-08\nouvert_le: 2026-11-08T09:00:00+01:00\n---\n\n"
    "## Échanges\n\n[09:00 francis] Le garage Dupont veut un devis pour jeudi.\n", encoding="utf-8")
(M / "raw" / ".chaine.jsonl").write_text('{"fichier": "2026-11-08_01.md"}\n', encoding="utf-8")
C.Consolidateur(M, __import__("zoneinfo").ZoneInfo("Europe/Paris"), faux, modele="t", fiches=False, nom_agent="nexa",
                nom_utilisateur="francis", consigne="petit_modele").consolider()
verif("« petit_modele » : la consigne envoyée au modèle", vu.get("s", "").startswith(pm[:300]))
print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
