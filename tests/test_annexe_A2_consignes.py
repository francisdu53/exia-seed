import importlib, json, sys
from pathlib import Path
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); M = H / "memoire"; ok = ko = 0
def verif(n, c, d=""):
    global ok, ko
    ok += bool(c); ko += (not c); print(f"  {'✓' if c else '✗'} {n}" + (f" — {d}" if d else ""))
from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
p.initialize("s1", hermes_home=str(H), platform="telegram", agent_context="primary")
C = importlib.import_module(type(p).__module__ + ".consolidation")

print("── détection des consignes ──")
D = importlib.import_module(type(p).__module__ + ".consignes")
cas = [("Ne note pas ça, c'est personnel.", "hors_brut_et_precedent"),
       ("n'écris pas ça s'il te plaît", "hors_brut_et_precedent"),
       ("hors mémoire : je te raconte un truc", "hors_brut"),
       ("Oublie ce que je viens de dire.", "retrait_precedent"),
       ("ne note pas ce que je viens de dire", "retrait_precedent"),
       ("efface ce que j'ai dit", "retrait_precedent"),
       ("Note que Olivier est chef d'atelier.", ""),
       ("Il faut que je note les tarifs sur le devis.", "")]
for texte, attendu in cas:
    r = D.detecter(texte)
    verif(f"« {texte[:44]} » → {r or 'aucune consigne'}", r == attendu)

print("── effet sur le brut ──")
p.sync_turn("Le chef d'atelier d'Autoplus Rocheval est Olivier.", "Noté.", session_id="s1")
p.sync_turn("Ne note pas ça : j'ai un souci avec un client.", "Entendu, je n'en garde rien.", session_id="s1")
p.sync_turn("Combien je facture à partir de deux éléments ?", "45 € l'élément.", session_id="s1")
p.sync_turn("Oublie ce que je viens de dire.", "C'est retiré.", session_id="s1")
brut = sorted((M / "raw").glob("*_open.md"))[0].read_text(encoding="utf-8")
verif("l'échange non conservé n'apparaît pas", "souci avec un client" not in brut)
verif("un repère horodaté le signale", "échange non conservé à la demande de francis" in brut)
verif("le tour normal est bien écrit", "Olivier" in brut)
verif("le retrait est marqué avec ses lignes", "retrait:" in brut and "lignes" in brut and "non consolidables" in brut)
verif("le tour retiré reste dans le fichier (ajout seul)", "45 € l'élément" in brut)
verif("la demande de retrait elle-même n'est pas écrite", "Oublie ce que je viens de dire" not in brut)

print("── effet sur la consolidation ──")
p.on_session_switch("s2", reset=True)
lot = sorted(f.name for f in (M / "raw").glob("*.md") if "_open" not in f.name)[0]
c = C.Consolidateur(M, __import__("zoneinfo").ZoneInfo("Europe/Paris"), lambda m: '{"fragments": []}', nom_agent="nexa")
vues = " ".join(t for _, t in c._lignes_de(lot))
verif("le modèle NE VOIT PAS le tour retiré", "45 €" not in vues)
verif("le modèle voit toujours le reste", "Olivier" in vues)
verif("le modèle ne voit aucun repère", "non conservé" not in vues and "retrait:" not in vues)

print("── comptage ──")
p.shutdown()
tele = json.loads(sorted((M / "telemetrie").glob("*.json"))[-1].read_text())
verif("tours non conservés comptés (consigne + demande de retrait)", tele.get("tours_non_conserves") == 2, str(tele.get("tours_non_conserves")))
verif("retraits comptés", tele.get("retraits") == 1, str(tele.get("retraits")))
print(f"\n  RÉSULTAT : {ok} réussis · {ko} échoués")
