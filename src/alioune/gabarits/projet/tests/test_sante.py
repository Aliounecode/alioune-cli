from fastapi.testclient import TestClient


def test_sante_indique_que_la_base_est_connectee(client: TestClient) -> None:
    reponse = client.get("/sante")

    assert reponse.status_code == 200
    assert reponse.json() == {"statut": "ok", "base_de_donnees": "connectee"}
