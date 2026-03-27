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

---

## Arquitectura (8 contenedores)

```
Nginx (80) → React Frontend (3000)
           → FastAPI Backend (8000) → PostgreSQL (5432)
                                    → Redis (6379) → ai_worker (Celery)
                                                   → notification_worker (Celery)
                                                   → celery_beat
```

**Routing Nginx:** `/` → React frontend · `/api/v1` → FastAPI backend

---

## Estructura de Directorios Clave

```
SAPI/
├── docker-compose.yml
├── nginx/conf.d/default.conf
├── sapi_backend/
│   ├── app/
│   │   ├── main.py                            # Entry point FastAPI
│   │   ├── core/config.py                     # Settings (Pydantic)
│   │   ├── core/security.py                   # JWT + bcrypt
│   │   ├── api/v1/endpoints/
│   │   │   ├── auth.py                        # Login, register
│   │   │   ├── documents.py                   # CRUD documentos
│   │   │   └── users.py                       # /me endpoint
│   │   ├── db/models/
│   │   │   ├── user.py                        # UUID PK
│   │   │   ├── document.py                    # Document + DocumentType
│   │   │   └── extracted_data.py              # ExtractedData + AuditLog
│   │   ├── services/
│   │   │   ├── ai_service.py                  # GeminiAIService
│   │   │   ├── storage_service.py             # S3 / local abstraction
│   │   │   ├── message_broker_service.py      # Celery publisher
│   │   │   └── notification_service.py        # Email (no implementado aún)
│   │   └── tasks/
│   │       ├── celery_app.py
│   │       ├── document_processing_tasks.py   # process_document_task
│   │       └── notification_tasks.py
│   ├── alembic/versions/001_initial.py
│   ├── tests/
│   └── requirements.txt
└── sapi_frontend/
    ├── src/
    │   ├── App.tsx
    │   ├── api/client.ts                      # Axios + interceptores JWT
    │   ├── contexts/auth-context.tsx          # Zustand auth store
    │   ├── pages/
    │   │   ├── Login.tsx
    │   │   ├── Dashboard.tsx
    │   │   └── DocumentDetail.tsx
    │   └── types/
    │       ├── auth.ts
    │       └── document.ts
    └── package.json
```

---

## Modelos de Datos

- **User** — UUID PK, roles: `admin | document_reviewer | user`
- **DocumentType** — UUID PK, nombre del tipo (Factura, Contrato)
- **Document** — UUID PK, status: `UPLOADED → PROCESSING → PROCESSED | REVIEW_NEEDED | ERROR`
- **ExtractedData** — `ai_extracted_value` + `final_value` + `is_corrected` (Human-in-the-Loop)
- **AuditLog** — registro de todas las acciones

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

---

## Estado de Desarrollo (Plan 12 semanas — iniciado 2026-03-25)

| Fase | Estado | Descripción |
|------|--------|-------------|
| **Fase 0** — Correcciones | ✅ Completa | UUID estandarizado, `eval()` eliminado, deps circulares resueltas, Dockerfile multi-stage |
| **Fase 1** — Backend Core | ✅ Completa | JWT auth, CRUD documentos, storage S3/local, modelos DB |
| **Fase 2** — IA/Workers | ✅ Completa | Gemini integrado, Celery con reintentos, extracción de entidades |
| **Fase 3** — Frontend | ✅ Completa | Login, Dashboard, DocumentDetail, upload, corrección HIL |
| **Fase 4** — Testing | ⚠️ En progreso | Tests existen, cobertura objetivo >80% |
| **Fase 5** — Deploy | ❌ Pendiente | CI/CD, SSL, monitoreo, producción |

---

## Issues Conocidos (Pendientes)

1. **CORS `allow_origins=["*"]`** — debe restringirse al dominio del frontend
2. **PDF viewer** en frontend — parcialmente implementado
3. **Email notifications** — `NotificationService` existe pero sin implementación real
4. **JWT refresh token** — no implementado (solo access token de 30 min)
5. **Rate limiting** — ningún endpoint tiene throttling
6. **Endpoint duplicado** — `/register` aparece dos veces en `auth.py`
7. **Cobertura de tests** — debe superar 80% (Fase 4)
8. **Directorio `/crud`** — vacío, la lógica vive en los endpoints

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
# PostgreSQL:  localhost:5432 (sapi_user / sapi_password)
# Redis:       localhost:6379
```
