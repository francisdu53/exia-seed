"""EXIA SEED — la mémoire de Nexa, greffée sur Hermès comme fournisseur de mémoire (MemoryProvider).

WIKI EXIA + FCM EXIA : des pages markdown lisibles, indexées par un graphe associatif, sans vecteurs.
Spec complète : SPEC-EXIA-SEED.md (spécification interne, non publiée).

PHASE 1 — écriture seule. Le brut s'écrit, les lots se ferment et se signent. RIEN n'est injecté
dans le contexte de l'agent : `prefetch` et `system_prompt_block` rendent "". La phase 2 (rappel
injecté) n'est activée que sur décision de Francis.

Invariant n°4 : panne = dégradation, jamais blocage. Aucune méthode ne lève d'exception vers
Hermès ; en cas de problème, EXIA SEED journalise et se met en retrait.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider, spawn_context_thread

from . import config as _config
from .enveloppes import reponse_vocale
from .ingestion import Brut
from .registre import Registre
from .secrets import contient_secret
from .util import ecrire_json, fuseau, lire_json, maintenant, verrou

logger = logging.getLogger(__name__)

# Seule une session « principale » écrit : un cron, un sous-agent ou une passe de nettoyage ne
# sont pas une conversation avec l'utilisateur (spec §3.1 — périmètre du brut).
_CONTEXTES_ECRIVAINS = {None, "", "primary"}


def _hermes_home() -> Path:
    from hermes_constants import get_hermes_home
    return Path(get_hermes_home())


def _schemas() -> List[Dict[str, Any]]:
    """Les trois schémas d'outils, dans la langue configurée et au nom de l'utilisateur configuré (docs/10).
    Lus dans config.yaml SANS initialisation (Hermès les demande avant `initialize`, docs/07 D5) ; une
    configuration illisible donne ceux d'une mémoire par défaut — les outils restent déclarés."""
    from . import langues
    try:
        reg = _config.charger()
        m, nom = langues.masque(reg.get("langue") or langues.DEFAUT), str(reg.get("nom_utilisateur") or "")
    except Exception:
        m, nom = langues.masque(langues.DEFAUT), ""
    s = m.schemas_outils(nom)
    return [s["memoire_noter"], s["memoire_chercher"], s["memoire_lire"]]


def _etiquette(nom: str, m=None) -> str:
    """« Francis Babin » → « francis_babin » : le nom tel qu'il apparaît dans le brut. Sans nom : le mot du
    masque pour « utilisateur »."""
    if m is None:
        from . import langues
        m = langues.masque(langues.DEFAUT)
    defaut = m.textes["locuteur_defaut"]
    return re.sub(r"\s+", "_", (nom or defaut).strip().lower())[:30] or defaut


class ExiaSeedProvider(MemoryProvider):
    """Phase 1 : écrit le brut, ne rappelle rien."""

    def __init__(self) -> None:
        self._actif = False
        self._brut: Optional[Brut] = None
        self._registre: Optional[Registre] = None
        self._fil_consolidation = None
        self._reglages: Dict[str, Any] = {}
        self._racine: Optional[Path] = None
        self._session = ""
        self._contexte: Optional[str] = None
        self._compteurs = self._compteurs_vides()

    # ── contrat obligatoire ────────────────────────────────────────────────
    @property
    def name(self) -> str:
        return "exia_seed"

    def is_available(self) -> bool:
        return True            # aucune dépendance externe, aucun réseau

    def initialize(self, session_id: str, **kwargs) -> None:
        try:
            self._reglages = _config.charger()
            home = Path(kwargs.get("hermes_home") or _hermes_home())
            self._racine = home / self._reglages["dossier"]
            # La langue est une propriété de la mémoire (docs/10) : inscrite à sa création, et une
            # configuration qui demanderait une autre langue sur une mémoire existante est REFUSÉE.
            from . import langues
            self._masque = langues.fixer(self._racine, self._reglages["langue"])
            self._contexte = kwargs.get("agent_context")
            self._session = session_id or ""
            self._actif = self._contexte in _CONTEXTES_ECRIVAINS
            # Le registre accepte toutes les sessions : un cron qui repère une information
            # durable (un email de client) doit pouvoir la noter. Seul le brut est réservé à la
            # conversation principale.
            self._registre = Registre(self._racine, fuseau(self._reglages["fuseau"]))
            if self._actif:
                self._brut = Brut(
                    self._racine,
                    self._reglages["seuil_lot_tokens"],
                    fuseau(self._reglages["fuseau"]),
                    _etiquette(self._reglages["nom_agent"], self._masque),
                    self._reglages["langue"],
                )
            from .rappel import Rappeleur
            from .requete import Lecteur
            implicites = (self._reglages.get("nom_utilisateur"), self._reglages.get("nom_agent"),
                          *(self._reglages.get("interlocuteurs") or ()))
            partage = Rappeleur(self._racine, implicites=implicites)      # un seul cache pour tous
            self._lecteur = Lecteur(self._racine, rappeleur=partage)      # outils : tous contextes, lecture seule
            self._rappeleur = partage if (self._actif and (self._reglages.get("rappel_a_blanc", True)
                                                            or int(self._reglages.get("phase") or 1) >= 2)) else None
            logger.info("EXIA SEED phase %s : contexte=%s écriture=%s racine=%s",
                        self._reglages.get("phase"), self._contexte, self._actif, self._racine)
        except Exception:
            self._actif = False
            logger.exception("EXIA SEED : initialisation impossible — mémoire en retrait")

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """TOUJOURS les trois schémas, initialisé ou non (docs/07 D5).

        Défaut trouvé le 27/09/2026 : Hermès lit cette liste dans `add_provider`, AVANT
        `initialize_all` (agent_init.py:1278 puis 1286). Rendre [] tant que le plugin n'était pas
        initialisé laissait la table d'aiguillage vide : les trois appels réels de Nexa à
        memoire_noter (23, 25 et 26/09) ont échoué en « Unknown tool »."""
        return _schemas()

    def _t(self, cle: str, **valeurs) -> str:
        """Un texte rendu au modèle, dans la langue de la mémoire (celle par défaut si pas encore initialisé)."""
        m = getattr(self, "_masque", None)
        if m is None:
            from . import langues
            m = langues.masque(langues.DEFAUT)
        return m.textes[cle].format(**valeurs) if valeurs else m.textes[cle]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if tool_name in ("memoire_chercher", "memoire_lire"):
            return self._requete(tool_name, args or {})
        if tool_name != "memoire_noter":
            return json.dumps({"ok": False, "erreur": self._t("outil_inconnu", outil=tool_name)}, ensure_ascii=False)
        if not getattr(self, "_registre", None):
            return json.dumps({"ok": False, "erreur": self._t("pas_prete")}, ensure_ascii=False)
        texte = str((args or {}).get("texte") or "").strip()
        if not texte:
            return json.dumps({"ok": False, "erreur": self._t("texte_vide")}, ensure_ascii=False)
        if contient_secret(texte):
            self._compteurs["secrets_refuses"] += 1
            return json.dumps({"ok": False, "erreur": self._t("secret_refuse")}, ensure_ascii=False)
        try:
            ident = self._registre.noter(texte, source=f"outil:{self._contexte or 'primary'}",
                                         noeud=str(args.get("noeud") or ""),
                                         privacy=str(args.get("confidentialite") or "normal"))
            self._compteurs["notes_outil"] += 1
            return json.dumps({"ok": True, "id": ident,
                               "message": self._t("note_ok")},
                              ensure_ascii=False)
        except Exception as e:
            self._compteurs["erreurs"] += 1
            logger.exception("EXIA SEED : note impossible")
            return json.dumps({"ok": False, "erreur": str(e)[:200]}, ensure_ascii=False)

    def _requete(self, outil: str, args: Dict[str, Any]) -> str:
        """memoire_chercher / memoire_lire (docs/07 D3, D4) — lecture seule, jamais d'exception."""
        lecteur = getattr(self, "_lecteur", None)
        if lecteur is None:
            return json.dumps({"ok": False, "erreur": self._t("pas_prete")}, ensure_ascii=False)
        try:
            instant = maintenant(fuseau(self._reglages["fuseau"])).replace(tzinfo=None)
            if outil == "memoire_chercher":
                r = lecteur.chercher(str(args.get("requete") or ""), int(args.get("nombre") or 5), instant)
            else:
                r = lecteur.lire(str(args.get("sujet") or ""), instant)
            self._compteurs["requetes"] = self._compteurs.get("requetes", 0) + 1
            return json.dumps(r, ensure_ascii=False)
        except Exception as e:
            logger.exception("EXIA SEED : %s en échec", outil)
            return json.dumps({"ok": False, "erreur": f"{type(e).__name__}: {e}"[:200]}, ensure_ascii=False)

    def on_memory_write(self, action: str, target: str, content: str,
                        metadata: Optional[Dict[str, Any]] = None) -> None:
        """Recopie les écritures de la mémoire native d'Hermès dans le registre : rien de ce que
        l'agent retient ne doit rester hors d'EXIA SEED."""
        if not self._registre or not (content or "").strip() or contient_secret(content or ""):
            return
        try:
            prefixe = "[retiré de la mémoire native] " if action == "remove" else ""
            self._registre.noter(prefixe + content.strip(), source=f"memoire_native:{target}")
            self._compteurs["notes_natives"] += 1
        except Exception:
            self._compteurs["erreurs"] += 1
            logger.exception("EXIA SEED : recopie de la mémoire native impossible")

    # ── écriture ───────────────────────────────────────────────────────────
    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "",
                  messages: Optional[List[Dict[str, Any]]] = None,
                  turn_author: Optional[Dict[str, Any]] = None) -> None:
        if not (self._actif and self._brut):
            self._compteurs["tours_ignores"] += 1
            return
        t0 = time.perf_counter()
        try:
            qui = self._reglages.get("nom_utilisateur") or (turn_author or {}).get("name") or ""
            vocal = reponse_vocale(assistant_content, messages, self._masque.textes["repere_vocal"])
            if vocal is not None:                   # répondu en vocal : le texte prononcé, pas le seul marqueur
                assistant_content = vocal
                self._compteurs["reponses_vocales"] += 1
            self._brut.ecrire_tour(session_id or self._session, _etiquette(qui, self._masque),
                                   user_content or "", assistant_content or "")
            self._compteurs["tours_ecrits"] += 1
            for champ in ("tours_non_conserves", "retraits"):
                valeur = getattr(self._brut, champ)
                if valeur:
                    self._compteurs[champ] += valeur
                    setattr(self._brut, champ, 0)
            if self._brut.secrets_masques:
                self._compteurs["secrets_masques"] += self._brut.secrets_masques
                self._brut.secrets_masques = 0
                logger.warning("EXIA SEED : secret masqué dans le brut — il n'a pas été écrit en clair")
            if self._brut.dernier_ferme:
                self._brut.dernier_ferme = ""
                self._compteurs["lots_fermes"] += 1
                self._lancer_consolidation()
        except Exception:
            self._compteurs["erreurs"] += 1
            logger.exception("EXIA SEED : échec d'écriture du tour (la conversation continue)")
        finally:
            ms = (time.perf_counter() - t0) * 1000
            self._compteurs["ecriture_ms_total"] += ms
            self._compteurs["ecriture_ms_max"] = max(self._compteurs["ecriture_ms_max"], ms)

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        # Tout échange est déjà écrit par sync_turn : ici, on pose seulement un repère.
        if self._actif and self._brut:
            try:
                self._brut.marquer(f"compression de l'historique — {len(messages or [])} messages")
            except Exception:
                logger.exception("EXIA SEED : repère de compression impossible")
        return ""              # phase 1 : rien n'est injecté dans le résumé

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        self._fermer_lot("fin_de_session")

    def on_session_switch(self, new_session_id: str, *, parent_session_id: str = "", reset: bool = False,
                          rewound: bool = False, **kwargs) -> None:
        self._session = new_session_id or self._session
        if reset:
            self._fermer_lot("nouvelle_session")

    def shutdown(self) -> None:
        fil = self._fil_consolidation
        if fil is not None and fil.is_alive():
            fil.join(timeout=2.0)       # ne jamais bloquer l'arrêt de l'agent
        self._persister_compteurs()

    # ── consolidation (étape 4) ────────────────────────────────────────────
    def _lancer_consolidation(self) -> None:
        """Sur un fil à part : la consolidation appelle le modèle, elle ne doit JAMAIS retenir une
        réponse de l'agent. Si une consolidation tourne déjà, le lot attendra la suivante."""
        if not self._reglages.get("consolidation_auto", True):
            return
        if self._fil_consolidation is not None and self._fil_consolidation.is_alive():
            return
        self._fil_consolidation = spawn_context_thread(self._consolider, name="exia-seed-consolidation")
        self._fil_consolidation.start()

    def _consolider(self) -> None:
        """Lance la consolidation dans un PROCESSUS À PART — le même outil que le cron de 23h55.

        Défaut trouvé le 26/09/2026 : depuis le renouvellement des jetons Codex du 24/09 à 17h15 UTC,
        chaque consolidation lancée DANS la passerelle échouait (401 token_expired, 8 fois sur 8),
        alors que celle du cron, dans un processus neuf, réussissait (2 sur 2). Le client auxiliaire
        d'Hermès 0.21.3 relance après un 401 avec le jeton qu'il garde en mémoire vive ; un processus
        neuf relit les jetons sur disque. Bénéfice annexe : un appel LLM d'une minute ne tourne plus
        dans les fils de la passerelle. Le verrou de `Consolidateur` empêche tout chevauchement."""
        import subprocess
        import sys
        outil = Path(__file__).resolve().parent / "outils" / "consolider.py"
        try:
            r = subprocess.run([sys.executable, str(outil)], capture_output=True, text=True,
                               timeout=self._reglages.get("consolidation_delai_s", 900))
        except subprocess.TimeoutExpired:
            logger.error("EXIA SEED : consolidation interrompue après %ss (les lots restent en attente)",
                         self._reglages.get("consolidation_delai_s", 900))
            return
        except Exception:
            logger.exception("EXIA SEED : consolidation non lancée (les lots restent en attente)")
            return
        if r.returncode != 0:
            logger.error("EXIA SEED : consolidation échouée, code %s (les lots restent en attente) — %s",
                         r.returncode, (r.stderr or "").strip()[-600:])
        elif r.stdout.strip():
            logger.warning("EXIA SEED consolidation, anomalie : %s", r.stdout.strip()[:600])
        else:
            logger.info("EXIA SEED consolidation : faite (processus à part)")

    # ── phase 1 : rappel À BLANC — calculé et journalisé, jamais injecté ────────
    def system_prompt_block(self) -> str:
        return ""

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Étape 6a (docs/06-rappel.md, D1) : le rappel est calculé dans un fil à part et
        journalisé dans memoire/rappel/<date>.jsonl ; on rend "" tout de suite — zéro latence
        ajoutée à Nexa, rien d'injecté. Une panne du rappel est journalisée, jamais propagée (D8)."""
        r = getattr(self, "_rappeleur", None)
        if r is None or not query:
            return ""
        # docs/12 §8 : se rappeler du CONTENU, pas de l'enveloppe d'Hermès (« Model: ? » allumait JEV 42 fois)
        from .enveloppes import pour_rappel
        texte = pour_rappel(query)
        if not texte.strip():
            return ""
        if int(self._reglages.get("phase") or 1) >= 2:
            return self._souvenirs(r, query, texte)
        fil = getattr(self, "_fil_rappel", None)
        if fil is not None and fil.is_alive():
            return ""                                  # le précédent tourne encore : on n'empile pas
        instant = maintenant(fuseau(self._reglages["fuseau"]))

        def _calculer():
            try:
                res = r.rappeler(texte, instant.replace(tzinfo=None), amorce=self._amorce_du(instant))
                self._garder_amorce(instant, res)
                r.journaliser(query, res, instant)
            except Exception as e:
                logger.warning("EXIA SEED : rappel à blanc en échec (%s) — sans effet sur la réponse", e)
                try:
                    r.journaliser(query, {"statut": "echec", "erreur": f"{type(e).__name__}: {e}"[:200]}, instant)
                except Exception:
                    pass
        self._fil_rappel = spawn_context_thread(_calculer, name="exia-seed-rappel")
        self._fil_rappel.start()
        return ""

    def _amorce_du(self, instant):
        """docs/12 §10 — les sujets du message précédent, s'il date de moins de `amorce_minutes`."""
        prec = getattr(self, "_amorce", None)
        minutes = float(self._reglages.get("amorce_minutes", 30) or 0)
        if not prec or minutes <= 0 or (instant - prec[0]).total_seconds() > minutes * 60:
            return None
        return prec[1]

    def _garder_amorce(self, instant, res) -> None:
        if res.get("statut") == "ok":
            self._amorce = (instant, dict(res.get("entrees") or {}))

    def _souvenirs(self, r, query: str, texte: str = "") -> str:
        """Phase 2 (docs/11) : les souvenirs qui remontent avec le message, rendus à Hermès qui les joint au
        message de Francis (bloc <memory-context>). Calcul SYNCHRONE : Hermès attend au plus 8 s ; mesuré ≈ 5 ms,
        ≈ 0,5 s juste après une consolidation (cache reconstruit). Toujours journalisé, comme le rappel à blanc.
        Une panne rend "" : Nexa répond sans souvenirs, jamais sans réponse (D8)."""
        instant = maintenant(fuseau(self._reglages["fuseau"]))
        try:
            from .rappel import souvenirs
            res = r.rappeler(texte or query, instant.replace(tzinfo=None), amorce=self._amorce_du(instant))
            self._garder_amorce(instant, res)
            s = souvenirs(r.memoire(), res, float(self._reglages.get("souvenirs_seuil", 0.5)),
                          int(self._reglages.get("souvenirs_max_sujets", 3)),
                          int(self._reglages.get("souvenirs_faits_par_sujet", 2)))
            res["injecte"] = {"sujets": s["sujets"], "faits": s["faits"], "tokens": s["tokens"]}
            try:
                r.journaliser(query, res, instant)
            except Exception:
                pass
            return s["bloc"]
        except Exception as e:
            logger.warning("EXIA SEED : souvenirs en échec (%s) — Nexa répond sans eux", e)
            try:
                r.journaliser(query, {"statut": "echec", "erreur": f"{type(e).__name__}: {e}"[:200]}, instant)
            except Exception:
                pass
            return ""

    # ── interne ────────────────────────────────────────────────────────────
    def _fermer_lot(self, raison: str) -> None:
        if not (self._actif and self._brut):
            return
        try:
            if self._brut.fermer(raison):
                self._brut.dernier_ferme = ""
                self._compteurs["lots_fermes"] += 1
                self._lancer_consolidation()
        except Exception:
            self._compteurs["erreurs"] += 1
            logger.exception("EXIA SEED : fermeture du lot impossible")
        self._persister_compteurs()

    @staticmethod
    def _compteurs_vides() -> Dict[str, float]:
        return {"tours_ecrits": 0, "tours_ignores": 0, "lots_fermes": 0, "erreurs": 0,
                "notes_outil": 0, "notes_natives": 0, "secrets_refuses": 0, "secrets_masques": 0,
                "tours_non_conserves": 0, "retraits": 0, "reponses_vocales": 0,
                "ecriture_ms_total": 0.0, "ecriture_ms_max": 0.0}

    def _persister_compteurs(self) -> None:
        """Cumule les compteurs du processus dans telemetrie/<jour>.json (§9)."""
        if not self._racine or not any(v for k, v in self._compteurs.items() if not k.startswith("ecriture_")):
            return
        try:
            dossier = self._racine / "telemetrie"
            dossier.mkdir(parents=True, exist_ok=True)
            jour = maintenant(fuseau(self._reglages.get("fuseau", "UTC"))).date().isoformat()
            chemin = dossier / f"{jour}.json"
            with verrou(dossier / ".verrou"):
                cumul = lire_json(chemin, {})
                for k, v in self._compteurs.items():
                    cumul[k] = max(cumul.get(k, 0), v) if k.endswith("_max") else cumul.get(k, 0) + v
                ecrire_json(chemin, cumul)
            self._compteurs = self._compteurs_vides()
        except Exception:
            logger.exception("EXIA SEED : télémétrie non persistée")


def register(ctx) -> None:
    ctx.register_memory_provider(ExiaSeedProvider())
