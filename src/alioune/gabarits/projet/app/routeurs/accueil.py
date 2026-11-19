from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import obtenir_parametres

routeur = APIRouter()

gabarits = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "gabarits")


@routeur.get("/", response_class=HTMLResponse, include_in_schema=False)
def accueil(request: Request) -> HTMLResponse:
    """Page d'accueil affichée au premier `uvicorn`."""
    parametres = obtenir_parametres()
    return gabarits.TemplateResponse(
        request,
        "accueil.html",
        {
            "nom": parametres.nom_application,
            "version": parametres.version,
            "environnement": parametres.environnement,
        },
    )
