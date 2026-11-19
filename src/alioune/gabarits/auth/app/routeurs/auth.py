from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.base_de_donnees import SessionDep
from app.dependances import UtilisateurCourant
from app.schemas.auth import Jeton, UtilisateurCreation, UtilisateurLecture
from app.securite import creer_jeton_acces
from app.services import auth as service_auth

routeur = APIRouter(prefix="/auth", tags=["Authentification"])


@routeur.post("/inscription", response_model=UtilisateurLecture, status_code=status.HTTP_201_CREATED)
def inscrire(donnees: UtilisateurCreation, session: SessionDep):
    if service_auth.obtenir_par_email(session, donnees.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Un compte existe déjà avec cet e-mail"
        )
    return service_auth.creer_utilisateur(session, donnees)


@routeur.post("/connexion", response_model=Jeton)
def connecter(formulaire: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep):
    """Connexion OAuth2 (formulaire) : `username` = e-mail, `password` = mot de passe."""
    utilisateur = service_auth.authentifier(session, formulaire.username, formulaire.password)
    if utilisateur is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Jeton(access_token=creer_jeton_acces(utilisateur.email))


@routeur.get("/moi", response_model=UtilisateurLecture)
def lire_profil(utilisateur: UtilisateurCourant):
    return utilisateur
