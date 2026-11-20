import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import obtenir_parametres

routeur = APIRouter()

RACINE = Path(__file__).resolve().parent.parent.parent
gabarits = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "gabarits")


def _version_alioune() -> str | None:
    """Version d'alioune qui a généré le projet (lue dans alioune.json, absente = None)."""
    try:
        return json.loads((RACINE / "alioune.json").read_text(encoding="utf-8")).get("version_alioune")
    except (OSError, ValueError):
        return None


def _ressources(request: Request) -> list[dict]:
    """Ressources de l'API (une par tag OpenAPI, hors « Système »), avec leur nombre de routes."""
    comptes: dict[str, int] = {}
    for operations in request.app.openapi().get("paths", {}).values():
        for operation in operations.values():
            for tag in operation.get("tags", []):
                if tag != "Système":
                    comptes[tag] = comptes.get(tag, 0) + 1
    return [{"nom": tag, "routes": nombre} for tag, nombre in comptes.items()]


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
            "version_alioune": _version_alioune(),
            "ressources": _ressources(request),
        },
    )
