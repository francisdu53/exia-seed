"""Le lot journalier (docs/18 §11, 09/11/2026) — conteneur jetable, vrai chargeur d'Hermès.

`fermer_lot_fin_de_session` (vrai par défaut) : faux, une fin de session ou une remise à zéro ne ferme plus le lot ; il
continue de se remplir et se ferme au seuil ou chaque nuit. Vrai : le comportement d'avant."""
import json, sys
from pathlib import Path
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))
from plugins.memory import load_memory_provider
import importlib
p = load_memory_provider("exia_seed")
p.initialize("s1", hermes_home=str(H), platform="telegram", agent_context="primary")
CFG = importlib.import_module(type(p).__module__ + ".config")
M = H / "memoire"; chaine = M / "raw" / ".chaine.jsonl"
fermes = lambda: len([l for l in chaine.read_text().splitlines() if l.strip()]) if chaine.exists() else 0
verif("défaut : on ferme en fin de session (comportement d'avant)", CFG.DEFAUTS["fermer_lot_fin_de_session"] is True)
p._reglages["consolidation_auto"] = False                      # le test ne consolide pas
p._reglages["fermer_lot_fin_de_session"] = False
p.sync_turn("Le garage Dupont veut un devis pour jeudi.", "C'est noté.", session_id="s1")
p.on_session_end([])
p.on_session_switch("s2", reset=True)
verif("réglage faux : ni la fin de session ni la remise à zéro ne ferment le lot", fermes() == 0, str(fermes()))
p.sync_turn("Le devis est de 450 euros.", "Je l'ajoute.", session_id="s2")
ouverts = sorted(f.name for f in (M / "raw").glob("*_open.md"))
verif("le lot continue d'une session à l'autre (un seul lot ouvert)", len(ouverts) == 1 and "450 euros" in (M / "raw" / ouverts[0]).read_text(encoding="utf-8"), str(ouverts))
p._reglages["fermer_lot_fin_de_session"] = True
p.on_session_end([])
verif("réglage vrai : la fin de session ferme le lot", fermes() == 1, str(fermes()))
print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
