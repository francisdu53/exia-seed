"""R2 — le temps des faits (26/09/2026). Conteneur jetable, sans réseau, vrai chargeur d'Hermès.

Cas réels de la première semaine : « lundi 16h45 chez Amandine » dit un mercredi (23/09),
« demain 17h » pour Sophie, « toute la journée » devenu « de 8 h à 18 h » (25/09)."""
import importlib, json, re, sys
from datetime import date
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
T = importlib.import_module(type(p).__module__ + ".temps")
C = importlib.import_module(type(p).__module__ + ".consolidation")

print("── 1. le calcul, sans modèle ──")
mer = date(2026, 9, 23)                                  # un mercredi
lun = date(2026, 9, 28)                                  # un lundi
verif("en clair : mercredi 23 septembre 2026", T.en_clair(mer) == "mercredi 23 septembre 2026")
verif("« lundi » dit un mercredi → 28/09", T.prochain(mer, 0) == lun)
verif("« lundi » dit un lundi → 7 jours plus tard (règle de Francis)", T.prochain(lun, 0) == date(2026, 10, 5))
verif("« mardi » dit un lundi → le lendemain", T.prochain(lun, 1) == date(2026, 9, 29))
verif("dit_le : lot du 23, ligne [12:20 …]", T.dit_le(mer, "10:01", "[12:20 francis] rdv lundi") == "2026-09-23T12:20")
verif("dit_le : ligne après minuit → lendemain", T.dit_le(mer, "23:58", "[00:05 francis] …") == "2026-09-24T00:05")

cite_a = "[12:20 francis] tu vas me mettre un rendez-vous pour lundi 16h45 chez Amandine"
verif("Amandine : 2026-09-28T16:45 vérifié", T.verifier("2026-09-28T16:45", cite_a, mer) == ("2026-09-28T16:45", None))
v, r = T.verifier("2026-09-29T16:45", cite_a, mer)
verif("Amandine : mauvais lundi (29) retiré", v is None and "non justifiée" in r, r)
cite_l = "[19:40 francis] rappelle-moi d'appeler Sophie demain à 17h"
verif("Sophie : « demain 17h » → 24/09 17:00", T.verifier("2026-09-24T17:00", cite_l, mer)[0] == "2026-09-24T17:00")
cite_d = "[18:02 francis] le vendredi 2 octobre 2026, toute la journée, OPEL JOGGER chez Autoplus Valmont"
v, r = T.verifier("2026-10-02T08:00", cite_d, date(2026, 9, 25))
verif("Opel : heure inventée (8 h) retirée, date gardée", v == "2026-10-02" and "heure" in (r or ""), f"{v} / {r}")
verif("date explicite « 28.09.2026 »", T.verifier("2026-09-28", "[22:24 francis] mon rdv de lundi prochain (28.09.2026)", mer)[0] == "2026-09-28")
verif("« lundi dernier » → le 21", T.verifier("2026-09-21", "[10:00 francis] lundi dernier j'ai vu Stéphane", mer)[0] == "2026-09-21")
verif("« après-demain » ne vaut pas « demain »", T.verifier("2026-09-24", "[10:00 francis] après-demain", mer)[0] is None)
verif("le jour même est toujours accepté", T.verifier("2026-09-23", "[16:00 francis] j'ai appelé Stephane", mer)[0] == "2026-09-23")
verif("date illisible → retirée", T.verifier("lundi", cite_a, mer)[0] is None)
verif("horodatage retiré d'une ligne", T.sans_horodatage("[16:55 francis] Mon tarif est de 45 €") == "Mon tarif est de 45 €")
v, r = T.verifier("2026-09-28T16:45", "[16:45 francis] rendez-vous lundi chez Amandine", mer)
verif("une heure ne se justifie pas par l'horodatage de la ligne", v == "2026-09-28" and "heure" in (r or ""), f"{v} / {r}")
cite_h = "[17:31 francis] Oui pardon, pour Autoplus Valmont le 2 octobre, tu peux mettre à partir de huit heures et jusqu’à 18 heures"
verif("« huit heures » en lettres justifie 08:00 (fait VRAI rejeté le 25/09)",
      T.verifier("2026-10-02T08:00", cite_h, date(2026, 9, 25)) == ("2026-10-02T08:00", None))
verif("nombres en lettres : huit, dix-huit", {"8", "18"} <= T.nombres_en_lettres("huit heures à dix-huit heures"))
verif("suffixe en clair", T.suffixe("RDV chez Amandine lundi à 16 h 45", "2026-09-28T16:45") == " (→ lundi 28/09/2026 à 16h45)")
verif("pas de suffixe si la date est déjà écrite", T.suffixe("Opel le vendredi 2 octobre 2026", "2026-10-02") == "")

print("── 2. une consolidation complète (faux modèle, vrai contrôle) ──")
brut = M / "raw"; brut.mkdir(parents=True, exist_ok=True)
(brut / "2026-09-23_02.md").write_text("""---
type: raw
date: 2026-09-23
session_id: s1
lang: fr
ouvert_le: 2026-09-23T12:20:57+02:00
---

## Échanges

[12:20 francis] Oui il faut pas que tu te trompes au niveau des dates, tu vas me mettre un rendez-vous pour lundi 16h45 chez Amandine. Tu me mets un rappel une heure avant
[12:20 nexa] Lundi prochain, c'est le 28 septembre 2026 : rendez-vous chez Amandine à 16 h 45.
[12:22 francis] Tu comptes 1H de rdv
""", encoding="utf-8")
ch = brut / ".chaine.jsonl"
ch.write_text(json.dumps({"fichier": "2026-09-23_02.md"}) + "\n", encoding="utf-8")

vu = {}
def faux_llm(messages):
    if "FICHE D'IDENTITÉ" in messages[0]["content"]:
        return '{"fiches": {}}'                  # second appel (docs/12) : ce test regarde l'appel de consolidation
    vu["prompt"] = messages[0]["content"]; vu["sources"] = messages[1]["content"]
    F = [{"noeud": "amandine", "nouveau": True, "type_noeud": "entite", "alias": {"fr": ["Amandine"], "en": ["Amandine"]},
          "section": "prospective", "fait": "Rendez-vous chez Amandine lundi à 16 h 45, pour une heure.",
          "src": ["raw/2026-09-23_02.md:11", "raw/2026-09-23_02.md:13"], "conf": 1.0,
          "event_time": "2026-09-28T16:45", "echeance": None, "speaker": "francis"},
         {"noeud": "amandine", "section": "prospective", "fait": "Mettre un rappel pour Amandine mardi.",
          "src": ["raw/2026-09-23_02.md:11"], "conf": 0.5, "event_time": "2026-09-30", "speaker": "francis"}]
    return json.dumps({"fragments": F}, ensure_ascii=False)

c = C.Consolidateur(M, __import__("zoneinfo").ZoneInfo("Europe/Paris"), faux_llm, modele="test", nom_agent="nexa",
                    nom_utilisateur="francis")
r = c.consolider()
verif("passage réussi", r.get("statut") == "ok", str(r.get("statut")))
verif("le modèle reçoit le jour de la conversation", "conversation du mercredi 23 septembre 2026" in vu.get("sources", ""))
verif("le modèle reçoit la règle du prochain jour", "PROCHAIN jour de ce nom" in vu.get("prompt", ""))
page = (M / "pages" / "amandine.md").read_text(encoding="utf-8")
ligne = next((l for l in page.splitlines() if "16 h 45" in l), "")
verif("le fait garde « lundi » ET porte la date en clair", "lundi à 16 h 45" in ligne and "(→ lundi 28/09/2026 à 16h45)" in ligne, ligne[:160])
verif("dit_le écrit par le code", "dit_le:2026-09-23T12:20" in ligne)
verif("event_time vérifié écrit", "event_time:2026-09-28T16:45" in ligne)
autre = next((l for l in page.splitlines() if "mardi" in l), "")
verif("mauvaise date (mardi ≠ 30/09) retirée, fait gardé et ancré",
      autre and "event_time" not in autre and "dit_le:2026-09-23T12:20" in autre, autre[:160])
verif("la date retirée est tracée", len(r.get("dates_retirees", [])) == 1, json.dumps(r.get("dates_retirees"), ensure_ascii=False))

print("── 2b. message sur plusieurs lignes : la suite hérite de l'heure ──")
(brut / "2026-09-25_03.md").write_text("""---
type: raw
date: 2026-09-25
session_id: s1
lang: fr
ouvert_le: 2026-09-25T09:00:00+02:00
---

## Échanges

[16:29 francis] Alors j’ai deux rendez-vous que tu dois noter dans l’agenda.
Le premier c’est chez le mécanicien mardi prochain, avec le garagiste MOREL à 16h45.
[17:31 francis] Pour Autoplus Valmont le 2 octobre, tu peux mettre à partir de huit heures et jusqu’à 18 heures
""", encoding="utf-8")
with ch.open("a", encoding="utf-8") as f:
    f.write(json.dumps({"fichier": "2026-09-25_03.md"}) + "\n")
def faux_llm_multi(messages):
    return json.dumps({"fragments": [
        {"noeud": "francis", "section": "prospective", "fait": "Rendez-vous chez le garagiste MOREL mardi prochain à 16h45.",
         "src": ["raw/2026-09-25_03.md:12"], "conf": 1.0, "event_time": "2026-09-29T16:45", "privacy": "personnel", "speaker": "francis"},
        {"noeud": "autoplus_valmont", "nouveau": True, "type_noeud": "entite", "alias": {"fr": ["Autoplus Valmont"], "en": ["Autoplus Valmont"]},
         "section": "prospective", "fait": "Journée chez Autoplus Valmont le 2 octobre, de 8 h à 18 h.",
         "src": ["raw/2026-09-25_03.md:13"], "conf": 1.0, "event_time": "2026-10-02T08:00", "speaker": "francis"}]})
r = C.Consolidateur(M, __import__("zoneinfo").ZoneInfo("Europe/Paris"), faux_llm_multi, modele="test", nom_agent="nexa",
                    nom_utilisateur="francis").consolider()
fr = (M / "pages" / "francis.md").read_text(encoding="utf-8") if (M / "pages" / "francis.md").exists() else ""
verif("ligne de suite : dit_le reprend l'heure du message (16:29)", "dit_le:2026-09-25T16:29" in fr, fr[-240:])
verif("« mardi prochain » dit un vendredi → 29/09 vérifié", "event_time:2026-09-29T16:45" in fr)
rm = (M / "pages" / "autoplus-valmont.md").read_text(encoding="utf-8") if (M / "pages" / "autoplus-valmont.md").exists() else ""
verif("« de 8 h à 18 h » accepté quand Francis a écrit « huit heures »", "de 8 h à 18 h" in rm and "event_time:2026-10-02T08:00" in rm,
      json.dumps(r.get("rejets"), ensure_ascii=False))

print("── 3. le chiffre inventé qui tombe sur l'heure de la ligne (défaut v0.1, trouvé le 26/09) ──")
(brut / "2026-09-24_01.md").write_text("""---
type: raw
date: 2026-09-24
session_id: s1
lang: fr
ouvert_le: 2026-09-24T16:45:00+02:00
---

## Échanges

[16:55 francis] Mon tarif est de 45 € l'élément à partir de deux éléments.
""", encoding="utf-8")
with ch.open("a", encoding="utf-8") as f:
    f.write(json.dumps({"fichier": "2026-09-24_01.md"}) + "\n")
def faux_llm_45(messages):
    return json.dumps({"fragments": [
        {"noeud": "tarifs", "nouveau": True, "type_noeud": "concept", "alias": {"fr": ["tarifs"], "en": ["pricing"]},
         "section": "semantic", "fait": "Le tarif est de 55 € pour un élément seul.", "src": ["raw/2026-09-24_01.md:11"]}]})
r = C.Consolidateur(M, __import__("zoneinfo").ZoneInfo("Europe/Paris"), faux_llm_45, modele="test", nom_agent="nexa",
                    nom_utilisateur="francis").consolider()
verif("« 55 € » inventé rejeté, bien que la ligne soit dite à 16h55",
      r.get("faits_retenus") == 0 and any("55" in x["raison"] for x in r.get("rejets", [])),
      json.dumps(r.get("rejets"), ensure_ascii=False))

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
