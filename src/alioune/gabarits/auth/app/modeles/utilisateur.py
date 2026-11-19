from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.modeles.base import Base, HorodatageMixin

ROLE_UTILISATEUR = "utilisateur"
ROLE_ADMIN = "admin"


class Utilisateur(HorodatageMixin, Base):
    __tablename__ = "utilisateurs"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    nom_complet: Mapped[str] = mapped_column(String(255))
    mot_de_passe_hache: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default=ROLE_UTILISATEUR)
    est_actif: Mapped[bool] = mapped_column(Boolean, default=True)
