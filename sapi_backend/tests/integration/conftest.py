"""
Fixtures para tests de integración con PostgreSQL real.

Uso:
    pytest tests/integration/ --integration

Los tests marcados con @pytest.mark.integration se saltan automáticamente
a menos que se pase la flag --integration o la variable de entorno
INTEGRATION_DATABASE_URL esté definida.

En CI/CD o con Docker Compose activo:
    INTEGRATION_DATABASE_URL=postgresql+psycopg2://sapi_user:sapi_password@localhost:5432/sapi_db \
    python -m pytest tests/integration/ -v
"""
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.api.v1.deps import get_db


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Ejecutar tests de integración que requieren PostgreSQL real",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--integration"):
        skip_integration = pytest.mark.skip(reason="Pasar --integration para ejecutar")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


@pytest.fixture(scope="session")
def pg_engine():
    """Motor SQLAlchemy conectado a PostgreSQL real.

    Requiere INTEGRATION_DATABASE_URL o que el stack Docker esté activo en localhost:5432.
    """
    url = os.getenv(
        "INTEGRATION_DATABASE_URL",
        "postgresql+psycopg2://sapi_user:sapi_password@localhost:5432/sapi_db_test",
    )
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def pg_session(pg_engine):
    """Sesión PostgreSQL con rollback al finalizar cada test."""
    connection = pg_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def pg_client(pg_session):
    """TestClient del backend usando una sesión PostgreSQL real."""
    def override_get_db():
        yield pg_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
