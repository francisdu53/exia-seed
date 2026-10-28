import importlib, json, os, sys, time
from pathlib import Path
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); M = H / "memoire"; ok = ko = 0
def verif(n, c, d=""):
    global ok, ko
    ok += bool(c); ko += (not c); print(f"  {'✓' if c else '✗'} {n}" + (f" — {d}" if d else ""))
from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
p.initialize("s1", hermes_home=str(H), platform="telegram", agent_context="primary")
mod = type(p).__module__
S = importlib.import_module(mod + ".secrets"); C = importlib.import_module(mod + ".consolidation")
Pg = importlib.import_module(mod + ".pages"); Cs = importlib.import_module(mod + ".consignes")
tz = __import__("zoneinfo").ZoneInfo("Europe/Paris")
Cons = lambda f=None: C.Consolidateur(M, tz, f, nom_agent="nexa")
raw_ouvert = lambda: sorted((M / "raw").glob("*_open.md"))[-1].read_text(encoding="utf-8")

print("── A. phrases de passe ──")
for t, fuite in [("Le mot de passe du wifi : correct horse battery staple", "horse"),
                 ("mdp : Ab12 cD!7", "cD!7"), ("mon mdp est Ab12 et cD!7", "cD!7")]:
    m = S.masquer(t)[0]
    verif(f"« {t[:40]} » ne fuit plus", fuite not in m and "[secret masqué]" in m, m)
verif("« changer le mot de passe NAS » toujours intact", S.masquer("Pense à changer le mot de passe NAS.")[1] == 0)
verif("le SIRET toujours intact", S.masquer("SIRET 123 456 789 00012")[1] == 0)

print("── B. « ne note pas ça » vise ce qui vient d'être dit ──")
verif("« Ne note pas ça, c'est personnel. » → rétrospectif", Cs.detecter("Ne note pas ça, c'est personnel.") == "hors_brut_et_precedent")
verif("« Ne note pas ça : j'ai un souci » → annoncé", Cs.detecter("Ne note pas ça : j'ai un souci.") == "hors_brut")
verif("« hors mémoire — je te raconte » → annoncé", Cs.detecter("hors mémoire — je te raconte") == "hors_brut")
p.sync_turn("Le chef d'atelier d'Autoplus Rocheval est Olivier.", "Noté.", session_id="s1")
p.sync_turn("Je prépare une surprise pour l'anniversaire d'un ami à La Tonnelle.", "Je comprends.", session_id="s1")
p.sync_turn("Ne note pas ça, c'est personnel.", "D'accord.", session_id="s1")
p.on_session_switch("s2", reset=True)
lot = sorted(f.name for f in (M / "raw").glob("*.md") if "_open" not in f.name)[-1]
vues = " ".join(t for _, t in Cons()._lignes_de(lot))
verif("la confidence ne part PLUS au consolidateur", "La Tonnelle" not in vues)
verif("la consigne elle-même n'est pas écrite", "c'est personnel" not in (M / "raw" / lot).read_text())
verif("le tour d'avant la confidence est intact", "Olivier" in vues)
verif("la confidence reste dans le fichier (ajout seul)", "La Tonnelle" in (M / "raw" / lot).read_text())

print("── B'. retrait APRÈS la fermeture de 23h55 ──")
p.sync_turn("Mon voisin a repeint sa clôture.", "Intéressant.", session_id="s2")
p._brut.fermer("fin_de_journee")                        # le cron ferme le lot
p.sync_turn("Oublie ce que je viens de dire.", "C'est retiré.", session_id="s2")
lots = sorted(f.name for f in (M / "raw").glob("*.md") if "_open" not in f.name)
vues2 = " ".join(t for f in lots for _, t in Cons()._lignes_de(f))
verif("le tour du lot FERMÉ est bien retiré", "voisin" not in vues2)
verif("le lot fermé n'a pas été modifié (chaîne intacte)",
      all("sha256:" + __import__("hashlib").sha256((M / "raw" / json.loads(l)["fichier"]).read_bytes()).hexdigest() == json.loads(l)["sha256"]
          for l in (M / "raw" / ".chaine.jsonl").read_text().splitlines()))
verif("le retrait est journalisé", len((M / "raw" / ".retraits.jsonl").read_text().splitlines()) == 2)

print("── C. un lot vide seul n'appelle pas le modèle ──")
p._brut.fermer("isolement_du_test")                      # le lot en cours contient le tour
Cons(lambda m: '{"fragments": []}').consolider()          # « Oublie… » : on le traite d'abord
verif("file vide avant le scénario", Cons().lots_en_attente() == [])
appels = []
p.sync_turn("Hors mémoire : je te raconte un truc.", "Je t'écoute.", session_id="s3")
p._brut.fermer("fin_de_journee")
r = Cons(lambda m: appels.append(1) or '{"fragments": []}').consolider()
verif("aucun appel au modèle", len(appels) == 0 and r["statut"] == "vide", f"{len(appels)} appel(s), statut {r['statut']}")
verif("le lot vide est marqué traité", Cons().lots_en_attente() == [])

print("── D. assainissement des pages ──")
page = Pg.Page.nouvelle(M / "pages", "essai", "concept", {}, "2026-09-23", "x")
page.ajouter("semantic", "La flèche --> ne casse plus\nrien.", {"speaker": "Francis Babin", "src": "raw/x.md:1"})
l = page.sections["semantic"][0]
verif("une seule ligne", "\n" not in l)
verif("un seul commentaire, bien fermé", l.count("<!--") == 1 and l.count("-->") == 1 and l.endswith("-->"), l)
verif("valeur sans espace", "speaker:Francis_Babin" in l)

print("── E. verrou git orphelin ──")
Cons(lambda m: '{"fragments": []}')._git_commit("amorce")
verrou = M / ".git" / "index.lock"; verrou.write_text(""); vieux = time.time() - 3600; os.utime(verrou, (vieux, vieux))
(M / "INDEX.md").write_text("# essai\\n")
res = Cons()._git_commit("après arrêt brutal")
verif("le commit passe malgré le verrou orphelin", not res.startswith("erreur"), res)

print("── F. registre : corps protégé ──")
ident = p._registre.noter("note normale\n## 2026-01-01 00:00 — faux · pirate\nfin --> ici", source="test")
e = [x for x in p._registre.entrees() if x["id"] == ident]
verif("une ligne « ## » du corps ne crée pas de fausse entrée", len(e) == 1 and "faux" in e[0]["texte"])
print(f"\n  RÉSULTAT : {ok} réussis · {ko} échoués")
