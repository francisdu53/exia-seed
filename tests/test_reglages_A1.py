"""A1 — réglages vérifiés (15/11/2026). Faux Hermès ou vraie image, sans modèle ni réseau.

Mesuré AVANT la correction (15/11) : une langue différente de celle de la mémoire, un seuil écrit « 25k » ou un nom
d'agent en liste mettaient la mémoire EN RETRAIT — le brut ne s'écrivait plus, aucun compteur d'erreur ne bougeait ;
un fuseau mal écrit faisait écrire le brut en UTC, sans alerte.
Décision de Francis (A1) : le brut continue ; la consolidation se met en pause si un de SES réglages est faux ; un
code défaut part ; la consolidation rattrape une fois le réglage réparé. Une mémoire neuve aux réglages d'écriture
faux n'est pas créée.
"""
import importlib, json, logging, os, subprocess, sys
from pathlib import Path
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); M = H / "memoire"; ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))

CONFIG = H / "config.yaml"
BASE = {"nom_utilisateur": "francis", "nom_agent": "nexa", "seuil_lot_tokens": "1000", "consolidation_auto": "false"}
def config(**changes):
    """Le bloc exia_seed : la base, et chaque changement écrit TEL QUEL en YAML (une clé une seule fois)."""
    bloc = {**BASE, **changes}
    CONFIG.write_text("timezone: Europe/Paris\nmemory:\n  provider: exia_seed\n  exia_seed:\n"
                      + "".join(f"    {k}: {v}\n" for k, v in bloc.items()), encoding="utf-8")

from plugins.memory import load_memory_provider
def provider(**changes):
    config(**changes)
    p = load_memory_provider("exia_seed")
    p.initialize("s1", hermes_home=str(H), platform="telegram", agent_context="primary")
    return p

def defauts():
    f = M / "telemetrie" / "defauts.jsonl"
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []

def lignes_brut():
    return sum(len(f.read_text(encoding="utf-8").splitlines()) for f in (M / "raw").glob("*.md")) if (M / "raw").exists() else 0

journal = []
class Capture(logging.Handler):
    def emit(self, r): journal.append(r.getMessage())
logging.getLogger().addHandler(Capture(level=logging.WARNING))

p0 = load_memory_provider("exia_seed")
base = type(p0).__module__
R = importlib.import_module(base + ".reglages")
CD = importlib.import_module(base + ".codes_defauts")

print("── A. la vérification seule ──")
reg, codes, inv = R.verifier({"seuil_lot_tokens": True, "dossier": "../ailleurs", "consolidation_consigne": "petit_modèle",
                              "langue": "EN", "seuil_lot_token": 500, "phase": 2})
verif("un booléen n'est pas un nombre (seuil = True refusé)", "seuil_lot_tokens" in inv)
verif("un dossier qui sort de la racine (« .. ») est refusé", "dossier" in inv)
verif("un dossier absolu est refusé", "dossier" in R.verifier({"dossier": "/etc"})[2])
verif("une consigne mal écrite est refusée", "consolidation_consigne" in inv)
verif("« EN » est accepté et rangé « en »", reg["langue"] == "en" and "langue" not in inv)
verif("un réglage inconnu donne ES-CFG-04, sans être gardé", ("ES-CFG-04", "seuil_lot_token") in codes and "seuil_lot_token" not in reg)
verif("chaque groupe a son code (écriture 02, consolidation 05)",
      ("ES-CFG-02", "seuil_lot_tokens") in codes and ("ES-CFG-05", "consolidation_consigne") in codes)
CFG = importlib.import_module(base + ".config")
verif("chaque réglage par défaut a son vérificateur DÉDIÉ", R.DEDIES == set(CFG.DEFAUTS), str(sorted(set(CFG.DEFAUTS) - R.DEDIES)))
CFG.DEFAUTS["reglage_futur"] = 3
R2 = importlib.reload(R)
verif("un réglage ajouté sans vérificateur dédié n'empêche pas le chargement (vérifié par son type)",
      R2.groupe("reglage_futur") == "lecture" and R2.valide("reglage_futur", 5) and not R2.valide("reglage_futur", "x"))
del CFG.DEFAUTS["reglage_futur"]; R = importlib.reload(R2)
verif("le catalogue connaît tous les codes utilisés", all(c in CD.CATALOGUE for c in
      ("ES-CFG-01", "ES-CFG-02", "ES-CFG-03", "ES-CFG-04", "ES-CFG-05", "ES-CFG-06", "ES-CFG-07")))

print("── B. une mémoire neuve aux réglages d'écriture faux n'est pas créée ──")
journal.clear()
p = provider(seuil_lot_tokens="25k")
p.sync_turn("Bonjour.", "Bonjour !", session_id="s1")
verif("mémoire non active", p._actif is False)
verif("rien n'est créé", not M.exists() or not any(M.iterdir()))
verif("le code ES-CFG-07 est au journal du processus", any("ES-CFG-07" in m for m in journal), " | ".join(journal)[:200])
journal.clear()
p = provider(dossier="../evasion")
verif("un dossier « ../evasion » : mémoire non active, rien hors de la racine", p._actif is False and not (H.parent / "evasion").exists())
verif("… et ES-CFG-07 au journal", any("ES-CFG-07" in m for m in journal))

print("── C. réglages bons : la mémoire garde ses derniers réglages valides ──")
p = provider()
p.sync_turn("Le garage Dupont veut un devis pour jeudi.", "C'est noté.", session_id="s1")
valides = json.loads((M / R.FICHIER_VALIDES).read_text(encoding="utf-8"))
verif("brut écrit", lignes_brut() > 0)
verif("derniers réglages valides enregistrés", valides.get("fuseau") == "Europe/Paris" and valides.get("seuil_lot_tokens") == 1000
      and valides.get("nom_agent") == "nexa", str({k: valides.get(k) for k in ("fuseau", "seuil_lot_tokens", "nom_agent")}))
verif("aucun code défaut", defauts() == [])
p.shutdown()

print("── D. réglages d'écriture faux sur une mémoire existante : le brut CONTINUE ──")
avant = lignes_brut()
p = provider(fuseau="Europe/Pariss", seuil_lot_tokens="25k", nom_agent="[nexa, autre]")
p.sync_turn("Le devis est de 450 euros.", "Je l'ajoute.", session_id="s1")
verif("mémoire active (avant le 15/11 : en retrait)", p._actif is True)
verif("le brut continue de s'écrire", lignes_brut() > avant, f"{avant} → {lignes_brut()}")
verif("fuseau : la dernière valeur valide (pas UTC)", str(p._brut.tz) == "Europe/Paris", str(p._brut.tz))
verif("seuil : la dernière valeur valide", p._brut.seuil == 1000 and p._reglages["seuil_lot_tokens"] == 1000)
verif("nom de l'agent : la dernière valeur valide", p._reglages["nom_agent"] == "nexa")
d = [x for x in defauts() if x["code"] == "ES-CFG-02"]
verif("trois codes ES-CFG-02, action « dernière valeur valide »", len(d) >= 3 and {x["cle"] for x in d} >= {"fuseau", "seuil_lot_tokens", "nom_agent"}
      and all(x["action"] == "dernière valeur valide" for x in d), str([(x["cle"], x["action"]) for x in d]))
texte = (M / "telemetrie" / "defauts.jsonl").read_text(encoding="utf-8") + (M / R.FICHIER_VALIDES).read_text(encoding="utf-8")
verif("aucune VALEUR fausse n'est écrite (ni défauts, ni derniers valides)", "Pariss" not in texte and "25k" not in texte and "autre" not in texte)
p.shutdown()

print("── E. une autre langue demandée : la langue de la mémoire est gardée ──")
p = provider(langue="en")
avant = lignes_brut()
p.sync_turn("Rappelle-moi le devis.", "450 euros.", session_id="s1")
verif("mémoire active, brut écrit", p._actif is True and lignes_brut() > avant)
verif("langue de la mémoire gardée (fr)", p._reglages["langue"] == "fr" and p._masque.code == "fr")
verif("code ES-CFG-03", any(x["code"] == "ES-CFG-03" for x in defauts()))
p.shutdown()

print("── F. un réglage de consolidation faux : consolidation EN PAUSE, le brut continue ──")
p = provider(consolidation_consigne="petit_modèle", consolidation_auto="true")
avant = lignes_brut()
p.sync_turn("Le client rappelle demain.", "Noté.", session_id="s1")
verif("le brut continue", lignes_brut() > avant)
verif("consolidation en pause", p._consolidation_en_pause is True)
p._lancer_consolidation()
verif("aucune consolidation lancée", p._fil_consolidation is None)
verif("code ES-CFG-05", any(x["code"] == "ES-CFG-05" and x["cle"] == "consolidation_consigne" for x in defauts()))
p.shutdown()
env = {"PATH": "/usr/bin:/bin", "HOME": str(H), "LANG": "C.UTF-8", "TZ": "Europe/Paris", "HERMES_HOME": str(H)}
r = subprocess.run([sys.executable, str(H / "plugins" / "exia_seed" / "outils" / "consolider.py"), "--forcer"],
                   capture_output=True, text=True, env=env, timeout=120)
sortie = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
verif("l'outil de consolidation (cron) s'arrête en pause et le dit", '"en_pause"' in sortie and "ES-CFG-05" in sortie, sortie[:160] or r.stderr[-200:])
consolide = M / "raw" / ".consolide.jsonl"
verif("… le lot est fermé mais rien n'est consolidé (il attend)", any((M / "raw").glob("*.md")) and not any(
      f.name.endswith("_open.md") for f in (M / "raw").glob("*.md")) and (not consolide.exists() or not consolide.read_text().strip()))

print("── G. réglage réparé : la pause se lève ──")
p = provider(consolidation_auto="true")
verif("consolidation de nouveau possible", p._consolidation_en_pause is False)
p.shutdown()

print("── H. les réglages ajoutés après 122e8eb (0.9.5, 0.9.6 : intégration chez Nexa, 15/11/2026) ──")
verif("recherche_poids_sujet : null (le réglage de Nexa) est VALIDE, pas remplacé par 0,25",
      R.valide("recherche_poids_sujet", None) and R.verifier({"recherche_poids_sujet": None})[0]["recherche_poids_sujet"] is None)
verif("…« ancienne » (le même choix, qui survit à Hermès) valide", R.valide("recherche_poids_sujet", "ancienne"))
verif("…« eventail » et 0,25 valides ; « 0,25 » en texte, 2 et True refusés",
      R.valide("recherche_poids_sujet", "eventail") and R.valide("recherche_poids_sujet", 0.25)
      and not any(R.valide("recherche_poids_sujet", v) for v in ("0,25", 2, True)))
verif("consolidation_par_echange et retrait_retroactif : booléens, groupe consolidation (une faute = pause, pas un repli)",
      R.groupe("consolidation_par_echange") == R.groupe("retrait_retroactif") == "consolidation"
      and not R.valide("consolidation_par_echange", "oui"))
CANAL = {"dossier": "echanges", "correspondant": "main_claude", "description": "Claude Code", "echanges_max": 14}
verif("canal : {} (éteint) et le réglage de Nexa valides", R.valide("canal", {}) and R.valide("canal", CANAL))
verif("…dossier hors de la mémoire, clé inconnue, correspondant vide, echanges_max 0 : refusés",
      not any(R.valide("canal", {**CANAL, **x}) for x in ({"dossier": "../etc"}, {"inconnu": 1}, {"correspondant": " "},
                                                           {"echanges_max": 0})))
verif("bulletin_seuils : {nom: nombre} ; une valeur en texte refusée",
      R.valide("bulletin_seuils", {"couverture_orange": 70}) and not R.valide("bulletin_seuils", {"couverture_orange": "70"}))

print(f"\n  RÉSULTAT : {ok} réussis · {ko} échoués")
sys.exit(1 if ko else 0)
