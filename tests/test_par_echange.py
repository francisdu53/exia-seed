"""« 1 échange par lot » (14/11/2026, docs/17 §28-§33, décision de Francis) — conteneur jetable, vrai chargeur d'Hermès.

Un appel au modèle par échange (un message de quelqu'un d'autre que l'agent + les réponses de l'agent qui suivent), sans
jamais découper le brut : les lignes consolidées sont notées dans `raw/.consolide_echanges.jsonl`, et le lot n'entre dans
`raw/.consolide.jsonl` qu'avec son dernier échange. Même découpage que le banc (banc/modeles/decouper.py)."""
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
LOT = "2026-11-10_01.md"
LIGNES = ["---", "type: raw", "date: 2026-11-10", "lang: fr", "ouvert_le: 2026-11-10T09:00:00+01:00", "---", "",
          "## Échanges", "",
          "[09:00 nexa] Bonjour Francis, voici ton point du matin avec trois rendez-vous.",          # 10 : échange 1 (agent en tête)
          "[09:01 francis] Le garage Dupont veut un devis de 1200 euros pour jeudi prochain.",       # 11 : échange 2
          "[09:01 nexa] C'est noté pour le garage Dupont.",                                          # 12
          "Je prépare le devis dans la journée.",                                                    # 13 : suite du message de l'agent
          "[09:10 francis] Ma voiture personnelle est une Polo rouge de deux mille douze.",          # 14 : échange 3, RETIRÉ
          "[09:10 nexa] Bien noté pour ta Polo.",                                                    # 15 : RETIRÉ
          "<!-- 09:11 retrait: 2026-11-10_01.md lignes 14-15 -->",                                   # 16 : repère
          "[09:20 systeme] Rapport du sous-agent : la facture 42 a été envoyée au client.",         # 17 : échange 4
          "[09:30 francis] Je pars en vacances en Bretagne le vingt décembre avec Claire.",          # 18 : échange 5
          "[09:30 nexa] Bonnes vacances en Bretagne !"]                                              # 19


def memoire():
    r = Path(tempfile.mkdtemp(prefix="par-echange-")); (r / "raw").mkdir(); (r / "pages").mkdir()
    (r / ".langue").write_text("fr\n", encoding="utf-8")
    (r / "raw" / LOT).write_text("\n".join(LIGNES) + "\n", encoding="utf-8")
    (r / "raw" / ".chaine.jsonl").write_text(json.dumps({"fichier": LOT, "sha256": "x", "precedent": "genese"}) + "\n", encoding="utf-8")
    (r / "raw" / ".retraits.jsonl").write_text(json.dumps({"fichier": LOT, "lignes": [14, 15]}) + "\n", encoding="utf-8")
    return r


SRC = re.compile(r"^\[(raw/[^\]]+)\] \[\d\d:\d\d ([a-z_]+)\] ?(.*)$", re.M)
def factice(appels, panne_au=None):
    def appeler(messages):
        user = messages[-1]["content"]
        appels.append(sorted(int(n) for n in re.findall(r"^\[raw/[^\]]+:(\d+)\]", user, re.M)))   # toutes les lignes montrées
        if panne_au is not None and len(appels) == panne_au:
            return "désolé"                                                  # JSON illisible : le passage échoue
        frs = [{"noeud": "francis", "nouveau": False, "type_noeud": "entite", "section": "episodic",
                "fait": " ".join(t.split()[:9]), "src": [ref], "conf": 1.0, "speaker": "francis", "concepts": []}
               for ref, qui, t in SRC.findall(user) if qui == "francis"]
        return json.dumps({"fragments": frs, "concepts_nouveaux": {}}, ensure_ascii=False)
    return appeler


def jusqu_au_bout(c):
    """La boucle de l'outil de consolidation : jusqu'à ce qu'il ne reste rien."""
    for _ in range(50):
        r = c.consolider()
        if r.get("statut") not in ("ok", "vide"):
            return r
    return r


def consolides(r):
    f = r / "raw" / ".consolide.jsonl"
    return [json.loads(l)["fichier"] for l in f.read_text().splitlines() if l.strip()] if f.exists() else []


print("── 1. par lots (défaut) : un seul appel, comme avant ──")
r = memoire(); appels = []
c = C(r, TZ, factice(appels), modele="essai", nom_agent="nexa", nom_utilisateur="francis", fiches=False)
jusqu_au_bout(c)
verif("un appel pour tout le lot", len(appels) == 1, str(appels))
verif("…avec toutes les lignes sauf celles retirées et le repère", appels and appels[0] == [10, 11, 12, 13, 17, 18, 19], str(appels))
verif("lot consolidé une fois", consolides(r) == [LOT], str(consolides(r)))
verif("aucun registre d'échanges en mode lots", not (r / "raw" / ".consolide_echanges.jsonl").exists())
shutil.rmtree(r)

print("── 2. un échange par appel ──")
r = memoire(); appels = []
c = C(r, TZ, factice(appels), modele="essai", nom_agent="nexa", nom_utilisateur="francis", fiches=False, par_echange=True)
verif("le découpage du banc : agent en tête, échange + suite de l'agent, « systeme » ouvre un échange, retrait exclu",
      c._echanges_de(LOT) == [[10], [11, 12, 13], [17], [18, 19]], str(c._echanges_de(LOT)))
r1 = c.consolider()
verif("1er passage : le 1er échange seul", appels == [[10]], str(appels))
verif("…le lot n'est pas encore consolidé", consolides(r) == [] and c.lots_en_attente() == [LOT])
jusqu_au_bout(c)
verif("4 appels, un par échange, dans l'ordre", appels == [[10], [11, 12, 13], [17], [18, 19]], str(appels))
verif("les lignes retirées ne sont jamais montrées", all(14 not in a and 15 not in a for a in appels))
verif("lot consolidé une seule fois, avec son dernier échange", consolides(r) == [LOT], str(consolides(r)))
pages = "\n".join(x.read_text(encoding="utf-8") for x in (r / "pages").glob("*.md"))
verif("faits écrits avec les VRAIS numéros de ligne du brut", "raw/2026-11-10_01.md:11" in pages and "raw/2026-11-10_01.md:18" in pages,
      re.findall(r"src:\S+", pages)[:4].__str__())
verif("…rien de la ligne retirée", "Polo" not in pages)
verif("le brut n'est pas touché (chaîne d'intégrité)", (r / "raw" / LOT).read_text(encoding="utf-8") == "\n".join(LIGNES) + "\n")
verif("plus rien en attente", c.lots_en_attente() == [] and c.consolider().get("statut") == "rien")
shutil.rmtree(r)

print("── 3. reprise après une panne, sans doublon ──")
r = memoire(); appels = []
c = C(r, TZ, factice(appels, panne_au=2), modele="essai", nom_agent="nexa", nom_utilisateur="francis", fiches=False, par_echange=True)
rp = jusqu_au_bout(c)
verif("la panne arrête la boucle au 2e échange", rp.get("statut") == "echec_json" and appels == [[10], [11, 12, 13]], str(appels))
appels2 = []
c = C(r, TZ, factice(appels2), modele="essai", nom_agent="nexa", nom_utilisateur="francis", fiches=False, par_echange=True)
jusqu_au_bout(c)
verif("la reprise commence à l'échange en panne, pas au début", appels2 == [[11, 12, 13], [17], [18, 19]], str(appels2))
pages = "\n".join(x.read_text(encoding="utf-8") for x in (r / "pages").glob("*.md"))
verif("aucun fait en double", pages.count("raw/2026-11-10_01.md:11") == 1, str(pages.count("raw/2026-11-10_01.md:11")))
verif("lot consolidé une seule fois", consolides(r) == [LOT])
shutil.rmtree(r)

print("── 4. un retrait qui arrive entre deux passages ──")
r = memoire(); appels = []
c = C(r, TZ, factice(appels), modele="essai", nom_agent="nexa", nom_utilisateur="francis", fiches=False, par_echange=True)
c.consolider(); c.consolider()                                               # échanges 1 et 2 faits
with open(r / "raw" / ".retraits.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps({"fichier": LOT, "lignes": [18, 19]}) + "\n")       # « oublie ça » sur les vacances
jusqu_au_bout(c)
verif("l'échange retiré avant sa consolidation n'est jamais montré", all(18 not in a for a in appels), str(appels))
verif("…et le lot se ferme quand même", consolides(r) == [LOT], str(consolides(r)))
shutil.rmtree(r)

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
