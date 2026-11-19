"""Logique métier de l'authentification."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modeles.utilisateur import ROLE_UTILISATEUR, Utilisateur
from app.schemas.auth import UtilisateurCreation
from app.securite import hacher_mot_de_passe, verifier_mot_de_passe

# Hachage factice : permet de vérifier un mot de passe même quand l'e-mail est inconnu,
# pour que le temps de réponse ne révèle pas si un compte existe.
_HACHE_FACTICE = hacher_mot_de_passe("mot-de-passe-factice")


def obtenir_par_email(session: Session, email: str) -> Utilisateur | None:
    return session.scalar(select(Utilisateur).where(Utilisateur.email == email.lower()))


def creer_utilisateur(
    session: Session, donnees: UtilisateurCreation, role: str = ROLE_UTILISATEUR
) -> Utilisateur:
    utilisateur = Utilisateur(
        email=donnees.email.lower(),
        nom_complet=donnees.nom_complet,
        mot_de_passe_hache=hacher_mot_de_passe(donnees.mot_de_passe),
        role=role,
    )
    session.add(utilisateur)
    session.commit()
    session.refresh(utilisateur)
    return utilisateur


def authentifier(session: Session, email: str, mot_de_passe: str) -> Utilisateur | None:
    utilisateur = obtenir_par_email(session, email)
    if utilisateur is None:
        verifier_mot_de_passe(mot_de_passe, _HACHE_FACTICE)
        return None
    if not verifier_mot_de_passe(mot_de_passe, utilisateur.mot_de_passe_hache):
        return None
    return utilisateur if utilisateur.est_actif else None
