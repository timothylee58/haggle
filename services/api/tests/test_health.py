from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_hosted_database_urls_are_made_async() -> None:
    from app.config import Settings

    for given in (
        "postgres://u:p@h:5432/db",
        "postgresql://u:p@h/db",
        "postgresql+asyncpg://u:p@h/db",
    ):
        assert Settings(_env_file=None, database_url=given).database_url.startswith(
            "postgresql+asyncpg://u:p@h"
        )


def test_the_frontend_url_is_always_an_allowed_origin() -> None:
    from app.config import Settings

    s = Settings(
        _env_file=None,
        frontend_url="https://haggle-web.onrender.com/",
        cors_origins=["http://localhost:3000"],
    )
    assert s.allowed_origins == ["http://localhost:3000", "https://haggle-web.onrender.com"]
    again = Settings(
        _env_file=None, frontend_url="http://localhost:3000", cors_origins=["http://localhost:3000"]
    )
    assert again.allowed_origins == ["http://localhost:3000"]
