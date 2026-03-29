"""
Tests de carga con Locust para SAPI backend.

Requisitos:
    pip install locust

Uso:
    # Modo headless (CI)
    locust --headless -u 50 -r 5 --run-time 60s \
      --host http://localhost:8000/api/v1 \
      --csv=locust_results -f locustfile.py

    # Modo web UI
    locust --host http://localhost:8000/api/v1 -f locustfile.py
    # Abrir http://localhost:8089

Escenarios:
    SAPIReadUser  — 70% del tráfico: listado de documentos + consulta de estado
    SAPIWriteUser — 30% del tráfico: upload + detalle de documento

Meta de aceptación (RNF005):
    - P95 latencia < 500ms con 50 usuarios concurrentes
    - Tasa de error < 1%

Notas de diseño:
    - El login se realiza UNA sola vez antes de iniciar el test (evita el rate
      limiter de 5 req/min en /auth/login/json). Todos los usuarios virtuales
      comparten ese token. En un escenario real de staging se usarían múltiples
      cuentas de prueba.
    - El endpoint /metrics vive fuera de /api/v1 — se consulta con URL absoluta.
"""
import io
import os
import threading

import requests as _requests
from locust import HttpUser, task, between, events


# ---------------------------------------------------------------------------
# Credenciales de prueba — ajustar a un entorno de staging
# ---------------------------------------------------------------------------
TEST_USER = os.getenv("LOCUST_TEST_USER", "admin")
TEST_PASS = os.getenv("LOCUST_TEST_PASS", "admin123")

# Token compartido entre todos los usuarios virtuales
_shared_token: str = ""
_token_lock = threading.Lock()
_token_ready = threading.Event()


# ---------------------------------------------------------------------------
# Login único antes de iniciar el test
# ---------------------------------------------------------------------------

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Obtiene el access token una sola vez, antes de que arranquen los usuarios."""
    global _shared_token
    host = environment.host.rstrip("/")
    # El host ya incluye /api/v1
    url = f"{host}/auth/login/json"
    try:
        resp = _requests.post(
            url,
            json={"username": TEST_USER, "password": TEST_PASS},
            timeout=10,
        )
        if resp.status_code == 200:
            _shared_token = resp.json().get("access_token", "")
            print(f"\n✓ Login exitoso como '{TEST_USER}' — token obtenido")
        else:
            print(f"\n✗ Login fallido ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        print(f"\n✗ Error en login: {e}")
    finally:
        _token_ready.set()


# ---------------------------------------------------------------------------
# Clases de usuario
# ---------------------------------------------------------------------------

class SAPIBaseUser(HttpUser):
    abstract = True
    wait_time = between(1, 3)

    def on_start(self):
        # Espera a que el token esté disponible (máx. 30s)
        _token_ready.wait(timeout=30)

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {_shared_token}"}


class SAPIReadUser(SAPIBaseUser):
    """Simula un usuario que principalmente consulta documentos (70% del tráfico)."""

    weight = 7

    @task(5)
    def list_documents(self):
        self.client.get("/documents/", headers=self._auth(), name="/documents/ (list)")

    @task(3)
    def list_documents_filtered(self):
        self.client.get(
            "/documents/?status=PROCESSED&size=10",
            headers=self._auth(),
            name="/documents/ (filtered)",
        )

    @task(2)
    def list_document_types(self):
        self.client.get("/documents/types/", headers=self._auth(), name="/documents/types/")

    @task(1)
    def get_metrics(self):
        """Prometheus scrape — URL absoluta porque vive fuera de /api/v1."""
        base = self.host.split("/api/v1")[0]
        with self.client.get(
            f"{base}/metrics",
            name="/metrics",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")


class SAPIWriteUser(SAPIBaseUser):
    """Simula un usuario que sube y consulta documentos (30% del tráfico)."""

    weight = 3

    @task(3)
    def upload_document(self):
        pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        files = {"file": ("locust_test.pdf", io.BytesIO(pdf_content), "application/pdf")}
        with self.client.post(
            "/documents/",
            headers=self._auth(),
            files=files,
            name="/documents/ (upload)",
            catch_response=True,
        ) as resp:
            # 200/201/202 = éxito; 400/422 = validación esperada (también OK)
            if resp.status_code in (200, 201, 202, 400, 422):
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")

    @task(2)
    def list_then_detail(self):
        resp = self.client.get(
            "/documents/?size=5",
            headers=self._auth(),
            name="/documents/ (list)",
        )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            if items:
                doc_id = items[0]["id"]
                self.client.get(
                    f"/documents/{doc_id}",
                    headers=self._auth(),
                    name="/documents/{id}",
                )


# ---------------------------------------------------------------------------
# Reporte al finalizar
# ---------------------------------------------------------------------------

@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    stats = environment.stats.total
    if stats.num_requests == 0:
        return

    p50 = stats.get_response_time_percentile(0.50) or 0
    p95 = stats.get_response_time_percentile(0.95) or 0
    err_rate = stats.num_failures / stats.num_requests * 100

    print("\n" + "=" * 60)
    print("RESUMEN DE CARGA — SAPI")
    print(f"  Requests totales : {stats.num_requests}")
    print(f"  Errores          : {stats.num_failures} ({err_rate:.1f}%)")
    print(f"  P50 latencia     : {p50:.0f} ms")
    print(f"  P95 latencia     : {p95:.0f} ms")
    print(f"  RPS              : {stats.total_rps:.1f}")
    print()
    print("  Objetivos (RNF005):")
    print(f"  {'✓' if p95 <= 500 else '⚠'} P95 < 500ms  →  {p95:.0f} ms")
    print(f"  {'✓' if err_rate <= 1 else '⚠'} Error < 1%  →  {err_rate:.1f}%")
    print("=" * 60)
