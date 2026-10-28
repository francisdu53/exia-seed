"""Le garde-fou anti-secret — une seule définition pour toute la mémoire.

Une mémoire se relit, se consolide, se versionne dans git et finit dans une sauvegarde. Un mot de
passe ou une clé d'API n'y a rien à faire : il y survivrait à sa propre rotation.

DEUX COMPORTEMENTS, selon la couche :
  · le REGISTRE refuse la note        — c'est un geste délibéré, on peut le refuser et le dire ;
  · le BRUT masque la valeur          — on ne peut pas refuser d'écrire la conversation, mais on
                                        remplace le secret par un marqueur : la phrase reste, la
                                        valeur disparaît.

CE QUI N'EST PAS FILTRÉ, VOLONTAIREMENT : les longues suites de chiffres. Un SIRET
(123 456 789 00012), un IBAN, un numéro de téléphone ou un montant doivent rester mémorisables.
"""
from __future__ import annotations

import re
from typing import Tuple

MARQUEUR = "[secret masqué]"

# Formes reconnaissables d'un secret. Le mot-clé « mot de passe » est accepté jusqu'à 40 caractères
# avant sa valeur : « Le mot de passe NAS : … » (défaut trouvé au test du 22/09, le mot « NAS »
# s'intercalait), ainsi que la forme « mon mdp est … ».
RE_SECRET = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|xox[bp]-[A-Za-z0-9-]{10,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\b(?:mot de passe|password|passwd|mdp|passphrase|code secret|code pin)\b"
    # La valeur court JUSQU'À LA FIN DE LA LIGNE, pas jusqu'au premier espace : une phrase de
    # passe (« correct horse battery staple ») ou un mot de passe à espace (« Ab12 cD!7 »)
    # fuyait sinon à partir de son deuxième mot. Défaut trouvé à la revue du 23/09/2026.
    # Masquer quelques mots de trop est l'échec sûr ; en laisser passer un ne l'est pas.
    r"(?:.{0,40}?[:=][ \t]*[^\n]+|\s+(?:est|is)\s+\S{4,}[^\n]*))", re.I)


def contient_secret(texte: str) -> bool:
    return bool(RE_SECRET.search(texte or ""))


def masquer(texte: str) -> Tuple[str, int]:
    """Rend (texte masqué, nombre de masquages). Le mot-clé est conservé, la valeur disparaît.

    « Le mot de passe NAS : Ab12!cD »  →  « Le mot de passe NAS : [secret masqué] »
    « wifi : mdp : correct horse battery »  →  « wifi : mdp : [secret masqué] »  (tout le reste de la ligne)
    """
    if not texte:
        return texte, 0
    compteur = 0

    def _remplacer(m: re.Match) -> str:
        nonlocal compteur
        compteur += 1
        trouve = m.group(0)
        # Forme « mot-clé … : valeur » : on garde tout jusqu'au séparateur, on masque la valeur.
        sep = re.search(r"[:=]\s*", trouve)
        if sep:
            return trouve[:sep.end()] + MARQUEUR
        # Forme « mot-clé est valeur » : on garde le verbe.
        verbe = re.search(r"\s+(est|is)\s+", trouve, re.I)
        if verbe:
            return trouve[:verbe.end()] + MARQUEUR
        return MARQUEUR

    return RE_SECRET.sub(_remplacer, texte), compteur
