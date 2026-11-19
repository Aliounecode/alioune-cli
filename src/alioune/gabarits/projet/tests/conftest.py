from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.base_de_donnees import obtenir_session
from app.main import app
from app.modeles import Base


@pytest.fixture()
def session_test() -> Iterator[Session]:
    """Base SQLite en mémoire, recréée pour chaque test."""
    moteur = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(moteur, "connect")
    def activer_cles_etrangeres(connexion_dbapi, _enregistrement) -> None:
        curseur = connexion_dbapi.cursor()
        curseur.execute("PRAGMA foreign_keys=ON")
        curseur.close()

    Base.metadata.create_all(moteur)
    fabrique = sessionmaker(bind=moteur, autoflush=False, expire_on_commit=False)
    with fabrique() as session:
        yield session
    Base.metadata.drop_all(moteur)
    moteur.dispose()


@pytest.fixture()
def client(session_test: Session) -> Iterator[TestClient]:
    app.dependency_overrides[obtenir_session] = lambda: session_test
    with TestClient(app) as client_http:
        yield client_http
    app.dependency_overrides.clear()
