"""Fiches d'identité (docs/12) — une phrase par sujet : ce que c'est, à quoi ça sert, où le trouver.
Conteneur jetable, sans réseau, vrai chargeur d'Hermès ; faux modèle, vrai contrôle."""
import importlib, json, sys
from pathlib import Path
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); M = H / "memoire"; ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))

from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
p.initialize("s1", hermes_home=str(H), platform="telegram", agent_context="primary")
base = type(p).__module__
F = importlib.import_module(base + ".fiches")
P = importlib.import_module(base + ".pages")
C = importlib.import_module(base + ".consolidation")
G = importlib.import_module(base + ".graphe")
R = importlib.import_module(base + ".rappel")

M.mkdir(parents=True, exist_ok=True)
(M / "pages").mkdir(exist_ok=True)
COURSES = """---
node: application_liste_courses
node_type: concept
aliases:
  fr:
  - application de liste de courses
  en:
  - shopping list application
created: '2026-09-25'
updated: '2026-10-15'
strength: 1.0
---

# application de liste de courses

## Sémantique
- Le bouton « Gérer les zones » permet de créer et déplacer les zones ; les changements sont partagés avec Claire. Les accès et la procédure API sont documentés dans workspace/courses-app/README.md. <!-- conf:1.0 src:raw/2026-10-15_01.md:3 dit_le:2026-10-15T16:50 speaker:francis -->

## Procédural
- Le circuit de courses suit l’ordre Gâteaux → Céréales → Café → Confiserie → Boissons. <!-- conf:1.0 src:raw/2026-10-10_01.md:5 dit_le:2026-10-10T09:00 speaker:francis -->
- Les demandes de préparation de courses doivent être appliquées à l’application partagée avec Claire. <!-- conf:1.0 src:raw/2026-10-15_01.md:9 dit_le:2026-10-15T17:00 speaker:francis -->
"""
(M / "pages" / "application-liste-courses.md").write_text(COURSES, encoding="utf-8")
page = P.Page.charger(M / "pages" / "application-liste-courses.md")
BONNE = ("Application de liste de courses partagée avec Claire, classée par zones du magasin ; "
         "l’assistant y ajoute les courses demandées (accès et API : workspace/courses-app/README.md).")

print("── 1. le contrôle : rien que la page n'ait déjà ──")
verif("fiche fidèle acceptée", F.controler(BONNE, page)[0], F.controler(BONNE, page)[1])
verif("nom propre inventé refusé (Leclerc)", not F.controler("Application de courses du Leclerc partagée avec Claire.", page)[0])
verif("nombre inventé refusé", not F.controler("Application de courses partagée avec 3 personnes.", page)[0])
verif("chemin inventé refusé", not F.controler("Application de courses (voir workspace/courses/app.py).", page)[0])
verif("trop longue refusée", not F.controler("Application de courses. " * 20, page)[0])
verif("vide refusée", not F.controler("  ", page)[0])
verif("un nom à tirets présent dans la page est accepté (« App-Readme » ← courses-app/README.md, cas LIEN-PRIVE-RECETTES)",
      F.controler("Application de courses ; voir App-Readme.", page)[0], F.controler("Application de courses ; voir App-Readme.", page)[1])
verif("l'utilisateur, implicite, est accepté (Francis)", F.controler("Application de courses de Francis, partagée avec Claire.", page, ("francis", "nexa"))[0])
verif("…mais pas sans être déclaré", not F.controler("Application de courses de Francis, partagée avec Claire.", page)[0])
verif("un nom lu dans un mot de la page est accepté (API → « procédure API »)", F.controler("Application de courses, avec une API.", page)[0])

print("── 2. rédiger : posée dans l'en-tête, lisible en tête de page ──")
vu = []
def faux(messages):
    vu.append(messages)
    return json.dumps({"fiches": {"application_liste_courses": BONNE}}, ensure_ascii=False)
verif("la page sans fiche est à rafraîchir", [x.entete["node"] for x in F.a_rafraichir([page])] == ["application_liste_courses"])
essai = F.rediger([page], faux, "2026-10-16", ecrire=False)
verif("essai à blanc : proposée, rien d'écrit", essai["proposees"].get("application_liste_courses") == BONNE
      and "summary" not in (M / "pages" / "application-liste-courses.md").read_text(encoding="utf-8"))
r = F.rediger([page], faux, "2026-10-16")
texte = (M / "pages" / "application-liste-courses.md").read_text(encoding="utf-8")
entete = texte.split("\n---\n")[0]
verif("écrite", r["ecrites"] == ["application_liste_courses"], str(r))
verif("summary juste après les alias, avec sa date", entete.index("summary:") > entete.index("aliases:")
      and entete.index("summary:") < entete.index("created:") and "summary_date: '2026-10-16'" in entete, entete)
verif("lisible en tête de page (> …)", "\n> " + BONNE in texte)
relue = P.Page.charger(M / "pages" / "application-liste-courses.md")
verif("la page se relit intacte (mêmes faits)", relue.nb_fragments() == page.nb_fragments() and relue.entete.get("summary") == BONNE)
verif("plus rien à rafraîchir", F.a_rafraichir([relue]) == [])
verif("le modèle a reçu les faits, le durable d'abord", "[semantic]" in vu[-1][1]["content"]
      and vu[-1][1]["content"].index("[semantic]") < vu[-1][1]["content"].index("[procedural]"))

print("── 3. refus, panne : l'ancienne fiche reste ──")
r2 = F.rediger([relue], lambda m: json.dumps({"fiches": {"application_liste_courses": "Application de courses du Leclerc."}}), "2026-10-17")
verif("fiche inventée refusée, raison donnée", r2["refusees"] and "Leclerc" in r2["refusees"][0][1], str(r2["refusees"]))
verif("…l'ancienne reste", P.Page.charger(M / "pages" / "application-liste-courses.md").entete.get("summary") == BONNE)
def panne(m): raise RuntimeError("panne simulée")
r3 = F.rediger([relue], panne, "2026-10-17")
verif("panne du modèle → partiel, pas d'exception", r3["statut"] == "partiel" and not r3["ecrites"])
verif("JSON illisible → absente, rien d'écrit", F.rediger([relue], lambda m: "pas du json", "2026-10-17")["absentes"] == ["application_liste_courses"])
vu.clear(); F.rediger([relue], faux, "2026-10-17", ecrire=False)
verif("la fiche actuelle est montrée au modèle (stabilité)", "Fiche actuelle : " + BONNE in vu[-1][1]["content"])

print("── 4. le rappel la fait remonter, le sujet d'abord ──")
G.calculer(M, implicites=("francis", "nexa"))
rp = R.Rappeleur(M, implicites=("francis", "nexa"))
res = rp.rappeler("on va préparer la liste de courses : tomates, pâtes", mode="complet")
s = R.souvenirs(rp.memoire(), res, 0.3, 3, 2)
lignes = s["bloc"].splitlines()
i = next((k for k, l in enumerate(lignes) if l.startswith("• application de liste de courses")), -1)
verif("la fiche suit le titre du sujet", i >= 0 and lignes[i + 1].strip() == BONNE, "\n".join(lignes[:5]))
Q = importlib.import_module(base + ".requete")
lu = Q.Lecteur(M, implicites=("francis", "nexa"), rappeleur=rp).lire("application de liste de courses")
verif("memoire_lire rend la fiche", lu.get("fiche") == BONNE, str(lu)[:200])

print("── 5. la consolidation écrit la fiche des pages qu'elle touche ──")
brut = M / "raw"; brut.mkdir(parents=True, exist_ok=True)
(brut / "2026-10-16_01.md").write_text("""---
type: raw
date: 2026-10-16
session_id: s1
lang: fr
ouvert_le: 2026-10-16T09:00:00+02:00
---

## Échanges

[09:00 francis] Le garage Dupont à Rocheval me paie toujours à trente jours.
""", encoding="utf-8")
(brut / ".chaine.jsonl").write_text(json.dumps({"fichier": "2026-10-16_01.md"}) + "\n", encoding="utf-8")
appels = []
def faux_conso(messages):
    appels.append(messages[0]["content"][:40])
    if "FICHE D'IDENTITÉ" in messages[0]["content"]:
        return json.dumps({"fiches": {"garage_dupont": "Garage Dupont à Rocheval, client de l’utilisateur, payé à trente jours."}}, ensure_ascii=False)
    return json.dumps({"fragments": [{"noeud": "garage_dupont", "nouveau": True, "type_noeud": "entite",
                                      "alias": {"fr": ["garage Dupont"], "en": ["Dupont garage"]}, "section": "semantic",
                                      "fait": "Le garage Dupont à Rocheval paie à trente jours.", "src": ["raw/2026-10-16_01.md:11"],
                                      "conf": 1.0, "event_time": None, "echeance": None, "speaker": "francis"}]}, ensure_ascii=False)
c = C.Consolidateur(M, __import__("zoneinfo").ZoneInfo("Europe/Paris"), faux_conso, modele="test", nom_agent="nexa", nom_utilisateur="francis")
rc = c.consolider()
verif("passage réussi, deux appels (consolidation puis fiches)", rc.get("statut") == "ok" and len(appels) == 2, f"{rc.get('statut')} · {len(appels)}")
dupont = (M / "pages" / "garage-dupont.md").read_text(encoding="utf-8")
verif("la page créée a sa fiche", "summary: Garage Dupont à Rocheval" in dupont, dupont[:300])
verif("le rapport de consolidation compte les fiches", (rc.get("fiches") or {}).get("ecrites") == ["garage_dupont"], str(rc.get("fiches")))
index = (M / "INDEX.md").read_text(encoding="utf-8")
verif("INDEX.md montre la fiche (le résumé d'une ligne de Karpathy)", "Garage Dupont à Rocheval, client" in index)
ligne_courses = next(l for l in index.splitlines() if "application_liste_courses" in l)
verif("…tronquée à ~110 caractères dans l'index (économie), entière dans la page", "…" in ligne_courses and len(ligne_courses) < len(BONNE) + 120, ligne_courses)
c2 = C.Consolidateur(M, __import__("zoneinfo").ZoneInfo("Europe/Paris"), faux_conso, modele="test", nom_agent="nexa",
                     nom_utilisateur="francis", fiches=False)
verif("fiches=False est transmis au consolidateur (réglage `fiches` de config.yaml)", c2.fiches is False)


print("── 6. mots distinctifs (docs/12 §9) : écrits avec la fiche, seuls à allumer un sujet par un mot ──")
PLATEFORME = """---
node: plateforme_donnees_meteo
node_type: concept
aliases:
  fr:
  - plateforme de données météo
  - place de marché de données
  en:
  - data exchange platform
created: '2026-09-28'
updated: '2026-09-28'
strength: 1.0
---

# plateforme de données météo

## Sémantique
- Francis envisage une plateforme de vente de données météo locales. <!-- conf:1.0 src:raw/2026-09-28_01.md:3 dit_le:2026-09-28T09:00 speaker:francis -->
"""
VALMONT = """---
node: autoplus_valmont
node_type: entite
aliases:
  fr:
  - Autoplus Valmont
  en: []
created: '2026-09-20'
updated: '2026-09-20'
strength: 1.0
---

# Autoplus Valmont

## Sémantique
- Autoplus Valmont paie ses factures à trente jours. <!-- conf:1.0 src:raw/2026-09-20_01.md:3 dit_le:2026-09-20T09:00 speaker:francis -->
"""
(M / "pages" / "plateforme-donnees-meteo.md").write_text(PLATEFORME, encoding="utf-8")
(M / "pages" / "autoplus-valmont.md").write_text(VALMONT, encoding="utf-8")
pl = P.Page.charger(M / "pages" / "plateforme-donnees-meteo.md"); ma = P.Page.charger(M / "pages" / "autoplus-valmont.md")
verif("mot des alias gardé, mot inventé écarté", F.mots_valides(["Valmont", "garage", "Valmont"], ma) == ["valmont"])
vu.clear()
def faux_mots(messages):
    vu.append(messages)
    return json.dumps({"fiches": {"plateforme_donnees_meteo": {"fiche": "Idée de plateforme de vente de données météo locales.", "mots": []},
                                  "autoplus_valmont": {"fiche": "Autoplus Valmont, client qui paie ses factures à trente jours.", "mots": ["Valmont"]}}}, ensure_ascii=False)
r6 = F.rediger([pl, ma], faux_mots, "2026-10-16")
verif("le modèle reçoit la consigne des mots distinctifs", "MOTS DISTINCTIFS" in vu[-1][0]["content"])
verif("mots posés dans l'en-tête (liste vide comprise)", P.Page.charger(M / "pages" / "plateforme-donnees-meteo.md").entete.get("keywords") == []
      and P.Page.charger(M / "pages" / "autoplus-valmont.md").entete.get("keywords") == ["valmont"], str(r6["mots"]))
verif("les mots actuels sont montrés au modèle (stabilité)", (F.rediger([P.Page.charger(M / "pages" / "autoplus-valmont.md")], faux_mots, "2026-10-17", ecrire=False)
      and "Mots actuels : valmont" in vu[-1][1]["content"]))
verif("l'ancienne forme {nœud: phrase} reste lue (mots inchangés)",
      F._extraire('{"fiches": {"x": "Une phrase."}}') == {"x": ("Une phrase.", None)})
G.calculer(M, implicites=("francis", "nexa"))
rp2 = R.Rappeleur(M, implicites=("francis", "nexa")); m2 = rp2.memoire()
verif("« données » est un mot COURANT pour la plateforme (mots distinctifs = [])", ("donnees", "plateforme_donnees_meteo") in m2.mots_courants)
verif("« Valmont » est distinctif pour Autoplus Valmont", "autoplus_valmont" in m2.mots_alias.get("valmont", set())
      and ("valmont", "autoplus_valmont") not in m2.mots_courants)
verif("…le nom complet reste un alias (« plateforme de données météo »)", any("plateforme_donnees_meteo" in v for k, v in m2.alias.items() if "plateforme" in k))
verif("page SANS mots distinctifs : ses mots d'alias comme avant (« courses », pas courant)",
      "application_liste_courses" in m2.mots_alias.get("courses", set()) and ("courses", "application_liste_courses") not in m2.mots_courants)
a1 = rp2.activer(m2, "Je regarde les données de mon club")["entrees"].get("plateforme_donnees_meteo", 0)
a2 = rp2.activer(m2, "La facture de Valmont est payée ?")["entrees"].get("autoplus_valmont", 0)
verif("mot courant : le sujet s'allume à moitié (poids continu, pas d'exclusion)", 0 < a1 <= R.ACT_MOT * R.POIDS_MOT_COMMUN + 1e-9, f"{a1:.3f}")
verif("mot distinctif : pleinement", abs(a2 - R.ACT_MOT) < 1e-9, f"{a2:.3f}")
R.POIDS_MOT_COMMUN = 1.0
verif("POIDS_MOT_COMMUN = 1 : exactement le comportement d'avant", abs(rp2.activer(m2, "Je regarde les données de mon club")["entrees"].get("plateforme_donnees_meteo", 0) - R.ACT_MOT) < 1e-9)
R.POIDS_MOT_COMMUN = 0.5


print("── 7. règles de conduite et mots distinctifs courts ──")
REGLE = """---
node: controle_documents_assistant
node_type: etat_agent
aliases:
  fr:
  - contrôle des documents avant envoi
  en: []
keywords: []
created: '2026-10-01'
updated: '2026-10-01'
strength: 1.0
---

# contrôle des documents avant envoi

## Procédural
- Vérifier systématiquement les documents avant envoi. <!-- conf:1.0 src:raw/2026-10-01_01.md:3 dit_le:2026-10-01T09:00 speaker:francis -->
"""
SEED = """---
node: systeme_memoire_agents
node_type: concept
aliases:
  fr:
  - système de mémoire EXIA SEED
  en: []
keywords:
- exia
- seed
created: '2026-10-01'
updated: '2026-10-01'
strength: 1.0
---

# système de mémoire EXIA SEED

## Sémantique
- Francis a créé un système de mémoire pour agents. <!-- conf:1.0 src:raw/2026-10-01_01.md:5 dit_le:2026-10-01T09:00 speaker:francis -->
"""
(M / "pages" / "controle-documents-assistant.md").write_text(REGLE, encoding="utf-8")
(M / "pages" / "systeme-memoire-agents.md").write_text(SEED, encoding="utf-8")
G.calculer(M, implicites=("francis", "nexa"))
rp3 = R.Rappeleur(M, implicites=("francis", "nexa")); m3 = rp3.memoire()
verif("une règle de conduite (etat_agent) garde ses mots d'alias pleins, même avec keywords: []",
      "controle_documents_assistant" in m3.mots_alias.get("documents", set()) and ("documents", "controle_documents_assistant") not in m3.mots_courants)
verif("mot distinctif de 4 lettres : « seed » allume le système de mémoire",
      "systeme_memoire_agents" in rp3.activer(m3, "Parle-moi de seed ce matin")["entrees"])
verif("…en correspondance exacte seulement (« seedx » ne s'en rapproche pas)",
      "systeme_memoire_agents" not in rp3.activer(m3, "regarde seedx ce matin")["entrees"])


print("── 8. amorçage (docs/12 §10) : le tour précédent, affaibli, cumulé par cab_pull ──")
am = {"autoplus_valmont": 0.6}
seul = rp3.rappeler("D'accord, on continue demain matin.", amorce=am)
verif("l'amorce SEULE ne ressert pas le sujet (sans écho dans le message)",
      not any(f["page"] == "autoplus-valmont.md" for f in seul.get("faits", [])), str(seul.get("faits"))[:200])
e0 = rp3.activer(m3, "les factures à trente jours")["entrees"].get("autoplus_valmont", 0)
e1 = rp3.activer(m3, "les factures à trente jours", amorce=am)["entrees"].get("autoplus_valmont", 0)
verif("indice du message + amorce = plus fort que chacun (a + b(1 − a))", e1 > max(e0, R.AMORCE * 0.6) - 1e-9 and e1 <= 1.0, f"{e0:.3f} → {e1:.3f}")
verif("l'amorce ne touche ni l'utilisateur ni un sujet inconnu",
      "francis" not in rp3.activer(m3, "bonjour", amorce={"francis": 1.0, "inconnu": 1.0})["entrees"])
from datetime import datetime, timedelta
t0 = datetime(2026, 10, 16, 9, 0)
p._garder_amorce(t0, {"statut": "ok", "entrees": {"autoplus_valmont": 0.6}})
verif("le fournisseur garde l'amorce du message précédent", p._amorce_du(t0 + timedelta(minutes=10)) == {"autoplus_valmont": 0.6})
verif("…et l'oublie après 30 minutes", p._amorce_du(t0 + timedelta(minutes=31)) is None)
p._reglages["amorce_minutes"] = 0
verif("amorce_minutes = 0 : coupé", p._amorce_du(t0 + timedelta(minutes=1)) is None)
p._reglages["amorce_minutes"] = 30

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
