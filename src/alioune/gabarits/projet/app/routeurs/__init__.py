"""Routeurs de l'API.

`accueil` et `sante` sont à la racine ; les routeurs métier sont regroupés
sous `/api` (alioune les inscrit ici automatiquement).
"""

from fastapi import APIRouter

# --- alioune:imports ---

routeur_api = APIRouter(prefix="/api")

# --- alioune:inclusions ---
