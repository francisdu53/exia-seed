"""Réponses vocales (26/10/2026) — conteneur jetable, vrai chargeur d'Hermès.

Quand l'agent répond en vocal, Hermès renvoie pour toute réponse « [[audio_as_voice]] » + « MEDIA:<fichier> » ; le
texte prononcé n'est que dans l'appel text_to_speech du tour. Du 23 au 25/10, 8 réponses vocales de Nexa sont entrées
dans le brut réduites à ce marqueur. Décision de Francis : une réponse vocale est traitée comme une réponse écrite."""
import importlib, json, sys
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
E = importlib.import_module(type(p).__module__ + ".enveloppes")

def voix(texte, arguments_en_texte=True):
    args = {"provider": "denise_temp", "output_path": "/opt/data/workspace/r.mp3", "text": texte}
    return {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function",
            "function": {"name": "text_to_speech", "arguments": json.dumps(args) if arguments_en_texte else args}}]}
MARQUEUR = "[[audio_as_voice]]\nMEDIA:/opt/data/workspace/r.mp3"
# forme relevée dans state.db le 26/10 : message de Francis, appel d'outil, résultat, réponse = marqueur
tour = [{"role": "user", "content": "Bonjour"}, voix("Réponse d'un tour PRÉCÉDENT."), {"role": "assistant", "content": "ok"},
        {"role": "user", "content": '"Il faudra rajouter des courgettes et du paprika."'},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c0", "type": "function",
         "function": {"name": "terminal", "arguments": "{}"}}]}, {"role": "tool", "content": "{}"},
        voix("C'est ajouté : courgettes et paprika."), {"role": "tool", "content": '{"success": true}'}]

print("── 1. la fonction ──")
r = E.reponse_vocale(MARQUEUR, tour, "(vocal) ")
verif("le texte prononcé remplace le marqueur", r == "(vocal) C'est ajouté : courgettes et paprika.", repr(r))
verif("rien du tour précédent", r and "PRÉCÉDENT" not in r)
verif("une réponse écrite passe inchangée (None)", E.reponse_vocale("C'est ajouté.", tour, "(vocal) ") is None)
verif("texte introuvable : le marqueur reste (None)", E.reponse_vocale(MARQUEUR, tour[:4], "(vocal) ") is None)
verif("sans messages : None", E.reponse_vocale(MARQUEUR, None) is None)
deux = tour + [voix("Deuxième phrase.", arguments_en_texte=False)]
verif("plusieurs lectures dans l'ordre, arguments en dict acceptés",
      E.reponse_vocale(MARQUEUR + "\nPS écrit", deux, "(vocal) ") ==
      "(vocal) C'est ajouté : courgettes et paprika.\nDeuxième phrase.\nPS écrit")

print("── 2. dans le brut, par sync_turn ──")
p.sync_turn('"Il faudra rajouter des courgettes et du paprika."', MARQUEUR, session_id="s1", messages=tour,
            turn_author={"name": "Francis"})
p.sync_turn("Merci, parfait.", "Avec plaisir.", session_id="s1", messages=tour + [{"role": "user", "content": "Merci, parfait."}])
brut = sorted((M / "raw").glob("*_open.md"))[0].read_text(encoding="utf-8")
verif("la réponse vocale est écrite en clair au nom de l'agent", "nexa] (vocal) C'est ajouté : courgettes et paprika." in brut,
      brut[brut.find("## "):][:300])
verif("le marqueur n'est plus dans le brut", "audio_as_voice" not in brut and "MEDIA:" not in brut)
verif("la réponse écrite suivante est intacte", "nexa] Avec plaisir." in brut)
verif("compteur reponses_vocales = 1", p._compteurs.get("reponses_vocales") == 1, str(p._compteurs.get("reponses_vocales")))

print(f"\n{ok} réussis, {ko} échoués")
sys.exit(1 if ko else 0)
