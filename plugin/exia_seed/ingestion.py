"""Le brut — ce que l'utilisateur dit et ce que l'agent répond, en AJOUT SEUL.

Spec §3.1 et §6.1. Invariant n°1 : un fichier brut n'est jamais modifié après sa fermeture, jamais
supprimé. Toute page consolidée doit pouvoir être retracée jusqu'à ses lignes de brut.

Périmètre (§3.1, mesuré le 20/09/2026) : la CONVERSATION seulement. Les sorties d'outils (94 % du
volume des sessions) n'entrent pas ici : `sync_turn` ne reçoit que le texte de l'utilisateur et la
réponse de l'agent.

Fichiers :
  raw/2026-09-22_01_open.md   le lot en cours (suffixe `_open`)
  raw/2026-09-22_01.md        un lot fermé : figé
  raw/.etat.json              le lot ouvert et son volume
  raw/.chaine.jsonl           registre d'intégrité : un lot fermé = une ligne (sha256 + précédent)
  raw/.dernier_tour.json      le dernier tour écrit (fichier + lignes) — survit aux fermetures
  raw/.retraits.jsonl         lignes que l'utilisateur a retirées — ajout seul, lu par la consolidation

Le hachage vit dans `.chaine.jsonl` et non dans l'en-tête du fichier : écrire l'empreinte DANS le
fichier modifierait le contenu qu'elle certifie.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Optional

from .enveloppes import est_avis
from .consignes import HORS_BRUT, HORS_BRUT_ET_PRECEDENT, RETRAIT_PRECEDENT, detecter
from .secrets import masquer
from .util import (ajouter_ligne_jsonl, ecrire_json, estimer_tokens, lire_json,
                   maintenant, sha256_fichier, verrou)

# Avis système (docs/12 §5) : Hermès injecte comme un message de l'utilisateur les comptes rendus de ses
# sous-agents et processus (« [ASYNC DELEGATION BATCH COMPLETE — …] », « [IMPORTANT: Background process … »),
# sans aucun signal qui les distingue — même auteur, même identifiant. Mesuré le 16/10 : 15 % du brut
# (≈ 41 000 tokens en trois semaines) relu par la consolidation pour UN fait sur 502. Ils sont écrits au nom de
# « systeme », réduits à leur en-tête et à leurs titres de tâches ; la réponse de l'agent, elle, reste entière.
AVIS_MAX = 400
QUI_AVIS = "systeme"


def resumer_avis(texte: str) -> Optional[str]:
    """None si ce n'est pas un avis système ; sinon sa première ligne et ses titres (« --- … », « Command: »)."""
    if not est_avis(texte):
        return None
    lignes = texte.splitlines()
    garde = [lignes[0][:200]] + [l[:200] for l in lignes[1:] if l.startswith("--- ") or l.startswith("Command:")]
    return " · ".join(garde)[:AVIS_MAX]


class Brut:
    def __init__(self, racine: Path, seuil_tokens: int, tz, nom_agent: str, langue: str = "fr"):
        self.dossier = racine / "raw"
        self.dossier.mkdir(parents=True, exist_ok=True)
        self.seuil = max(1000, int(seuil_tokens))
        self.tz = tz
        self.nom_agent = nom_agent
        self.langue = langue
        from . import langues
        self.masque = langues.masque(langue)      # consignes et repères dans la langue de la mémoire (docs/10)
        self._etat_chemin = self.dossier / ".etat.json"
        self._chaine = self.dossier / ".chaine.jsonl"
        self._verrou = self.dossier / ".verrou"
        self._dernier_tour = self.dossier / ".dernier_tour.json"
        self.retraits_chemin = self.dossier / ".retraits.jsonl"
        self.dernier_ferme = ""      # lu par le fournisseur pour déclencher la consolidation
        self.secrets_masques = 0     # compteurs repris par la télémétrie
        self.tours_non_conserves = 0
        self.retraits = 0

    # ── écriture d'un tour ──────────────────────────────────────────────────
    def ecrire_tour(self, session_id: str, qui: str, texte_utilisateur: str, texte_agent: str) -> int:
        """Ajoute un échange au lot en cours ; ferme et rouvre si le jour change ou si le seuil est atteint."""
        texte_utilisateur = (texte_utilisateur or "").strip()
        texte_agent = (texte_agent or "").strip()
        # Le brut est la source de vérité de la CONVERSATION, pas des secrets : on ne refuse pas
        # d'écrire un tour, on remplace la valeur sensible par un marqueur. Un mot de passe écrit
        # ici serait consolidé, versionné dans git et sauvegardé — il survivrait à sa rotation.
        texte_utilisateur, n1 = masquer(texte_utilisateur)
        texte_agent, n2 = masquer(texte_agent)
        self.secrets_masques += n1 + n2
        if not texte_utilisateur and not texte_agent:
            return 0
        avis = resumer_avis(texte_utilisateur)
        if avis is not None:
            # un avis n'est pas Francis : ni sa parole, ni ses consignes (« ne note pas ça » cité par un sous-agent)
            texte_utilisateur, qui = avis, QUI_AVIS
        consigne = None if avis is not None else detecter(texte_utilisateur, self.masque)
        with verrou(self._verrou):
            now = maintenant(self.tz)
            jour = now.date().isoformat()
            ajout = estimer_tokens(texte_utilisateur) + estimer_tokens(texte_agent)
            etat = lire_json(self._etat_chemin, {})
            if etat:
                if etat.get("jour") != jour:
                    self._fermer(etat, "changement_de_jour")
                    etat = {}
                elif etat.get("tokens", 0) > 0 and etat["tokens"] + ajout > self.seuil:
                    self._fermer(etat, "seuil_atteint")
                    etat = {}
            if not etat:
                etat = self._ouvrir(jour, session_id, now)
            heure = now.strftime("%H:%M")
            fichier_courant = self.dossier / etat["fichier"]
            # Consignes qui visent le tour PRÉCÉDENT (« oublie ce que je viens de dire », ou
            # « ne note pas ça » sans annonce) : le tour reste dans son fichier — ajout seul, et
            # un lot fermé est figé par sa chaîne d'intégrité — mais il est inscrit au journal des
            # retraits, que la consolidation respecte. Le dernier tour est suivi dans un fichier à
            # part : il survit à la fermeture du lot (défaut trouvé à la revue du 23/09/2026 — un
            # retrait juste après la fermeture de 23h55 ne savait plus quoi viser).
            if consigne in (RETRAIT_PRECEDENT, HORS_BRUT_ET_PRECEDENT):
                cible = lire_json(self._dernier_tour, {})
                if cible.get("fichier") and cible.get("lignes"):
                    a, b = cible["lignes"]
                    ajouter_ligne_jsonl(self.retraits_chemin, {
                        "fichier": cible["fichier"], "lignes": [a, b], "qui": qui,
                        "consigne": consigne, "ts": now.isoformat(timespec="seconds")})
                    with open(fichier_courant, "a", encoding="utf-8") as f:
                        f.write(self.masque.textes["repere_retrait"].format(heure=heure, fichier=cible["fichier"], a=a, b=b, qui=qui))
                    ecrire_json(self._dernier_tour, {})     # rien de plus ancien à viser
                    self.retraits += 1
            # Le tour qui porte la consigne n'est jamais écrit, quelle que soit la consigne : c'est
            # une instruction, pas un souvenir. Il ne reste qu'un repère, pour que l'histoire ne
            # comporte pas de trou invisible.
            # Défaut trouvé sur GPT-6 réel à la revue du 23/09/2026 : la demande « Oublie ce que je
            # viens de dire » était écrite. Le tour retiré étant caché au modèle, la demande
            # apparaissait juste après le tour D'AVANT — un tarif — et le modèle a logiquement
            # écarté le tarif. Un fait juste était perdu par la consigne censée en protéger un autre.
            if consigne:
                with open(fichier_courant, "a", encoding="utf-8") as f:
                    f.write(self.masque.textes["repere_non_conserve"].format(heure=heure, qui=qui))
                self.tours_non_conserves += 1
                ecrire_json(self._etat_chemin, etat)
                return 0
            lignes = []
            if texte_utilisateur:
                lignes.append(f"[{heure} {qui}] {texte_utilisateur}")
            if texte_agent:
                lignes.append(f"[{heure} {self.nom_agent}] {texte_agent}")
            premiere = sum(1 for _ in open(fichier_courant, encoding="utf-8")) + 1
            with open(fichier_courant, "a", encoding="utf-8") as f:
                f.write("\n".join(lignes) + "\n")
            # Nom FINAL du lot (sans « _open ») : c'est sous ce nom que la consolidation le lira.
            ecrire_json(self._dernier_tour, {
                "fichier": etat["fichier"].replace("_open.md", ".md"),
                "lignes": [premiere, premiere + len(lignes) - 1]})
            etat["tokens"] = etat.get("tokens", 0) + ajout
            etat["session_id"] = session_id
            ecrire_json(self._etat_chemin, etat)
            return len(lignes)

    def marquer(self, texte: str) -> None:
        """Repère non conversationnel (compression, reprise…) — commentaire HTML, ignoré à la lecture."""
        with verrou(self._verrou):
            etat = lire_json(self._etat_chemin, {})
            if etat:
                heure = maintenant(self.tz).strftime("%H:%M")
                with open(self.dossier / etat["fichier"], "a", encoding="utf-8") as f:
                    f.write(f"<!-- {heure} {texte} -->\n")

    def fermer(self, raison: str) -> str:
        with verrou(self._verrou):
            etat = lire_json(self._etat_chemin, {})
            return self._fermer(etat, raison) if etat else ""

    def lot_ouvert(self) -> Dict:
        return lire_json(self._etat_chemin, {})

    # ── interne ─────────────────────────────────────────────────────────────
    def _ouvrir(self, jour: str, session_id: str, now) -> Dict:
        # Premier numéro libre, ouvert OU fermé : compter les fichiers ne suffit pas si l'un
        # d'eux a été déplacé à la main — l'ouverture en mode « x » échouerait et le tour serait
        # perdu.
        numero = 1
        while (self.dossier / f"{jour}_{numero:02d}.md").exists() or \
                (self.dossier / f"{jour}_{numero:02d}_open.md").exists():
            numero += 1
        nom = f"{jour}_{numero:02d}_open.md"
        entete = (
            "---\n"
            "type: raw\n"
            f"date: {jour}\n"
            f"session_id: {session_id}\n"
            f"lang: {self.langue}\n"
            f"ouvert_le: {now.isoformat(timespec='seconds')}\n"
            "---\n\n"
            "## Échanges\n\n"
        )
        with open(self.dossier / nom, "x", encoding="utf-8") as f:
            f.write(entete)
        return {"fichier": nom, "jour": jour, "tokens": 0, "session_id": session_id,
                "ouvert_le": now.isoformat(timespec="seconds")}

    def _fermer(self, etat: Dict, raison: str) -> str:
        ouvert = self.dossier / etat["fichier"]
        if not ouvert.exists():
            ecrire_json(self._etat_chemin, {})
            return ""
        final = ouvert.with_name(ouvert.name.replace("_open.md", ".md"))
        os.replace(ouvert, final)
        precedent = "genese"
        if self._chaine.exists():
            lignes = self._chaine.read_text(encoding="utf-8").strip().splitlines()
            if lignes:
                precedent = __import__("json").loads(lignes[-1]).get("sha256", "genese")
        ajouter_ligne_jsonl(self._chaine, {
            "fichier": final.name,
            "sha256": sha256_fichier(final),
            "precedent": precedent,
            "ferme_le": maintenant(self.tz).isoformat(timespec="seconds"),
            "raison": raison,
            "tokens": etat.get("tokens", 0),
            "consolide": False,
        })
        ecrire_json(self._etat_chemin, {})
        self.dernier_ferme = final.name
        return final.name
