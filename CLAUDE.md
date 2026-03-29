# SAPI — Contexto del Proyecto para Claude Code

## ¿Qué es SAPI?
**Sistema de Automatización y Procesamiento Documental Inteligente.** Plataforma AI que extrae, clasifica y resume automáticamente **facturas y contratos** usando Google Gemini API, con revisión humana (Human-in-the-Loop).

---

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | FastAPI + Python 3.11, SQLAlchemy 2.0, Alembic, PostgreSQL 15 |
| Async | Celery + Redis 7 (colas `ai_processing` y `notifications`) |
| IA | Google Gemini API — `gemini-2.5-flash` (clasificar, extraer entidades, resumir) |
| Frontend | React 18 + TypeScript, Vite, Tailwind CSS, Zustand, React Query |
| Infra | Docker Compose (8 contenedores), Nginx como reverse proxy |
| Rate Limiting | slowapi (basado en IP) |

---

## Arquitectura (8 contenedores)

```
Nginx (80) → React Frontend (web_client:80)
           → FastAPI Backend (backend:8000) → PostgreSQL (db:5432)
                                            → Redis (redis:6379) → ai_worker (Celery, concurrency=2)
                                                                  → notification_worker (Celery, concurrency=2)
                                                                  → celery_beat
```

**Routing Nginx:**
- `/` → React frontend (`web_client:80`)
- `/api/` → FastAPI backend (`backend:8000`)
- `/uploads/` → archivos estáticos servidos por Nginx
- Client max body size: 15 MB | Read timeout: 300s

---

## Estructura de Directorios Clave

```
SAPI/
├── docker-compose.yml
├── .env / .env.example
├── nginx/conf.d/default.conf
├── sapi_backend/
│   ├── app/
│   │   ├── main.py                            # Entry point FastAPI + CORS + rate limiter
│   │   ├── core/
│   │   │   ├── config.py                      # Settings Pydantic (JWT, CORS, DB, AI, storage, email)
│   │   │   ├── security.py                    # JWT access+refresh tokens, bcrypt
│   │   │   └── limiter.py                     # slowapi Limiter (IP-based)
│   │   ├── api/v1/
│   │   │   ├── api.py                         # Router agregador (/auth, /users, /documents)
│   │   │   ├── deps.py                        # get_db, get_current_user, get_current_superuser
│   │   │   └── endpoints/
│   │   │       ├── auth.py                    # login (form+JSON), register, refresh, logout
│   │   │       ├── documents.py               # CRUD documentos + preview/download/data
│   │   │       └── users.py                   # CRUD usuarios (admin) + /me
│   │   ├── db/
│   │   │   ├── base.py                        # SQLAlchemy declarative_base
│   │   │   ├── session.py                     # Engine (pool 10/20) + SessionLocal
│   │   │   └── models/
│   │   │       ├── user.py                    # User (UUID PK, roles, is_superuser)
│   │   │       ├── document.py                # Document + DocumentType
│   │   │       └── extracted_data.py          # ExtractedData + AuditLog
│   │   ├── schemas/
│   │   │   ├── user.py                        # UserCreate, UserResponse, UserRole enum
│   │   │   ├── document.py                    # DocumentResponse, ExtractedFieldResponse, etc.
│   │   │   ├── token.py                       # Token, TokenPayload
│   │   │   └── common.py                      # PaginatedResponse[T], MessageResponse
│   │   ├── services/
│   │   │   ├── ai_service.py                  # GeminiAIService (classify, extract, summarize)
│   │   │   ├── storage_service.py             # StorageService (LOCAL o AWS_S3)
│   │   │   ├── message_broker_service.py      # MessageBrokerService (publica tareas Celery)
│   │   │   └── notification_service.py        # NotificationService (CONSOLE o SMTP)
│   │   ├── tasks/
│   │   │   ├── celery_app.py                  # Celery config + routing de colas
│   │   │   ├── document_processing_tasks.py   # process_document_task (3 reintentos, 60s delay)
│   │   │   └── notification_tasks.py          # send_notification_task
│   │   └── crud/                              # VACÍO — lógica CRUD vive en los endpoints
│   ├── alembic/versions/001_initial.py        # Migración inicial (todas las tablas)
│   ├── tests/
│   │   ├── conftest.py                        # SQLite in-memory, TestClient, fixtures
│   │   ├── api/
│   │   │   ├── test_auth.py                   # 16 tests (login form+JSON, register, refresh, logout, inactivo)
│   │   │   ├── test_documents.py              # 19 tests (upload, CRUD, data, types)
│   │   │   ├── test_documents_extra.py        # 13 tests (filtros, download, preview, status, HIL)
│   │   │   ├── test_misc.py                   # 10 tests (health, deps edge cases, docs misc)
│   │   │   ├── test_users.py                  # 1 test (/me)
│   │   │   └── test_users2.py                 # 12 tests (CRUD admin, password, role)
│   │   ├── db/
│   │   │   ├── test_models.py                 # 5 tests (__repr__ de todos los modelos)
│   │   │   └── test_session.py                # 2 tests (get_db generator + cierre en finally)
│   │   ├── services/
│   │   │   ├── test_gemini_service.py         # 15 tests (classify, extract, summarize, JSON parse, no client)
│   │   │   ├── test_storage_service.py        # 16 tests (LOCAL + AWS S3 completo)
│   │   │   ├── test_message_broker_service.py # 7 tests (publish, no celery, init failure)
│   │   │   └── test_notification_service.py   # 11 tests (CONSOLE + SMTP + html_body)
│   │   └── tasks/
│   │       ├── test_document_processing.py    # 8 tests (success, pypdf, existing field, exception, retry)
│   │       └── test_notification_tasks.py     # 4 tests (all statuses, not found, exception)
│   ├── pytest.ini                             # asyncio_mode=auto, cov --fail-under=80
│   ├── requirements.txt
│   └── Dockerfile                             # python:3.11-slim, health check en /health
└── sapi_frontend/
    ├── src/
    │   ├── App.tsx                            # Rutas + ProtectedRoute + PublicRoute
    │   ├── main.tsx                           # BrowserRouter, QueryClient (5min stale), Toaster
    │   ├── api/
    │   │   ├── client.ts                      # Axios + interceptor refresh automático + cola
    │   │   ├── auth.ts                        # login, loginJson, refresh, logout, getCurrentUser
    │   │   ├── documents.ts                   # listDocuments, upload, preview, download, etc.
    │   │   └── index.ts                       # Re-exports
    │   ├── contexts/auth-context.tsx          # Zustand store (persiste en localStorage)
    │   ├── components/ui/
    │   │   └── PdfViewer.tsx                  # Viewer PDF (iframe) + imágenes (img) con Blob URL
    │   ├── hooks/                             # Directorio existente (vacío actualmente)
    │   ├── pages/
    │   │   ├── Login.tsx                      # Formulario login (credenciales test: admin/admin123)
    │   │   ├── Dashboard.tsx                  # Lista docs, upload, filtros, paginación
    │   │   └── DocumentDetail.tsx             # Preview + campos extraídos + edición HIL
    │   └── types/
    │       ├── auth.ts                        # UserRole, User, Token, LoginRequest
    │       └── document.ts                    # DocumentStatus, DocumentDetail, ExtractedField, etc.
    ├── package.json
    └── Dockerfile
```

---

## Endpoints de la API

### Auth (`/api/v1/auth/`)
| Método | Ruta | Rate limit | Descripción |
|--------|------|-----------|-------------|
| POST | `/login` | 5/min | Login form-data → access_token + refresh_token cookie |
| POST | `/login/json` | 5/min | Login JSON → mismo resultado que `/login` |
| POST | `/register` | 3/min | Registro de usuario |
| POST | `/refresh` | — | Renueva access_token usando cookie refresh_token |
| POST | `/logout` | — | Elimina cookie refresh_token |

> **Nota:** Existen dos endpoints de login (`/login` form-data y `/login/json`). Esto es técnicamente redundante y podría unificarse.

### Documents (`/api/v1/documents/`)
| Método | Ruta | Rate limit | Descripción |
|--------|------|-----------|-------------|
| GET | `/` | — | Listar docs (filtros: status, type, search; paginación) |
| POST | `/` | 10/min | Upload documento (PDF/PNG/JPG, max 10 MB) |
| GET | `/{id}` | — | Detalle del documento |
| GET | `/{id}/status` | — | Estado de procesamiento |
| GET | `/{id}/data` | — | Campos extraídos por IA |
| PUT | `/{id}/data` | — | Corregir campos (Human-in-the-Loop) |
| GET | `/{id}/download` | — | Descargar archivo |
| GET | `/{id}/preview` | — | Preview inline |
| GET | `/types/` | — | Listar tipos de documento |

> **Pendiente:** `DELETE /{id}` no está implementado (RF004 del PRD).

### Users (`/api/v1/users/`)
| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| GET | `/me` | Auth | Usuario actual |
| POST | `/` | Superuser | Crear usuario |
| GET | `/` | Superuser | Listar usuarios (skip/limit) |
| GET | `/{id}` | Superuser | Obtener usuario |
| PUT | `/{id}` | Superuser | Actualizar usuario |
| DELETE | `/{id}` | Superuser | Eliminar usuario (204) |

---

## Modelos de Datos

- **User** — UUID PK, roles: `admin | document_reviewer | user`, `is_superuser`, `is_active`
- **DocumentType** — UUID PK, nombre, descripción, `is_active`
- **Document** — UUID PK, status: `UPLOADED → PROCESSING → PROCESSED | REVIEW_NEEDED | ERROR`
  - Campos: `original_filename`, `storage_path`, `file_size`, `mime_type`, `classification_confidence`, `executive_summary`, `processing_error`
- **ExtractedData** — `ai_extracted_value` + `ai_confidence` + `final_value` + `is_corrected` + `corrected_by_user_id` (Human-in-the-Loop)
- **AuditLog** — `user_id`, `action`, `entity_type`, `entity_id`, `details`, `ip_address`, `timestamp`
  - ⚠️ El modelo existe completo pero **ningún endpoint escribe en esta tabla aún**.

---

## Campos Extraídos por IA

```python
# Facturas
["numero_factura", "fecha_emision", "fecha_vencimiento",
 "nombre_proveedor", "nif_cif_proveedor", "importe_total", "importe_iva"]

# Contratos
["partes_involucradas", "fecha_firma", "fecha_inicio",
 "fecha_fin", "objeto_contrato", "valor_monetario", "clausulas_clave"]
```

Confianza de clasificación: umbral 0.7 (< 0.7 → `REVIEW_NEEDED`, ≥ 0.7 → `PROCESSED`)

---

## Seguridad y Configuración

- **CORS:** orígenes restringidos vía variable `ALLOWED_ORIGINS` (default: `http://localhost:3000,http://localhost`)
- **JWT access token:** 30 min | **JWT refresh token:** 7 días (httponly cookie, path `/api/v1/auth/refresh`)
- **Contraseñas:** bcrypt (limitadas a 72 chars)
- **Rate limiting:** slowapi en auth (5/min login, 3/min register) y upload (10/min)
- **Storage:** LOCAL (dev) o AWS_S3 (producción) via `STORAGE_PROVIDER`
- **Email:** CONSOLE (dev, loguea en logger) o SMTP (producción) via `EMAIL_PROVIDER`
- ⚠️ `secure=False` en la cookie del refresh token — debe cambiarse a `True` en producción.

---

## Estado de Desarrollo (Plan 12 semanas — iniciado 2026-03-25)

| Fase | Estado | Descripción |
|------|--------|-------------|
| **Fase 0** — Correcciones | ✅ Completa | UUID estandarizado, `eval()` eliminado, deps circulares resueltas, Dockerfile |
| **Fase 1** — Backend Core | ✅ Completa | JWT auth + refresh, CRUD documentos, storage S3/local, modelos DB |
| **Fase 2** — IA/Workers | ✅ Completa | Gemini integrado, Celery con reintentos, extracción de entidades |
| **Fase 3** — Frontend | ✅ Completa | Login, Dashboard, DocumentDetail, upload, corrección HIL, PDF viewer |
| **Fase 4** — Testing | ✅ Completa | 191 backend + 49 frontend, coberturas >80% |
| **Fase 5** — Hardening | 🔄 En curso | Ver plan de producción más abajo |

---

## KPIs del Proyecto

| KPI | Objetivo | Estado |
|-----|----------|--------|
| Precisión clasificación IA | >90% | ✅ Verificado en producción (0.95–0.99) |
| Tiempo procesamiento | <30s/documento | ❓ Sin medir formalmente |
| Tiempo respuesta API | <500ms | ❓ Sin medir formalmente |
| Cobertura de tests (backend) | 100% | ✅ 228 tests |
| Cobertura de tests (frontend) | >80% | ✅ 49 tests, 92.85% funciones |
| Reducción trabajo manual | -70% | ❓ Sin medir |
| Volumen objetivo | 10 000 docs/mes | ❓ Sin test de carga |

---

## Documentación de Referencia

- **PRD y specs:** `Sample-SAPI/` (00_prd.md, 01_arquitectura.md, 02_spec_backend.md, 04_spec_frontend.md)
- **Informe de verificación PRD/Arquitectura:** `informe-prd-arquitectura-SAPI.md` ← leer antes de iniciar Fase 5
- **Plan de desarrollo:** `PLAN_CORRECCIONES_Y_DESARROLLO_SAPI.md`
- **README:** `README.md`

---

## Acceso Local (Docker Compose)

```bash
docker-compose up --build -d

# Frontend:    http://localhost
# API:         http://localhost/api/v1
# Swagger:     http://localhost/api/v1/docs
# PostgreSQL:  localhost:5432  (sapi_user / sapi_password / sapi_db)
# Redis:       localhost:6379
# Credenciales test: admin / admin123
```

---

## Ejecutar Tests Localmente (sin Docker)

```bash
cd sapi_backend

# Activar entorno virtual
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

# Instalar dependencias (primera vez)
pip install -r requirements.txt

# Ejecutar todos los tests con cobertura
python -m pytest --cov=app --cov-report=term-missing

# Ejecutar un módulo específico
python -m pytest tests/api/test_auth.py -v

# Ejecutar con reporte HTML
python -m pytest --cov=app --cov-report=html
# → Abre htmlcov/index.html en el navegador
```

> **Nota:** Los tests usan SQLite in-memory — no requieren PostgreSQL ni Redis.
> **Limitación conocida:** SQLite no valida todas las restricciones de PostgreSQL (ej.: NOT NULL en ciertas operaciones).
> Al agregar lógica nueva que toque la BD, verificar también con el entorno Docker completo.

---

## Plan de Hardening — Fase 5 (Hacia Producción)

El informe `informe-prd-arquitectura-SAPI.md` identificó las brechas entre el PRD/arquitectura y la implementación actual.
El siguiente plan ordena el trabajo por **criticidad y dependencias**, de modo que cada sprint deja el sistema en un estado funcional y más seguro que el anterior.

> **Convención de estado:**
> - `[ ]` Pendiente — `[~]` En progreso — `[x]` Completado

---

### Sprint A — Correcciones Urgentes de Código (estimado: 1 sesión)

Fixes puntuales que no requieren diseño previo. Deben hacerse primero porque afectan correctitud y reproducibilidad.

- [x] **A1. Descomentar `psycopg2-binary` en `requirements.txt`**
  - Actualmente comentado → instalación local fuera de Docker falla silenciosamente.
  - Archivo: `sapi_backend/requirements.txt` línea ~8.

- [x] **A2. Agregar `email-validator` a `requirements.txt`**
  - Pydantic lo necesita para validar `email`; se instala hoy dinámicamente en Docker Compose.
  - Agregar: `email-validator==2.1.0` (o la versión compatible con la versión de Pydantic instalada).

- [x] **A3. Mover `pip install` del comando Docker Compose al Dockerfile**
  - Los workers instalan paquetes en cada arranque (`pip install pypdf email-validator`).
  - Mover esos paquetes a `sapi_backend/Dockerfile` con `RUN pip install`.
  - Esto hace la imagen reproducible y el arranque más rápido.

- [x] **A4. Eliminar definición duplicada en `schemas/document.py`**
  - `ExtractedDataUpdate` y `ExtractedDataUpdateList` están definidos dos veces.
  - Eliminar la primera ocurrencia (líneas ~61-66); dejar solo la segunda.

- [x] **A5. Activar `secure=True` en cookie del refresh token condicionalmente**
  - Archivo: `sapi_backend/app/api/v1/endpoints/auth.py`.
  - Agregar `ENVIRONMENT: str = "development"` a `config.py`.
  - En `auth.py`: `secure=settings.ENVIRONMENT == "production"`.

- [x] **A6. Agregar validación de `document_type_id` en upload**
  - Si el cliente envía un `document_type_id` inexistente, el upload debe retornar 422.
  - Archivo: `sapi_backend/app/api/v1/endpoints/documents.py` (función `upload_document`).

---

### Sprint B — Seguridad: Autorización por Roles (estimado: 2 sesiones)

La autenticación es correcta, pero la **autorización granular** está ausente en los endpoints de documentos. Cualquier usuario autenticado puede leer y editar documentos de otros usuarios.

- [x] **B1. Crear dependency `get_document_or_404_owned`**
  - Archivo: `sapi_backend/app/api/v1/deps.py`.
  - Nueva función: recibe `document_id` y el usuario actual; retorna el documento si existe y el usuario es propietario o tiene rol `admin` / `document_reviewer`; lanza 403 en caso contrario.
  - Esta dependency reemplaza el patrón manual `db.query(Document).filter(...)` que se repite en varios endpoints.

- [x] **B2. Aplicar la dependency en todos los endpoints de documento**
  - `GET /documents/{id}` — solo propietario, reviewer o admin.
  - `GET /documents/{id}/data` — solo propietario, reviewer o admin.
  - `PUT /documents/{id}/data` — solo reviewer o admin (los `user` solo pueden subir).
  - `GET /documents/{id}/download` — solo propietario, reviewer o admin.
  - `GET /documents/{id}/preview` — solo propietario, reviewer o admin.

- [x] **B3. Crear dependency `require_role(*roles)`**
  - Reutilizable para cualquier endpoint que requiera un rol específico.
  - Ejemplo: `Depends(require_role("document_reviewer", "admin"))`.

- [x] **B4. Actualizar tests de autorización**
  - Agregar casos en `test_documents.py` y `test_documents_extra.py` que verifiquen que un usuario sin permiso recibe 403.
  - Mantener cobertura al 100%.

---

### Sprint C — Auditoría: Activar AuditLog (estimado: 1 sesión)

El modelo `AuditLog` está completo pero nunca se escribe. Sin trazabilidad no hay cumplimiento ni capacidad de investigar incidentes.

- [x] **C1. Crear helper `log_action(db, user_id, action, entity_type, entity_id, details, ip_address)`**
  - Archivo nuevo: `sapi_backend/app/core/audit.py`.
  - Función simple que crea y hace `db.add()` de un `AuditLog`. No hace commit (el commit lo hace el endpoint llamador).

- [x] **C2. Registrar acciones en endpoints de documentos**
  - `POST /documents/` → acción `"document.upload"`.
  - `PUT /documents/{id}/data` → acción `"document.correct_field"` (una entrada por campo modificado o una por operación).
  - `DELETE /documents/{id}` (cuando se implemente) → acción `"document.delete"`.

- [x] **C3. Registrar acciones en endpoints de auth**
  - `POST /auth/login` → acción `"auth.login"` con IP.
  - `POST /auth/logout` → acción `"auth.logout"`.

- [x] **C4. Registrar acciones en endpoints de usuarios (admin)**
  - `POST /users/` → `"user.create"`.
  - `PUT /users/{id}` → `"user.update"`.
  - `DELETE /users/{id}` → `"user.delete"`.

- [x] **C5. Agregar tests de auditoría**
  - Verificar que cada acción registrada crea la fila correcta en `AuditLog`.

---

### Sprint D — Funcionalidad Faltante del PRD (estimado: 1 sesión)

Requisitos del PRD marcados como ausentes o parciales en el informe.

- [x] **D1. Implementar `DELETE /documents/{id}` (RF004)**
  - Eliminar el documento de la BD, sus `ExtractedData` asociados y el archivo del storage.
  - Solo propietario o admin puede eliminar.
  - Registrar en `AuditLog`.
  - Agregar botón "Eliminar" en `DocumentDetail.tsx` con modal de confirmación.

- [x] **D2. Agregar filtro por tipo de documento en el Dashboard (RF017)**
  - Backend: el endpoint `GET /documents/` ya acepta `document_type_id`; verificar que funciona.
  - Frontend: agregar un `<select>` en el Dashboard para filtrar por tipo (poblar con `listDocumentTypes()`).

- [x] **D3. Agregar filtro por rango de fechas en listado (RF017)**
  - Backend: agregar parámetros `date_from` y `date_to` (ISO 8601) al endpoint `GET /documents/`.
  - Frontend: dos `<input type="date">` en la sección de filtros del Dashboard.

- [x] **D4. Hacer `GET /users/` devolver `PaginatedResponse`**
  - Actualmente retorna lista plana sin metadatos. Unificar con el patrón del listado de documentos.

---

### Sprint E — Performance: Consultas y Caché ✅ COMPLETO

- [x] **E1. Corregir N+1 query en `GET /documents/`**
  - Archivo: `sapi_backend/app/api/v1/endpoints/documents.py`.
  - Reemplazar el loop que hace una query por documento con `options(joinedload(Document.document_type))` en la query principal.
  - Verificar con `SQLALCHEMY_ECHO=True` que se genera una sola consulta SQL.

- [x] **E2. Agregar índices en migración Alembic**
  - Creado `sapi_backend/alembic/versions/002_add_indexes.py`.
  - Índices agregados: `documents.created_at`, `(extracted_data.document_id, field_name)` UNIQUE, `audit_logs.entity_id`, `audit_logs.action`.

- [x] **E3. Caché de `DocumentType` en Redis**
  - Creado `sapi_backend/app/services/cache_service.py` con `CacheService` (graceful degradation).
  - `GET /documents/types/` usa cache-aside con TTL 5 min.
  - 18 tests unitarios + 1 test de cache-hit en endpoint.

---

### Sprint F — Infraestructura: HTTPS y Operacional ✅ COMPLETO

- [x] **F1. Configurar HTTPS en Nginx**
  - `nginx/conf.d/default.conf`: bloque HTTP→HTTPS + servidor 443 ssl con TLSv1.2/1.3.
  - Script `nginx/generate-certs.sh` para cert autofirmado de desarrollo local.
  - Certs montados en `/etc/nginx/ssl/` vía volume en docker-compose.

- [x] **F2. Configurar backups automáticos de PostgreSQL**
  - Servicio `db_backup` en docker-compose: `pg_dump` diario comprimido en `backups/`.
  - Retención automática: `find ./backups -mtime +7 -delete`.

- [x] **F3. Corregir healthcheck de `celery_beat`**
  - Beat arranca con `--pidfile=/tmp/celerybeat.pid`.
  - Healthcheck: `test -f /tmp/celerybeat.pid && kill -0 $(cat /tmp/celerybeat.pid)`.

- [x] **F4. Agregar variables de entorno para producción en `.env.example`**
  - Documentadas: `ENVIRONMENT`, `SSL_CERT_PATH`, `SSL_KEY_PATH`, `ALLOWED_ORIGINS`.
  - Cada variable con comentario `[PROD]` indicando su criticidad.

- [x] **F5. Configurar logs estructurados (JSON)**
  - `python-json-logger==2.0.7` en `requirements.txt`.
  - `_setup_logging()` en `main.py`: logs JSON con timestamp, level, logger, message.

---

### Sprint G — Monitoreo y Observabilidad ✅ COMPLETO

- [x] **G1. Exponer métricas Prometheus en el backend**
  - `prometheus-fastapi-instrumentator==6.1.0` en `requirements.txt`.
  - `Instrumentator().instrument(app).expose(app, endpoint="/metrics")` en `main.py`.
  - Métricas: latencia (histograma), tasa de requests, errores, requests en vuelo.

- [x] **G2. Agregar `docker-compose.monitoring.yml` con Prometheus + Grafana**
  - `docker-compose.monitoring.yml`: Prometheus (9090), Grafana (3001, admin/admin), Flower (5555).
  - `monitoring/prometheus.yml` con scrape config al backend cada 10s.
  - Dashboard `sapi_overview.json` provisionado automáticamente en Grafana.

- [x] **G3. Alertas básicas**
  - `monitoring/alerts/sapi_alerts.yml` con 3 reglas:
    - `HighErrorRate` → 5xx > 10% en 5 min (critical)
    - `HighLatency` → P95 > 500ms en 5 min (warning)
    - `BackendDown` → scrape fallando > 2 min (critical)

---

### Sprint H — Tests de Integración y Frontend ✅ COMPLETO

- [x] **H1. Agregar fixture de PostgreSQL real en `conftest.py`**
  - `tests/integration/conftest.py`: fixtures `pg_engine`, `pg_session`, `pg_client` con rollback por test.
  - `tests/integration/test_documents_pg.py`: 3 tests (UNIQUE constraint, upload+retrieve, audit log).
  - Skipped por defecto; ejecutar con `pytest tests/integration/ --integration`.

- [x] **H2. Tests de carga con Locust**
  - `sapi_backend/locustfile.py`: SAPIReadUser (70%) + SAPIWriteUser (30%), reporte P50/P95/error rate.
  - Ejecutar: `locust --headless -u 50 -r 5 --run-time 60s --host http://localhost/api/v1`.

- [x] **H3. Tests de frontend con Vitest + React Testing Library**
  - 49 tests en 5 archivos: Dashboard (15), DocumentDetail (16), Login (6), hooks (12).
  - Cobertura: 99.85% líneas | 90.56% ramas | 92.85% funciones (umbral 80% superado).
  - Ejecutar: `cd sapi_frontend && npm test` / `npm run test:coverage`.

- [x] **H4. Extraer lógica de fetching a custom hooks**
  - `sapi_frontend/src/hooks/useDocumentList.ts` — useDocumentList, useDocumentTypes, useDocumentUpload.
  - `sapi_frontend/src/hooks/useDocumentDetail.ts` — useDocumentDetail, useDocumentFieldUpdate.

---

### Sprint I — Migración y Deuda Técnica ✅ COMPLETO

- [x] **I1. Migrar `google.generativeai` a `google.genai`**
  - La librería `google-generativeai` está deprecada (FutureWarning en cada arranque).
  - Actualizar `requirements.txt` y refactorizar `ai_service.py` a la nueva API.
  - Los tests de `test_gemini_service.py` deben actualizarse en consecuencia.

- [x] **I2. Implementar Repository Pattern en `app/crud/`**
  - Crear `CRUDDocument`, `CRUDExtractedData`, `CRUDUser` con operaciones comunes.
  - Mover la lógica de BD de `documents.py`, `users.py` a las clases CRUD.
  - Permite testear la lógica de negocio sin pasar por la capa HTTP.

- [x] **I3. Implementar Circuit Breaker para Gemini API**
  - Agregar `tenacity` a `requirements.txt`.
  - En `ai_service.py`: si Gemini falla 3 veces consecutivas, abrir el circuito y retornar fallback durante 2 minutos sin llamar a la API.
  - Previene saturar la API de Google y acumular reintentos en cola.

- [x] **I4. Agregar backoff exponencial en reintentos de Celery**
  - Actualmente `default_retry_delay=60` (fijo).
  - Cambiar a: `countdown = 60 * (2 ** self.request.retries)` → 60s, 120s, 240s.

---

### Sprint J — Cumplimiento Normativo GDPR (estimado: 1 sesión)

Requerido si el sistema maneja datos de ciudadanos de la UE.

- [ ] **J1. Endpoint de exportación de datos del usuario**
  - `GET /users/me/export` → retorna JSON con todos los documentos y campos extraídos del usuario.

- [ ] **J2. Endpoint de eliminación completa (derecho al olvido)**
  - `DELETE /users/me` → elimina usuario, sus documentos, campos extraídos, audit logs y archivos del storage.
  - Requiere confirmación con contraseña actual.

- [ ] **J3. Cifrado en reposo**
  - PostgreSQL: configurar `pgcrypto` o usar cifrado a nivel de disco en el servidor.
  - S3: activar SSE-S3 o SSE-KMS en el bucket.
  - Documentar configuración en `.env.example`.

---

## Orden Recomendado de Ejecución

```
Sprint A ✅ →  Sprint B ✅ →  Sprint C ✅ →  Sprint D ✅
(fixes)       (authz)       (audit)       (funcional faltante)
    │                                       │
    └───────────────────────────────────────┘
                        │
                        ▼
Sprint E  →  Sprint F  →  Sprint G
(perf)       (HTTPS+ops)  (monitoring)
    │
    └───────────────────────────────────────────┐
                                                │
                                                ▼
                                    Sprint H  →  Sprint I  →  Sprint J
                                    (tests)      (deuda)       (GDPR)
```

> Los sprints A–D son **prerrequisito para producción**.
> Los sprints E–G son **fuertemente recomendados**.
> Los sprints H–J son **mejoras de calidad y cumplimiento**.

---

## Bugs Conocidos (No Bloqueantes en Dev, Bloqueantes en Prod)

| ID | Archivo | Descripción | Sprint |
|----|---------|-------------|--------|
| BUG-001 | `documents.py` | N+1 query en `GET /documents/` (1 query por documento para obtener el tipo) | E1 |
| BUG-002 | `auth.py` | `secure=False` en cookie del refresh token | A5 |
| BUG-003 | `requirements.txt` | `psycopg2-binary` comentado; `email-validator` ausente | A1/A2 |
| BUG-004 | `document.py` (schema) | `ExtractedDataUpdate` definido dos veces | A4 |
| BUG-005 | `documents.py` | `document_type_id` no se valida que exista en BD al hacer upload | A6 |
| BUG-006 | `users.py` | `GET /users/` retorna lista plana, no `PaginatedResponse` | D4 |
| BUG-007 | `docker-compose.yml` | `celery_beat` arranca pero no tiene tareas programadas definidas | F3 |
| BUG-008 | `docker-compose.yml` | Paquetes instalados en runtime en lugar de en la imagen Docker | A3 |

---

## Criterio de "Listo para Producción"

El MVP se considera listo para producción cuando:

- [x] Procesamiento IA funcional end-to-end (imágenes + PDFs)
- [x] Autenticación JWT con refresh tokens
- [x] Human-in-the-Loop implementado
- [x] Cobertura de tests backend 100%
- [x] Autorización por roles en endpoints de documentos (Sprint B)
- [x] AuditLog activo (Sprint C)
- [x] `DELETE /documents/{id}` implementado (Sprint D)
- [x] HTTPS configurado en Nginx (Sprint F1)
- [x] Backups automáticos de PostgreSQL (Sprint F2)
- [x] Logs estructurados en JSON (Sprint F5)
- [x] Al menos un dashboard de monitoreo operativo (Sprint G)
- [x] Tests de integración con PostgreSQL real (Sprint H1)

---

## Notas para Claude Code

- Al implementar cualquier sprint, mantener la cobertura de tests al 100% en backend.
- Cada sprint debe terminar con un commit siguiendo el formato `tipo(scope): descripción` en español.
- Antes de tocar `documents.py`, leer también `deps.py` — los cambios de autorización van principalmente ahí.
- Los cambios en modelos de BD requieren una nueva migración Alembic (`alembic revision --autogenerate -m "descripción"`).
- Al agregar endpoints nuevos, agregar también el test correspondiente antes de hacer el commit.
- Para probar HTTPS localmente, el certificado autofirmado causará advertencia en el navegador; es esperado.
- Al migrar de `google.generativeai` a `google.genai` (Sprint I1), revisar que todos los mocks en `test_gemini_service.py` se actualicen correctamente.
