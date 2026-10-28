#!/usr/bin/env python3
"""Banc 9 — la vérification propre annoncée au doc 08 §9.1 : B++ contre embeddings sur des conversations
JAMAIS vues pendant la conception (à partir du 27/09), moteur figé (plugin 0.7.0 tel que déployé).

Rien de nouveau dans la méthode : mêmes moteurs, même consigne de requête, même budget (9 faits), même
juge aveugle que le banc 8 (banc8_requetes.SYS, banc8_juge.juger / plein_texte). Seul changement :
l'instantané garde son thesaurus.json (la production a des concepts depuis le 27/09 15h10).

Instantanés antérieurs au 27/09 15h10 (sans concepts) : les faits reçoivent les concepts que le
rattrapage du 27/09 (commit 9954cbb) leur a donnés — une métadonnée sur le fait lui-même, aucun fait
futur. Ces messages sont comptés à part (« rattrapés »), les autres sont « natifs ».

Trois temps, comme au banc 8 :
    conteneur  python3 banc9_verif.py rejeu    <memoire> <banc-9> <plugins>
    conteneur  python3 banc9_verif.py requetes <memoire> <banc-9> <plugins>
    hôte       banc8_embeddings.py <banc-9> <banc-9>
    conteneur  python3 banc9_verif.py juge     <memoire> <banc-9> <plugins>
Lecture seule sur la mémoire (`git archive`).
"""
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ETAPE, MEMOIRE, SORTIE, PLUGINS = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
DEBUT = "2026-09-27T00:00"
RATTRAPAGE = "9954cbb"                       # B+ : 137 faits rattachés aux concepts (27/09 15h10)
PARIS = ZoneInfo("Europe/Paris")
IMPLICITES = ("francis", "nexa")
sys.path.insert(0, "/opt/hermes")
sys.path.insert(0, PLUGINS)
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.argv = [sys.argv[0], str(SORTIE), str(SORTIE), PLUGINS]      # SOURCE = SORTIE pour les modules du banc 8
from exia_seed import graphe as G                                          # noqa: E402
from exia_seed.util import estimer_tokens                                  # noqa: E402
from banc_rappel import messages, instantanes                              # noqa: E402

_RE_FAIT = re.compile(r"^(- (.*?) <!-- )(.*?)( -->)\s*$")


def git(*a, binaire=False):
    return subprocess.run(["git", "-C", str(MEMOIRE), "-c", "safe.directory=*", *a], capture_output=True, check=True,
                          text=not binaire).stdout


def extraire(commit: str, dossier: Path) -> bool:
    """Instantané + thésaurus ; rend True si les concepts viennent du rattrapage (instantané sans concepts)."""
    if dossier.exists():
        shutil.rmtree(dossier)
    dossier.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(git("archive", commit, binaire=True))) as t:
        t.extractall(dossier, members=[x for x in t.getmembers() if x.name.startswith(("pages/", "INDEX.md", "thesaurus.json"))],
                     filter="data")
    (dossier / "raw").mkdir(exist_ok=True)
    rattrape = not (dossier / "thesaurus.json").exists()
    if rattrape:
        tags = {}
        with tarfile.open(fileobj=io.BytesIO(git("archive", RATTRAPAGE, "pages", "thesaurus.json", binaire=True))) as t:
            for m in t.getmembers():
                if m.name == "thesaurus.json":
                    (dossier / "thesaurus.json").write_bytes(t.extractfile(m).read())
                elif m.isfile():
                    for l in t.extractfile(m).read().decode("utf-8").splitlines():
                        x = _RE_FAIT.match(l)
                        c = x and re.search(r"(?:^| )concepts:(\S+)", x.group(3))
                        if c:
                            tags[x.group(2).strip()] = c.group(1)
        for f in (dossier / "pages").glob("*.md"):
            lignes = f.read_text(encoding="utf-8").splitlines()
            for i, l in enumerate(lignes):
                x = _RE_FAIT.match(l)
                if x and "concepts:" not in x.group(3) and x.group(2).strip() in tags:
                    lignes[i] = x.group(1) + x.group(3) + f" concepts:{tags[x.group(2).strip()]}" + x.group(4)
            f.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    G.calculer(dossier, implicites=IMPLICITES)            # le graphe est une fonction des pages (05 D1)
    return rattrape


def rejeu() -> int:
    SORTIE.mkdir(parents=True, exist_ok=True)
    snaps, faits_extraits, lignes = instantanes(MEMOIRE), {}, []
    for n, (instant, texte, reponse) in enumerate(messages(MEMOIRE)):
        if instant.isoformat() < DEBUT:
            continue
        avant = [h for ct, h in snaps if ct < instant.replace(tzinfo=PARIS).timestamp()]
        h = avant[-1][:7]
        if h not in faits_extraits:
            faits_extraits[h] = extraire(h, SORTIE / "instantanes" / h)
        lignes.append({"n": n, "instant": instant.isoformat(timespec="minutes"), "message": texte[:500],
                       "reponse": reponse[:800], "instantane": h, "rattrape": faits_extraits[h]})
    (SORTIE / "rejeu.jsonl").write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lignes), encoding="utf-8")
    print(f"{len(lignes)} messages depuis le {DEBUT[:10]} · {len(faits_extraits)} instantanés "
          f"({sum(faits_extraits.values())} rattrapés) · {sum(1 for l in lignes if l['rattrape'])} messages sur instantané rattrapé")
    return 0


def requetes() -> int:
    import banc8_requetes
    return banc8_requetes.main()


def juge() -> int:
    import banc8_juge as J
    from exia_seed.requete import Lecteur
    rejeu = {json.loads(l)["n"]: json.loads(l) for l in (SORTIE / "rejeu.jsonl").read_text(encoding="utf-8").splitlines()}
    reqs = [json.loads(l) for l in (SORTIE / "requetes.jsonl").read_text(encoding="utf-8").splitlines()]
    emb = {json.loads(l)["n"]: json.loads(l)["embeddings"] for l in (SORTIE / "embeddings.jsonl").read_text(encoding="utf-8").splitlines()}
    lecteurs, res = {}, []
    for r in reqs:
        if not r["requete"]:
            continue
        s, q, n = r["instantane"], r["requete"], r["n"]
        if s not in lecteurs:
            lecteurs[s] = Lecteur(SORTIE / "instantanes" / s, implicites=IMPLICITES)
        L = lecteurs[s]
        c = L.chercher(q, 9, datetime.fromisoformat(r["instant"]), faits_max=9)       # exactement banc8_bpp
        bpp = [f["fait"] for y in c.get("resultats", []) for f in y["faits"]]
        bpp += [p["fait"] for p in (c.get("pistes") or {}).get("faits", []) if p["fait"] not in bpp]
        moteurs = {"FCM B++": bpp[:9], "Embeddings": [f for x in emb.get(n, []) for f in x["faits"]],
                   "Plein texte": J.plein_texte(L.r, L.r.memoire(), q)}
        union = set().union(*map(set, moteurs.values()))
        l = rejeu[n]
        utiles = J.juger(90_000 + n, l["message"], l["reponse"], list(union)) if union else set()
        res.append({"n": n, "instant": r["instant"], "requete": q, "rattrape": l["rattrape"], "utiles": sorted(utiles), **moteurs})
        print(f"  {n:3} {'ratt.' if l['rattrape'] else 'natif'} « {q[:40]:40} » union {len(union):2} utiles {len(utiles):2} · "
              + " · ".join(f"{k} {len(set(v) & utiles)}/{len(v)}" for k, v in moteurs.items()), flush=True)
    (SORTIE / "resultats9.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in res), encoding="utf-8")
    noms = ["FCM B++", "Embeddings", "Plein texte"]
    bilan = {"messages_rejoues": len(rejeu), "messages_avec_requete": len(res)}
    for jeu, garde in (("tout", lambda x: True), ("natifs", lambda x: not x["rattrape"]), ("rattrapes", lambda x: x["rattrape"])):
        xs = [x for x in res if garde(x)]
        tot = sum(len(x["utiles"]) for x in xs)
        b = {"messages": len(xs), "utiles_dans_l_union": tot}
        for k in noms:
            trouves = sum(len(set(x[k]) & set(x["utiles"])) for x in xs)
            proposes = sum(len(x[k]) for x in xs)
            b[k] = {"utiles": trouves, "rappel": round(trouves / tot, 3) if tot else None,
                    "precision": round(trouves / proposes, 3) if proposes else None, "faits_proposes": proposes,
                    "parle_pour_rien": sum(1 for x in xs if x[k] and not set(x[k]) & set(x["utiles"])),
                    "seul_a_trouver": sum(len((set(x[k]) & set(x["utiles"])) - set().union(*(set(x[o]) for o in noms if o != k))) for x in xs),
                    "tokens": round(sum(estimer_tokens(" ".join(x[k])) for x in xs) / max(1, len(xs)))}
        bilan[jeu] = b
    bilan["cout_banc_tokens"] = sum(v.get("tokens", 0) for v in J.CACHE.values())
    (SORTIE / "bilan9.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(bilan, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit({"rejeu": rejeu, "requetes": requetes, "juge": juge}[ETAPE]())
