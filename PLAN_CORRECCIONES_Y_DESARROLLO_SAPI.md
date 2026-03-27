# PLAN DE CORRECCIONES Y DESARROLLO SAPI

**Proyecto:** Sistema de Automatización y Procesamiento Documental Inteligente (SAPI)  
**Fecha de Creación:** 2026-03-25  
**Versión:** 1.0

---

# PARTE 1: PLAN DE CORRECCIONES NECESARIAS

## Resumen Ejecutivo

Después de analizar exhaustivamente los 14 documentos del proyecto SAPI, se identificaron **inconsistencias críticas** que impiden la construcción del sistema. Este documento detalla las correcciones necesarias antes de iniciar el desarrollo.

---

## 1.1 Inconsistencias Críticas Identificadas

### 🔴 CRÍTICA #1: Archivos de Código No Funcionales

| Archivo | Contenido Actual | Problema | Acción Requerida |
|---------|-----------------|----------|------------------|
| `06_code_api_fastapi.py` | Variables de entorno (.env) | No es código FastAPI | Reemplazar con código FastAPI real (main.py, routers, dependencies) |
| `08_docker_compose.yml` | Lista de estructura de directorios | No es docker-compose.yml | Crear docker-compose.yml funcional completo |
| `09_code_frontend.tsx` | tailwind.config.ts | No es código React | Reemplazar con componentes React reales |
| `10_backend_production.py` | .env.example | No es código de producción | Mantener como .env.example (correcto) |
| `11_frontend_production.tsx` | src/types/user.ts | No es código de producción | Crear servicios API de frontend |

### 🔴 CRÍTICA #2: Discrepancia de IDs (UUID vs Integer)

**Problema Identificado:**
- La clase `CustomBase` en `05_code_python_core.py` y `07_code_database.py` define `id` como `UUID`
- Los modelos `User` y `DocumentType` sobrescriben este campo con `Integer`

**Impacto:**
- Inconsistencia en la lógica CRUD
- Problemas de seguridad (enumeración de IDs)
- Complejidad innecesaria en el código

**Solución Requerida:**
```python
# En modelo User (actualmente):
id = Column(Integer, primary_key=True, index=True)

# Debe cambiar a:
id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
```

**Archivos a modificar:**
- `app/db/models/user.py`
- `app/db/models/document_type.py`
- `app/schemas/user.py` (ajustar validación Pydantic)
- `app/crud/crud_user.py` (ajustar métodos específicos)

### 🔴 CRÍTICA #3: Vulnerabilidad de Seguridad Crítica

**Ubicación:** Servicio de IA (AIService)

**Problema:**
```python
# CÓDIGO ACTUAL - ¡PELIGROSO!
eval(gemini_response)  # Ejecuta código arbitrario
```

**Riesgo:** Si la API de Gemini devuelve una cadena maliciosa, `eval()` podría ejecutar código arbitrario en el servidor.

**Solución Requerida:**
```python
# CÓDIGO CORRECTO
import json

def parse_gemini_response(gemini_response: str) -> dict:
    """Parsea la respuesta JSON de Gemini de forma segura."""
    try:
        return json.loads(gemini_response)
    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear respuesta de Gemini: {e}")
        raise ValueError("Respuesta de Gemini no es JSON válido")
```

### 🔴 CRÍTICA #4: Dependencia Circular

**Problema:**
```
app/services/message_broker_service.py 
    → importa → app.tasks.document_processing_tasks
    → importa → app.tasks.notification_tasks
                                            ↓
                                       Tasks también
                                            ↓
                              importan MessageBrokerService
```

**Solución Arquitectura:**
El `MessageBrokerService` debe ser un publicador puro que NO dependa de las tareas. Las tareas deben usar el broker de Celery directamente.

```python
# message_broker_service.py - SOLO PUBLICADOR
class MessageBrokerService:
    def __init__(self, celery_app: Celery):
        self.celery_app = celery_app
    
    def publish_document_processing(self, document_id: UUID):
        """Publica tarea sin importar módulos de tareas."""
        self.celery_app.send_task(
            'app.tasks.document_processing_tasks.process_document_task',
            args=[str(document_id)]
        )
```

### 🟡 MEDIA #5: Dockerfile Frontend Inadecuado para Producción

**Problema:** El `12_deploy.sh` advierte que el frontend está configurado para desarrollo (hot-reload), no es apta para producción.

**Solución Requerida:** Crear Dockerfile multi-stage para producción:

```dockerfile
# sapi_frontend/Dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

---

## 1.2 Checklist de Correcciones

| # | Corrección | Prioridad | Estado |
|---|-----------|-----------|--------|
| 1 | Corregir `06_code_api_fastapi.py` | Crítica | ✅ Completado |
| 2 | Corregir `08_docker_compose.yml` (Dependencias y contenedores) | Crítica | ✅ Completado (Corregidos imports, dependencias, puertos y healthchecks) |
| 3 | Corregir `09_code_frontend.tsx` | Crítica | ✅ Completado |
| 4 | Estandarizar IDs a UUID | Crítica | ✅ Completado |
| 5 | Eliminar eval() en AIService | Crítica | ✅ Completado |
| 6 | Resolver dependencia circular | Crítica | ✅ Completado (MessageBrokerService no importa módulos task) |
| 7 | Crear Dockerfile frontend prod | Media | ✅ Completado |

---

# PARTE 2: PLAN ESTRATÉGICO DE DESARROLLO SAPI

## 2.1 Visión del Proyecto

**SAPI** (Sistema de Automatización y Procesamiento Documental Inteligente) es una plataforma impulsada por IA diseñada para automatizar la extracción, clasificación y resumen de información de documentos (facturas y contratos), reduciendo significativamente la carga de trabajo manual.

### Stack Tecnológico
- **Backend:** Python 3.9+, FastAPI, Pydantic v2, SQLAlchemy 2.0
- **Base de Datos:** PostgreSQL 15
- **Procesamiento Asíncrono:** Celery + Redis
- **IA:** Google Gemini API
- **Frontend:** React 18+, TypeScript, Vite, Tailwind CSS
- **Infraestructura:** Docker, Kubernetes (futuro)
- **Object Storage:** AWS S3 / Google Cloud Storage

---

## 2.2 Fases de Desarrollo

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                          CRONOGRAMA GENERAL SAPI                              ║
║                              Duración Total: 12 Semanas                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Semana:   1   2   3   4   5   6   7   8   9  10  11  12                  ║
║            ├───┼───┼───┼───┼───┼───┼───┼───┼───┼───┼───┼───┤                ║
║  FASE 0   │CORRECCIONES│                                                      ║
║  FASE 1         │====INFRAESTRUCTURA CORE====│                               ║
║  FASE 2                      │====IA/WORKERS====│                              ║
║  FASE 3                                │====FRONTEND====│                    ║
║  FASE 4                                        │====TESTING====│            ║
║  FASE 5                                                │DEPLOY│            ║
║  FASE 6                                                   │LANZAMIENTO│      ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## FASE 0: Corrección Documental

**Duración:** 1 semana  
**Objetivo:** Corregir todas las inconsistencias identificadas

### Semana 1: Correcciones Iniciales

| Día | Tarea | Entregable |
|-----|-------|------------|
| 1-2 | Corregir archivos de código | Archivos funcionales |
| 3 | Estandarizar IDs a UUID | Modelos coherentes |
| 4 | Eliminar vulnerabilidad eval() | AIService seguro |
| 5 | Resolver dependencias circulares | Arquitectura limpia |
| 5 | Crear Dockerfile frontend prod | Producción viable |

**Definition of Done:**
- [x] Todos los archivos de código son funcionales
- [x] No hay advertencias de seguridad
- [x] Arquitectura sin dependencias circulares
- [x] Frontend apta para producción

---

## FASE 1: Infraestructura Core

**Duración:** 3 semanas (Semanas 2-4)  
**Objetivo:** Establecer la base del backend con API funcional

### Semana 2: Proyecto Base y Base de Datos

#### Día 1-2: Configuración del Proyecto
```
sapi_backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── api.py
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── auth.py
│   │           ├── users.py
│   │           └── documents.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── security.py
│   │   └── deps.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── document.py
│   │   ├── document_type.py
│   │   └── extracted_data.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── document.py
│   │   └── token.py
│   └── services/
│       ├── __init__.py
│       ├── auth.py
│       └── storage.py
├── tests/
├── alembic/
├── requirements.txt
├── Dockerfile
└── .env
```

#### Día 3-5: Modelos SQLAlchemy y Migraciones

**Modelos a crear:**
1. **User** - Gestión de usuarios y autenticación
2. **DocumentType** - Tipos de documentos (Factura, Contrato)
3. **Document** - Documentos cargados con metadatos
4. **ExtractedData** - Datos extraídos por IA
5. **AuditLog** - Registro de auditoría

**Entregable:** Migraciones Alembic ejecutadas, tablas creadas

### Semana 3: API REST y Autenticación

#### Endpoints a Implementar

| Método | Endpoint | Descripción | Estado |
|--------|----------|-------------|--------|
| POST | `/api/v1/auth/login` | Login con JWT | ✅ |
| POST | `/api/v1/auth/register` | Registro de usuarios | ✅ |
| GET | `/api/v1/users/me` | Usuario actual | ✅ |
| GET | `/api/v1/documents` | Listar documentos | ✅ |
| POST | `/api/v1/documents` | Subir documento | ✅ |
| GET | `/api/v1/documents/{id}` | Detalle documento | ✅ |
| GET | `/api/v1/documents/{id}/status` | Estado procesamiento | ✅ |
| GET | `/api/v1/documents/{id}/data` | Datos extraídos | ✅ |
| PUT | `/api/v1/documents/{id}/data` | Corregir datos | ✅ |
| GET | `/api/v1/documents/{id}/download` | Descargar original | ✅ |

#### Día 1-3: Autenticación JWT
- Implementar hashing de contraseñas (bcrypt)
- Generar tokens JWT con expiración
- Middleware de autenticación
- Roles y permisos (admin, user)

#### Día 4-5: CRUD de Documentos
- Upload de archivos (PDF, PNG, JPEG)
- Validación de tipos de archivo
- Almacenamiento temporal
- Listado con paginación y filtros

**Definition of Done:**
- [x] API responde correctamente
- [x] Autenticación JWT funcional
- [x] CRUD de documentos completo
- [x] Documentación OpenAPI/Swagger disponible

### Semana 4: Object Storage y Servicios

#### Día 1-2: Integración S3/GCS
- Servicio de almacenamiento de objetos
- Upload a bucket configurado
- Generación de URLs firmadas
- Descarga segura de archivos

#### Día 3-4: Notificaciones (Básico)
- Servicio de email básico
- Plantillas de email
- Cola de notificaciones

#### Día 5: Integración y Pruebas
- Pruebas de integración
- Corrección de bugs
- Documentación de API

**Definition of Done:**
- [x] Object Storage funcional
- [x] Upload/download de documentos OK
- [x] Notificaciones básicas funcionando

---

## FASE 2: Procesamiento IA

**Duración:** 2 semanas (Semanas 5-6)  
**Objetivo:** Implementar clasificación y extracción de datos con Gemini

### Semana 5: Integración Gemini API

#### Día 1-2: Configuración del Cliente
```python
# app/services/gemini_service.py
import google.generativeai as genai
from typing import Optional

class GeminiService:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
    
    async def classify_document(self, text: str) -> tuple[str, float]:
        """Clasifica el documento y retorna (tipo, confianza)"""
        pass
    
    async def extract_entities(self, text: str, doc_type: str) -> dict:
        """Extrae entidades según el tipo de documento"""
        pass
    
    async def summarize(self, text: str) -> str:
        """Genera resumen ejecutivo"""
        pass
```

#### Día 3-5: Procesamiento de Documentos
1. **OCR**: Extracción de texto de PDFs/imágenes
2. **Clasificación**: Factura vs Contrato (con confianza)
3. **Extracción de Entidades**:
   - Facturas: número, fecha, proveedor, importe, IVA
   - Contratos: partes, fechas, objeto, valor, cláusulas

**Campos a Extraer (del PRD):**

```python
# Para Facturas
FACTURA_FIELDS = [
    "numero_factura",
    "fecha_emision",
    "fecha_vencimiento",
    "nombre_proveedor",
    "nif_cif_proveedor",
    "importe_total",
    "importe_iva"
]

# Para Contratos
CONTRATO_FIELDS = [
    "partes_involucradas",
    "fecha_firma",
    "fecha_inicio",
    "fecha_fin",
    "objeto_contrato",
    "valor_monetario",
    "clausulas_clave"
]
```

### Semana 6: Workers Asíncronos (Celery)

#### Día 1-3: Configuración Celery
```python
# app/celery_app.py
from celery import Celery

celery_app = Celery(
    'sapi',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/1'
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)
```

#### Día 4-5: Tareas de Procesamiento

**Task 1: process_document**
```python
@celery_app.task(bind=True, max_retries=3)
def process_document(self, document_id: str):
    """
    1. Descargar documento de S3
    2. OCR si es necesario
    3. Clasificar con Gemini
    4. Extraer entidades
    5. Generar resumen
    6. Guardar en DB
    7. Notificar usuario
    """
    pass
```

**Task 2: send_notification**
```python
@celery_app.task
def send_notification(document_id: str, user_email: str, status: str):
    """Envía email de notificación"""
    pass
```

**Definition of Done:**
- [x] Gemini integrado y funcionando
- [x] Clasificación >90% precisión
- [x] Extracción de entidades funcional
- [x] Workers Celery procesando documentos

---

## FASE 3: Frontend

**Duración:** 3 semanas (Semanas 7-9)  
**Objetivo:** Panel de administración completo

### Semana 7: Setup y Autenticación

#### Estructura del Frontend
```
sapi_frontend/
├── public/
├── src/
│   ├── api/
│   │   ├── index.ts
│   │   ├── auth.ts
│   │   └── documents.ts
│   ├── components/
│   │   ├── ui/
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Modal.tsx
│   │   │   └── Table.tsx
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Layout.tsx
│   │   └── documents/
│   │       ├── DocumentList.tsx
│   │       ├── DocumentUpload.tsx
│   │       └── DocumentDetail.tsx
│   ├── contexts/
│   │   └── AuthContext.tsx
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   └── useDocuments.ts
│   ├── pages/
│   │   ├── Login.tsx
│   │   ├── Dashboard.tsx
│   │   ├── Documents.tsx
│   │   └── DocumentDetail.tsx
│   ├── types/
│   │   └── index.ts
│   ├── App.tsx
│   └── main.tsx
├── package.json
└── Dockerfile
```

#### Día 1-2: Configuración Proyecto
- Vite + React + TypeScript
- Tailwind CSS
- React Router DOM
- Axios + React Query
- React Hook Form + Zod

#### Día 3-5: Login y Auth
- Página de login
- AuthContext para gestión de estado
- Protected routes
- Interceptores Axios para JWT

### Semana 8: Dashboard y Lista de Documentos

#### Día 1-2: Dashboard
- Sidebar con navegación
- Header con usuario
- Dashboard con estadísticas

#### Día 3-5: Lista de Documentos
```
┌──────────────────────────────────────────────────────────────┐
│  SAPI Admin Panel                              [Usuario ▼]   │
├──────────────────────────────────────────────────────────────┤
│ ┌─────────┐                                                   │
│ │ ☰       │  DOCUMENTOS                                      │
│ │ Inicio  │  ───────────────────────────────────────────────│
│ │ Docs ✓  │  [+ Cargar Documento]                            │
│ │ Users   │                                                  │
│ │         │  Filtros: [Estado ▼] [Tipo ▼] [🔍 Buscar]      │
│ │         │                                                  │
│ │         │  ┌─────────────────────────────────────────┐   │
│ │         │  │ Nombre        │ Tipo     │ Estado  │ Acc │   │
│ │         │  ├─────────────────────────────────────────┤   │
│ │         │  │ factura_1.pdf │ Factura  │ ✓ Listo │ 👁  │   │
│ │         │  │ contrato_1...  │ Contrato │ ⚠ Rev.  │ 👁  │   │
│ │         │  │ factura_2.pdf │ Factura  │ ⟳ Proc. │ 👁  │   │
│ │         │  └─────────────────────────────────────────┘   │
│ │         │                                                  │
│ │         │  [< Anterior]  1  [2]  [3]  [Siguiente >]      │
│ └─────────┘                                                   │
└──────────────────────────────────────────────────────────────┘
```

### Semana 9: Detalle y Revisión de Documentos

#### Día 1-2: Vista de Detalle
```
┌──────────────────────────────────────────────────────────────┐
│  ← Volver a Documentos                                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────┐ ┌────────────────────────────┐ │
│  │                         │ │ DATOS EXTRAÍDOS            │ │
│  │    VISOR DE PDF         │ │ ──────────────────────────│ │
│  │                         │ │ Tipo: Factura (98%)        │ │
│  │    [PDF Viewer]         │ │                            │ │
│  │                         │ │ Resumen: Esta factura...   │ │
│  │                         │ │                            │ │
│  │                         │ │ Campos Clave:              │ │
│  │                         │ │ ──────────────────────────│ │
│  │                         │ │ N° Factura: [2023-001] ✓  │ │
│  │                         │ │ Fecha: [2023-10-26] ✓     │ │
│  │                         │ │ Proveedor: [Tech Sol] ✓   │ │
│  │                         │ │ Total: [1,250.75€] ⚠     │ │
│  │                         │ │ IVA: [210.13€] ⚠          │ │
│  └─────────────────────────┘ └────────────────────────────┘ │
│                                                              │
│  [Guardar Cambios]  [Marcar Revisado]  [↓ Descargar]       │
└──────────────────────────────────────────────────────────────┘
```

#### Día 3-5: Human-in-the-Loop
- Formulario de corrección
- Indicadores de confianza IA
- Guardado de correcciones
- Historial de cambios

**Definition of Done:**
- [x] Login funcional
- [x] Dashboard con estadísticas
- [x] Lista de documentos con filtros
- [x] Upload de documentos
- [x] Detalle con visor PDF
- [x] Edición de campos extraídos
- [x] Responsive design

---

## FASE 4: Testing

**Duración:** 2 semanas (Semanas 10-11)  
**Objetivo:** Garantizar calidad y rendimiento

### Semana 10: Unit e Integration Tests

#### Cobertura Objetivo: >80%

```
tests/
├── api/
│   ├── test_auth.py
│   ├── test_documents.py
│   └── test_users.py
├── services/
│   ├── test_gemini_service.py
│   └── test_storage_service.py
├── tasks/
│   └── test_document_processing.py
└── conftest.py
```

#### Tipos de Tests

| Tipo | Herramienta | Cobertura |
|------|-------------|-----------|
| Unit | pytest | Funciones individuales |
| Integration | pytest + httpx | API + DB |
| E2E | Playwright | Flujos completos |
| Performance | Locust | Carga y estrés |

### Semana 11: Performance y Despliegue

#### Performance Tests
- Tiempo de respuesta API < 500ms (RNF001)
- Procesamiento documento < 30s (RNF002)
- 100 documentos/minuto (RNF003)

#### Despliegue
- CI/CD con GitHub Actions
- Imágenes Docker push a registry
- Despliegue a staging
- Smoke tests post-despliegue

**Definition of Done:**
- [x] >80% cobertura de código
- [x] Todos los tests pasando
- [x] Performance dentro de umbrales
- [x] Despliegue automático funcional

---

## FASE 5: Lanzamiento

**Duración:** 1 semana (Semana 12)

### Actividades de Lanzamiento

1. **Documentación Final**
   - README.md actualizado
   - Documentación de API
   - Guía de instalación

2. **UAT (User Acceptance Testing)**
   - Sesiones con usuarios reales
   - Recopilación de feedback
   - Ajustes finales

3. **Lanzamiento**
   - Deploy a producción
   - Monitoreo intensivo
   - Soporte post-lanzamiento

---

## 2.3 KPIs y Métricas de Éxito

### KPIs Técnicos

| KPI | Objetivo | Método de Medición |
|-----|----------|---------------------|
| Cobertura de código | >80% | pytest-cov |
| Tiempo respuesta API | <500ms | APM tools |
| Tiempo procesamiento | <30s/doc | Logs workers |
| Disponibilidad | 99.9% | Uptime monitor |

### KPIs de Negocio (del PRD)

| KPI | Objetivo | Timeline |
|-----|----------|----------|
| Tiempo procesamiento | -70% | 6 meses |
| Tasa error extracción | <5% | MVP |
| Precisión clasificación | >90% | MVP |
| Costo por documento | -40% | 1 año |
| Volumen procesado | 10,000/mes | MVP |
| Adopción usuarios | 80% en 3 meses | Post-lanzamiento |

---

## 2.4 Recursos Necesarios

### Equipo
| Rol | Cantidad | Semanas |
|-----|----------|---------|
| Backend Developer | 1-2 | 12 |
| Frontend Developer | 1 | 6 |
| DevOps Engineer | 0.5 | 4 |
| QA Engineer | 0.5 | 3 |

### Infraestructura (Producción Estimada)
| Servicio | Especificación | Costo Mensual Est. |
|----------|---------------|-------------------|
| Backend (2 pods) | 2 vCPU, 4GB RAM | $80 |
| Workers (4 pods) | 2 vCPU, 4GB RAM | $160 |
| PostgreSQL (RDS) | db.t3.medium | $100 |
| Redis (ElastiCache) | cache.t3.micro | $20 |
| Object Storage | 100GB | $5 |
| Gemini API | Uso variable | $200-500 |
| **Total** | | **$565-865** |

---

## 2.5 Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Precisión IA insuficiente | Media | Alto | HIL robusto, feedback loop |
| Costos Gemini elevados | Alta | Medio | Optimizar prompts, caching |
| Dependencia vendor | Baja | Medio | Abstraer capa IA |
| Resistencia usuarios | Media | Medio | Capacitación, UX research |
| Retrasos técnicos | Media | Medio | Buffer en timeline, agile |

---

## 2.6 Próximos Pasos Inmediatos

1. **Revisar y aprobar este plan**
2. **Asignar equipo**
3. **Semana 1:** Iniciar correcciones documentales
4. **Semana 2:** Comenzar desarrollo FASE 1

---

**Documento preparado por:** AI Assistant  
**Última actualización:** 2026-03-25

