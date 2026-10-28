"""Pour chaque déclenchement « mot d'alias » (mot → sujet), le sujet a-t-il apporté un fait utile ? Réglage seul."""
import json, sys, math
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, "/opt/hermes"); sys.path.insert(0, "/opt/data/workspace/banc-souvenirs/plugins")
from exia_seed.rappel import Rappeleur
B = Path("/opt/data/workspace/banc-souvenirs")
L = [json.loads(l) for l in (B / "juge.jsonl").read_text(encoding="utf-8").splitlines()]
L = [l for l in L if l["tranche"] == sys.argv[1]]
rap = {}; ev = []
for l in L:
    h = l["instantane"]
    if h not in rap: rap[h] = Rappeleur(B / "instantanes" / h, implicites=("francis", "nexa"))
    r = rap[h]; m = r.memoire(); a = r.activer(m, l["message"])
    utiles = set(l["utiles"]); montre = {x["fait"] for x in l["V1"] if x["score"] >= 0.5}
    par_noeud = defaultdict(set)
    for i, x in enumerate(m.faits): pass
    for e in a["etages"].get("mot_alias", []):
        w, n = e.split("→")
        faits_n = {x["fait"] for x in l["V1"] if x["score"] >= 0.5 and x.get("page") == m.fichiers.get(n)}
        if not faits_n: continue                      # le sujet n'a rien montré : pas de bruit visible
        alias_n = [a_ for a_ in (m.alias_par_noeud.get(n, []) if hasattr(m, "alias_par_noeud") else [])]
        dff = sum(1 for x in m.faits if w[:5] in x["racines"])
        brut = (B / "instantanes" / h / "pages" / m.fichiers.get(n, "x")).read_text(encoding="utf-8") if m.fichiers.get(n) else ""
        import re as _re, unicodedata as _u
        sans = lambda t: _u.normalize("NFKD", t).encode("ascii", "ignore").decode()
        porteurs = [a for a in _re.findall(r"^  - (.+)$", brut.split("\n---")[0], _re.M) if w in sans(a.lower()).replace("’", " ").replace("'", " ").split()]
        maj = any(any(sans(x).lower() == w and x[:1].isupper() for x in _re.split(r"[\s’']+", a)) for a in porteurs)
        mots_alias = min((len(a.split()) for a in porteurs), default=0)
        ev.append({"maj": maj, "long": mots_alias, "w": w, "n": n, "utile": bool(faits_n & utiles), "dff": dff, "nf": len(m.faits),
                   "cibles": len(m.mots_alias.get(w, ())) or 0, "avis": l["message"].startswith("[")})
print(len(ev), "déclenchements visibles ;", sum(e["utile"] for e in ev), "utiles")
def table(nom, f):
    g = defaultdict(lambda: [0, 0])
    for e in ev: g[f(e)][0] += e["utile"]; g[f(e)][1] += 1
    print(nom, " · ".join(f"{k}: {u}/{t}" for k, (u, t) in sorted(g.items())))
table("rareté dans les faits (nb faits portant le mot) :", lambda e: "0" if e["dff"] == 0 else "1-3" if e["dff"] <= 3 else "4-9" if e["dff"] <= 9 else "10+")
table("sujets portant le mot :", lambda e: e["cibles"])
table("mot en MAJUSCULE dans son alias :", lambda e: e["maj"])
table("longueur de l alias porteur :", lambda e: min(e["long"], 4))
table("message = avis système :", lambda e: e["avis"])
