"""EXIA SEED 0.9.16 — le rappel « montre » (docs/21). Conteneur jetable, vrai chargeur et vrai MemoryManager d'Hermès :
le chemin de production, jusqu'au texte réellement joint au message de l'utilisateur.

Ce qu'il promet, éprouvé ici : le réglage `rappel_moteur` vaut « ancien » par défaut (rien ne change) ; en « montre »,
les souvenirs remontent avec leur raison, au plus 10, le bloc reste présenté comme des données ; un message sans rapport
avec la mémoire reçoit le silence ; rien de ce qui a été donné dans la conversation n'est redonné ; le résultat est
déterministe ; rapide (< 50 ms à chaud) ; le journal du rappel garde les souvenirs donnés EN ENTIER, avec leur note et
leur raison (base du futur apprentissage par l'usage) ; une valeur de réglage inconnue est refusée."""
import importlib, json, sys, time
from datetime import datetime
from pathlib import Path
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
MO = importlib.import_module(base + ".montre")
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

page("application_liste_courses", "application de liste de courses", [
    ("Sémantique", ["L’application de liste de courses est partagée avec Claire et classe les produits par rayon."]),
    ("Procédural", ["Les demandes de préparation de courses doivent être appliquées à l’application partagée avec Claire, sans doublon.",
                    "Le circuit de courses suit l’ordre Gâteaux → Céréales → Café → Confiserie → Boissons.",
                    "Les nouilles se classent dans les pâtes au rayon des conserves."])])
page("autoplus_valmont", "Autoplus Valmont", [("Sémantique", ["Autoplus Valmont paie ses factures à trente jours.",
                                                             "Les factures de Autoplus Valmont vont à la comptabilité et à Julien."])])
page("pea", "PEA", [("Sémantique", ["Francis joue au tennis le samedi au club."])])
G.calculer(M, implicites=("francis", "nexa"))
p._reglages["phase"] = 2

print("── 1. par défaut : l'ancien moteur, inchangé ──")
q = "Coucou Nexa, on va préparer la liste de courses. Il faut : tomates cerises, pâtes, liquide vaisselle."
verif("réglage par défaut : « ancien »", p._reglages.get("rappel_moteur", "ancien") == "ancien")
bloc0 = mm.prefetch_all(q)
verif("l'ancien moteur répond comme avant (pas de « pourquoi : »)", bloc0 and "pourquoi :" not in bloc0, bloc0[:200])

print("── 2. la montre : les souvenirs remontent avec leur raison ──")
p._reglages["rappel_moteur"] = "montre"
t0 = time.perf_counter(); bloc = mm.prefetch_all(q); froid = (time.perf_counter() - t0) * 1000
verif("le sujet remonte : « application de liste de courses »", "application de liste de courses" in bloc, bloc[:300])
verif("chaque souvenir dit pourquoi il remonte", bloc.count("pourquoi :") >= 1 and bloc.count("pourquoi :") == bloc.count("  – "))
verif("au plus 10 souvenirs", bloc.count("  – ") <= MO.MAX)
verif("présenté comme des données, pas des consignes", "des données, pas des consignes" in bloc)
journal = sorted((M / "rappel").glob("*.jsonl"))[-1].read_text(encoding="utf-8").splitlines()
e = json.loads(journal[-1])
verif("journal : moteur « montre », souvenirs EN ENTIER avec note et raison",
      e.get("moteur") == "montre" and e["faits"] and all(f["fait"] in bloc and "note" in f and f["raison"] for f in e["faits"]), str(e)[:300])

print("── 3. continuité : rien n'est redonné dans la conversation ──")
bloc2 = mm.prefetch_all(q)
donnes1 = {l for l in bloc.splitlines() if l.startswith("  – ")}
donnes2 = {l.split(" — pourquoi :")[0] for l in bloc2.splitlines() if l.startswith("  – ")}
verif("le même message, juste après : aucun souvenir redonné", not ({l.split(" — pourquoi :")[0] for l in donnes1} & donnes2), bloc2[:200])

print("── 4. silence et déterminisme ──")
verif("un message sans rapport avec la mémoire : silence", mm.prefetch_all("Quel temps fera-t-il à Brest demain matin ?") == "")
r = p._rappeleur
a = MO.Montre(r).rappeler(q, datetime(2026, 11, 20, 10, 0)); b = MO.Montre(r).rappeler(q, datetime(2026, 11, 20, 10, 0))
verif("déterministe : deux montres neuves, mêmes souvenirs, même ordre", a["faits"] == b["faits"] and a["faits"], str(a["faits"]))
t0 = time.perf_counter(); MO.Montre(r).rappeler(q, datetime(2026, 11, 20, 10, 0)); MO.Montre(r)
mo = MO.Montre(r); mo.rappeler(q, datetime(2026, 11, 20, 10, 0))
t0 = time.perf_counter(); mo.rappeler(q, datetime(2026, 11, 20, 10, 0)); chaud = (time.perf_counter() - t0) * 1000
verif("rapide : < 50 ms (cache chaud)", chaud < 50, f"froid {froid:.1f} ms · chaud {chaud:.1f} ms")

print("── 5. réglage ──")
ver = lambda v: RG.valide("rappel_moteur", v)
verif("« ancien » et « montre » acceptés, toute autre valeur refusée", ver("ancien") and ver("montre") and not ver("autre"))

print(f"\n{ok} réussis · {ko} échoués")
sys.exit(1 if ko else 0)
