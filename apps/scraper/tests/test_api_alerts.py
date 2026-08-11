from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from api.alerts import router as alerts_router
from database import get_session
from database.models import Alert as AlertModel


@pytest.fixture()
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        json_serializer=lambda obj: __import__("json").dumps(obj, ensure_ascii=False),
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture()
def app(test_engine):
    def override_get_session() -> Iterator[Session]:
        with Session(test_engine) as session:
            yield session

    app = FastAPI()
    app.include_router(alerts_router)
    app.dependency_overrides[get_session] = override_get_session
    return app


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def create_test_alert(client: TestClient):
    created: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def _create(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        response = client.post("/alerts", json=payload)
        assert response.status_code == 201
        body = response.json()
        created.append((payload, body))
        return payload, body

    yield _create

    for payload, body in created:
        client.delete(f"/alerts/{payload['chat_id']}/{body['id']}")


def test_create_alert_returns_201_with_id(client: TestClient) -> None:
    payload = {
        "chat_id": 123456,
        "alert_name": "Apto 2 quartos Ponta Verde",
        "min_price": 200_000,
        "max_price": 400_000,
        "neighbourhoods": ["Ponta Verde", "Jatiúca"],
    }

    response = client.post("/alerts", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body == {"id": 1, "message": "Alerta criado com sucesso"}


def test_create_alert_validates_payload(client: TestClient) -> None:
    payload = {
        "chat_id": "nao-e-int",
        "min_price": 200_000,
    }

    response = client.post("/alerts", json=payload)

    assert response.status_code == 422


def test_create_alert_rejects_empty_price_range(client: TestClient) -> None:
    payload = {
        "chat_id": 123456,
        "neighbourhoods": ["Ponta Verde"],
    }

    response = client.post("/alerts", json=payload)

    assert response.status_code == 422


def test_create_alert_persists_expected_fields(test_engine, client: TestClient) -> None:
    payload = {
        "chat_id": 123456,
        "alert_name": "Casa em Jatiúca",
        "min_price": 150_000,
        "max_price": 300_000,
        "neighbourhoods": ["Jatiúca"],
    }

    response = client.post("/alerts", json=payload)
    assert response.status_code == 201
    alert_id = response.json()["id"]

    with Session(test_engine) as verify_session:
        stored = verify_session.get(AlertModel, alert_id)
        assert stored is not None
        assert stored.chat_id == payload["chat_id"]
        assert stored.alert_name == payload["alert_name"]
        assert stored.min_price == payload["min_price"]
        assert stored.max_price == payload["max_price"]
        assert stored.neighbourhoods == payload["neighbourhoods"]
        assert stored.active is True


def test_list_alerts_returns_empty_when_no_alerts(client: TestClient) -> None:
    response = client.get("/alerts/123456")

    assert response.status_code == 200
    body = response.json()
    assert body == {"alerts": [], "total": 0}


def test_list_alerts_returns_user_alerts(client: TestClient, create_test_alert: Any) -> None:
    create_test_alert(
        {
            "chat_id": 123456,
            "alert_name": "Apto 1",
            "min_price": 100_000,
            "neighbourhoods": ["Ponta Verde"],
        }
    )
    create_test_alert(
        {
            "chat_id": 123456,
            "alert_name": "Apto 2",
            "max_price": 500_000,
            "neighbourhoods": ["Jatiúca"],
        }
    )

    response = client.get("/alerts/123456")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["alert_name"] for item in body["alerts"]] == ["Apto 2", "Apto 1"]


def test_list_alerts_excludes_alerts_from_other_users(
    test_engine, client: TestClient, create_test_alert: Any
) -> None:
    _, alert_a = create_test_alert(
        {
            "chat_id": 123456,
            "alert_name": "Meu alerta",
            "min_price": 100_000,
            "neighbourhoods": ["Ponta Verde"],
        }
    )
    create_test_alert(
        {
            "chat_id": 999999,
            "alert_name": "Alerta de outro",
            "min_price": 200_000,
            "neighbourhoods": ["Jatiúca"],
        }
    )

    response = client.get("/alerts/123456")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["alerts"][0]["id"] == alert_a["id"]


def test_get_inactive_alert_returns_200(
    test_engine, client: TestClient, create_test_alert: Any
) -> None:
    _, created = create_test_alert(
        {
            "chat_id": 123456,
            "alert_name": "Inativo",
            "min_price": 100_000,
            "neighbourhoods": ["Ponta Verde"],
        }
    )

    with Session(test_engine) as session:
        alert = session.get(AlertModel, created["id"])
        assert alert is not None
        alert.active = False
        session.commit()

    response = client.get(f"/alerts/123456/{created['id']}")
    assert response.status_code == 200
    assert response.json()["active"] is False


def test_create_alert_requires_alert_name_and_neighbourhoods(client: TestClient) -> None:
    response = client.post("/alerts", json={"chat_id": 123456, "min_price": 100_000})
    assert response.status_code == 422

    response = client.post(
        "/alerts",
        json={"chat_id": 123456, "alert_name": "Sem bairros", "min_price": 100_000},
    )
    assert response.status_code == 422


def test_list_active_alerts_excludes_inactive(
    test_engine, client: TestClient, create_test_alert: Any
) -> None:
    _, active_body = create_test_alert(
        {
            "chat_id": 123456,
            "alert_name": "Alert A",
            "min_price": 100_000,
            "neighbourhoods": ["Ponta Verde"],
        }
    )
    _, inactive_body = create_test_alert(
        {
            "chat_id": 123456,
            "alert_name": "Alert B",
            "min_price": 100_000,
            "neighbourhoods": ["Ponta Verde"],
        }
    )

    with Session(test_engine) as session:
        alert = session.get(AlertModel, inactive_body["id"])
        assert alert is not None
        alert.active = False
        session.commit()

    response = client.get("/alerts/123456/active")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["alerts"][0]["alert_name"] == "Alert A"


def test_get_alert_returns_expected_fields(client: TestClient, create_test_alert: Any) -> None:
    payload, created = create_test_alert(
        {
            "chat_id": 123456,
            "alert_name": "Casa em Jatiúca",
            "min_price": 150_000,
            "max_price": 300_000,
            "neighbourhoods": ["Jatiúca"],
        }
    )

    response = client.get(f"/alerts/{payload['chat_id']}/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["chat_id"] == 123456
    assert body["alert_name"] == "Casa em Jatiúca"
    assert body["min_price"] == 150_000
    assert body["max_price"] == 300_000
    assert body["neighbourhoods"] == ["Jatiúca"]
    assert body["active"] is True
    assert "created_at" in body


def test_get_alert_returns_404_when_missing(client: TestClient) -> None:
    response = client.get("/alerts/123456/999")

    assert response.status_code == 404


def test_get_alert_returns_404_when_wrong_chat(client: TestClient, create_test_alert: Any) -> None:
    payload, created = create_test_alert(
        {
            "chat_id": 123456,
            "alert_name": "Casa",
            "min_price": 150_000,
            "neighbourhoods": ["Jatiúca"],
        }
    )

    response = client.get(f"/alerts/999999/{created['id']}")

    assert response.status_code == 404


def test_delete_alert_returns_success_message(client: TestClient, create_test_alert: Any) -> None:
    payload, created = create_test_alert(
        {
            "chat_id": 123456,
            "alert_name": "Casa",
            "min_price": 150_000,
            "neighbourhoods": ["Jatiúca"],
        }
    )

    response = client.delete(f"/alerts/{payload['chat_id']}/{created['id']}")

    assert response.status_code == 200
    assert response.json() == {"message": "Alerta removido com sucesso"}


def test_delete_alert_removes_record(
    test_engine, client: TestClient, create_test_alert: Any
) -> None:
    payload, created = create_test_alert(
        {
            "chat_id": 123456,
            "alert_name": "Casa",
            "min_price": 150_000,
            "neighbourhoods": ["Jatiúca"],
        }
    )

    response = client.delete(f"/alerts/{payload['chat_id']}/{created['id']}")
    assert response.status_code == 200

    with Session(test_engine) as verify_session:
        stored = verify_session.get(AlertModel, created["id"])
        assert stored is None


def test_delete_alert_returns_404_when_missing(client: TestClient) -> None:
    response = client.delete("/alerts/123456/999")

    assert response.status_code == 404


def test_delete_alert_returns_404_when_wrong_chat(
    client: TestClient, create_test_alert: Any
) -> None:
    payload, created = create_test_alert(
        {
            "chat_id": 123456,
            "alert_name": "Casa",
            "min_price": 150_000,
            "neighbourhoods": ["Jatiúca"],
        }
    )

    response = client.delete(f"/alerts/999999/{created['id']}")

    assert response.status_code == 404
