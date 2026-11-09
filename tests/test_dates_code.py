"""Dates calculées par le code (docs/18 §10, 08/11/2026) et deux défauts corrigés — conteneur jetable.

`temps.proposer` calcule la date d'un événement depuis le calendrier et le jour où la phrase a été dite ; la
vérification des dates d'un modèle ne doit plus trouver « hier » dans « fichier », ni une date dans « 17,5 % »."""
import importlib, sys
from datetime import date
sys.path.insert(0, "/opt/hermes")
ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))
from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
T = importlib.import_module(type(p).__module__ + ".temps")
L = importlib.import_module(type(p).__module__ + ".langues")
FR = L.masque("fr"); A = date(2026, 11, 2)                       # un lundi

print("── 1. le code calcule ──")
for texte, attendu in (("je passe au garage demain", "2026-11-03"), ("rendez-vous après-demain", "2026-11-04"),
                       ("on se voit jeudi", "2026-11-05"), ("je l'ai appelé lundi dernier", "2026-10-26"),
                       ("la facture est due le 12/11", "2026-11-12"), ("le contrôle technique le 3 mars", "2027-03-03"),
                       ("rappelle-moi dans 3 jours", "2026-11-05"), ("ce soir à 18 heures", "2026-11-02T18:00"),
                       ("je l'ai vu hier", "2026-11-01")):
    d, r = T.proposer(texte, A, FR)
    verif(f"« {texte} » → {attendu}", d == attendu, f"{d} ({r})")
print("── 2. le code s'abstient ──")
for texte in ("envoie-moi le fichier tel quel", "les taux sont de 17,5 % désormais", "version 2.3 installée",
              "lundi le devis, jeudi la facture"):
    d, r = T.proposer(texte, A, FR)
    verif(f"« {texte} » → rien", d is None, f"{d} ({r})")
print("── 3. la vérification ne se laisse plus tromper ──")
v, raison = T.verifier("2026-11-01", "envoie-moi le fichier tel quel", A, FR)
verif("« fichier » ne justifie pas la veille", v is None and "non justifiée" in (raison or ""), str(raison))
v, raison = T.verifier("2026-11-01", "je l'ai vu hier", A, FR)
verif("« hier » justifie toujours la veille", v == "2026-11-01", str(raison))
print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
