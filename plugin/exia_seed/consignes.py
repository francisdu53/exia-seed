"""Les consignes de mémoire — le contrôle de l'utilisateur sur ce qui est retenu.

Demande de Francis, 22/09/2026 : *« il n'existe aucun moyen de dire ne l'écris pas du tout. »*

Deux formules, détectées SANS appel au modèle — un garde-fou ne doit pas dépendre d'un jugement :

    « ne note pas ça : … »          → le tour n'est PAS écrit dans le brut (la consigne annonce
                                      ce qui suit). Seul un repère horodaté reste.

    « ne note pas ça » (sans « : ») → le tour n'est pas écrit ET le tour précédent devient non
                                      consolidable : « ça » désigne ce qui vient d'être dit.

    « oublie ce que je viens de     → le tour précédent est marqué NON CONSOLIDABLE.
      dire »                          Il reste dans le fichier (ajout seul), mais la
                                      consolidation ne le lira pas : il n'ira jamais en page.

Le second cas ne supprime rien : effacer une ligne d'un fichier en ajout seul romprait la chaîne
d'intégrité et la promesse de la couche brute. On marque, on n'efface pas — et le marquage est
lisible par un humain.
"""
from __future__ import annotations


# Les formules (« oublie ce que je viens de dire », « ne note pas ça », « forget what I just said »…)
# viennent du masque de langue (docs/10) : `re_retrait_precedent`, `re_hors_brut`, `re_annonce`.

HORS_BRUT = "hors_brut"                          # vise le message courant seulement
HORS_BRUT_ET_PRECEDENT = "hors_brut_et_precedent"  # vise le message courant ET le précédent
RETRAIT_PRECEDENT = "retrait_precedent"


def detecter(texte: str, m=None) -> str:
    """Rend la consigne trouvée dans le message de l'utilisateur, ou une chaîne vide.

    Le retrait est testé en premier : « ne note pas ce que je viens de dire » contient aussi la
    formule du hors-brut.
    """
    if m is None:
        from . import langues
        m = langues.masque(langues.DEFAUT)
    t = texte or ""
    if m.re_retrait_precedent.search(t):
        return RETRAIT_PRECEDENT
    trouve = m.re_hors_brut.search(t)
    if trouve:
        # Défaut trouvé à la revue du 23/09/2026 : « Je prépare une surprise pour un ami. » puis, au
        # message suivant, « Ne note pas ça, c'est personnel. » — la version 1 ne protégeait
        # que le second message ; la confidence partait au consolidateur. En français, « ça »
        # sans annonce désigne ce qui vient d'être dit. Dans le doute, l'oubli l'emporte :
        # au pire, un tour anodin n'est pas consolidé ; jamais une confidence ne l'est.
        return HORS_BRUT if m.re_annonce.match(t[trouve.end():]) else HORS_BRUT_ET_PRECEDENT
    return ""
