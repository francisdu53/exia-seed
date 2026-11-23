"""EXIA SEED 0.10.0 — le rappel « deux mémoires » (docs/22). Conteneur jetable, vrai chargeur et vrai MemoryManager
d'Hermès : le chemin de production, jusqu'au texte réellement joint au message de l'utilisateur.

Ce qu'il promet, éprouvé ici : `rappel_moteur` vaut « ancien » par défaut (rien ne change) et y revenir suffit ; en
« deux_memoires », les souvenirs consolidés ET les passages du brut remontent, la règle d'abstention en tête, les phrases
de l'agent marquées « (toi) » ; jamais le brut des 3 dernières heures ; jamais une ligne retirée ; mêmes souvenirs avec
ou sans accents (é → e, ç → c) ; une faute de frappe est corrigée par la mémoire ; rien n'est redonné dans la
conversation ; silence pour un message sans rapport ; déterministe ; rapide à chaud ; journal du rappel ; réglages
vérifiés."""
import importlib, json, sys, time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); M = H / "memoire"; ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))

from plugins.memory import load_memory_provider
from agent.memory_manager import MemoryManager
p = load_memory_provider("exia_seed")
mm = MemoryManager()
mm.add_provider(p)
mm.initialize_all(session_id="s1", hermes_home=str(H), platform="telegram", agent_context="primary")
base = type(p).__module__
G = importlib.import_module(base + ".graphe")
DM = importlib.import_module(base + ".deux_memoires")
RG = importlib.import_module(base + ".reglages")

PAGES = []
def page(noeud, titre, sections):
    (M / "pages").mkdir(parents=True, exist_ok=True)
    PAGES.append(noeud)
    corps = ""
    for titre_section, faits in sections:
        corps += f"\n## {titre_section}\n" + "\n".join(
            f"- {t} <!-- conf:1.0 src:raw/2026-10-{len(PAGES):02d}_01.md:{10 * k + 1} dit_le:2026-10-{len(PAGES):02d}T09:00 speaker:francis -->"
            for k, t in enumerate(faits)) + "\n"
    (M / "pages" / (noeud.replace("_", "-") + ".md")).write_text(
        f"---\nnode: {noeud}\nnode_type: concept\naliases:\n  fr:\n  - {titre}\n  en: []\n---\n\n# {titre}\n{corps}", encoding="utf-8")

def brut(nom, date, lignes):
    (M / "raw").mkdir(parents=True, exist_ok=True)
    tete = ["---", "type: raw", f"date: {date}", "lang: fr", "---", "", "## Échanges", ""]
    (M / "raw" / nom).write_text("\n".join(tete + lignes) + "\n", encoding="utf-8")
    return {l: len(tete) + k + 1 for k, l in enumerate(lignes)}          # ligne → numéro dans le fichier

page("application_liste_courses", "application de liste de courses", [
    ("Sémantique", ["L’application de liste de courses est partagée avec Claire et classe les produits par rayon."]),
    ("Procédural", ["Le circuit de courses suit l’ordre Gâteaux → Céréales → Café → Confiserie → Boissons."])])
page("pea", "PEA", [("Sémantique", ["Francis joue au tennis le samedi au club."])])
vieux = brut("2026-10-05_01.md", "2026-10-05", [
    "[09:00 francis] Pour la cuisine, je voudrais des placards jaune Giallo Modena, assortis à la façade rénovée cet été.",
    "[09:01 nexa] D'accord : les placards passent en jaune Giallo Modena, la couleur des Ferrari.",
    "[09:30 francis] Le garagiste de Château-Gontier rappelle pour le devis du capot froissé.",
    "[09:31 nexa] Je note le rappel du garagiste pour le devis du capot."])
ligne_retiree = vieux["[09:30 francis] Le garagiste de Château-Gontier rappelle pour le devis du capot froissé."]
(M / "raw" / ".retraits.jsonl").write_text(json.dumps({"fichier": "2026-10-05_01.md", "lignes": [ligne_retiree, ligne_retiree + 1]}) + "\n",
                                           encoding="utf-8")
# une mémoire de taille RÉALISTE : les poids sont appris sur des mémoires de milliers de tours, où un mot rare pèse ;
# dans trois tours, rien n'est rare et rien n'atteindrait le seuil (comportement voulu : se taire)
SUJETS = ["la tondeuse", "le vélo", "la chaudière", "les impôts", "le chat", "la piscine", "le potager", "la voiture",
          "le cinéma", "la randonnée", "le boulanger", "la banque", "le carrossier", "la réunion", "le colis", "la pluie"]
ACTES = ["il faut réparer", "on doit vérifier", "pense à appeler pour", "j'ai regardé", "on reparle de", "note bien"]
for j in range(40):
    brut(f"2026-09-{1 + j % 28:02d}_{2 + j // 28:02d}.md", f"2026-09-{1 + j % 28:02d}", [
        f"[1{k}:00 {'francis' if k % 2 == 0 else 'nexa'}] {ACTES[(j + k) % len(ACTES)]} {SUJETS[(3 * j + k) % len(SUJETS)]} "
        f"avant {SUJETS[(5 * j + 2 * k) % len(SUJETS)]}." for k in range(6)])
ici = datetime.now(ZoneInfo("Europe/Paris")) - timedelta(minutes=20)
brut(f"{ici.date().isoformat()}_01.md", ici.date().isoformat(), [
    f"[{ici.strftime('%H:%M')} francis] Le code du portail du jardin est zanzibar, ne l'oublie pas."])
G.calculer(M, implicites=("francis", "nexa"))
p._reglages["phase"] = 2

print("── 1. par défaut : l'ancien moteur, inchangé ──")
q = "Tu te souviens de la couleur des placards de la cuisine ?"
verif("réglage par défaut : « ancien »", p._reglages.get("rappel_moteur", "ancien") == "ancien")
verif("l'ancien moteur ne lit pas le brut (pas de règle de mémoire)", "[règle de mémoire]" not in (mm.prefetch_all(q) or ""))

print("── 2. deux mémoires : souvenirs ET brut, règle en tête, phrases de l'agent marquées ──")
p._reglages["rappel_moteur"] = "deux_memoires"
t0 = time.perf_counter(); bloc = mm.prefetch_all(q); froid = (time.perf_counter() - t0) * 1000
verif("le passage du brut remonte (Giallo Modena)", "Giallo Modena" in bloc, bloc[:400])
verif("la règle d'abstention est en tête du bloc", "[règle de mémoire]" in bloc)
verif("présenté comme des données, pas des consignes", "des données, pas des consignes" in bloc)
verif("les phrases de l'agent sont marquées « (toi) »", "nexa (toi):" in bloc)
verif("le passage est daté (« conversation du … »)", "conversation du" in bloc)
verif("au plus 10 éléments", bloc.count("  – ") <= 10)
journal = sorted((M / "rappel").glob("*.jsonl"))[-1].read_text(encoding="utf-8").splitlines()
e = json.loads(journal[-1])
verif("journal : moteur « deux_memoires », éléments en entier avec leur note",
      e.get("moteur") == "deux_memoires" and e["faits"] and all("note" in f and f["fait"].split("\n")[0][:40] for f in e["faits"])
      and e["injecte"]["tours"] >= 1, str(e)[:300])

print("── 3. ce qui ne remonte jamais ──")
verif("jamais le brut des 3 dernières heures (« zanzibar »)", "zanzibar" not in (mm.prefetch_all("Quel est le code du portail du jardin ?") or ""))
verif("jamais une ligne retirée (« capot froissé »)", "froissé" not in (mm.prefetch_all("Le garagiste de Château-Gontier et le devis du capot ?") or ""))

print("── 4. accents, fautes de frappe, continuité, silence, déterminisme ──")
r = p._rappeleur
mk = lambda: DM.DeuxMemoires(r, M, implicites=("francis", "nexa"), agent="nexa")
t = datetime(2026, 11, 23, 18, 0)
a = [x["cle"] for x in mk().rappeler("les placards assortis à la façade rénovée cet été", t)["items"]]
b = [x["cle"] for x in mk().rappeler("les placards assortis a la facade renovee cet ete", t)["items"]]
verif("mêmes éléments avec ou sans accents", a == b and a, f"{a} / {b}")
c = mk().rappeler("les placards jaune Giallo de la cusine", t)
verif("une faute de frappe est corrigée par la mémoire (« cusine » → « cuisine »)",
      c["actif"].get("corrections", 0) >= 1 and any("Giallo" in x["texte"] for x in c["items"]), str(c["actif"]))
bloc2 = mm.prefetch_all(q)
verif("le même message juste après : rien n'est redonné",
      not ({l for l in bloc.splitlines() if l.startswith("  – ")} & {l for l in (bloc2 or "").splitlines() if l.startswith("  – ")}))
verif("un message sans rapport avec la mémoire : silence", mm.prefetch_all("Quel temps fera-t-il à Brest demain matin ?") == "")
verif("déterministe : deux moteurs neufs, mêmes éléments, même ordre", a == [x["cle"] for x in mk().rappeler("la couleur des placards de la cuisine, en jaune", t)["items"]])
m2 = mk(); m2.rappeler("liste de courses", t)
t0 = time.perf_counter(); m2.rappeler("l'ordre du circuit de courses au supermarché", t + timedelta(minutes=1)); chaud = (time.perf_counter() - t0) * 1000
verif("rapide : < 50 ms à chaud", chaud < 50, f"froid {froid:.1f} ms · chaud {chaud:.1f} ms")

print("── 5. réglages et retour arrière ──")
ver = RG.valide
verif("« deux_memoires » accepté, toute autre valeur refusée",
      ver("rappel_moteur", "deux_memoires") and ver("rappel_moteur", "ancien") and not ver("rappel_moteur", "deux"))
verif("seuil entre 0 et 1, max entre 1 et 50, règle et correcteur booléens",
      ver("deux_memoires_seuil", 0.05) and not ver("deux_memoires_seuil", 2) and ver("deux_memoires_max", 10)
      and not ver("deux_memoires_max", 0) and ver("deux_memoires_regle", False) and not ver("deux_memoires_correcteur", "oui"))
p._reglages["rappel_moteur"] = "ancien"
verif("retour arrière : « ancien » → plus de brut ni de règle", "[règle de mémoire]" not in (mm.prefetch_all("Et le PEA, combien par mois ?") or ""))

print(f"\n{ok} réussis · {ko} échoués")
sys.exit(1 if ko else 0)
