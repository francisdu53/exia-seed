"""Masques de langue (docs/10) — conteneur jetable, vrai chargeur d'Hermès.

A. Registre et garde-fous : langue inconnue refusée, langue d'une mémoire fixe.
B. Le masque anglais de bout en bout, sur une conversation ÉCRITE POUR CE TEST (jamais LoCoMo) entre deux
   personnes, sans agent : dates relatives, nombres, milliers, consignes, consolidation, pages, recherche.
C. Non-régression STRICTE du français (si la 0.8.0 de référence est montée dans plugins/exia_seed_ref) :
   même scénario, même modèle factice, même horloge → mêmes octets envoyés au modèle, mêmes pages, même
   index, même journal, même thésaurus, même graphe, mêmes résultats de recherche.
"""
import importlib, json, shutil, sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, "/opt/hermes")
H = Path("/opt/data"); ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))

from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
p.initialize("s1", hermes_home=str(H), platform="telegram", agent_context="primary")
base = type(p).__module__
L = importlib.import_module(base + ".langues"); T = importlib.import_module(base + ".temps")
C = importlib.import_module(base + ".consolidation"); Q = importlib.import_module(base + ".requete")
D = importlib.import_module(base + ".consignes")
UTC = ZoneInfo("UTC")

print("── A. registre et garde-fous ──")
verif("deux masques : en, fr", [m.code for m in L.tous()] == ["en", "fr"])
try:
    L.masque("de"); verif("langue inconnue refusée", False)
except ValueError as e:
    verif("langue inconnue refusée, message clair", "de" in str(e) and "en, fr" in str(e), str(e))
verif("la mémoire de Nexa du test (créée en fr) porte .langue = fr", (H / "memoire" / ".langue").read_text().strip() == "fr")
try:
    L.fixer(H / "memoire", "en"); verif("une mémoire ne change pas de langue", False)
except ValueError as e:
    verif("une mémoire ne change pas de langue (fr → en refusé)", "ne change pas" in str(e), str(e))
vieille = H / "vieille"; (vieille / "pages").mkdir(parents=True); (vieille / "pages" / "x.md").write_text("---\nnode: x\n---\n")
try:
    L.fixer(vieille, "en"); verif("une mémoire SANS .langue mais avec des pages est française", False)
except ValueError:
    verif("une mémoire SANS .langue mais avec des pages est française (en refusé)", True)

print("── B. masque anglais ──")
en = L.masque("en"); ancre = date(2023, 5, 8)                     # un lundi
v = lambda val, cite: T.verifier(val, cite, ancre, en)[0]
verif("« yesterday » → 2023-05-07", v("2023-05-07", "I went to a support group yesterday") == "2023-05-07")
verif("« last Saturday » → 2023-05-06", v("2023-05-06", "I painted a sunset last Saturday") == "2023-05-06")
verif("« on Friday » (récit au passé) → le vendredi précédent", v("2023-05-05", "I went hiking on Friday") == "2023-05-05")
verif("« on Friday » → aussi le prochain (plan)", v("2023-05-12", "we meet on Friday") == "2023-05-12")
verif("« next week » → dans la semaine suivante", v("2023-05-17", "next week I start a course") == "2023-05-17")
verif("« last week » → dans la semaine précédente", v("2023-05-03", "last week I moved") == "2023-05-03")
verif("une date non justifiée est retirée", v("2023-05-01", "I went to a support group yesterday") is None)
verif("« May 20 » / « 20 May »", v("2023-05-20", "the concert is on May 20") == "2023-05-20")
verif("nombres en lettres : « eight » → 8, « twenty-two » → 22", T.nombres_en_lettres("at eight, then twenty-two", en) == {"8", "22"})
verif("heure : « at 4:45 » justifie 16:45 ? non (4 ≠ 16) → date seule", T.verifier("2023-05-09T16:45", "tomorrow at 4:45", ancre, en)[0] == "2023-05-09")
verif("suffixe anglais, sans ambiguïté jour/mois", T.suffixe("Caroline went to a support group", "2023-05-07", m=en) == " (→ Sunday 2023-05-07)")
verif("milliers : « 1,200 » se lit 1200", C._nombres("it costs 1,200 dollars", en) == ["1200"])
verif("consigne : « don't note this: … » → annoncé", D.detecter("don't note this: my salary", en) == D.HORS_BRUT)
verif("consigne : « forget what I just said »", D.detecter("Please forget what I just said", en) == D.RETRAIT_PRECEDENT)
verif("…et le français reste reconnu par son masque", D.detecter("Ne note pas ça : j'ai un souci.", L.masque("fr")) == D.HORS_BRUT)

M = H / "en"; L.fixer(M, "en"); (M / "raw").mkdir(parents=True)
(M / "raw" / "2023-05-08_01.md").write_text("""---
type: raw
date: 2023-05-08
lang: en
ouvert_le: 2023-05-08T13:56:00+00:00
---

## Échanges

[13:56 caroline] I went to a LGBTQ support group yesterday and it was so powerful.
[13:57 melanie] That's great! I painted a sunset last Saturday, it took me 3 hours.
[13:58 caroline] Next week I'm starting a counseling course, it costs 1,200 dollars.
[13:59 melanie] I went hiking on Friday with my kids.
""", encoding="utf-8")
(M / "raw" / ".chaine.jsonl").write_text(json.dumps({"fichier": "2023-05-08_01.md"}) + "\n")
vu = {}
def faux_en(messages):
    if "IDENTITY SUMMARY" in messages[0]["content"] or "FICHE D'IDENTITÉ" in messages[0]["content"]:
        vu["fiches"] = messages[0]["content"]           # second appel (docs/12) : la consigne des fiches
        return '{"fiches": {}}'
    vu["systeme"], vu["user"] = messages[0]["content"], messages[1]["content"]
    R = "raw/2023-05-08_01.md:"
    F = [{"noeud": "caroline", "nouveau": True, "type_noeud": "entite", "alias": {"en": ["Caroline"], "fr": []}, "section": "episodic",
          "fait": "Caroline went to an LGBTQ support group yesterday and found it powerful.", "src": [R + "10"], "conf": 1.0,
          "event_time": "2023-05-07", "concepts": ["support_group"]},
         {"noeud": "melanie", "nouveau": True, "type_noeud": "entite", "alias": {"en": ["Melanie"], "fr": []}, "section": "episodic",
          "fait": "Melanie painted a sunset last Saturday; it took her 3 hours.", "src": [R + "11"], "conf": 1.0,
          "event_time": "2023-05-06", "concepts": ["painting"]},
         {"noeud": "caroline", "section": "prospective", "fait": "Caroline is starting a counseling course next week that costs 1,200 dollars.",
          "src": [R + "12"], "conf": 1.0, "event_time": "2023-05-15", "concepts": ["education"]},
         {"noeud": "melanie", "section": "episodic", "fait": "Melanie went hiking on Friday with her kids.", "src": [R + "13"], "conf": 1.0,
          "event_time": "2023-05-05", "concepts": ["outdoors"]},
         {"noeud": "melanie", "section": "episodic", "fait": "Melanie painted for 5 hours.", "src": [R + "11"], "conf": 1.0}]
    return json.dumps({"fragments": F, "concepts_nouveaux": {
        "support_group": {"en": ["support group", "community", "peer support", "meeting"], "fr": ["groupe de soutien"]},
        "painting": {"en": ["painting", "art", "canvas", "drawing"], "fr": ["peinture"]},
        "education": {"en": ["course", "training", "school", "class"], "fr": ["formation"]},
        "outdoors": {"en": ["hiking", "nature", "trail", "walk"], "fr": ["randonnée"]}}})
c = C.Consolidateur(M, UTC, faux_en, modele="t", nom_agent="", nom_utilisateur="", interlocuteurs=["caroline", "melanie"])
r = c.consolider()
verif("consolidation anglaise réussie, 4 faits, 1 rejet (le « 5 hours » inventé)", r.get("statut") == "ok" and r["faits_retenus"] == 4
      and r["fragments_rejetes"] == 1 and "5" in r["rejets"][0]["raison"], json.dumps({k: r.get(k) for k in ("statut", "faits_retenus", "rejets")}))
verif("télémétrie : langue en/1", r.get("langue") == "en/1")
verif("consigne en anglais, faits « in English »", "in English, without pleasantries" in vu["systeme"] and "en français" not in vu["systeme"])
verif("sans agent : la règle 4 dit que tous sont des personnes ; les interlocuteurs sont nommés",
      "All speakers are people" in vu["systeme"] and "“caroline”, “melanie”" in vu["systeme"])
verif("en-tête du lot en anglais", "conversation of Monday 8 May 2023 (local time, UTC)" in vu["user"])
verif("0.9.1 : mémoire anglaise → consigne des fiches EN ANGLAIS (docs/12)", "IDENTITY SUMMARY" in vu.get("fiches", "")
      and "FICHE" not in vu.get("fiches", "") and "DISTINCTIVE WORDS" in vu.get("fiches", ""), vu.get("fiches", "")[:120])
verif("blocs « EXISTING NODES / EXISTING CONCEPTS / SOURCES »", vu["user"].startswith("EXISTING NODES\n(none)\n\nEXISTING CONCEPTS\n(none)\n\nSOURCES\n"))
car = (M / "pages" / "caroline.md").read_text(encoding="utf-8"); mel = (M / "pages" / "melanie.md").read_text(encoding="utf-8")
verif("« Caroline » accepté : l'interlocuteur est implicite dans ce qu'il dit", "support group yesterday" in car)
verif("date ajoutée en anglais : (→ Sunday 2023-05-07)", "(→ Sunday 2023-05-07)" in car, car[-300:])
verif("« on Friday » au passé daté au vendredi précédent", "(→ Friday 2023-05-05)" in mel, mel[-300:])
verif("intitulés de sections anglais", "## Episodic" in car and "## Prospective" in car and "Épisodique" not in car)
verif("INDEX.md en anglais", (M / "INDEX.md").read_text(encoding="utf-8").startswith("# Memory index"))
th = json.loads((M / "thesaurus.json").read_text(encoding="utf-8"))
verif("thésaurus : l'anglais en premier (≤ 12), le français en second", list(th["concepts"]["painting"]) == ["en", "fr"])
G = importlib.import_module(base + ".graphe")
noeuds = {n["noeud"]: n for n in json.loads((M / "graphe" / "noeuds.json").read_text(encoding="utf-8"))}
verif("graphe : titre = alias anglais", noeuds["caroline"]["titre"] == "Caroline")
verif("graphe : rapport tracé en/1", json.loads((M / "graphe" / "rapport.json").read_text())["langue"] == "en/1")
lec = Q.Lecteur(M, implicites=("caroline", "melanie"))
res = lec.chercher("When did Caroline go to the support group?", 5, datetime(2023, 5, 9), faits_max=6)
tous = [f["fait"] for x in res.get("resultats", []) for f in x["faits"]]
verif("recherche anglaise : la question trouve le fait", any("support group" in t for t in tous), str(tous))
verif("…les mots interrogatifs ne pèsent pas (when, did : mots vides)", not {"when", "did"} & set(res.get("mots_inconnus", [])), str(res.get("mots_inconnus")))
res = lec.chercher("art", 5, datetime(2023, 5, 9))
verif("champ lexical anglais : « art » trouve la peinture (concept painting)", any("sunset" in f["fait"] for x in res.get("resultats", []) for f in x["faits"]))
verif("message sans résultat en anglais", lec.chercher("weather in Brest", 5, datetime(2023, 5, 9)).get("message", "").startswith("Nothing related"))

print("── C. non-régression stricte du français (version de référence montée par REF : 0.8.0, puis 0.8.1 depuis le 16/10) ──")
REF = H / "plugins" / "exia_seed_ref"
if not REF.exists():
    print("  (référence absente : partie C sautée)")
else:
    sys.path.insert(0, str(H / "plugins"))
    def scenario(paquet, dossier):
        Cx = importlib.import_module(paquet + ".consolidation"); Qx = importlib.import_module(paquet + ".requete")
        U = importlib.import_module(paquet + ".util")
        fige = datetime(2026, 9, 28, 23, 55, 0, tzinfo=ZoneInfo("Europe/Paris"))
        Cx.maintenant = lambda tz=None: fige                       # même horloge pour les deux
        Mx = H / dossier; (Mx / "raw").mkdir(parents=True)
        (Mx / "raw" / "2026-09-28_01.md").write_text("""---
type: raw
date: 2026-09-28
lang: fr
ouvert_le: 2026-09-28T09:00:00+02:00
---

## Échanges

[09:00 francis] J'ai rendez-vous chez le garagiste Martin lundi à huit heures.
[09:01 nexa] C'est noté pour lundi.
[09:02 francis] Le devis d'Autoplus Valmont s'élève à 12345€, la facture 42 est partie hier.
[09:03 francis] Pour l’encadré de l’application personnelle, mets le titre en vert.
""", encoding="utf-8")
        (Mx / "raw" / ".chaine.jsonl").write_text(json.dumps({"fichier": "2026-09-28_01.md"}) + "\n")
        envoye = {}
        def faux(messages):
            envoye["m"] = json.dumps(messages, ensure_ascii=False)
            R = "raw/2026-09-28_01.md:"
            return json.dumps({"fragments": [
                {"noeud": "francis", "nouveau": True, "type_noeud": "entite", "alias": {"fr": ["Francis"], "en": []}, "section": "prospective",
                 "fait": "Rendez-vous chez le garagiste Martin lundi à 8 h.", "src": [R + "10"], "conf": 1.0, "event_time": "2026-10-05T08:00", "concepts": ["entretien"]},
                {"noeud": "autoplus_valmont", "nouveau": True, "type_noeud": "entite", "alias": {"fr": ["Autoplus Valmont"], "en": []}, "section": "semantic",
                 "fait": "Le devis d'Autoplus Valmont s'élève à 12 345 € ; la facture 42 est partie hier.", "src": [R + "12"], "conf": 1.0, "event_time": "2026-09-27", "concepts": ["facturation"]},
                {"noeud": "application_personnelle", "nouveau": True, "type_noeud": "concept", "alias": {"fr": ["application personnelle"], "en": []},
                 "section": "procedural", "fait": "Dans l’encadré de l’application personnelle, le titre est en vert.", "src": [R + "13"], "conf": 1.0, "concepts": ["mise_en_page"]},
                {"noeud": "francis", "section": "semantic", "fait": "Francis a 99 timbres de collection.", "src": [R + "10"], "conf": 1.0}],
                "concepts_nouveaux": {"entretien": {"fr": ["entretien", "mécanicien", "garagiste"], "en": ["maintenance"]},
                                      "facturation": {"fr": ["facture", "montant"], "en": ["invoice"]},
                                      "mise_en_page": {"fr": ["mise en page", "encadré", "couleur"], "en": ["layout"]}}}, ensure_ascii=False)
        rap = Cx.Consolidateur(Mx, ZoneInfo("Europe/Paris"), faux, modele="t", nom_agent="nexa", nom_utilisateur="francis").consolider()
        fichiers = {f: (Mx / f).read_bytes() for f in ["INDEX.md", "log.md", "thesaurus.json", "graphe/noeuds.json", "graphe/aretes.json"]
                    + [f"pages/{x.name}" for x in sorted((Mx / "pages").glob("*.md"))]}
        lec = Qx.Lecteur(Mx, implicites=("francis", "nexa"))
        recherches = {q: json.dumps({k: v for k, v in lec.chercher(q, 5, datetime(2026, 9, 29, 10, 0)).items() if k != "tokens"}, ensure_ascii=False, sort_keys=True)
                      for q in ("mécanicien lundi", "facture Autoplus", "encadré solde", "météo Brest", "application")}
        lu = json.dumps(lec.lire("Autoplus Valmont", datetime(2026, 9, 29, 10, 0)), ensure_ascii=False, sort_keys=True)
        return envoye["m"], fichiers, recherches, lu, {k: rap.get(k) for k in ("statut", "faits_retenus", "rejets", "dates_retirees")}
    ref = scenario("exia_seed_ref", "ref"); new = scenario(base, "nouveau")
    verif("consigne de consolidation envoyée au modèle : identique AU CARACTÈRE PRÈS", ref[0] == new[0],
          next((f"écart au caractère {i}: {ref[0][i-40:i+40]!r} / {new[0][i-40:i+40]!r}" for i in range(min(len(ref[0]), len(new[0]))) if ref[0][i] != new[0][i]), f"longueurs {len(ref[0])}/{len(new[0])}"))
    verif("même bilan (faits, rejets, dates retirées)", ref[4] == new[4], f"{ref[4]} / {new[4]}")
    for f in ref[1]:
        verif(f"fichier identique : {f}", ref[1][f] == new[1].get(f))
    verif("mêmes pages, ni plus ni moins", set(ref[1]) == set(new[1]))
    for q in ref[2]:
        verif(f"recherche identique : « {q} »", ref[2][q] == new[2][q])
    verif("lecture d'une page identique (memoire_lire)", ref[3] == new[3])
    verif("schémas d'outils identiques (Francis, exemples)", json.dumps(importlib.import_module("exia_seed_ref")._SCHEMA_NOTER, ensure_ascii=False)
          == json.dumps(p.get_tool_schemas()[0], ensure_ascii=False))
    try:                                                   # référence 0.8.1 (docs/12) : fiches et souvenirs
        ref_fiches = importlib.import_module("exia_seed_ref.fiches"); ref_rappel = importlib.import_module("exia_seed_ref.rappel")
    except ImportError:
        ref_fiches = None
    if ref_fiches is not None:
        fr = importlib.import_module(base + ".langues").masque("fr")
        verif("consigne des fiches identique AU CARACTÈRE PRÈS (0.8.1 → masque fr)", ref_fiches.PROMPT == fr.consigne_fiches(),
              f"longueurs {len(ref_fiches.PROMPT)}/{len(fr.consigne_fiches())}")
        verif("en-tête des souvenirs identique (0.8.1 → masque fr)", ref_rappel._ENTETE_SOUVENIRS == fr.textes["souvenirs_entete"])

print("── D. garde : aucun mot de langue dans le code central ──")
import ast, re
SUSPECTS = re.compile(r"\b(lundi|mardi|demain|hier|semaine|janvier|février|utilisateur|assistante|mémoire pas|Rien de lié|"
                      r"Noté\.|Ce qu'on sait|Index de la mémoire|dit le|heure de Paris|conversation du|en français|"
                      r"yesterday|tomorrow)\b", re.I)
# Sensibles à la casse : les intitulés (« Sémantique », « Semantic ») — pas la clé interne « semantic » ;
# « NŒUDS » du message au modèle — pas « nœuds » des messages à l'opérateur.
SUSPECTS_CASSE = re.compile(r"\b(Sémantique|Épisodique|Semantic|Episodic|NŒUDS|Monday)\b")
# Exceptions déclarées (docs/10 §4) : messages pour l'opérateur (journal technique, commits git, alertes du graphe)
# et l'outil de rattrapage des concepts, qui ne sert qu'aux mémoires françaises antérieures à la 0.7.
EXCEPTIONS = {"outils/concepts.py"}
racine_plugin = Path(importlib.import_module(base).__file__).parent
trouves = []
for f in sorted(racine_plugin.glob("*.py")) + sorted((racine_plugin / "outils").glob("*.py")):
    rel = str(f.relative_to(racine_plugin))
    if rel in EXCEPTIONS:
        continue
    arbre = ast.parse(f.read_text(encoding="utf-8")); docs = set()
    for n in ast.walk(arbre):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and n.body and isinstance(n.body[0], ast.Expr) \
                and isinstance(getattr(n.body[0], "value", None), ast.Constant):
            docs.add(id(n.body[0].value))
    trouves += [f"{rel}:{n.lineno} {n.value[:50]!r}" for n in ast.walk(arbre)
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs and (SUSPECTS.search(n.value) or SUSPECTS_CASSE.search(n.value))]
verif("aucune donnée linguistique hors des masques (hors commentaires et exceptions déclarées)", not trouves, "; ".join(trouves))

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
