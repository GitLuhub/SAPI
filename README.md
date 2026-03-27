# SAPI - Sistema de Automatización y Procesamiento Documental Inteligente

![SAPI Banner](https://img.shields.io/badge/SAPI-Inteligencia%20Artificial-0052CC?style=for-the-badge)

**SAPI** es una plataforma impulsada por IA (Google Gemini) diseñada para automatizar la extracción, clasificación y resumen de información de documentos estructurados y semi-estructurados (facturas y contratos), reduciendo significativamente la carga de trabajo manual, los tiempos de procesamiento y los errores humanos.

---

## 🚀 Características Principales

*   **Clasificación Automática:** Identificación inteligente del tipo de documento (Ej. "Factura de Proveedor" vs "Contrato Simple") basada en su contenido con un umbral de confianza.
*   **Extracción de Entidades con IA:** Extracción de campos clave (Nº de factura, fechas, importes, partes involucradas, cláusulas) utilizando Google Gemini 1.5 Pro.
*   **Resúmenes Ejecutivos:** Generación automática de resúmenes concisos del contenido del documento para revisión rápida.
*   **Procesamiento Asíncrono:** Arquitectura robusta y escalable basada en workers de Celery y Redis para manejar altos volúmenes de documentos sin bloquear la API.
*   **Revisión Humana (Human-in-the-Loop):** Panel de administración en React donde los usuarios pueden verificar, editar y aprobar los datos extraídos por la IA antes de darlos por procesados.
*   **Almacenamiento Seguro:** Integración con proveedores de Object Storage (S3/GCS o Local) para guardar de forma segura los documentos originales.

---

## 🛠️ Stack Tecnológico

**Backend:**
*   **Framework:** FastAPI (Python 3.13+)
*   **Base de Datos:** PostgreSQL 15 (SQLAlchemy 2.0 + Alembic)
*   **Procesamiento en Background:** Celery + Redis
*   **Inteligencia Artificial:** Google Generative AI API (Gemini-1.5-Pro)
*   **Autenticación:** JWT (JSON Web Tokens) con Passlib/Bcrypt

**Frontend:**
*   **Framework:** React 18+ con TypeScript
*   **Herramientas de Construcción:** Vite
*   **Estilos:** Tailwind CSS
*   **Estado & Data Fetching:** React Query + Zustand / Context API
*   **Enrutamiento:** React Router DOM

**Infraestructura & DevOps:**
*   **Contenedores:** Docker & Docker Compose
*   **Proxy Inverso:** Nginx
*   **Testing:** Pytest (Cobertura >80%)

---

## ⚙️ Arquitectura del Sistema

SAPI utiliza una arquitectura de microservicios contenerizados:

1.  **API Gateway (Nginx):** Enruta el tráfico estático al frontend y las peticiones `/api/v1` al backend.
2.  **SAPI Frontend:** Interfaz de usuario React que consume la API REST.
3.  **SAPI Backend (FastAPI):** Gestiona la lógica de negocio, autenticación, CRUD de documentos y delegación de tareas pesadas.
4.  **Message Broker (Redis):** Actúa como cola de mensajes para las tareas asíncronas.
5.  **AI Workers (Celery):** Descargan el documento, llaman a la API de Gemini, extraen los datos y actualizan el estado en la base de datos de manera asíncrona.
6.  **Database (PostgreSQL):** Almacena metadatos de documentos, datos extraídos y usuarios.

---

## 📦 Instalación y Despliegue (Local / Desarrollo)

### Prerrequisitos
*   [Docker](https://docs.docker.com/get-docker/) y Docker Compose instalados.
*   Una API Key de Google Gemini (puedes obtenerla en [Google AI Studio](https://aistudio.google.com/)).

### Pasos de Configuración

1.  **Clonar el repositorio:**
    ```bash
    git clone <url-del-repositorio>
    cd SAPI
    ```

2.  **Configurar Variables de Entorno:**
    Copia el archivo de ejemplo y configura tus credenciales reales (especialmente la `GEMINI_API_KEY`):
    ```bash
    cp sapi_backend/.env.example sapi_backend/.env
    ```
    *Edita el archivo `sapi_backend/.env` con tus credenciales.*

3.  **Construir y levantar los contenedores:**
    ```bash
    docker-compose up --build -d
    ```

4.  **Verificar el estado de los servicios:**
    ```bash
    docker-compose ps
    ```
    Asegúrate de que `backend`, `db`, `redis`, `ai_worker` y `web_client` estén en estado *Up*.

### Acceso a la Aplicación
*   **Frontend (Panel de Administración):** `http://localhost`
*   **Documentación de la API (Swagger UI):** `http://localhost/api/v1/docs` o `http://localhost:8000/docs`

---

## 🧪 Ejecución de Pruebas (Testing)

El proyecto cuenta con una suite completa de pruebas unitarias y de integración para el backend utilizando `pytest` y bases de datos en memoria (SQLite) para garantizar que la lógica de IA y procesamiento de documentos funcione correctamente.

Para ejecutar los tests localmente (fuera de Docker):

```bash
cd sapi_backend
# Crear un entorno virtual e instalar dependencias
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Ejecutar la suite de pruebas con cobertura
./run_tests.sh --cov=app tests/
```

---

## 📖 Uso del Sistema (Flujo Principal)

1.  **Registro/Login:** Accede al panel frontend e inicia sesión.
2.  **Carga de Documentos:** Sube un archivo PDF, JPG o PNG desde el Dashboard. El sistema pondrá el documento en estado `UPLOADED`.
3.  **Procesamiento IA:** El Celery Worker toma el documento, extrae el texto, llama a Gemini y clasifica el documento (Factura o Contrato). El estado cambia a `PROCESSING` y luego a `PROCESSED` (o `REVIEW_NEEDED` si la confianza de la IA es baja).
4.  **Revisión:** Entra al detalle del documento en la interfaz. Verás el documento original a la izquierda y los datos extraídos (con su % de confianza) a la derecha.
5.  **Corrección Manual:** Si la IA cometió un error, el operador puede editar el campo y guardarlo. El sistema registrará la intervención humana.

---

## 📄 Estructura del Proyecto

```text
SAPI/
├── sapi_backend/                 # Código fuente de FastAPI
│   ├── app/
│   │   ├── api/                  # Endpoints (Auth, Users, Documents)
│   │   ├── core/                 # Configuración, Seguridad (JWT)
│   │   ├── db/                   # Modelos SQLAlchemy y Base de Datos
│   │   ├── schemas/              # Modelos Pydantic (Validación I/O)
│   │   ├── services/             # Lógica de Negocio (AI, Storage)
│   │   └── tasks/                # Tareas Asíncronas (Celery)
│   ├── tests/                    # Suite de Pruebas (Pytest)
│   ├── Dockerfile                # Configuración de contenedor Backend
│   └── requirements.txt          # Dependencias de Python
├── sapi_frontend/                # Código fuente de React
│   ├── src/
│   │   ├── api/                  # Llamadas Axios al Backend
│   │   ├── components/           # Componentes UI reutilizables
│   │   ├── pages/                # Vistas (Dashboard, DocumentDetail, Login)
│   │   └── types/                # Interfaces TypeScript
│   └── Dockerfile                # Configuración de contenedor Frontend
├── nginx/                        # Configuración del Proxy Inverso
├── docker-compose.yml            # Orquestación de contenedores
└── PLAN_CORRECCIONES_...md       # Documento de diseño y arquitectura
```

---

## 🛡️ Seguridad y Buenas Prácticas Implementadas

*   **Hasheo de Contraseñas:** Se utiliza `Bcrypt` para almacenar contraseñas de forma segura.
*   **Autenticación JWT:** Tokens de corta duración para la comunicación Frontend-Backend.
*   **Desacoplamiento de Base de Datos:** Modelos agnósticos (ej. `sqlalchemy.UUID`) que permiten pruebas locales rápidas (SQLite) y escalabilidad en producción (PostgreSQL).
*   **Sanitización de Respuestas IA:** Lógica estricta de parseo JSON para evitar la inyección de código desde las respuestas del LLM (eliminación de vulnerabilidades tipo `eval()`).
*   **Dockerización Multi-Stage:** El frontend se compila y se sirve como estático a través de Nginx en producción, minimizando la superficie de ataque y el tamaño de la imagen.

---

**SAPI (Sistema de Automatización y Procesamiento Documental Inteligente) - Versión 1.0.0**  
*Desarrollado para optimizar los flujos de trabajo documentales corporativos.*