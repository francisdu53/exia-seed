import json, sys
from pathlib import Path
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); M = H / "memoire"; ok = ko = 0
def verif(n, c, d=""):
    global ok, ko
    ok += bool(c); ko += (not c); print(f"  {'✓' if c else '✗'} {n}" + (f" — {d}" if d else ""))
from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
p.initialize("s1", hermes_home=str(H), platform="telegram", agent_context="primary")

print("── le brut masque, il ne refuse pas ──")
p.sync_turn("Le mot de passe de contact@exemple.fr : Ab12!cDeF", "Je ne le note pas.", session_id="s1")
p.sync_turn("Ma clé c'est sk-abcdefghijklmnopqrstuvwx1234", "Compris.", session_id="s1")
p.sync_turn("Mon SIRET est 123 456 789 00012 et mon tarif 45 € l'élément.", "Noté.", session_id="s1")
p.sync_turn("Rappelle-moi de changer le mot de passe NAS la semaine prochaine.", "Entendu.", session_id="s1")
brut = sorted((M / "raw").glob("*_open.md"))[0].read_text(encoding="utf-8")
verif("le tour est bien écrit (pas de refus)", brut.count("] ") == 8, f"{brut.count('] ')} lignes")
verif("le mot de passe n'apparaît PAS", "Ab12" not in brut)
verif("la clé d'API n'apparaît PAS", "sk-abcdefghijklmnop" not in brut)
verif("la phrase reste lisible avec son marqueur", "Le mot de passe de contact@exemple.fr : [secret masqué]" in brut)
verif("clé remplacée par le marqueur", "Ma clé c'est [secret masqué]" in brut)
verif("le SIRET est conservé", "123 456 789 00012" in brut)
verif("le tarif est conservé", "45 €" in brut)
verif("« changer le mot de passe NAS » reste intact (pas de valeur)", "changer le mot de passe NAS la semaine prochaine" in brut)

print("── comptage ──")
p.shutdown()
tele = json.loads(sorted((M / "telemetrie").glob("*.json"))[-1].read_text())
verif("secrets masqués comptés", tele.get("secrets_masques") == 2, str(tele.get("secrets_masques")))

print("── le registre refuse toujours (non-régression) ──")
r = json.loads(p.handle_tool_call("memoire_noter", {"texte": "mdp NAS : Ab12!cDeF"}))
verif("note refusée", r.get("ok") is False)
verif("rien dans le registre", not (M / "registre.md").exists() or "Ab12" not in (M / "registre.md").read_text())
print(f"\n  RÉSULTAT : {ok} réussis · {ko} échoués")
