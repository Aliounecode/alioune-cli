from fastapi.testclient import TestClient

DONNEES = {
    "email": "fatou@exemple.com",
    "nom_complet": "Fatou Diop",
    "mot_de_passe": "motdepasse123",
}


def _connecter(client: TestClient) -> str:
    reponse = client.post(
        "/api/auth/connexion",
        data={"username": DONNEES["email"], "password": DONNEES["mot_de_passe"]},
    )
    assert reponse.status_code == 200
    return reponse.json()["access_token"]


def test_inscription_connexion_puis_profil(client: TestClient) -> None:
    inscription = client.post("/api/auth/inscription", json=DONNEES)
    assert inscription.status_code == 201
    assert "mot_de_passe" not in inscription.text
    assert inscription.json()["role"] == "utilisateur"

    jeton = _connecter(client)
    profil = client.get("/api/auth/moi", headers={"Authorization": f"Bearer {jeton}"})
    assert profil.status_code == 200
    assert profil.json()["email"] == DONNEES["email"]


def test_inscription_refuse_un_email_deja_utilise(client: TestClient) -> None:
    client.post("/api/auth/inscription", json=DONNEES)

    assert client.post("/api/auth/inscription", json=DONNEES).status_code == 409


def test_connexion_refuse_un_mauvais_mot_de_passe(client: TestClient) -> None:
    client.post("/api/auth/inscription", json=DONNEES)

    reponse = client.post(
        "/api/auth/connexion", data={"username": DONNEES["email"], "password": "incorrect"}
    )

    assert reponse.status_code == 401


def test_profil_exige_un_jeton_valide(client: TestClient) -> None:
    assert client.get("/api/auth/moi").status_code == 401
    assert (
        client.get("/api/auth/moi", headers={"Authorization": "Bearer faux"}).status_code == 401
    )
