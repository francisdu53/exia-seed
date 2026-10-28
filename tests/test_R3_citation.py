"""R3 — revue des rejets du 27/09 : deux faux rejets du contrôle de citation. Conteneur jetable, vrai chargeur."""
import importlib, sys
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
C = importlib.import_module(type(p).__module__ + ".consolidation")
c = C.Consolidateur(H / "memoire", __import__("zoneinfo").ZoneInfo("Europe/Paris"), lambda m: "{}", nom_agent="nexa", nom_utilisateur="francis")
L = "raw/2026-09-26_05.md"
sources = {f"{L}:116": ("[22:11 francis] Le devis global pour la flotte est de 12345€, hors pièces, comme dans le courrier en pièce jointe.", False),
           f"{L}:139": ("[22:17 francis] je ne sais pas exactement... le stock de consommables doit être aux alentours de 1200€.", False),
           f"{L}:28": ("[21:50 francis] parle moi en français s'il te plait", False),
           f"{L}:177": ("[14:33 francis] Tu n'as pas intégré le garage Dupont non plus dans la liste des clients.", False),
           f"{L}:200": ("[22:30 francis] Mon tarif est de 45 € l'élément.", False)}
def ctl(fait, src, section="semantic"):
    return c._controler({"noeud": "devis_flotte", "section": section, "fait": fait, "src": [src]}, sources)

print("── séparateurs de milliers ──")
r = ctl("Le devis global pour la flotte s'élève à 12 345 €.", f"{L}:116")
verif("« 12 345 € » accepté quand la source dit « 12345€ » (rejeté à tort le 26/09)", r[0], r[1])
r = ctl("Le stock de consommables est aux alentours de 1 200 €.", f"{L}:139")
verif("« 1 200 € » accepté quand la source dit « 1200€ »", r[0], r[1])
r = ctl("Le devis global pour la flotte s'élève à 12 000 €.", f"{L}:116")
verif("…mais un montant inventé (12 000) reste rejeté", not r[0] and "12000" in r[1], r[1])
r = ctl("Le tarif est de 55 € l'élément.", f"{L}:200")
verif("…et le « 55 € » inventé aussi", not r[0] and "55" in r[1], r[1])

print("── utilisateur et agent implicites dans le calcul des mots communs ──")
r = ctl("Répondre en français à l'utilisateur.", f"{L}:28", "procedural")
verif("« Répondre en français à l'utilisateur » accepté (rejeté 1/3 le 26/09)", r[0], r[1])
r = ctl("Francis veut que le garage Dupont figure dans la liste des clients.", f"{L}:177")
verif("« Francis veut… » : le prénom ne compte plus contre le fait", r[0], r[1])
r = ctl("Francis adore la pêche en mer et le jardinage.", f"{L}:177")
verif("…mais un fait sans rapport avec la source reste rejeté", not r[0], r[1])

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
