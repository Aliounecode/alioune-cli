"""Crée un administrateur (ou promeut un compte existant).

    python -m app.creer_admin admin@exemple.com --nom "Nom Complet"
"""

import argparse
import getpass
import sys

from pydantic import ValidationError

from app.base_de_donnees import SessionLocale
from app.modeles.utilisateur import ROLE_ADMIN
from app.schemas.auth import UtilisateurCreation
from app.services import auth as service_auth


def principal() -> int:
    analyseur = argparse.ArgumentParser(description="Crée ou promeut un administrateur.")
    analyseur.add_argument("email")
    analyseur.add_argument("--nom", default="Administrateur", help="Nom complet")
    arguments = analyseur.parse_args()

    with SessionLocale() as session:
        existant = service_auth.obtenir_par_email(session, arguments.email)
        if existant is not None:
            existant.role = ROLE_ADMIN
            session.commit()
            print(f"Le compte {existant.email} est maintenant administrateur.")
            return 0

        mot_de_passe = getpass.getpass("Mot de passe (8 caractères minimum) : ")
        if mot_de_passe != getpass.getpass("Confirmation : "):
            print("Les mots de passe ne correspondent pas.", file=sys.stderr)
            return 1
        try:
            donnees = UtilisateurCreation(
                email=arguments.email, nom_complet=arguments.nom, mot_de_passe=mot_de_passe
            )
        except ValidationError as erreur:
            print(erreur, file=sys.stderr)
            return 1
        utilisateur = service_auth.creer_utilisateur(session, donnees, role=ROLE_ADMIN)
        print(f"Administrateur {utilisateur.email} créé.")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
