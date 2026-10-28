#!/usr/bin/env python3
"""Banc 6b, partie 2 — le rappel C « à la Karpathy » et le juge aveugle (GPT-6, effort bas).

Entrée : rejeu.jsonl de la partie 1 (banc_rappel.py). Pour chaque message rejouable :
    C      le modèle lit l'INDEX.md de l'instantané + le message, et choisit au plus 3 pages ;
           coût = lecture de l'index (appel) + pages injectées.
    juge   le message, la réponse réellement donnée par l'agent (contexte), et l'UNION des faits
           proposés par A, Bk, B5 et C, mélangés et numérotés SANS ÉTIQUETTE → « lesquels auraient
           été utiles ? ». Au-delà de 40 faits, en plusieurs appels.
    D      sur un échantillon de messages, le juge voit TOUS les faits de l'instantané : on estime
           ainsi les faits utiles qu'aucun des rappels n'a proposés (le plafond réel de D).

Reprise : chaque appel au modèle est enregistré dans appels.jsonl ; relancer ne refait que ce qui
manque (utile si le quota s'épuise en route).

    python3 banc_juge.py /opt/data/workspace/banc-6b [/chemin/vers/plugins] [--echantillon-D 15]
"""
import hashlib
import json
import random
import re
import sys
from pathlib import Path

DOSSIER = Path(sys.argv[1])
sys.path.insert(0, "/opt/hermes")
sys.path.insert(0, sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "/opt/data/plugins")
from exia_seed import graphe as G                                         # noqa: E402
from exia_seed.consolidation import appel_llm_hermes                      # noqa: E402
from exia_seed.util import estimer_tokens                                 # noqa: E402

ECH_D = int(sys.argv[sys.argv.index("--echantillon-D") + 1]) if "--echantillon-D" in sys.argv else 15
PAQUET = 40
APPELS = DOSSIER / "appels.jsonl"
llm = appel_llm_hermes("low")

SYS_C = ("Tu aides un assistant personnel à retrouver ses souvenirs. Tu reçois l'INDEX de sa mémoire (une ligne "
         "par page) et le dernier message de l'utilisateur. Choisis les pages, AU PLUS 3, dont le contenu aiderait "
         "l'assistant à bien comprendre ou traiter ce message ; aucune si rien n'est pertinent. Réponds UNIQUEMENT "
         'par un objet JSON : {"pages": ["nom_du_noeud", ...]}')
SYS_J = ("Tu évalues des souvenirs proposés à un assistant personnel. On te donne le message de l'utilisateur, la "
         "réponse que l'assistant a réellement donnée (pour le contexte seulement) et des souvenirs numérotés. "
         "Indique ceux qui auraient été UTILES à l'assistant pour comprendre la demande ou bien y répondre : une "
         "information pertinente qu'il gagne à avoir sous les yeux. Un souvenir seulement sur le même thème, sans "
         "apport pour CE message, n'est PAS utile. Sois exigeant. Réponds UNIQUEMENT par un objet JSON : "
         '{"utiles": [numéros]}')


def charger_appels():
    fait = {}
    if APPELS.exists():
        for l in APPELS.read_text(encoding="utf-8").splitlines():
            e = json.loads(l); fait[e["cle"]] = e
    return fait


CACHE = charger_appels()


def appeler(cle: str, systeme: str, contenu: str) -> dict:
    if cle in CACHE:
        return CACHE[cle]
    rep = llm([{"role": "system", "content": systeme}, {"role": "user", "content": contenu}])
    m = re.search(r"\{.*\}", rep or "", re.S)
    try:
        donnees = json.loads(m.group(0)) if m else {}
    except ValueError:
        donnees = {}
    e = {"cle": cle, "reponse": donnees, "tokens_entree": estimer_tokens(systeme + contenu), "tokens_sortie": estimer_tokens(rep or "")}
    with APPELS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    CACHE[cle] = e
    return e


def juger(n: int, message: str, reponse: str, faits: list, etiquette: str) -> set:
    """Rend l'ensemble des faits (textes) jugés utiles. Ordre mélangé, déterministe, sans étiquette."""
    faits = sorted(set(faits))
    random.Random(n).shuffle(faits)
    utiles = set()
    for k in range(0, len(faits), PAQUET):
        lot = faits[k:k + PAQUET]
        liste = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(lot))
        contenu = f"MESSAGE DE L'UTILISATEUR\n{message}\n\nRÉPONSE DE L'ASSISTANT (contexte)\n{reponse[:600]}\n\nSOUVENIRS\n{liste}"
        cle = f"juge:{etiquette}:{n}:{k}:" + hashlib.sha256(liste.encode()).hexdigest()[:10]
        for i in appeler(cle, SYS_J, contenu)["reponse"].get("utiles", []) or []:
            if isinstance(i, int) and 1 <= i <= len(lot):
                utiles.add(lot[i - 1])
    return utiles


def main() -> int:
    lignes = [json.loads(l) for l in (DOSSIER / "rejeu.jsonl").read_text(encoding="utf-8").splitlines()]
    jouables = [l for l in lignes if l.get("memoire") != "vide"]
    if "--limite" in sys.argv:                                  # essai de tuyauterie
        jouables = jouables[:int(sys.argv[sys.argv.index("--limite") + 1])]
    faits_instantane, index_instantane = {}, {}
    resultats = []
    for l in jouables:
        d = DOSSIER / "instantanes" / l["instantane"]
        if l["instantane"] not in faits_instantane:
            _, faits = G._lire(d)
            faits_instantane[l["instantane"]] = faits
            index_instantane[l["instantane"]] = (d / "INDEX.md").read_text(encoding="utf-8") if (d / "INDEX.md").exists() else ""
        faits, index = faits_instantane[l["instantane"]], index_instantane[l["instantane"]]
        # C — à la Karpathy
        e = appeler(f"C:{l['n']}", SYS_C, f"INDEX\n{index}\n\nMESSAGE\n{l['message']}")
        choisis = [str(x) for x in (e["reponse"].get("pages") or [])][:3]
        c_faits = [f["texte"] for f in faits if f["noeud"] in choisis]
        pages_tok = sum(estimer_tokens(f["texte"]) for f in faits if f["noeud"] in choisis)
        l["C"] = {"pages": choisis, "faits": c_faits, "tokens": e["tokens_entree"] + e["tokens_sortie"] + pages_tok,
                  "tokens_injectes": pages_tok}
        union = set(l["A"]["faits"]) | set(l["Bk"]["faits"]) | set(l["B5"]["faits"]) | set(c_faits)
        l["utiles"] = sorted(juger(l["n"], l["message"], l["reponse"], list(union), "union")) if union else []
        resultats.append(l)
        print(f"  {l['n']:3}/{len(lignes)}  union {len(union):3}  utiles {len(l['utiles']):2}  C={choisis}", flush=True)

    # D — échantillon : le juge voit tout
    rnd = random.Random(2026)
    avec = [l for l in resultats if l["A"]["faits"] or l["C"]["faits"] or l["B5"]["faits"]]
    ech = sorted(rnd.sample(avec, min(ECH_D, len(avec))), key=lambda l: l["n"])
    for l in ech:
        tous = [f["texte"] for f in faits_instantane[l["instantane"]]]
        l["utiles_tous"] = sorted(juger(l["n"], l["message"], l["reponse"], tous, "tous"))

    (DOSSIER / "juge.jsonl").write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in resultats), encoding="utf-8")

    # Mesures
    def mesure(cle):
        trouves = sum(len(set(l[cle]["faits"]) & set(l["utiles"])) for l in resultats)
        proposes = sum(len(l[cle]["faits"]) for l in resultats)
        return {"utiles_trouves": trouves, "proposes": proposes,
                "precision": round(trouves / proposes, 3) if proposes else None,
                "tokens_moyens": round(sum(l[cle]["tokens"] for l in resultats) / len(resultats)),
                "messages_parlant": sum(1 for l in resultats if l[cle]["faits"]),
                "bruit_seul": sum(1 for l in resultats if l[cle]["faits"] and not set(l[cle]["faits"]) & set(l["utiles"]))}
    total_utiles = sum(len(l["utiles"]) for l in resultats)
    res = {"messages_juges": len(resultats), "utiles_dans_l_union": total_utiles,
           "A": mesure("A"), "Bk": mesure("Bk"), "B5": mesure("B5"), "C": mesure("C")}
    for k in ("A", "Bk", "B5", "C"):
        res[k]["rappel_relatif"] = round(res[k]["utiles_trouves"] / total_utiles, 3) if total_utiles else None
    # Association : utiles trouvés par A et par AUCUN rappel lexical (Bk, B5)
    res["A_association"] = sum(len((set(l["A"]["faits"]) & set(l["utiles"])) - set(l["Bk"]["faits"]) - set(l["B5"]["faits"])) for l in resultats)
    # D : sur l'échantillon, part des utiles que personne n'a proposés
    if ech:
        u_tous = sum(len(l["utiles_tous"]) for l in ech)
        u_union = sum(len(set(l["utiles_tous"]) & (set(l["A"]["faits"]) | set(l["Bk"]["faits"]) | set(l["B5"]["faits"]) | set(l["C"]["faits"]))) for l in ech)
        res["D_echantillon"] = {"messages": len(ech), "utiles_parmi_tous_les_faits": u_tous,
                                "dont_proposes_par_A_B_C": u_union,
                                "A_trouve": sum(len(set(l["utiles_tous"]) & set(l["A"]["faits"])) for l in ech),
                                "C_trouve": sum(len(set(l["utiles_tous"]) & set(l["C"]["faits"])) for l in ech)}
    appels = list(CACHE.values())
    res["cout_banc_tokens"] = sum(e["tokens_entree"] + e["tokens_sortie"] for e in appels)
    (DOSSIER / "resume_partie2.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
