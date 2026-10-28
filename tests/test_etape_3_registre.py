import json, sys
from pathlib import Path
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))
from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
p.initialize("s1", hermes_home=str(H), platform="telegram", agent_context="primary")

print("── outil exposé ──")
noms = [t["name"] for t in p.get_tool_schemas()]
# Depuis l'étape 7 (27/09), trois outils : memoire_noter, memoire_chercher, memoire_lire.
verif("memoire_noter proposé à l'agent", "memoire_noter" in noms, str(noms))

print("── noter ──")
r = json.loads(p.handle_tool_call("memoire_noter", {"texte": "Le chef d'atelier d'Autoplus Rocheval s'appelle Olivier.", "noeud": "Autoplus_Rocheval"}))
verif("note acceptée", r.get("ok") is True, r.get("message", ""))
r2 = json.loads(p.handle_tool_call("memoire_noter", {"texte": "Préférence : regrouper les visites de garages le matin.", "confidentialite": "confidentiel"}))
verif("note confidentielle acceptée", r2.get("ok") is True)
reg = (H / "memoire" / "registre.md").read_text(encoding="utf-8")
verif("registre lisible, entrée datée et sourcée", "· outil:primary · nœud:autoplus_rocheval" in reg and "Olivier" in reg)
verif("confidentialité conservée", "<!-- privacy:confidentiel -->" in reg)

print("── garde anti-secret ──")
r3 = json.loads(p.handle_tool_call("memoire_noter", {"texte": "Le mot de passe NAS : Ab12!cD"}))
verif("mot de passe refusé", r3.get("ok") is False and "secret" in r3.get("erreur", ""))
r4 = json.loads(p.handle_tool_call("memoire_noter", {"texte": "clé sk-abcdefghijklmnopqrstuvwx1234"}))
verif("clé d'API refusée", r4.get("ok") is False)
verif("rien de secret dans le registre", "Ab12" not in (H / "memoire" / "registre.md").read_text() and "sk-abcdef" not in (H / "memoire" / "registre.md").read_text())

print("── recopie de la mémoire native d'Hermès ──")
p.on_memory_write("add", "user", "Francis préfère les réponses en prose, sans listes à puces.")
p.on_memory_write("remove", "memory", "Francis travaille le dimanche.")
e = p._registre.entrees()
verif("ajout natif recopié", any("prose" in x["texte"] and x["source"] == "memoire_native:user" for x in e))
verif("retrait natif tracé", any(x["texte"].startswith("[retiré de la mémoire native]") for x in e))

print("── lecture et intégration ──")
verif("4 entrées relues, champs complets", len(e) == 4 and all(set(x) >= {"id", "date", "source", "noeud", "privacy", "texte"} for x in e))
p._registre.marquer_integre(e[0]["id"], "pages/autoplus-rocheval.md", "lot_test")
att = p._registre.en_attente()
verif("une entrée intégrée sort de la file d'attente", len(att) == 3 and e[0]["id"] not in {x["id"] for x in att})
verif("le registre lui-même n'a pas été réécrit", (H / "memoire" / "registre.md").read_text(encoding="utf-8").startswith(reg[:200]))

print("── un cron peut noter, mais n'écrit pas le brut ──")
c = load_memory_provider("exia_seed")
c.initialize("cron1", hermes_home=str(H), platform="cron", agent_context="cron")
rc = json.loads(c.handle_tool_call("memoire_noter", {"texte": "Email reçu de la carrosserie Martin : demande de devis grêle."}))
verif("note depuis un cron acceptée", rc.get("ok") is True)
verif("source tracée « outil:cron »", any(x["source"] == "outil:cron" for x in c._registre.entrees()))
p.shutdown(); c.shutdown()
tele = json.loads(sorted((H / "memoire" / "telemetrie").glob("*.json"))[-1].read_text())
verif("télémétrie : notes et refus comptés", tele.get("notes_outil", 0) >= 3 and tele.get("secrets_refuses") == 2 and tele.get("notes_natives") == 2,
      f"outil {tele.get('notes_outil')} · natives {tele.get('notes_natives')} · refus {tele.get('secrets_refuses')}")
print(f"\n  RÉSULTAT : {ok} réussis · {ko} échoués")
