"""Le temps des faits : quand une phrase a été DITE, et quand la chose ARRIVE.

Ajouté le 26/09/2026 (révision R2). Défaut constaté sur la première journée réelle (23/09) :
« un rendez-vous pour lundi 16h45 chez Amandine » a été consolidé en « lundi », sans date. Le modèle
recevait l'heure de chaque ligne ([12:20 francis]) mais ni la date ni le jour de la semaine, et les
modèles de langage calculent mal un jour de semaine. Or « lundi », « demain », « ce soir » n'ont de
sens que rapportés au moment où on les dit : perdre ce moment, c'est perdre le sens.

Trois moments, trois responsables :
    dit_le      quand la phrase a été dite ─ écrit par le CODE, toujours, depuis la source citée
    event_time  quand la chose arrive      ─ proposé par le modèle, VÉRIFIÉ ici
    echeance    la date limite             ─ idem

La vérification est symbolique (aucun appel au modèle, < 1 ms) et fail-closed : une date que les
sources ne justifient pas est retirée ; le fait, lui, est gardé, et son `dit_le` permet toujours de
recalculer « lundi » plus tard.

Règle de Francis (23/09/2026) : un jour de semaine cité sans date désigne le PROCHAIN jour de ce nom.
Dit un lundi, « lundi » = dans 7 jours (pour le jour même, on dit « aujourd'hui »).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

# Les mots de la langue (jours, mois, « demain », nombres en lettres, formats de date) viennent du
# masque de la mémoire (docs/10) : chaque fonction qui lit ou écrit une date en reçoit un, `m`. Le code
# central le passe toujours ; sans masque, c'est celui d'une mémoire sans fichier `.langue` (le français).


def _m(m):
    if m is not None:
        return m
    from . import langues
    return langues.masque(langues.DEFAUT)


def en_clair(d: date, m=None) -> str:
    """date(2026, 9, 23) → « mercredi 23 septembre 2026 »."""
    return _m(m).en_clair(d)

_RE_HEURE_LIGNE = re.compile(r"^\[(\d\d):(\d\d) ")
_RE_HORODATAGE = re.compile(r"^\s*\[\d\d:\d\d [^\]]*\]\s*")


def sans_horodatage(ligne: str) -> str:
    """« [16:55 francis] Mon tarif est de 45 € » → « Mon tarif est de 45 € ».

    L'horodatage est une métadonnée de la ligne, pas une parole : ses chiffres ne doivent jamais
    justifier un nombre ou une heure. Défaut trouvé le 26/09/2026 (présent depuis la v0.1) : un
    tarif inventé à « 55 € » passait le contrôle parce que la ligne citée avait été dite à 16h55."""
    return _RE_HORODATAGE.sub("", ligne or "")


def dit_le(jour_lot: date, heure_ouverture: Optional[str], ligne: str) -> Optional[str]:
    """Moment où une ligne de brut a été dite, en heure de Paris : « 2026-09-23T12:20 ».

    Un lot porte la date de son ouverture ; une ligne dont l'heure précède l'ouverture a été dite
    après minuit, donc le lendemain."""
    m = _RE_HEURE_LIGNE.match(ligne)
    if not m:
        return jour_lot.isoformat()
    hhmm = f"{m.group(1)}:{m.group(2)}"
    jour = jour_lot + timedelta(days=1) if heure_ouverture and hhmm < heure_ouverture else jour_lot
    return f"{jour.isoformat()}T{hhmm}"


def _lire(valeur) -> Tuple[Optional[date], Optional[str]]:
    """« 2026-09-28 » ou « 2026-09-28T16:45[:00][+02:00] » → (date, « 16:45 » ou None)."""
    m = re.match(r"^\s*(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?", str(valeur or ""))
    if not m:
        return None, None
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None, None
    heure = f"{m.group(4)}:{m.group(5)}" if m.group(4) and f"{m.group(4)}:{m.group(5)}" != "00:00" else None
    return d, heure


def nombres_en_lettres(texte: str, m=None) -> set:
    """« à partir de huit heures » → {"8"}. Défaut trouvé le 26/09/2026 : Francis avait écrit « huit
    heures », le modèle « 8 h », et le contrôle rejetait un fait VRAI (le 25/09, puis l'heure le 26/09)."""
    m = _m(m)
    return {str(m.composes.get(x, m.nombres_lettres.get(x))) for x in m.re_nombres_lettres.findall((texte or "").lower())}


def _nombres(texte: str, m=None) -> set:
    return {n.lstrip("0") or "0" for n in re.findall(r"\d+", texte)} | nombres_en_lettres(texte, m)


def _mois_cites(bas: str, m=None) -> set:
    m = _m(m)
    sortie = {i + 1 for i, nom in enumerate(m.mois) if re.search(rf"\b{nom}\b", bas)}
    return sortie | {num for nom, num in m.mois_variantes.items() if re.search(rf"\b{nom}\b", bas)}


def prochain(ancre: date, jour_semaine: int) -> date:
    """Le prochain `jour_semaine` STRICTEMENT après `ancre` (dit un lundi, « lundi » = +7)."""
    return ancre + timedelta(days=((jour_semaine - ancre.weekday()) % 7) or 7)


def precedent(ancre: date, jour_semaine: int) -> date:
    return ancre - timedelta(days=((ancre.weekday() - jour_semaine) % 7) or 7)


def _date_justifiee(d: date, cite: str, ancre: date, m=None) -> bool:
    m = _m(m)
    bas = cite.lower()
    if d == ancre:                                   # ce qui arrive ou est arrivé le jour même
        return True
    nombres = _nombres(bas, m)
    # 1. Écrite en toutes lettres ou en chiffres : « 28.09.2026 », « 28/09 », « 2 octobre »
    if str(d.day) in nombres and (str(d.month) in nombres or d.month in _mois_cites(bas, m)):
        return True
    # 2. Un jour de semaine : le prochain de ce nom, ou le précédent s'il est dit « dernier »
    #    (en anglais, un jour cité seul peut aussi désigner le passé : masque, `jour_nu_passe`)
    for i, nom in enumerate(m.jours):
        if re.search(rf"\b{nom}\b", bas):
            if d == prochain(ancre, i):
                return True
            if (m.jour_nu_passe or re.search(m.motif_jour_passe.format(jour=nom), bas)) and d == precedent(ancre, i):
                return True
    # 3. Les mots relatifs
    for mot, decalage in m.relatifs:
        if mot in bas:
            if d == ancre + timedelta(days=decalage):
                return True
            bas = bas.replace(mot, " ")                 # « après-demain » ne vaut pas « demain »
    if m.semaine_prochaine and m.semaine_prochaine in bas:
        lundi = prochain(ancre, 0)
        if lundi <= d <= lundi + timedelta(days=6):
            return True
    if m.semaine_derniere and m.semaine_derniere in bas:
        lundi = ancre - timedelta(days=ancre.weekday() + 7)          # lundi de la semaine précédente
        if lundi <= d <= lundi + timedelta(days=6):
            return True
    return False


def _heure_justifiee(heure: str, cite: str, m=None) -> bool:
    h, mn = heure.split(":")
    nombres = _nombres(cite, m)
    return (h.lstrip("0") or "0") in nombres and (mn == "00" or mn.lstrip("0") in nombres)


def verifier(valeur, cite: str, ancre: Optional[date], m=None) -> Tuple[Optional[str], Optional[str]]:
    """Rend (valeur vérifiée ou None, raison d'un retrait ou None).

    La date doit être justifiée par les lignes citées ; l'heure aussi, sinon seule la date reste —
    c'est l'invention du 25/09 (« de 8 h à 18 h » pour « toute la journée »)."""
    if valeur in (None, "", "null"):
        return None, None
    d, heure = _lire(valeur)
    if d is None:
        return None, f"date illisible : {valeur}"
    if ancre is None:
        return None, "date de la conversation inconnue"
    cite = " ".join(sans_horodatage(l) for l in (cite or "").split("\n"))
    cite = re.sub(r"(?:^|\s)\[\d\d:\d\d [^\]]*\]", " ", cite)      # lignes jointes par des espaces
    if not _date_justifiee(d, cite, ancre, m):
        return None, f"date non justifiée par les sources : {d.isoformat()}"
    if heure and not _heure_justifiee(heure, cite, m):
        return d.isoformat(), f"heure non justifiée par les sources : {heure}"
    return (f"{d.isoformat()}T{heure}" if heure else d.isoformat()), None


def suffixe(fait: str, valeur: Optional[str], prefixe: str = "→", m=None) -> str:
    """« (→ lundi 28/09/2026 à 16h45) » — sauf si le fait porte déjà cette date en clair."""
    m = _m(m)
    d, heure = _lire(valeur)
    if d is None:
        return ""
    bas = fait.lower()
    if str(d.day) in _nombres(bas, m) and (str(d.month) in _nombres(bas, m) or d.month in _mois_cites(bas, m)) \
            and str(d.year) in _nombres(bas, m):
        return ""
    return f" ({prefixe} {m.date_suffixe(d, heure)})"
