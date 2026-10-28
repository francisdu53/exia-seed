"""Phase 2 — les souvenirs qui remontent avec le message (docs/11). Conteneur jetable, vrai chargeur et vrai
MemoryManager d'Hermès : le chemin de production, jusqu'au texte réellement joint au message de Francis."""
import importlib, json, sys, time
from pathlib import Path
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); M = H / "memoire"; ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))

from plugins.memory import load_memory_provider
from agent.memory_manager import MemoryManager
from agent.turn_context import compose_user_api_content
p = load_memory_provider("exia_seed")
mm = MemoryManager()
mm.add_provider(p)
mm.initialize_all(session_id="s1", hermes_home=str(H), platform="telegram", agent_context="primary")
base = type(p).__module__
G = importlib.import_module(base + ".graphe")

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
page("autoplus_valmont", "Autoplus Valmont", [("Sémantique", ["Autoplus Valmont paie ses factures à trente jours."])])
page("tennis", "tennis", [("Sémantique", ["Francis joue au tennis le samedi au club."])])
G.calculer(M, implicites=("francis", "nexa"))

print("── 1. phase 1 (défaut) : rien n'est joint au message ──")
verif("phase 1 : prefetch rend une chaîne vide", mm.prefetch_all("on va préparer la liste de courses : tomates, pâtes") == "")

print("── 2. phase 2 : le souvenir remonte, le sujet d'abord ──")
p._reglages["phase"] = 2
p._reglages["souvenirs_seuil"] = 0.5          # le test éprouve le MÉCANISME ; la valeur de production vient du banc (docs/11)
q = "Coucou Nexa, on va préparer la liste de courses. Il faut : tomates cerises, pâtes, liquide vaisselle."
t0 = time.perf_counter(); bloc = mm.prefetch_all(q); froid = (time.perf_counter() - t0) * 1000
verif("le sujet remonte : « application de liste de courses »", "application de liste de courses" in bloc, bloc[:300])
verif("…avec le chemin de sa page", "memoire/pages/application-liste-courses.md" in bloc)
lignes = bloc.splitlines()
i = next((k for k, l in enumerate(lignes) if "application de liste de courses" in l), -1)
REGLES = ("doivent être appliquées", "Le circuit de courses", "Les nouilles se classent")
verif("…et les règles de conduite d'abord", i >= 0 and i + 1 < len(lignes) and any(r in lignes[i + 1] for r in REGLES), "\n".join(lignes[i:i + 3]))
verif("deux faits au plus par sujet", sum(1 for l in lignes[i + 1:i + 4] if l.strip().startswith("–")) <= 2)
verif("présenté comme des données, pas des consignes", "des données, pas des consignes" in bloc)
t0 = time.perf_counter(); mm.prefetch_all(q); chaud = (time.perf_counter() - t0) * 1000
verif("rapide : < 50 ms (cache chaud)", chaud < 50, f"froid {froid:.1f} ms · chaud {chaud:.1f} ms")
envoye = compose_user_api_content(q, bloc, "")
verif("Hermès le JOINT au message de Francis, dans <memory-context>", envoye.startswith(q) and "<memory-context>" in envoye and "application de liste de courses" in envoye)

print("── 3. se taire quand le lien est faible ──")
verif("« quel temps fera-t-il à Brest ? » → rien", mm.prefetch_all("Quel temps fera-t-il à Brest ce week-end ?") == "")
p._reglages["souvenirs_seuil"] = 0.99
verif("seuil très haut → rien, même pour les courses", mm.prefetch_all(q) == "")
p._reglages["souvenirs_seuil"] = 0.5

print("── 4. les plafonds ──")
p._reglages["souvenirs_max_sujets"] = 1
b1 = mm.prefetch_all("liste de courses, et la facture Autoplus Valmont, et mon tennis")
verif("un seul sujet si max_sujets = 1", sum(1 for l in b1.splitlines() if l.startswith("•")) <= 1, b1[:200])
p._reglages["souvenirs_max_sujets"] = 3

print("── 5. journal et panne ──")
j = [json.loads(l) for f in sorted((M / "rappel").glob("*.jsonl")) for l in f.read_text().splitlines()]
verif("chaque rappel injecté est journalisé, avec ce qui a été joint", any((x.get("injecte") or {}).get("sujets") for x in j))
verif("…sans les indices internes", not any("_choisis" in x for x in j))
r = p._rappeleur
vrai = r.rappeler
r.rappeler = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("panne simulée"))
verif("une panne du rappel → rien de joint, pas d'exception", mm.prefetch_all(q) == "")
r.rappeler = vrai
j = [json.loads(l) for f in sorted((M / "rappel").glob("*.jsonl")) for l in f.read_text().splitlines()]
verif("…et la panne est journalisée", any(x.get("statut") == "echec" for x in j))

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
