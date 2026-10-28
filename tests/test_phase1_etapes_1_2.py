import json, sys, time, hashlib
from pathlib import Path
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data")
ok = 0; ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))

print("── 1. chargement par le vrai chargeur d'Hermès ──")
from plugins.memory import load_memory_provider, discover_memory_providers
noms = [d[0] for d in discover_memory_providers()]
verif("découvert parmi les fournisseurs", "exia_seed" in noms, f"{len(noms)} fournisseurs vus")
p = load_memory_provider("exia_seed")
verif("instancié", p is not None and p.name == "exia_seed")
verif("disponible", p.is_available())

print("── 2. session principale vs cron ──")
p.initialize("sess_test_1", hermes_home=str(H), platform="telegram", agent_context="primary")
verif("session principale : écriture active", p._actif)
cron = load_memory_provider("exia_seed")
cron.initialize("cron_x", hermes_home=str(H), platform="cron", agent_context="cron")
verif("cron : écriture coupée", not cron._actif)
cron.sync_turn("rapport du cron", "RAS")
verif("cron : rien écrit", not list((H / "memoire" / "raw").glob("*.md")))

print("── 3. écriture d'échanges ──")
temps = []
for u, a in [("Bonjour Nexa, demain je passe chez Autoplus Rocheval.", "Très bien. Veux-tu que je prépare la visite ?"),
             ("Oui. Ils ont 3 voitures grêlées.", "Noté : 3 véhicules grêlés chez Autoplus Rocheval."),
             ("Mon tarif c'est 45 € l'élément à partir de deux.", "Compris.")]:
    t0 = time.perf_counter(); p.sync_turn(u, a, session_id="sess_test_1", turn_author={"name": "Jean5 XYZ_T7"}); temps.append((time.perf_counter()-t0)*1000)
fichiers = sorted((H / "memoire" / "raw").glob("*_open.md"))
verif("un lot ouvert", len(fichiers) == 1, fichiers[0].name if fichiers else "aucun")
contenu = fichiers[0].read_text(encoding="utf-8") if fichiers else ""
verif("en-tête présent", contenu.startswith("---\ntype: raw\n"))
verif("6 lignes d'échange, bien attribuées", contenu.count("] ") == 6 and "[" in contenu and " francis] " in contenu and " nexa] " in contenu)
verif("pas de nom Telegram (config prioritaire)", "jean5" not in contenu)
verif(f"latence d'écriture < 5 ms", max(temps) < 5, f"max {max(temps):.2f} ms, moyenne {sum(temps)/len(temps):.2f} ms")

print("── 4. repère de compression ──")
r = p.on_pre_compress([{"role": "user"}] * 12)
verif("rien injecté dans le résumé", r == "")
verif("repère posé dans le brut", "compression de l'historique — 12 messages" in fichiers[0].read_text(encoding="utf-8"))

print("── 5. rotation au seuil (1 000 tokens en test) ──")
gros = "Détail du chantier. " * 150          # ~750 tokens
p.sync_turn(gros, "Noté.", session_id="sess_test_1")
p.sync_turn(gros, "Noté.", session_id="sess_test_1")
chaine = [json.loads(l) for l in (H / "memoire" / "raw" / ".chaine.jsonl").read_text().splitlines()]
verif("un lot fermé au seuil", len(chaine) >= 1 and chaine[0]["raison"] == "seuil_atteint", chaine[0]["fichier"] if chaine else "")
verif("premier maillon : précédent = genèse", chaine[0]["precedent"] == "genese")

print("── 6. nouvelle session → lot fermé, chaîne continue ──")
p.on_session_switch("sess_test_2", reset=True)
chaine = [json.loads(l) for l in (H / "memoire" / "raw" / ".chaine.jsonl").read_text().splitlines()]
verif("deuxième lot fermé", len(chaine) == 2 and chaine[1]["raison"] == "nouvelle_session")
verif("chaînage : précédent = empreinte du lot 1", chaine[1]["precedent"] == chaine[0]["sha256"])

print("── 7. intégrité vérifiable ──")
def empreinte(f): return "sha256:" + hashlib.sha256(f.read_bytes()).hexdigest()
raw = H / "memoire" / "raw"
verif("empreintes recalculées = chaîne", all(empreinte(raw / m["fichier"]) == m["sha256"] for m in chaine))
cible = raw / chaine[0]["fichier"]; sauve = cible.read_bytes()
cible.write_bytes(sauve.replace(b"45", b"55"))
verif("une falsification est détectée", empreinte(cible) != chaine[0]["sha256"])
cible.write_bytes(sauve)

print("── 8. passage par le vrai gestionnaire de mémoire d'Hermès ──")
from agent.memory_manager import MemoryManager
m = MemoryManager()
p2 = load_memory_provider("exia_seed")
m.add_provider(p2)
m.initialize_all("sess_test_3", hermes_home=str(H), platform="telegram", agent_context="primary")
m.sync_all("Rappelle-moi de relancer Autoplus Rocheval avant avril.", "Je le note.", session_id="sess_test_3")
for nom in ("drain", "flush", "wait_idle", "shutdown_all"):
    if hasattr(m, nom):
        try: getattr(m, nom)(); break
        except TypeError: pass
time.sleep(1.5)
ouverts = sorted(raw.glob("*_open.md"))
verif("tour écrit via le gestionnaire (fil d'arrière-plan)",
      bool(ouverts) and "relancer Autoplus Rocheval" in ouverts[-1].read_text(encoding="utf-8"))

print("── 9. télémétrie ──")
p.shutdown()
tele = sorted((H / "memoire" / "telemetrie").glob("*.json"))
verif("compteurs persistés", bool(tele), json.dumps(json.loads(tele[-1].read_text())) if tele else "")

print(f"\n  RÉSULTAT : {ok} réussis · {ko} échoués")
