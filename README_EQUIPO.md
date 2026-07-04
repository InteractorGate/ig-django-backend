# InteractorGate — Guía del Backend para el Equipo

> Documento para coordinar el trabajo entre el **backend** (Django) y el
> **frontend** (Flutter desktop). Explica qué está listo, cómo levantar el
> backend, y contra qué contrato debe integrarse la app.
>
> Última actualización: fase 5 (RNN de texto ya es real).

---

## 1. ¿Qué hace el backend?

Es el cerebro de InteractorGate: expone una **API REST sobre HTTPS** que la app
de escritorio en Flutter consume. Se encarga de:

- **Autenticación** de usuarios con **JWT** (login, registro, refresh, logout).
- **Predicción de texto (RNN real)**: dado un contexto de palabras, sugiere
  frases para el tablero de comunicación.
- **Predicción de mirada (CNN)**: enrutamiento listo; el modelo real está en
  desarrollo (ver sección 6).
- **Telemetría**: guarda eventos de interacción (mirada, selecciones, dwell…)
  en Cosmos DB para análisis y reentrenamiento.

- **URL en producción (ya desplegada):** https://ig-backend-tesis.azurewebsites.net
- **Repositorio backend:** `ig-django-backend`

---

## 2. Estado actual por fases

| Fase | Título | Estado |
|---|---|---|
| 1 | Entorno y scaffold | ✅ Completo |
| 2 | API principal (identidad y auth) | ✅ Completo |
| 3 | Pipeline de predicción | ✅ Completo |
| 4 | Logs de interacción (Cosmos DB) | ✅ Completo |
| 5 | Modelos de IA reales | ⚠️ **RNN de texto: listo (real)** · CNN de mirada: en desarrollo |
| 6 | Seguridad + Azure | ✅ Completo |
| 7 | CI/CD y despliegue | ✅ Completo (en vivo en Azure) |
| 8 | Testing y QA | ⚠️ Pendiente |

**En resumen:** el backend está **funcional y desplegado de punta a punta**.
El frontend ya puede integrarse contra la API real hoy mismo.

---

## 3. Contrato de la API (lo más importante para el frontend)

👉 **Todo el detalle de endpoints, cuerpos de petición y respuestas está en
[`docs/API.md`](docs/API.md).**

Resumen de lo esencial para empezar a integrar:

- **Autenticación:** `POST /api/users/login/` devuelve `access` y `refresh`.
  Enviar `Authorization: Bearer <access>` en cada petición protegida.
- **Access token:** dura 60 min. Cuando expire (error `401`), renovar con
  `POST /api/token/refresh/` y **guardar el nuevo refresh token** (hay rotación).
- **Predicción de texto (RNN):**
  ```json
  POST /api/predictions/
  { "input_type": "text", "raw_input": { "context": "me duele" }, "session_id": "<uuid>" }
  ```
  Respuesta: `result.output_text` trae las sugerencias separadas por `" | "`
  (ej. `"la cabeza | el estómago | mucho aquí"`) y `result.confidence_score`
  es la confianza real del modelo.
- **Telemetría:** `POST /api/logs/` para registrar eventos de la sesión
  (`gaze`, `selection`, `dwell`, `calibration`, `session_start`, `session_end`).

---

## 4. Cómo levantar el backend en local

Requisitos: **Python 3.13**, **ODBC Driver 17/18 for SQL Server**, y el archivo
`.env` con las credenciales de Azure (pedírselo a Eduardo — **no** está en el
repo por seguridad).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

El servidor queda en `http://localhost:8000`. Se puede probar la API index en
`http://localhost:8000/` y el health check en `http://localhost:8000/healthz/`.

> Nota: las dos bases de datos (Azure SQL y Cosmos DB) están **en la nube**, así
> que no hace falta instalar ninguna BD local — solo tener el `.env` correcto.

---

## 5. Prueba rápida (humo)

```powershell
# Registrar un usuario
curl -X POST http://localhost:8000/api/users/register/ -H "Content-Type: application/json" `
  -d '{"username":"demo","email":"demo@demo.com","password":"DemoPass123","password2":"DemoPass123"}'

# Login → copiar el "access" de la respuesta
curl -X POST http://localhost:8000/api/users/login/ -H "Content-Type: application/json" `
  -d '{"username":"demo","password":"DemoPass123"}'

# Predicción de texto (reemplazar <ACCESS>)
curl -X POST http://localhost:8000/api/predictions/ -H "Content-Type: application/json" `
  -H "Authorization: Bearer <ACCESS>" `
  -d '{"input_type":"text","raw_input":{"context":"me duele"},"session_id":"demo-1"}'
```

---

## 6. Sobre el modelo de mirada (CNN) — coordinación necesaria

**Recomendación técnica:** el eye tracking en tiempo real debería ejecutarse
**en la app Flutter (lado cliente)**, no en el backend. Razones:

1. **Latencia:** enviar cada frame de cámara al servidor y esperar respuesta es
   demasiado lento para controlar la mirada en tiempo real.
2. **Privacidad y ancho de banda:** subir video continuamente a la nube es
   costoso y sensible.
3. **Funciona sin conexión:** el usuario puede seguir comunicándose si se cae
   la red.

El backend seguirá teniendo su rol: **guardar los eventos de mirada/selección**
(ya implementado en `/api/logs/`) y, opcionalmente, un endpoint de verificación
por lotes. **A conversar entre los dos** cómo se captura la cámara en Flutter.

---

## 7. Convenciones de trabajo

- **Ramas:** trabajar en `develop` (o ramas `feat/...`) y hacer merge a `main`
  mediante **Pull Request** al cerrar cada fase o funcionalidad.
- **Commits incrementales:** no perder más de una sesión de trabajo.
- **Secretos:** solo en `.env` (ignorado por git) y en Azure Key Vault —
  **nunca** commitear credenciales.
- **Auth:** todos los endpoints excepto `register`, `login` y `token/refresh`
  requieren token JWT.

---

## 8. Qué falta (siguientes pasos del backend)

1. **CNN de mirada** (fase 5) — según lo acordado en la sección 6.
2. **Tests automatizados** (fase 8) — pruebas unitarias e integración de auth,
   predicciones y logs.
3. **Testing con usuarios** y validación de accesibilidad (fase 8 / OE4).

---

## Autores

- **Eduardo Chero** — Backend / IA
- **Xiao Lian Li** — Frontend (Flutter)

Proyecto de tesis — UPC, 2026.
