# InteractorGate — Auditoría de documentación y contrato (backend)

> **Propósito de este documento.** Recap de la auditoría del repo `ig-django-backend`
> realizada el **2026-09-02**. Está pensado como **entrada para una sesión
> posterior que abra los dos repos a la vez** (backend Django + cliente Flutter)
> y analice la sincronización completa entre ambos.
>
> Todo lo que aparece aquí está **verificado contra el código y ejecutado**, no
> inferido de los `.md`. Las citas son `archivo:línea` del commit `82d095f`.

---

## 0. Cómo usar este documento en la sesión combinada

1. Leer §1 (estado real) y §2 (contrato real de la API) — es la **fuente de
   verdad**, por encima de cualquier `.md` del repo.
2. Contrastar el cliente Flutter contra §2, usando la checklist de §5.
3. Los hallazgos de §3 son del backend y **siguen sin corregir**; varios de
   ellos son justamente los que pueden haber inducido a error al frontend.
4. No dar por buena ninguna afirmación de `docs/API.md`, `README_EQUIPO.md` o
   `InteractorGate_Recap_ClaudeCode.md` sobre el CNN: están desactualizados.

---

## 1. Estado real del backend (verificado el 2026-09-02)

| Elemento | Estado | Evidencia |
|---|---|---|
| Suite de tests | ✅ 23/23 pasan | `python manage.py test --settings=config.settings.test` → `Ran 23 tests in 2.760s — OK` |
| RNN (texto) | ✅ Real | `ai_modules/rnn/` + `artifacts/phrase_lstm.pt` + `metrics.json` |
| CNN (mirada) | ✅ **Real** | `ai_modules/cnn/` completo + `artifacts/gaze_cnn.pt` (253K params, 7.67° cross-person) |
| Export ONNX | ✅ Existe y está commiteado | `ai_modules/cnn/export_onnx.py`, `artifacts/gaze_cnn.onnx`, `artifacts/gaze_cnn.meta.json` |
| Despliegue | ✅ En vivo | `https://ig-backend-tesis.azurewebsites.net` |
| CI/CD | ✅ Tests + deploy | `.github/workflows/tests.yml`, `deploy.yml` (`needs: test`) |
| Stack IA | **PyTorch puro** | `requirements.txt` — **no hay TensorFlow ni OpenCV** |

**Fases:** 1–7 completas. Fase 8 parcial (tests automatizados + CI hechos;
usabilidad, accesibilidad y rendimiento pendientes → OE4).

> El commit que cambió el estado del CNN es `e2a1575`
> *"feat(cnn): real gaze-estimation CNN on MPIIGaze (Phase 5, OE3-I2)"*.
> **Toda la documentación anterior a ese commit quedó desincronizada.**

---

## 2. Contrato REAL de la ruta de mirada (lo crítico para Flutter)

Esta sección **corrige** a `docs/API.md`. Es lo primero que hay que contrastar
contra el cliente.

### 2.1 Formato de entrada — `POST /api/predictions/` con `input_type: "gaze"`

`ai_modules/cnn/infer.py:60-80` (`_coerce_patch`) acepta **únicamente**:

| Forma aceptada | Detalle |
|---|---|
| `str` base64 | de un **buffer crudo 36×60 uint8** = exactamente **2160 bytes** |
| `list` / `tuple` | numérica de **2160 valores** (plana o 2D 36×60) |
| `dict` | envolviendo cualquiera de las anteriores bajo las claves `patch`, `image`, `eye` o `frame` |

**NO acepta JPEG, PNG ni ninguna imagen codificada.** El parche debe ser el
recorte de ojo **ya normalizado** al estilo MPIIGaze (36×60, escala de grises).

> ⚠️ **Fallo silencioso.** Si el payload no encaja, el `except` de
> `infer.py:74` lo descarta y sustituye por un parche gris neutro (`127.0`).
> El endpoint responde **`201` con una celda y una confianza de aspecto
> normal, pero inventada**. No hay error, ni warning, ni indicio en la
> respuesta. Es la causa más probable de una integración "que funciona" pero
> con resultados sin sentido.

### 2.2 Formato de salida

`predictions/serializers.py` (`PredictionResultSerializer`) solo expone:

```json
{ "id", "model_used", "output_text", "confidence_score", "response_time_ms", "created_at" }
```

- `output_text` = **la palabra de la celda seleccionada** (string simple).
- `confidence_score` = softmax sobre distancias a las celdas (`board.py:52-63`).
- **`gaze.x/y` y `angle.pitch/yaw` NO se devuelven ni se persisten.** El
  orchestrator los recibe en `raw_output` (`orchestrator.py`) pero se descartan
  al serializar. Si el cliente los espera, no llegan.

### 2.3 Vocabulario del tablero (fijo, `ai_modules/cnn/board.py:20-23`)

Grid 4 columnas × 2 filas:

```
sí      no      agua     comida
ayuda   baño    dormir   gracias
```

Cualquier tablero del cliente con otras celdas u otra disposición **no coincide**
con lo que el backend puede devolver.

### 2.4 Proyección ángulo → pantalla

`board.py:36-46`: campo de visión fijo de ±25°, **sin calibración por usuario**.
Está declarado en el código como *placeholder de despliegue*: en el cliente la
calibración real del tracker debe reemplazarlo.

### 2.5 Arquitectura acordada

El eye tracking **en tiempo real corre en el cliente**, no en el backend
(latencia, privacidad, offline). El endpoint `/api/predictions/` en modo `gaze`
es **ruta de verificación por lotes**, no el bucle de mirada en vivo.
Para el cliente existe `gaze_cnn.onnx` + `gaze_cnn.meta.json` (media y desviación
de normalización + tamaño de imagen) para correr con `onnxruntime`.

---

## 3. Hallazgos de documentación (backend, SIN corregir)

### 🔴 Críticos

**H1 — `docs/API.md:161-172` describe el CNN como stub y con entrada equivocada.**
Dice *"the CNN returns random data for now"* y `"frame": "<base64-jpeg-or-coords>"`.
Ambas cosas son falsas: el modelo es real y **no acepta JPEG** (ver §2.1).
Es el único hallazgo que produce un **bug real de integración**, no solo
desinformación — y con fallo silencioso.

**H2 — `README.md:102` — `copy .env.example .env` no funciona.**
El archivo no existe: fue borrado (`89f8eab`, `b8ce5fd`) y además está listado en
`.gitignore:32`. El paso 3 del setup está muerto para cualquiera que clone.
`InteractorGate_Recap_ClaudeCode.md:119` también afirma que está commiteado.

### 🟡 Importantes

**H3 — `README_EQUIPO.md` está una fase entera atrasado** (y es el doc de handoff
al frontend):
- Cabecera L7: *"Última actualización: fase 5 (RNN de texto ya es real)"*
- Tabla L37: CNN *"en desarrollo"* · L40: Testing *"⚠️ Pendiente"*
- §6 completa (L112-126): *"el modelo real está en desarrollo"*
- §8 L144-146: ítems 1 (CNN) y 2 (tests) ya están hechos

**H4 — El export ONNX no está documentado en ningún `.md`.**
`export_onnx.py:4-6` dice que el sidecar de Flutter corre con `onnxruntime`, pero
hay **cero menciones** en los 6 markdown del repo. Es justo el artefacto que
necesita el frontend. (`onnxruntime` tampoco está en `requirements.txt`; solo se
usa en un chequeo opcional protegido por `try/except`, lo cual es correcto, pero
conviene decirlo.)

**H5 — `ai_modules/rnn/README.md:11`** — *"The eye-tracking CNN remains a stub"*.
Contradice directamente al `README.md` principal.

**H6 — `docs/API.md` no publica el vocabulario del tablero** (§2.3) ni aclara que
`gaze.x/y` y `pitch/yaw` no se devuelven (§2.2).

### 🟢 Menores

**H7 — `InteractorGate_Recap_ClaudeCode.md`**, el más desactualizado a nivel de stack:
- L54, L39, L250: *"OpenCV + TensorFlow"* → **no se usa ninguno**, es PyTorch puro
- L79: `ai_modules/ → CNN/RNN stubs`; el árbol tampoco incluye `production.py`,
  `docs/`, `cnn/`, `rnn/`
- L18: *"as of 2026-06-21"* con contenido posterior
- Backticks escapados (`` \` ``) desde L41: se renderizan como barras invertidas
  literales en GitHub

**H8 — `README.md`** es el más fiable de los cuatro. Solo le falta la fila del CNN
en la tabla de stack y la mención al ONNX.

---

## 4. Corrección propuesta (acordada, no ejecutada)

Rama `docs/sync-phase5-cnn` con:

1. `docs/API.md`: reescribir la sección de mirada con §2.1–§2.4 reales.
2. Crear `.env.example` con placeholders y **quitarlo de `.gitignore`**
   (mantener `.env` y `.env.*` ignorados).
3. `README_EQUIPO.md`: actualizar tabla de fases, §6 y §8; añadir ONNX.
4. Documentar el flujo ONNX (README principal + `ai_modules/cnn/README.md`).
5. `ai_modules/rnn/README.md:11`: eliminar la frase del stub.
6. `docs/API.md`: añadir vocabulario del tablero y aclarar campos no devueltos.
7. `InteractorGate_Recap_ClaudeCode.md`: corregir stack (PyTorch), árbol, fecha
   y backticks escapados.
8. `README.md`: fila CNN en la tabla de stack + mención al ONNX.

**Idealmente, además:** hacer que la ruta `gaze` **rechace** un parche inválido
con `400` en vez de degradar en silencio (o al menos devolver un flag
`"degraded": true`). Eso convierte H1 en un error visible en lugar de datos
falsos. Requiere decisión: cambia el contrato.

---

## 5. Checklist para la sesión combinada (backend ↔ Flutter)

Verificar en el repo Flutter, en este orden:

- [ ] **Formato del parche de ojo** que envía a `/api/predictions/` con
      `input_type: "gaze"` → ¿es el buffer crudo 36×60 de §2.1, o está mandando
      un JPEG/PNG en base64 (guiado por el `docs/API.md` erróneo)?
- [ ] **¿Usa `gaze_cnn.onnx`?** ¿Tiene el modelo embebido? ¿Aplica la
      normalización de `gaze_cnn.meta.json` (mean/std) antes de inferir?
- [ ] **Celdas del tablero** en la UI vs. las 8 de §2.3.
- [ ] **Split de sugerencias RNN**: `output_text` viene unido por `" | "`;
      ¿el cliente hace el split correcto?
- [ ] **Rotación de refresh token**: ¿guarda el **nuevo** refresh en cada
      `POST /api/token/refresh/`? (rotación + blacklist están activos).
- [ ] **Manejo de 401** → refresh → reintento único.
- [ ] **Manejo de 429**: límites reales son anon 60/min, auth 240/min,
      login 10/min, register 20/h. ¿Respeta `Retry-After`?
- [ ] **Telemetría**: ¿emite `session_start` / `session_end` y usa los
      `event_type` válidos (`gaze`, `selection`, `dwell`, `calibration`,
      `session_start`, `session_end`)?
- [ ] **`session_id`**: ¿UUID generado por sesión y reutilizado en logs y
      predicciones?
- [ ] **Base URL**: ¿apunta a `https://ig-backend-tesis.azurewebsites.net`
      en release y a `localhost:8000` en debug?
- [ ] **CORS**: ¿el origen de la app está en `CORS_ALLOWED_ORIGINS`?
- [ ] **Calibración**: ¿el cliente calibra por usuario y sustituye el FOV fijo
      de ±25° de `board.py`?

---

## 6. Pendientes del proyecto (más allá de los docs)

- **OE4:** testing de usabilidad con usuarios objetivo, validación de
  accesibilidad, pruebas de rendimiento/latencia, informe QA contra los
  indicadores de éxito.
- **CNN, mejoras documentadas como siguiente paso** (`ai_modules/cnn/README.md`):
  fusión de head-pose en la cabeza FC, más muestras por participante,
  data augmentation, y validación leave-one-person-out completa en vez de un
  único split.
- **RNN:** ampliar el corpus (103 frases es poco; val top-3 41.8%), early
  stopping sobre perplejidad de validación.
- **Colección Postman** (mencionada como pendiente; `postman/` está en
  `.gitignore:47`).

---

## 7. Datos de referencia rápidos

- **Repo backend:** `https://github.com/InteractorGate/ig-django-backend`
- **Prod:** `https://ig-backend-tesis.azurewebsites.net`
- **Commit auditado:** `82d095f`
- **Ejecutar tests:** `python manage.py test --settings=config.settings.test`
- **Reentrenar CNN:** `pip install scipy` · `$env:MPIIGAZE_DIR = "<ruta>"` ·
  `python -m ai_modules.cnn.train`
- **Reentrenar RNN:** `python -m ai_modules.rnn.train`
- **Exportar ONNX:** `python -m ai_modules.cnn.export_onnx`
- **Benchmarks:** CNN 5.67° train / **7.67° val cross-person** (p12–p14) ·
  RNN top-3 79.9% train / 41.8% val

---

*Auditoría generada con Claude Code el 2026-09-02. Proyecto de tesis UPC —
Eduardo Chero y Xiao Lian Li.*
