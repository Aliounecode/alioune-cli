from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Classe de base de tous les modèles."""


class HorodatageMixin:
    """Ajoute `cree_le` et `modifie_le` à un modèle."""

    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    modifie_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
