from fastapi.testclient import TestClient

from app.config import obtenir_parametres


def test_la_page_d_accueil_affiche_le_nom_du_projet(client: TestClient) -> None:
    reponse = client.get("/")

    assert reponse.status_code == 200
    assert obtenir_parametres().nom_application in reponse.text
    assert "/docs" in reponse.text


def test_la_documentation_interactive_est_disponible(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
