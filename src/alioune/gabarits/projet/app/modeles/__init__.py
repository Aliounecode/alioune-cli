"""Modèles SQLAlchemy.

Chaque modèle doit être importé ici pour qu'Alembic le détecte
(alioune ajoute les imports sous le marqueur ci-dessous).
"""

from app.modeles.base import Base, HorodatageMixin

# --- alioune:modeles ---

__all__ = ["Base", "HorodatageMixin"]
