from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import obtenir_parametres
from app.routeurs import accueil, routeur_api, sante

parametres = obtenir_parametres()

app = FastAPI(
    title=parametres.nom_application,
    version=parametres.version,
    description="API générée avec alioune.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=parametres.liste_origines,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accueil.routeur)
app.include_router(sante.routeur)
app.include_router(routeur_api)
