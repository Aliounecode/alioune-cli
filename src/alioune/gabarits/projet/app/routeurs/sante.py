from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.base_de_donnees import SessionDep

routeur = APIRouter(tags=["Système"])


@routeur.get("/sante")
def verifier_sante(session: SessionDep) -> dict[str, str]:
    """Indique que l'API répond et si la base de données est joignable."""
    try:
        session.execute(text("SELECT 1"))
        base_de_donnees = "connectee"
    except SQLAlchemyError:
        base_de_donnees = "indisponible"
    return {"statut": "ok", "base_de_donnees": base_de_donnees}
