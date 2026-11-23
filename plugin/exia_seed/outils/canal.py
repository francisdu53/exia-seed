#!/usr/bin/env python3
"""Canal d'échange par fichiers entre l'agent et un autre interlocuteur — sans modèle, pour un cron (15/11/2026).

Décision de Francis (15/11/2026) : Nexa et le Claude Code du VPS principal (« main_claude ») s'écrivent par fichiers,
et cette conversation ENRICHIT la mémoire comme une vraie conversation, chacun sous son nom.

    python3 /opt/data/plugins/exia_seed/outils/canal.py          # le passage du cron : SILENCIEUX sans message neuf
    python3 /opt/data/plugins/exia_seed/outils/canal.py --etat   # à la main : le dossier, ce qui est inscrit ou non

Un message = un fichier `AAAA-MM-JJ_HHMM_<de>-vers-<a>_<sujet>.md`, écrit d'un coup (fichier temporaire puis
renommage), avec un en-tête :

    ---
    de: main_claude
    a: nexa
    date: 2026-11-15T11:30:00+01:00
    sujet: bulletin
    reponse_a: 2026-11-15_1102_nexa-vers-main_claude_question.md      (facultatif)
    ---
    Le texte.

À chaque passage :
1. chaque fichier nouveau est INSCRIT AU BRUT, une ligne au nom de son auteur (`Brut.ecrire_ligne` : ni consigne, ni
   avis, le dernier tour de la conversation intact) ; la consolidation le range ensuite comme le reste ;
2. l'auteur est donné par le PROPRIÉTAIRE du fichier, pas par son en-tête : `uid_correspondant` (0 par défaut, celui
   qui administre la machine) = le correspondant ; le compte qui lance cet outil = l'agent. Un en-tête qui dit autre
   chose, ou un autre propriétaire : le fichier est refusé, signalé UNE fois, jamais inscrit ;
3. les messages neufs du CORRESPONDANT sont affichés — c'est ce qui réveille l'agent (cron d'Hermès à script : sans
   sortie, aucun appel au modèle). Ceux de l'agent sont inscrits sans bruit ;
4. le dossier garde les `echanges_max` derniers ÉCHANGES (un message et les réponses qui lui sont faites, suivies par
   `reponse_a`) ; les fichiers plus anciens sont effacés, SEULEMENT une fois inscrits au brut : la mémoire est l'archive.

Réglages (`memory.exia_seed.canal`) : dossier, correspondant, description, uid_correspondant, echanges_max.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/opt/hermes")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))          # …/plugins

from exia_seed import _etiquette, config as _config, langues      # noqa: E402
from exia_seed.ingestion import Brut                               # noqa: E402
from exia_seed.util import ajouter_ligne_jsonl, fuseau, maintenant, verrou  # noqa: E402

ECHANGES_MAX = 14
TEXTE_MAX = 6000            # caractères d'un message affiché au réveil ; le fichier entier est inscrit au brut
FRAIS_S = 10                # un fichier modifié il y a moins de 10 s attend le passage suivant (écriture en cours)
SESSION = "canal"


def lire_message(f: Path):
    """(en-tête, texte) ; en-tête vide si illisible."""
    try:
        brut = f.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}, ""
    m = re.match(r"---\n(.*?)\n---\n?(.*)\Z", brut, re.S)
    if not m:
        return {}, ""
    entete = {}
    for ligne in m.group(1).splitlines():
        if ":" in ligne:
            k, v = ligne.split(":", 1)
            entete[k.strip()] = v.strip().strip("\"'")
    return entete, m.group(2).strip()


def jsonl(chemin: Path):
    if not chemin.exists():
        return []
    sortie = []
    for l in chemin.read_text(encoding="utf-8").splitlines():
        try:
            sortie.append(json.loads(l))
        except ValueError:
            continue
    return sortie


def quand(entete: dict, f: Path, tz) -> datetime:
    try:
        d = datetime.fromisoformat(str(entete.get("date") or ""))
        return d if d.tzinfo else d.replace(tzinfo=tz)
    except ValueError:
        return datetime.fromtimestamp(f.stat().st_mtime, tz)


def racine_echange(nom: str, parents: dict) -> str:
    """Le premier message de l'échange : on remonte `reponse_a` (au plus 50 crans, contre les boucles)."""
    vus = 0
    while parents.get(nom) and parents[nom] in parents and vus < 50:
        nom, vus = parents[nom], vus + 1
    return nom


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--etat", action="store_true", help="afficher le dossier, sans rien inscrire ni effacer")
    a = ap.parse_args()

    from hermes_constants import get_hermes_home
    reg = _config.charger()
    canal = reg.get("canal") or {}
    if not (canal.get("dossier") and canal.get("correspondant")):
        return 0                                                   # canal éteint : rien à faire, rien à dire
    tz = fuseau(reg["fuseau"])
    home = Path(get_hermes_home())
    dossier = home / canal["dossier"]
    racine = home / reg["dossier"]
    masque = langues.de_la_memoire(racine)
    T = masque.textes
    correspondant = _etiquette(canal["correspondant"], masque)
    agent = _etiquette(reg["nom_agent"], masque)
    uid_correspondant = int(canal.get("uid_correspondant", 0))
    uid_agent = int(canal.get("uid_agent", os.getuid()))
    maximum = int(canal.get("echanges_max") or ECHANGES_MAX)
    etat_dir = racine / "canal"
    inscrits_chemin, signales_chemin = etat_dir / "inscrits.jsonl", etat_dir / "signales.jsonl"
    inscrits = {x["fichier"]: x for x in jsonl(inscrits_chemin)}
    if not dossier.is_dir():
        return 0

    fichiers = sorted(f for f in dossier.glob("*.md") if f.is_file() and not f.name.startswith("."))
    if a.etat:
        for f in fichiers:
            e, _ = lire_message(f)
            print(f"{'inscrit ' if f.name in inscrits else 'en attente'}  uid {f.stat().st_uid:<6} {f.name}  "
                  f"(de: {e.get('de', '?')}, reponse_a: {e.get('reponse_a') or '-'})")
        return 0
    if uid_agent == uid_correspondant:
        print(f"canal: uid_agent == uid_correspondant ({uid_agent}) — à lancer depuis le compte de l'agent", file=sys.stderr)
        return 2
    etat_dir.mkdir(parents=True, exist_ok=True)
    with verrou(etat_dir / ".verrou"):                             # deux passages en même temps : un seul inscrit
        return passage(fichiers, dossier, racine, reg, tz, T, masque, correspondant, agent, uid_correspondant,
                       uid_agent, maximum, inscrits_chemin, signales_chemin)


def passage(fichiers, dossier, racine, reg, tz, T, masque, correspondant, agent, uid_correspondant, uid_agent,
            maximum, inscrits_chemin, signales_chemin) -> int:
    inscrits = {x["fichier"]: x for x in jsonl(inscrits_chemin)}     # relus SOUS le verrou
    signales = {(x["fichier"], x["raison"]) for x in jsonl(signales_chemin)}
    sortie, refuses, nouveaux = [], 0, []
    maintenant_s = time.time()
    for f in fichiers:
        if f.name in inscrits or maintenant_s - f.stat().st_mtime < FRAIS_S:
            continue
        entete, texte = lire_message(f)
        uid = f.stat().st_uid
        auteur = correspondant if uid == uid_correspondant else agent if uid == uid_agent else None
        if auteur is None:
            raison = T["canal_raison_proprietaire"].format(uid=uid, correspondant=correspondant, agent=agent)
        elif not entete or not texte:
            raison = T["canal_raison_vide"]
        elif _etiquette(entete.get("de", ""), masque) != auteur:
            raison = T["canal_raison_entete"].format(de=entete.get("de", ""), auteur=auteur)
        else:
            nouveaux.append((quand(entete, f, tz), f, auteur, entete, texte))
            continue
        if (f.name, raison) not in signales:                      # signalé (et compté) une fois, pas à chaque passage
            refuses += 1
            sortie.append(T["canal_refus"].format(fichier=f.name, raison=raison))
            ajouter_ligne_jsonl(signales_chemin, {"fichier": f.name, "raison": raison,
                                                  "ts": maintenant(tz).isoformat(timespec="seconds")})

    brut = Brut(racine, reg["seuil_lot_tokens"], tz, agent, reg["langue"]) if nouveaux else None
    for d, f, auteur, entete, texte in sorted(nouveaux, key=lambda x: (x[0], x[1].name)):
        sujet = entete.get("sujet") or "-"
        parent = inscrits.get(entete.get("reponse_a") or "")
        prefixe = (T["canal_entete_reponse"].format(sujet=sujet, qui=parent["de"], quand=parent["quand"]) if parent
                   else T["canal_entete"].format(sujet=sujet))
        brut.ecrire_ligne(SESSION, auteur, f"{prefixe} {texte}")
        fiche = {"fichier": f.name, "de": auteur, "a": _etiquette(entete.get("a", ""), masque) if entete.get("a") else "",
                 "sujet": sujet, "quand": d.strftime("%d/%m %H:%M"), "reponse_a": entete.get("reponse_a") or "",
                 "sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
                 "inscrit_le": maintenant(tz).isoformat(timespec="seconds")}
        ajouter_ligne_jsonl(inscrits_chemin, fiche)
        inscrits[f.name] = fiche
        if auteur == correspondant:
            entier = texte if len(texte) <= TEXTE_MAX else texte[:TEXTE_MAX] + "\n" + T["canal_suite"].format(fichier=f.name)
            # 15/11/2026 : l'agent réveillé par un cron n'a pas d'horloge (outils fichiers + mémoire) et ne doit pas inventer
            # l'heure de sa réponse — premier essai réel, Nexa a refusé, à raison. L'heure vient donc du code : le nom et
            # l'en-tête de la réponse, prêts à l'emploi.
            ici = maintenant(tz)
            sortie.append(T["canal_reveil"].format(de=auteur, a=fiche["a"] or agent, quand=fiche["quand"], sujet=sujet,
                                                    fichier=f.name) + "\n" + entier + "\n" + T["canal_repondre"].format(
                nom=f"{ici:%Y-%m-%d_%H%M}_{agent}-vers-{auteur}_<sujet>.md", de=agent, a=auteur,
                date=ici.isoformat(timespec="seconds"), reponse_a=f.name))

    # Le tampon : les `maximum` derniers échanges ; plus ancien = effacé, seulement s'il est inscrit au brut
    parents = {n: x.get("reponse_a") or "" for n, x in inscrits.items()}
    presents = {f.name for f in dossier.glob("*.md") if f.is_file()}
    echanges = {}
    for n in presents & set(inscrits):
        echanges.setdefault(racine_echange(n, parents), []).append(n)
    recents = sorted(echanges, key=lambda r: max(inscrits[n]["inscrit_le"] for n in echanges[r]), reverse=True)
    effaces = 0
    for r in recents[maximum:]:
        for n in echanges[r]:
            try:
                (dossier / n).unlink(); effaces += 1
            except OSError:
                pass

    if nouveaux or refuses or effaces:
        ajouter_ligne_jsonl(racine / "telemetrie" / "canal.jsonl", {
            "ts": maintenant(tz).isoformat(timespec="seconds"), "inscrits": len(nouveaux),
            "du_correspondant": sum(1 for x in nouveaux if x[2] == correspondant), "refuses": refuses, "effaces": effaces})
    if sortie:
        print("\n\n".join(sortie))
    return 0


if __name__ == "__main__":
    sys.exit(main())
