#!/usr/bin/env python3
"""Rattrapage B+ (docs/08 §10) : rattacher aux concepts du thésaurus les faits écrits AVANT que la
consolidation ne le fasse d'elle-même.

    python3 outils/concepts.py [--graine thesaurus.json] [--ecrire]

1. `--graine` : un thésaurus de départ (celui du banc 8, validé par les mesures) — ses concepts et, pour
   les faits qu'il connaît, leurs rattachements. Sans graine : le thésaurus actuel de la mémoire.
2. Les faits encore sans concept sont rattachés par le modèle (GPT-6, effort bas), qui réutilise les
   concepts existants et ne crée un concept qu'avec son champ lexical — même consigne que la consolidation.
3. `--ecrire` : la métadonnée `concepts:` est ajoutée à chaque fait (le TEXTE du fait n'est jamais touché),
   le thésaurus enregistré, un commit git. Sans `--ecrire` : simulation (aucun appel au modèle).
Idempotent (un fait qui a déjà `concepts:` est laissé), sous le verrou de la consolidation.
"""
import argparse
import fcntl
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/opt/hermes")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))          # …/plugins
from exia_seed import config as _config                                # noqa: E402
from exia_seed import graphe as G                                      # noqa: E402
from exia_seed import pages as P                                       # noqa: E402

_RE_FAIT = re.compile(r"^(- (.*?) <!-- )(.*?)( -->)\s*$")
PAQUET = 50
SYS = ("Tu rattaches des faits d'une mémoire personnelle aux CONCEPTS de son thésaurus. Pour chaque fait numéroté, "
       "donne 1 à 3 concepts : des thèmes génériques et réutilisables, en minuscules_avec_tirets_bas. RÉUTILISE les "
       "concepts existants quand ils conviennent. Un concept n'est PAS un nom propre. Pour chaque concept NOUVEAU, donne "
       "5 à 10 synonymes ou mots proches en français et 2 à 4 en anglais. Réponds UNIQUEMENT par un objet JSON : "
       '{"faits": {"1": ["concept", ...], ...}, "concepts_nouveaux": {"concept": {"fr": [...], "en": [...]}}}')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--graine")
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()
    from hermes_constants import get_hermes_home
    racine = Path(get_hermes_home()) / _config.charger()["dossier"]
    th = json.loads(Path(a.graine).read_text(encoding="utf-8")) if a.graine else G.charger_thesaurus(racine)
    th.setdefault("concepts", {}); th.setdefault("faits", {})
    with open(racine / ".verrou-consolidation", "a+") as verrou:
        fcntl.flock(verrou, fcntl.LOCK_EX)
        lignes_par_page = {f: f.read_text(encoding="utf-8").splitlines() for f in sorted((racine / "pages").glob("*.md"))}
        sans = []                                          # (page, index de ligne, texte) sans concepts
        for f, lignes in lignes_par_page.items():
            for i, l in enumerate(lignes):
                m = _RE_FAIT.match(l)
                if m and not re.search(r"(^| )concepts:", m.group(3)):
                    sans.append((f, i, m.group(2).strip()))
        connus = {t for _, _, t in sans if t in th["faits"]}
        a_taguer = [t for _, _, t in sans if t not in th["faits"]]
        print(f"{len(sans)} faits sans concept · {len(connus)} connus de la graine · {len(a_taguer)} à rattacher par le modèle")
        if not a.ecrire:
            print("(simulation : rien n'est écrit, aucun appel au modèle)")
            return 0
        if a_taguer:
            from exia_seed.consolidation import appel_llm_hermes
            llm = appel_llm_hermes("low")
            for k in range(0, len(a_taguer), PAQUET):
                lot = a_taguer[k:k + PAQUET]
                existants = "\n".join(f"- {c} : {', '.join((v.get('fr') or [])[:4])}" for c, v in sorted(th["concepts"].items()))
                rep = llm([{"role": "system", "content": SYS}, {"role": "user", "content":
                           f"CONCEPTS EXISTANTS\n{existants or '(aucun)'}\n\nFAITS\n" + "\n".join(f"{i + 1}. {t}" for i, t in enumerate(lot))}])
                mm = re.search(r"\{.*\}", rep or "", re.S)
                try:
                    d = json.loads(mm.group(0)) if mm else {}
                except ValueError:
                    d = {}
                for c, v in (d.get("concepts_nouveaux") or {}).items():
                    s = P.slug(c)
                    if s and s not in th["concepts"] and isinstance(v, dict):
                        th["concepts"][s] = {"fr": [str(x) for x in (v.get("fr") or [])][:12], "en": [str(x) for x in (v.get("en") or [])][:6]}
                for i, cs in (d.get("faits") or {}).items():
                    try:
                        th["faits"][lot[int(i) - 1]] = [P.slug(c) for c in (cs or [])]
                    except (ValueError, IndexError):
                        continue
        ecrits = 0
        for f, i, texte in sans:
            cs = [c for c in dict.fromkeys(th["faits"].get(texte, [])) if c in th["concepts"]][:3]
            if not cs:
                continue
            m = _RE_FAIT.match(lignes_par_page[f][i])
            lignes_par_page[f][i] = m.group(1) + m.group(3) + f" concepts:{','.join(cs)}" + m.group(4)
            ecrits += 1
        for f, lignes in lignes_par_page.items():
            f.write_text("\n".join(lignes) + "\n", encoding="utf-8")
        # On garde TOUT concept utilisé par un fait de la mémoire — pas seulement ceux de la graine.
        # Défaut trouvé au test (27/09) : filtrer sur la graine effaçait les concepts créés par la consolidation.
        utilises = {c for lignes in lignes_par_page.values() for l in lignes
                    for mm in [re.search(r"(?:^| )concepts:(\S+)", l)] if mm for c in mm.group(1).split(",")}
        actuel = G.charger_thesaurus(racine).get("concepts") or {}
        fusion = {**{c: v for c, v in th["concepts"].items()}, **actuel}          # l'existant prime
        G.enregistrer_thesaurus(racine, {"concepts": {c: v for c, v in fusion.items() if c in utilises}, "faits": {}})
        print(f"{ecrits} faits rattachés · {len(utilises & set(th['concepts']))} concepts au thésaurus")
        if (racine / ".git").exists():
            subprocess.run(["git", "-C", str(racine), "add", "-A"], capture_output=True)
            r = subprocess.run(["git", "-C", str(racine), "-c", "user.name=EXIA SEED", "-c", "user.email=exia-seed@localhost",
                                "commit", "-q", "-m", f"B+ : {ecrits} faits rattachés aux concepts du thésaurus"], capture_output=True, text=True)
            print("  git :", "ok" if r.returncode == 0 else (r.stderr or r.stdout).strip()[:200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
