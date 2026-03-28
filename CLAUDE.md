# SAPI — Contexto del Proyecto para Claude Code

## ¿Qué es SAPI?
**Sistema de Automatización y Procesamiento Documental Inteligente.** Plataforma AI que extrae, clasifica y resume automáticamente **facturas y contratos** usando Google Gemini 1.5 Pro, con revisión humana (Human-in-the-Loop).

---

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | FastAPI + Python 3.11, SQLAlchemy 2.0, Alembic, PostgreSQL 15 |
| Async | Celery + Redis 7 (colas `ai_processing` y `notifications`) |
| IA | Google Gemini API (clasificar, extraer entidades, resumir) |
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
│   │   │   ├── test_auth.py                   # 14 tests (login, register, refresh, logout)
│   │   │   ├── test_documents.py              # 19 tests (upload, CRUD, data, types)
│   │   │   ├── test_users.py                  # 1 test (/me)
│   │   │   └── test_users2.py                 # 3 tests (CRUD admin) — algunos endpoints no existen aún
│   │   ├── services/
│   │   │   ├── test_gemini_service.py         # 2 tests (classify, extract — mocked)
│   │   │   ├── test_storage_service.py        # 1 test (local upload/download/delete)
│   │   │   └── test_notification_service.py   # 10 tests (CONSOLE + SMTP)
│   │   └── tasks/
│   │       └── test_document_processing.py    # 1 test (process_document_task — mocked)
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

---

## Estado de Desarrollo (Plan 12 semanas — iniciado 2026-03-25)

| Fase | Estado | Descripción |
|------|--------|-------------|
| **Fase 0** — Correcciones | ✅ Completa | UUID estandarizado, `eval()` eliminado, deps circulares resueltas, Dockerfile |
| **Fase 1** — Backend Core | ✅ Completa | JWT auth + refresh, CRUD documentos, storage S3/local, modelos DB |
| **Fase 2** — IA/Workers | ✅ Completa | Gemini integrado, Celery con reintentos, extracción de entidades |
| **Fase 3** — Frontend | ✅ Completa | Login, Dashboard, DocumentDetail, upload, corrección HIL, PDF viewer |
| **Fase 4** — Testing | ⚠️ En progreso | ~40 tests existentes, cobertura estimada ~40% — objetivo >80% |
| **Fase 5** — Deploy | ❌ Pendiente | CI/CD, SSL, monitoreo, producción |

---

## Issues Pendientes (Reales)

1. **Cobertura de tests < 80%** — ~40 tests cubren ~40% del código; hay tests que referencian endpoints inexistentes (ej. `PUT /users/me` en `test_users2.py`)
2. **Rate limiting incompleto** — solo en auth y upload; los endpoints GET, PUT y admin no tienen throttling
3. **Dos endpoints de login redundantes** — `POST /auth/login` (form-data) y `POST /auth/login/json` (JSON body); deberían unificarse o documentarse la distinción
4. **`/crud/` vacío** — la lógica CRUD vive directamente en los endpoints; no hay capa de repositorio
5. **Celery Beat sin tareas programadas** — `celery_beat` está configurado y en Docker Compose, pero no hay tareas periódicas definidas
6. **HTTPS no configurado en Nginx** — solo puerto 80 activo; producción requiere SSL/TLS
7. **`test_users2.py`** — referencia `PUT /api/v1/users/me` y `POST /api/v1/users` que no existen en `users.py`; estos tests fallan o son incorrectos
8. **`hooks/` vacío** — directorio creado pero sin custom hooks de React

---

## KPIs del Proyecto

| KPI | Objetivo |
|-----|----------|
| Precisión clasificación IA | >90% |
| Tiempo procesamiento | <30s/documento |
| Tiempo respuesta API | <500ms |
| Cobertura de tests | >80% |
| Reducción trabajo manual | -70% |
| Volumen objetivo | 10,000 docs/mes |

---

## Documentación de Referencia

- **PRD y specs:** `Sample-SAPI/` (00_prd.md, 01_arquitectura.md, 02_spec_backend.md, 04_spec_frontend.md)
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
