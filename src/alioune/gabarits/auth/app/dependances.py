"""Dépendances FastAPI d'authentification.

Usage dans une route :

    @routeur.get("/secret")
    def secret(utilisateur: UtilisateurCourant): ...

    @routeur.delete("/{id}")
    def supprimer(id: int, admin: UtilisateurAdmin): ...
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.base_de_donnees import SessionDep
from app.modeles.utilisateur import ROLE_ADMIN, Utilisateur
from app.securite import decoder_jeton
from app.services import auth as service_auth

schema_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/connexion")


def utilisateur_courant(
    jeton: Annotated[str, Depends(schema_oauth2)], session: SessionDep
) -> Utilisateur:
    erreur = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants invalides ou expirés",
        headers={"WWW-Authenticate": "Bearer"},
    )
    email = decoder_jeton(jeton)
    if email is None:
        raise erreur
    utilisateur = service_auth.obtenir_par_email(session, email)
    if utilisateur is None or not utilisateur.est_actif:
        raise erreur
    return utilisateur


UtilisateurCourant = Annotated[Utilisateur, Depends(utilisateur_courant)]


def exiger_role(*roles: str) -> Callable[[Utilisateur], Utilisateur]:
    """Fabrique une dépendance qui n'accepte que les utilisateurs ayant l'un de ces rôles."""

    def verifier(utilisateur: UtilisateurCourant) -> Utilisateur:
        if utilisateur.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé")
        return utilisateur

    return verifier


UtilisateurAdmin = Annotated[Utilisateur, Depends(exiger_role(ROLE_ADMIN))]
