"""L'oubli sous conditions (docs/18 §3, 07/11/2026) — conteneur jetable, vrai chargeur d'Hermès.

Ce que l'on éprouve : le déclin par section ; chaque condition de non-oubli ; le renfort par l'usage ; le plan ne
touche à rien ; l'application retire les faits, vide la page, écrit le registre des oublis ; la restauration remet."""
import importlib, sys
from datetime import date
from pathlib import Path
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))

from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
base = type(p).__module__
O = importlib.import_module(base + ".oubli")
P = importlib.import_module(base + ".pages")

M = H / "m"; (M / "pages").mkdir(parents=True)
def page(noeud, typ, faits):
    pg = P.Page.nouvelle(M / "pages", noeud, typ, {"fr": [noeud.replace("_", " ")]}, "2026-01-01", "t")
    for section, fait, meta in faits:
        pg.ajouter(section, fait, meta)
    pg.ecrire()
page("garage_dupont", "entite", [
    ("episodic", "Le garage Dupont a appelé pour un devis.", {"dit_le": "2026-01-02T09:00", "src": "raw/a.md:1"}),
    ("semantic", "Le garage Dupont est à Rocheval.", {"dit_le": "2026-01-02T09:00", "src": "raw/a.md:2"}),
    ("semantic", "Le contrat d'entretien du garage Dupont est renouvelé chaque année.", {"dit_le": "2026-01-02T09:00", "event_time": "2026-01-15", "src": "raw/a.md:3"}),
    ("episodic", "Le mariage de Luc a eu lieu.", {"dit_le": "2026-01-02T09:00", "protected": "true", "src": "raw/a.md:4"}),
    ("episodic", "Francis a demandé de retenir le code du portail.", {"dit_le": "2026-01-02T09:00", "src": "raw/a.md:5,registre:x1"}),
    ("episodic", "Le dossier d'assurance a été déposé.", {"dit_le": "2026-01-02T09:00", "concepts": "assurance", "src": "raw/a.md:6"}),
])
page("francis", "entite", [("episodic", "Francis était fatigué ce jour-là.", {"dit_le": "2026-01-02T09:00", "src": "raw/a.md:7"})])
page("ton_des_reponses", "etat_agent", [("procedural", "Répondre court.", {"dit_le": "2026-01-02T09:00", "src": "raw/a.md:8"})])
page("visite_salon", "concept", [("episodic", "Francis a visité le salon de l'auto.", {"dit_le": "2026-01-02T09:00", "src": "raw/a.md:9"})])

print("── 1. le déclin par section ──")
f_ep = {"section": "episodic", "fait": "x", "meta": {"dit_le": "2026-01-02T09:00"}}
f_se = {"section": "semantic", "fait": "x", "meta": {"dit_le": "2026-01-02T09:00"}}
from datetime import timedelta
t_ep = O.TAU["episodic"]
verif(f"épisodique : vivant à τ = {t_ep:.0f} jours, oublié au-delà de 3 τ",
      O.force(f_ep, date(2026, 1, 2) + timedelta(days=t_ep), None) > O.SEUIL > O.force(f_ep, date(2026, 1, 2) + timedelta(days=3.1 * t_ep), None))
verif("sémantique : vivant à 60 jours", O.force(f_se, date(2026, 3, 3), None) > O.SEUIL)
verif("l'usage de la page renforce", O.force(f_ep, date(2026, 1, 2) + timedelta(days=3.1 * t_ep), date(2026, 1, 2) + timedelta(days=3 * t_ep)) > O.SEUIL)
verif("sans date, rien n'est décidé", O.force({"section": "episodic", "fait": "x", "meta": {}}, date(2027, 1, 1), None) == 1.0)

print("── 2. le plan et les conditions ──")
avant = {q.chemin.name: q.chemin.read_text(encoding="utf-8") for q in P.lister(M / "pages")}
r = O.plan(P.lister(M / "pages"), date(2027, 1, 1), {}, implicites=("francis", "nexa"))
oublies = {o["fait"] for o in r["oublies"]}
verif("épisodique ordinaire oublié", "Le garage Dupont a appelé pour un devis." in oublies)
verif("sémantique ancien sans usage oublié", "Le garage Dupont est à Rocheval." in oublies)
verif("date récurrente (contrat annuel) épargnée", r["epargnes_par_condition"].get("date_recurrente") == 1)
verif("fait protégé épargné", r["epargnes_par_condition"].get("protege") == 1)
verif("note « note ça » épargnée", r["epargnes_par_condition"].get("note_demandee") == 1)
verif("concept protégé (assurance) épargné", r["epargnes_par_condition"].get("concept_protege") == 1)
verif("page de l'utilisateur épargnée", r["epargnes_par_condition"].get("page_utilisateur_ou_agent") == 1)
verif("consigne à l'agent épargnée", r["epargnes_par_condition"].get("consigne_agent") == 1)
verif("le plan n'écrit rien", avant == {q.chemin.name: q.chemin.read_text(encoding="utf-8") for q in P.lister(M / "pages")})

print("── 3. appliquer, puis restaurer ──")
a = O.appliquer(M, r)
verif("faits retirés", a["faits_retires"] == len(r["oublies"]), str(a["faits_retires"]))
verif("page vidée retirée", "visite-salon.md" in a["pages_retirees"] and not (M / "pages" / "visite-salon.md").exists())
g = (M / "pages" / "garage-dupont.md").read_text(encoding="utf-8")
verif("les faits épargnés restent", "contrat d'entretien" in g and "mariage de Luc" in g and "dossier d'assurance" in g)
verif("registre des oublis écrit", any((M / "oublis").glob("*.jsonl")))
n = O.restaurer(M, "visite-salon.md")
verif("restauration d'une page entière", n == 1 and "salon de l'auto" in (M / "pages" / "visite-salon.md").read_text(encoding="utf-8"))
n = O.restaurer(M, "garage-dupont.md", "Le garage Dupont est")
verif("restauration d'un seul fait", n == 1 and "à Rocheval" in (M / "pages" / "garage-dupont.md").read_text(encoding="utf-8"))

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
