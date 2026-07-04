# InteractorGate — Backend

Backend REST para **InteractorGate**, una aplicación de escritorio de
**Comunicación Aumentativa y Alternativa (CAA)** para personas con discapacidad
motriz en entornos domésticos. El sistema permite comunicarse mediante
**seguimiento ocular (eye tracking)** y **predicción contextual de texto**,
usando Deep Learning.

> Proyecto de tesis — Universidad Peruana de Ciencias Aplicadas (UPC).
> Autores: **Eduardo Chero** y **Xiao Lian Li**.

- **URL en producción:** https://ig-backend-tesis.azurewebsites.net
- **Contrato de la API (para el frontend):** [`docs/API.md`](docs/API.md)

---

## ¿Para qué sirve?

El backend orquesta la lógica central y expone endpoints sobre HTTPS a la
aplicación de escritorio en **Flutter** (repositorio aparte). Sus
responsabilidades:

- **Identidad y autenticación** de usuarios con JWT.
- **Pipeline de predicción**: recibe entrada (mirada o texto), la enruta al
  modelo de IA correspondiente y devuelve el resultado.
  - **RNN (texto):** modelo real **LSTM en PyTorch** que sugiere frases
    contextuales para el tablero de comunicación.
  - **CNN (mirada):** reconocimiento de la mirada (en desarrollo).
- **Registro de interacciones (telemetría)** en una base documental para
  análisis y reentrenamiento futuro de los modelos.

---

## Stack tecnológico

| Capa | Tecnología | Versión |
|---|---|---|
| Lenguaje | Python | 3.13 |
| Framework | Django | 5.1.15 |
| API REST | Django REST Framework | 3.15.2 |
| Autenticación | djangorestframework-simplejwt | 5.5.1 |
| BD relacional | Azure SQL Database (`mssql-django` + `pyodbc`) | 1.7.2 / 5.3.0 |
| BD documental | Azure Cosmos DB (API MongoDB) vía `pymongo` | 4.17.0 |
| IA — Predicción de texto (RNN) | PyTorch (LSTM) | 2.12.1 (CPU) |
| Cómputo numérico | NumPy | 2.5.0 |
| Variables de entorno | django-environ | 0.13.0 |
| CORS | django-cors-headers | 4.9.0 |
| Servidor WSGI | gunicorn | 26.0.0 |
| Estáticos en producción | WhiteNoise | 6.12.0 |

> Versiones exactas de todas las dependencias en [`requirements.txt`](requirements.txt).
> En Docker/Azure se instala la build **CPU** de PyTorch (Azure App Service B1
> no tiene GPU).

---

## Estructura del proyecto

```
ig-django-backend/
├── config/
│   ├── settings/
│   │   ├── base.py         # Configuración común (Azure SQL, Cosmos, JWT, CORS, throttling)
│   │   ├── local.py        # Overrides de desarrollo + logging
│   │   └── production.py   # DEBUG=False, cabeceras de seguridad, HTTPS, WhiteNoise
│   ├── mongo.py            # Cliente PyMongo (Cosmos DB) — logs y training_history
│   ├── urls.py             # Rutas raíz + healthz + inclusión de apps
│   └── views.py            # Endpoints públicos: / y /healthz/
├── users/                  # Modelo User personalizado + autenticación JWT
├── predictions/            # Modelos + endpoints del pipeline de predicción (Azure SQL)
├── interaction_logs/       # Escritura/lectura de telemetría (Cosmos DB, sin ORM)
├── ai_modules/
│   ├── orchestrator.py     # Enruta la petición al modelo CNN o RNN
│   ├── cnn_module.py       # Eye tracking (stub — en desarrollo)
│   ├── rnn_module.py       # Re-exporta el TextPredictor real
│   └── rnn/                # Modelo RNN real (LSTM PyTorch): corpus, vocab, entrenamiento, inferencia
├── docs/API.md             # Contrato de la API para el frontend
├── Dockerfile
├── requirements.txt
└── manage.py
```

---

## Puesta en marcha (desarrollo local)

Requisitos previos: **Python 3.13**, **ODBC Driver 17/18 for SQL Server** y
acceso a las credenciales de Azure (SQL + Cosmos).

```powershell
# 1. Crear y activar el entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
copy .env.example .env    # y completar los valores reales

# 4. Aplicar migraciones (contra Azure SQL)
python manage.py migrate

# 5. Levantar el servidor de desarrollo
python manage.py runserver
```

El módulo de settings por defecto en desarrollo es `config.settings.local`:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.local"
```

### Variables de entorno (`.env`)

| Variable | Descripción |
|---|---|
| `DJANGO_SECRET_KEY` | Clave secreta de Django |
| `DJANGO_DEBUG` | `True` en local, `False` en producción |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos (lista separada por comas) |
| `SQL_DB` / `SQL_USER` / `SQL_PASSWORD` / `SQL_HOST` / `SQL_PORT` | Credenciales de Azure SQL |
| `SQL_ODBC_DRIVER` | `ODBC Driver 17 for SQL Server` (local) / `18` (contenedor) |
| `MONGO_URI` / `MONGO_DB` | Cadena de conexión y BD de Cosmos DB (API MongoDB) |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | Vida del access token (por defecto 60) |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | Vida del refresh token (por defecto 7) |
| `CORS_ALLOWED_ORIGINS` | Orígenes permitidos para CORS |

> Las credenciales **nunca** se suben al repositorio: `.env` está en
> `.gitignore`. En producción se inyectan desde **Azure Key Vault**.

---

## Modelo de IA — RNN (predicción de texto)

Modelo **LSTM real en PyTorch** entrenado sobre un corpus de frases CAA en
español. Documentación y benchmark en
[`ai_modules/rnn/README.md`](ai_modules/rnn/README.md).

```powershell
# (Re)entrenar el modelo y regenerar el artefacto + métricas
python -m ai_modules.rnn.train
```

---

## Endpoints principales

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| GET | `/` | Público | Índice de la API |
| GET | `/healthz/` | Público | Health check |
| POST | `/api/users/register/` | Público | Registro |
| POST | `/api/users/login/` | Público | Login (devuelve JWT) |
| POST | `/api/token/refresh/` | Público | Renovar access token |
| POST | `/api/users/logout/` | JWT | Cerrar sesión (blacklist) |
| GET/PUT | `/api/users/me/` | JWT | Perfil del usuario |
| POST | `/api/predictions/` | JWT | Ejecutar predicción (CNN/RNN) |
| GET | `/api/predictions/history/` | JWT | Historial de predicciones |
| POST | `/api/logs/` | JWT | Registrar evento de interacción |
| GET | `/api/logs/session/<id>/` | JWT | Eventos de una sesión |

Detalle completo de cuerpos y respuestas en [`docs/API.md`](docs/API.md).

---

## Despliegue

Contenedor Docker desplegado en **Azure App Service for Containers**
(`ig-backend-tesis`, plan B1). CI/CD con **GitHub Actions**: build → push a
**Azure Container Registry** → deploy en cada push a `main`. Los secretos se
gestionan con **Azure Key Vault** (referencias + identidad administrada) y el
tráfico va sobre **HTTPS/TLS**.

---

## Estado del proyecto

| Fase | Descripción | Estado |
|---|---|---|
| 1 | Entorno y scaffold | ✅ Completo |
| 2 | API principal (identidad y auth) | ✅ Completo |
| 3 | Pipeline de predicción | ✅ Completo |
| 4 | Logs de interacción (Cosmos DB) | ✅ Completo |
| 5 | Integración de modelos de IA | ⚠️ RNN real (LSTM PyTorch) · CNN en desarrollo |
| 6 | Hardening de seguridad + Azure | ✅ Completo |
| 7 | CI/CD y despliegue | ✅ Completo |
| 8 | Testing y QA | ⚠️ Suite de tests automatizados (23) + CI en GitHub Actions · usabilidad/rendimiento pendientes |

---

## Autores

- **Eduardo Chero**
- **Xiao Lian Li**

Proyecto de tesis — Universidad Peruana de Ciencias Aplicadas (UPC), 2026.
