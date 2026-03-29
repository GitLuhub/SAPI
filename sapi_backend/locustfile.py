"""
Tests de carga con Locust para SAPI backend.

Requisitos:
    pip install locust

Uso:
    # Modo headless (CI)
    locust --headless -u 50 -r 5 --run-time 60s --host http://localhost/api/v1

    # Modo web UI
    locust --host http://localhost/api/v1
    # Abrir http://localhost:8089

Escenarios:
    SAPIReadUser  — 70% del tráfico: listado de documentos + consulta de estado
    SAPIWriteUser — 30% del tráfico: upload + corrección de campos

Meta de aceptación (RNF005):
    - P95 latencia < 500ms con 50 usuarios concurrentes
    - Tasa de error < 1%
"""
import io
import os
from locust import HttpUser, task, between, events


# ---------------------------------------------------------------------------
# Credenciales de prueba — ajustar a un entorno de staging
# ---------------------------------------------------------------------------
TEST_USER = os.getenv("LOCUST_TEST_USER", "admin")
TEST_PASS = os.getenv("LOCUST_TEST_PASS", "admin123")


class SAPIBaseUser(HttpUser):
    """Base class: hace login y almacena el access token."""

    abstract = True
    wait_time = between(1, 3)
    _token: str = ""

    def on_start(self):
        resp = self.client.post(
            "/auth/login/json",
            json={"username": TEST_USER, "password": TEST_PASS},
            name="/auth/login/json",
        )
        if resp.status_code == 200:
            self._token = resp.json().get("access_token", "")
        else:
            self._token = ""

    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}


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
        # El endpoint /metrics no requiere auth (prometheus scrape)
        self.client.get("/metrics", name="/metrics", catch_response=True)


class SAPIWriteUser(SAPIBaseUser):
    """Simula un usuario que sube y procesa documentos (30% del tráfico)."""

    weight = 3

    @task(3)
    def upload_document(self):
        # PDF mínimo válido de ~100 bytes
        pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        files = {"file": ("locust_test.pdf", io.BytesIO(pdf_content), "application/pdf")}
        with self.client.post(
            "/documents/",
            headers=self._auth(),
            files=files,
            name="/documents/ (upload)",
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 201, 400, 422):
                resp.failure(f"Unexpected status {resp.status_code}")
            else:
                resp.success()

    @task(1)
    def list_then_detail(self):
        resp = self.client.get("/documents/?size=5", headers=self._auth(), name="/documents/ (list)")
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
    p95 = stats.get_response_time_percentile(0.95) or 0
    err_rate = (stats.num_failures / stats.num_requests * 100) if stats.num_requests else 0

    print("\n" + "=" * 60)
    print("RESUMEN DE CARGA — SAPI")
    print(f"  Requests totales : {stats.num_requests}")
    print(f"  Errores          : {stats.num_failures} ({err_rate:.1f}%)")
    print(f"  P50 latencia     : {stats.get_response_time_percentile(0.5):.0f} ms")
    print(f"  P95 latencia     : {p95:.0f} ms")
    print(f"  RPS              : {stats.total_rps:.1f}")

    if p95 > 500:
        print("  ⚠ P95 supera los 500ms — revisar rendimiento")
    else:
        print("  ✓ P95 dentro del objetivo (<500ms)")

    if err_rate > 1:
        print("  ⚠ Tasa de error supera el 1%")
    else:
        print("  ✓ Tasa de error dentro del objetivo (<1%)")
    print("=" * 60)
