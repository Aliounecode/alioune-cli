from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UtilisateurCreation(BaseModel):
    email: EmailStr
    nom_complet: str = Field(min_length=1, max_length=255)
    mot_de_passe: str = Field(min_length=8, max_length=128)


class UtilisateurLecture(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    nom_complet: str
    role: str
    est_actif: bool
    cree_le: datetime


class Jeton(BaseModel):
    access_token: str
    token_type: str = "bearer"
