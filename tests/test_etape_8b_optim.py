"""Étape 8b — optimisation de memoire_chercher du 29/09 (docs/08 §12) : apostrophe typographique,
spécificité des concepts, pistes depuis les faits trouvés. Conteneur jetable, vrai chargeur d'Hermès."""
import importlib, json, sys
from datetime import datetime
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
G = importlib.import_module(base + ".graphe"); Q = importlib.import_module(base + ".requete")
T = datetime(2026, 9, 30, 10, 0)

PAGES = []
def page(noeud, titre, faits):
    (M / "pages").mkdir(parents=True, exist_ok=True)
    PAGES.append(noeud)                       # un brut par page : pas de « vécu ensemble » entre les pages du jeu d'essai
    lignes = [f"- {t} <!-- conf:1.0 src:raw/2026-09-29_{len(PAGES):02d}.md:{10 * k + 1} dit_le:2026-09-29T09:{k:02d} speaker:francis concepts:{c} -->"
              for k, (t, c) in enumerate(faits)]
    (M / "pages" / (noeud.replace("_", "-") + ".md")).write_text(
        f"---\nnode: {noeud}\nnode_type: entite\naliases:\n  fr:\n  - {titre}\n  en: []\n---\n\n# {titre}\n\n## Sémantique\n" + "\n".join(lignes) + "\n",
        encoding="utf-8")

page("francis", "Francis", [("Francis a rendez-vous chez le garagiste Martin mardi.", "entretien"),
                            ("Francis joue au tennis le samedi au club.", "loisirs"),
                            ("Son vélo de route est rangé dans l'abri.", "loisirs")])
page("hugo", "Hugo", [("Hugo a rendez-vous chez la carrossière Sophie jeudi.", "entretien")])
page("application_personnelle", "application personnelle", [("Renommer l’encadré « garder le cap » en « Objectif ».", "mise_en_page")])
page("autoplus_valmont", "Autoplus Valmont", [(f"Facture {n} d'Autoplus Valmont : présentation sur une page A4.", "facturation,mise_en_page") for n in range(40, 48)])
(M / "thesaurus.json").write_text(json.dumps({"concepts": {
    "entretien": {"fr": ["entretien", "mécanicien", "garagiste", "carrossier"], "en": ["maintenance"]},
    "loisirs": {"fr": ["loisirs", "sport", "tennis", "vélo"], "en": ["leisure"]},
    "mise_en_page": {"fr": ["mise en page", "encadré", "présentation", "cadre"], "en": ["layout"]},
    "facturation": {"fr": ["facture", "facturation", "montant"], "en": ["invoice"]}}, "faits": {}}, ensure_ascii=False), encoding="utf-8")
G.calculer(M, implicites=("francis", "nexa"))
L = Q.Lecteur(M, implicites=("francis", "nexa"))
m = L.r.memoire()

print("── 1. l'apostrophe typographique sépare les mots ──")
verif("« l’encadré » → « l encadre »", G._norm("Renommer l’encadré") == " renommer l encadre ", repr(G._norm("Renommer l’encadré")))
verif("« d’Amandine » → « d amandine »", " amandine " in G._norm("le rendez-vous d’Amandine"))
verif("ligatures : « cœur » → « coeur »", G._norm("cœur") == " coeur ")
verif("les accents restent retirés : « Ménard » = « menard »", G._norm("Ménard") == G._norm("menard"))

print("── 2. spécificité des concepts ──")
sp = m.specificite
verif("un concept porté par 8 faits est moins spécifique qu'un concept porté par 1", sp["facturation"] < sp["loisirs"] < 1.0 and sp["mise_en_page"] < 1.0, str({k: round(v, 2) for k, v in sp.items()}))
r = L.chercher("encadré", 5, T, faits_max=4)
premier = r["resultats"][0]["faits"][0]["fait"] if r.get("resultats") else ""
verif("« encadré » : le fait qui CONTIENT le mot passe devant les 8 factures qui l'ont seulement dans le champ de leur concept",
      "garder le cap" in premier, premier)

print("── 3. pistes depuis les faits trouvés ──")
r = L.chercher("mécanicien", 5, T)
tous = [f["fait"] for x in r.get("resultats", []) for f in x["faits"]] + [f["fait"] for f in (r.get("pistes") or {}).get("faits", [])]
verif("« mécanicien » trouve le garagiste (champ de `entretien`)", any("garagiste" in t for t in tous), str(tous))
verif("…et le rendez-vous de Hugo, par le même concept", any("Hugo" in t for t in tous), str(tous))
verif("…mais pas les loisirs de la fiche de l'utilisateur (défaut 0.7.0, docs/08 §10.5)", not any("tennis" in t or "vélo" in t for t in tous), str(tous))
verif("…ni les factures, sans rapport", not any("Facture" in t for t in tous), str(tous))
verif("rien de lié → silence", L.chercher("météo Brest", 5, T)["resultats"] == [])
r = L.chercher("entretien facture loisirs encadré", 9, T, faits_max=4)
verif("budget : faits_max respecté (4)", sum(len(x["faits"]) for x in r["resultats"]) + len((r.get("pistes") or {}).get("faits", [])) <= 4)

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
