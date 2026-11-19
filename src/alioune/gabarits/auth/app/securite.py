"""Hachage des mots de passe (Argon2) et jetons d'accès JWT."""

from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.config import obtenir_parametres

_hacheur = PasswordHash.recommended()

CLE_PAR_DEFAUT = "changez-moi"


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    return _hacheur.hash(mot_de_passe)


def verifier_mot_de_passe(mot_de_passe: str, hache: str) -> bool:
    return _hacheur.verify(mot_de_passe, hache)


def creer_jeton_acces(sujet: str, duree: timedelta | None = None) -> str:
    """Crée un JWT signé dont le sujet (`sub`) est l'e-mail de l'utilisateur."""
    parametres = obtenir_parametres()
    if parametres.environnement != "developpement" and parametres.cle_secrete == CLE_PAR_DEFAUT:
        raise RuntimeError("CLE_SECRETE doit être définie (autre que la valeur par défaut) hors développement.")
    expiration = datetime.now(timezone.utc) + (
        duree or timedelta(minutes=parametres.duree_jeton_minutes)
    )
    return jwt.encode(
        {"sub": sujet, "exp": expiration},
        parametres.cle_secrete,
        algorithm=parametres.algorithme_jwt,
    )


def decoder_jeton(jeton: str) -> str | None:
    """Retourne le sujet du jeton, ou None s'il est invalide ou expiré."""
    parametres = obtenir_parametres()
    try:
        charge = jwt.decode(
            jeton, parametres.cle_secrete, algorithms=[parametres.algorithme_jwt]
        )
    except jwt.InvalidTokenError:
        return None
    sujet = charge.get("sub")
    return sujet if isinstance(sujet, str) else None
