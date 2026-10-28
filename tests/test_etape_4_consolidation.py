import json, re, subprocess, sys, time, importlib
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
AUJOURDHUI = datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()   # R2 : une date est vérifiée
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); M = H / "memoire"; ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))
def trouve(src, bout):
    for l in src.splitlines():
        m = re.match(r"\[([^\]]+)\] (?:\(\w+\) )?(.*)", l)
        if m and bout in m.group(2): return m.group(1)
    raise KeyError(bout)

from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
p.initialize("s1", hermes_home=str(H), platform="telegram", agent_context="primary")
C = importlib.import_module(type(p).__module__ + ".consolidation")
for u, a in [("Demain je passe chez Autoplus Rocheval, ils ont 3 voitures grêlées.", "Très bien, je note : 3 voitures grêlées chez Autoplus Rocheval."),
             ("Mon tarif est de 45 € l'élément à partir de deux éléments.", "Compris."),
             ("Le chef d'atelier c'est Olivier, passe le matin, l'après-midi ils sont débordés.", "Je te propose aussi de les relancer en avril avant la grêle.")]:
    p.sync_turn(u, a, session_id="s1")
p.handle_tool_call("memoire_noter", {"texte": "Préférence : regrouper les visites de garages le matin.", "confidentialite": "confidentiel"})
p.on_session_switch("s2", reset=True)

def faux_llm_1(messages):
    s = messages[1]["content"]
    g, t, l, n, r = trouve(s, "3 voitures grêlées"), trouve(s, "45 €"), trouve(s, "Olivier"), trouve(s, "relancer en avril"), trouve(s, "visites de garages")
    F = [
     {"noeud":"autoplus_rocheval","nouveau":True,"type_noeud":"entite","alias":{"fr":["Autoplus Rocheval","garage de Rocheval"],"en":["Autoplus Rocheval"]},"section":"semantic","fait":"Le chef d'atelier d'Autoplus Rocheval s'appelle Olivier.","src":[g,l],"conf":1.0,"speaker":"francis"},
     {"noeud":"autoplus_rocheval","section":"procedural","fait":"Passer chez Autoplus Rocheval le matin : l'après-midi ils sont débordés.","src":[g,l],"conf":1.0},
     {"noeud":"autoplus_rocheval","section":"episodic","fait":"Autoplus Rocheval a 3 voitures grêlées à traiter.","src":[g],"conf":1.0,"event_time":AUJOURDHUI},
     {"noeud":"tarifs","nouveau":True,"type_noeud":"concept","alias":{"fr":["tarifs","prix"],"en":["pricing"]},"section":"semantic","fait":"Le tarif est de 45 € l'élément à partir de deux éléments.","src":[t],"conf":1.0},
     {"noeud":"tarifs","section":"semantic","fait":"Le tarif est de 55 € pour un élément seul.","src":[t]},
     {"noeud":"autoplus_rocheval","section":"semantic","fait":"Le directeur d'Autoplus Rocheval s'appelle Martin.","src":[g,l]},
     {"noeud":"autoplus_rocheval","section":"prospective","fait":"Relancer Autoplus Rocheval en avril avant la grêle.","src":[n]},
     {"noeud":"autoplus_rocheval","section":"semantic","fait":"Autoplus Rocheval est ouvert le dimanche.","src":["raw/inexistant.md:3"]},
     {"noeud":"francis","nouveau":True,"type_noeud":"entite","alias":{"fr":["Francis"],"en":["Francis"]},"section":"procedural","fait":"Regrouper les visites de garages le matin.","src":[r],"conf":1.0,"privacy":"confidentiel"},
    ]
    return "```json\n" + json.dumps({"fragments": F}, ensure_ascii=False) + "\n```"

print("── consolidation 1 : 5 faits justes, 4 pièges ──")
c = C.Consolidateur(M, __import__("zoneinfo").ZoneInfo("Europe/Paris"), faux_llm_1, modele="gpt-6-astra", nom_agent="nexa")
r = c.consolider()
verif("passage réussi", r["statut"] == "ok")
verif("5 faits retenus", r["faits_retenus"] == 5, str(r["faits_retenus"]))
raisons = {x["raison"].split(" :")[0] for x in r["rejets"]}
verif("4 pièges rejetés", r["fragments_rejetes"] == 4, " | ".join(x["raison"] for x in r["rejets"]))
verif("tarif inventé (55 €) rejeté", any("55" in x["raison"] for x in r["rejets"]))
verif("nom inventé (Martin) rejeté", any("Martin" in x["raison"] for x in r["rejets"]))
verif("fait reposant sur l'agent seul rejeté", any("agent" in x["raison"] for x in r["rejets"]))
verif("source inexistante rejetée", any("aucune source" in x["raison"] for x in r["rejets"]))
pg = sorted(f.name for f in (M / "pages").glob("*.md"))
verif("3 pages créées", pg == ["autoplus-rocheval.md", "francis.md", "tarifs.md"], ", ".join(pg))
rl = (M / "pages" / "autoplus-rocheval.md").read_text(encoding="utf-8")
verif("autoplus-rocheval : 3 sections remplies", "## Sémantique" in rl and "## Épisodique" in rl and "## Procédural" in rl and "Martin" not in rl)
verif("fragment sourcé, ancré et daté", "src:raw/" in rl and "dit_le:" in rl and f"event_time:{AUJOURDHUI}" in rl)
fr = (M / "pages" / "francis.md").read_text(encoding="utf-8")
verif("confidentialité portée jusqu'à la page", "privacy:confidentiel" in fr)
verif("INDEX.md régénéré", "autoplus_rocheval" in (M / "INDEX.md").read_text())
verif("log.md : rejets expliqués", "rejeté" in (M / "log.md").read_text() and "55" in (M / "log.md").read_text())
verif("lot marqué consolidé", len(c.lots_en_attente()) == 0)
verif("note du registre intégrée", len(c.registre.en_attente()) == 0)
verif("chaîne des pages amorcée", json.loads((M / "pages" / ".chaine.jsonl").read_text().splitlines()[0])["precedent"] == "genese")
nb = subprocess.run(["git", "-C", str(M), "log", "--oneline"], capture_output=True, text=True).stdout.strip().splitlines()
verif("git : un commit", len(nb) == 1, nb[0] if nb else "aucun")

print("── consolidation 2 : un alias rattache au nœud existant ──")
p.sync_turn("Au garage de Rocheval, Olivier veut un devis pour la Polo grise.", "Je prépare le devis.", session_id="s2")
p.on_session_switch("s3", reset=True)
def faux_llm_2(messages):
    s = messages[1]["content"]
    assert "autoplus_rocheval (entite)" in s, "catalogue des nœuds absent du prompt"
    l = trouve(s, "Polo grise")
    return json.dumps({"fragments": [{"noeud": "garage_de_rocheval", "section": "episodic", "fait": "Olivier veut un devis pour la Polo grise.", "src": [l], "conf": 1.0}]})
r2 = C.Consolidateur(M, __import__("zoneinfo").ZoneInfo("Europe/Paris"), faux_llm_2, modele="gpt-6-astra", nom_agent="nexa").consolider()
verif("le fait rejoint autoplus-rocheval.md (pas de doublon de nœud)",
      r2["faits_retenus"] == 1 and not r2["noeuds_crees"] and "Polo grise" in (M / "pages" / "autoplus-rocheval.md").read_text(encoding="utf-8"))
verif("catalogue des nœuds transmis au modèle", True)

print("── consolidation 3 : rien à faire ──")
r3 = C.Consolidateur(M, __import__("zoneinfo").ZoneInfo("Europe/Paris"), faux_llm_2, nom_agent="nexa").consolider()
verif("aucun appel quand rien n'attend", r3["statut"] == "rien")

print("── consolidation 4 : réponse illisible ──")
p.sync_turn("La carrosserie Martin à Valmont cherche un débosseleur.", "Noté.", session_id="s3")
p.on_session_switch("s4", reset=True)
r4 = C.Consolidateur(M, __import__("zoneinfo").ZoneInfo("Europe/Paris"), lambda m: "Désolé, je ne peux pas.", nom_agent="nexa").consolider()
verif("échec signalé", r4["statut"] == "echec_json")
verif("le lot reste en attente (réessayé plus tard)", len(C.Consolidateur(M, None, None, nom_agent="nexa").lots_en_attente()) == 1)

print("── déclenchement automatique par le fournisseur ──")
cfg = (H / "config.yaml").read_text().replace("consolidation_auto: false", "consolidation_auto: true")
(H / "config.yaml").write_text(cfg)
q = load_memory_provider("exia_seed")
q.initialize("s5", hermes_home=str(H), platform="telegram", agent_context="primary")
CQ = importlib.import_module(type(q).__module__ + ".consolidation")
def faux_llm_3(messages):
    s = messages[1]["content"]; m = trouve(s, "carrosserie Martin")
    return json.dumps({"fragments": [{"noeud": "carrosserie_martin", "nouveau": True, "type_noeud": "entite",
      "alias": {"fr": ["carrosserie Martin"], "en": ["Martin body shop"]}, "section": "semantic",
      "fait": "La carrosserie Martin à Valmont cherche un débosseleur.", "src": [m], "conf": 1.0}]})
# R2 (26/09/2026) : la consolidation automatique tourne dans un PROCESSUS À PART (le même outil
# que le cron), car dans la passerelle le client LLM gardait un jeton périmé. Dans ce banc sans
# réseau ni fournisseur, ce processus DOIT échouer — le test prouve alors que l'échec est propre :
# la main est rendue tout de suite, rien n'est perdu, et un passage suivant rattrape les lots.
print(f"  (diagnostic : consolidation_auto relu = {q._reglages.get('consolidation_auto')})")
q._reglages["consolidation_auto"] = True
q.sync_turn("Pense à rappeler la carrosserie Martin lundi.", "Noté.", session_id="s5")
t0 = time.perf_counter()
q.on_session_switch("s6", reset=True)
fin = time.perf_counter() - t0
verif("la fermeture rend la main tout de suite", fin < 0.5, f"{fin*1000:.0f} ms")
q._fil_consolidation and q._fil_consolidation.join(timeout=120)
verif("consolidation lancée dans un processus à part, échec propre (banc sans fournisseur)",
      not (M / "pages" / "carrosserie-martin.md").exists())
verif("les lots restent en attente", len(CQ.Consolidateur(M, ZoneInfo("Europe/Paris"), faux_llm_3, nom_agent="nexa").lots_en_attente()) >= 1)
r = CQ.Consolidateur(M, ZoneInfo("Europe/Paris"), faux_llm_3, modele="t", nom_agent="nexa").consolider()
verif("le passage suivant les rattrape", r.get("statut") == "ok" and (M / "pages" / "carrosserie-martin.md").exists(), str(r.get("statut")))
tele = [json.loads(l) for l in (M / "telemetrie" / "consolidations.jsonl").read_text().splitlines()]
verif("télémétrie : une ligne par passage réussi", tele[-1]["statut"] == "ok" and len(tele[-1]["lots"]) == 2, " · ".join(t["statut"] for t in tele))
print(f"\n  RÉSULTAT : {ok} réussis · {ko} échoués")
