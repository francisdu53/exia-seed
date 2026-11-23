"""Un autre interlocuteur dans la consolidation (15/11/2026, canal d'échange) — conteneur jetable, vrai chargeur d'Hermès.

La consigne qualifiée ne parle que de l'utilisateur et de l'agent. Quand un AUTRE interlocuteur parle dans les lignes
d'un passage (main_claude, par le canal), un paragraphe le présente au modèle — et SEULEMENT dans ce cas : un passage
ordinaire envoie exactement les mêmes octets qu'avant. Ses paroles sont des paroles d'un tiers, pas de l'agent : un
fait qui les cite est retenu, signé de son nom."""
import importlib, json, re, shutil, sys, tempfile
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, "/opt/hermes")
ok = ko = 0
def verif(nom, cond, detail=""):
    global ok, ko
    ok += bool(cond); ko += (not cond)
    print(f"  {'✓' if cond else '✗'} {nom}" + (f" — {detail}" if detail else ""))

from plugins.memory import load_memory_provider
p = load_memory_provider("exia_seed")
C = importlib.import_module(type(p).__module__ + ".consolidation").Consolidateur
TZ = ZoneInfo("Europe/Paris")
LOT = "2026-11-15_01.md"
ENTETE = ["---", "type: raw", "date: 2026-11-15", "lang: fr", "ouvert_le: 2026-11-15T09:00:00+01:00", "---", "", "## Échanges", ""]
DESCRIPTION = "Claude Code, l'agent qui développe EXIA SEED sur le VPS principal"


def memoire(lignes):
    r = Path(tempfile.mkdtemp(prefix="autres-")); (r / "raw").mkdir(); (r / "pages").mkdir()
    (r / ".langue").write_text("fr\n", encoding="utf-8")
    (r / "raw" / LOT).write_text("\n".join(ENTETE + lignes) + "\n", encoding="utf-8")
    (r / "raw" / ".chaine.jsonl").write_text(json.dumps({"fichier": LOT, "sha256": "x", "precedent": "genese"}) + "\n", encoding="utf-8")
    return r


def factice(vus, fragments):
    def appeler(messages):
        if "SOURCES" not in messages[-1]["content"]:
            return "{}"
        vus.append(messages[0]["content"])
        return json.dumps({"fragments": fragments, "concepts_nouveaux": {}}, ensure_ascii=False)
    return appeler


def faits(r):
    return "\n".join(x.read_text(encoding="utf-8") for x in (r / "pages").glob("*.md"))


print("── 1. un passage ordinaire : la consigne est inchangée ──")
r = memoire(["[09:01 francis] Le garage Dupont veut un devis de 1200 euros pour jeudi prochain.", "[09:01 nexa] C'est noté."])
vus = []
C(r, TZ, factice(vus, []), modele="essai", nom_agent="nexa", nom_utilisateur="francis", fiches=False,
  consigne="petit_modele", annuaire={"main_claude": DESCRIPTION}).consolider()
verif("aucun paragraphe « autres interlocuteurs »", vus and "AUTRES INTERLOCUTEURS" not in vus[0])
ordinaire = vus[0]
shutil.rmtree(r)
r = memoire(["[09:01 francis] Le garage Dupont veut un devis de 1200 euros pour jeudi prochain.", "[09:01 nexa] C'est noté."])
vus = []
C(r, TZ, factice(vus, []), modele="essai", nom_agent="nexa", nom_utilisateur="francis", fiches=False,
  consigne="petit_modele").consolider()
verif("…mêmes octets avec ou sans annuaire", vus and vus[0] == ordinaire)
shutil.rmtree(r)

print("── 2. main_claude parle dans les lignes : il est présenté, ses paroles sont les siennes ──")
lignes = ["[11:42 main_claude] (canal · objet : version) La version 0.9.5 d'EXIA SEED est installée chez Nexa depuis le 14/11 à 19h12.",
          "[11:57 nexa] (canal · objet : version · en réponse au message de main_claude du 15/11 11:42) Merci, c'est noté."]
r = memoire(lignes)
vus = []
frs = [{"noeud": "exia_seed", "nouveau": True, "type_noeud": "entite", "alias": {"fr": ["EXIA SEED"], "en": []},
        "section": "episodic", "fait": "La version 0.9.5 d'EXIA SEED est installée chez Nexa depuis le 14/11 à 19h12",
        "src": [f"raw/{LOT}:10"], "conf": 1.0, "speaker": "francis", "concepts": []},   # l'erreur redoutée du modèle
       {"noeud": "installation", "nouveau": True, "type_noeud": "evenement", "alias": {"fr": [], "en": []}, "section": "episodic",
        "fait": "main_claude indique que l'installation date du 14/11", "src": [f"raw/{LOT}:10"], "conf": 1.0,
        "speaker": "main_claude", "concepts": []},
       {"noeud": "nexa", "nouveau": True, "type_noeud": "entite", "alias": {"fr": ["Nexa"], "en": []}, "section": "semantic",
        "fait": "Nexa a noté le message", "src": [f"raw/{LOT}:11"], "conf": 1.0, "speaker": "nexa", "concepts": []}]
res = C(r, TZ, factice(vus, frs), modele="essai", nom_agent="nexa", nom_utilisateur="francis", fiches=False,
        consigne="petit_modele", annuaire={"main_claude": DESCRIPTION}).consolider()
verif("le paragraphe est ajouté, avec sa description", vus and "AUTRES INTERLOCUTEURS" in vus[0] and DESCRIPTION in vus[0]
      and "« main_claude »" in vus[0], vus[0][-500:] if vus else "")
verif("…dit de ne jamais prêter ses paroles à francis, « tu » = l'assistant, à la première personne", vus and "Ne prête jamais ses paroles à « francis »" in vus[0] and "désignent l'assistant, jamais « francis »" in vus[0] and "PREMIÈRE personne" in vus[0])
verif("…sans rien changer au reste de la consigne", vus and vus[0].startswith(ordinaire.split("\n\nLES CONCEPTS")[0][:2000]))
verif("le fait tiré de main_claude est RETENU (un tiers n'est pas l'agent)", "0.9.5" in faits(r), str(res.get("rejets")))
verif("…signé main_claude PAR LE CODE, même quand le modèle écrit « francis »", re.search(r"0\.9\.5[^\n]*speaker:main_claude", faits(r)) is not None,
      re.findall(r"- [^\n]*0\.9\.5[^\n]*", faits(r))[:1].__str__())
verif("la source est ajoutée au texte par le code quand le modèle l'omet", "Selon main_claude : La version 0.9.5" in faits(r),
      re.findall(r"- [^\n]*0\.9\.5[^\n]*", faits(r))[:1].__str__())
verif("…et pas en double quand le texte la nomme déjà", "main_claude indique que l'installation date du 14/11" in faits(r)
      and "Selon main_claude : main_claude" not in faits(r))
verif("la réponse de l'agent seule reste refusée (règle de l'assistant)", "Nexa a noté le message" not in faits(r),
      str(res.get("rejets")))
shutil.rmtree(r)

print("── 3. le découpage « 1 échange » : main_claude ouvre un échange, comme l'utilisateur ──")
r = memoire(["[09:01 francis] Le garage Dupont veut un devis de 1200 euros.", "[09:01 nexa] C'est noté.", lignes[0], lignes[1]])
c = C(r, TZ, factice([], []), modele="essai", nom_agent="nexa", nom_utilisateur="francis", fiches=False, par_echange=True)
verif("deux échanges : celui de francis, puis celui de main_claude avec la réponse de nexa",
      c._echanges_de(LOT) == [[10, 11], [12, 13]], str(c._echanges_de(LOT)))
shutil.rmtree(r)

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
