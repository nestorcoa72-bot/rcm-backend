# RCM Motores — Backend de Confiabilidad

API real (no aproximación) para gestión y análisis de confiabilidad de motores
eléctricos controlados por VFD. Reemplaza la lógica en JavaScript del prototipo
por ajuste de Weibull con **Máxima Verosimilitud y censura real** (librería
`reliability`), validado y probado — ver `test_weibull.py`.

## Levantar el proyecto

```bash
docker compose up --build
```

Esto levanta:
- **PostgreSQL** en `localhost:5432` con el esquema (`schema.sql`) ya aplicado y los 5 modos de falla precargados.
- **API FastAPI** en `localhost:8000`, con documentación interactiva automática en `http://localhost:8000/docs`.

## Flujo de uso típico (vía `/docs` o cualquier cliente HTTP)

1. `POST /motores` — registrar el activo.
2. `POST /fallas` — cargar historial (marcar `censurado: true` para motores que siguen operando).
3. `GET /amef?id_motor=...` — ver la matriz AMEF con NPR ya calculado.
4. `POST /simulaciones/weibull-montecarlo` — ejecutar el ajuste + Montecarlo (10,000 iteraciones por defecto).
5. `POST /rcm/plan` — con el `id_simulacion` obtenido, generar el intervalo óptimo y la rutina prescrita.

## Diferencia clave vs. el prototipo en el navegador

| | Prototipo (JS en el navegador) | Este backend |
|---|---|---|
| Ajuste de Weibull | Regresión de rango mediano (aproximación) | Máxima Verosimilitud con censura real (`reliability`) |
| Persistencia | `window.storage` (por usuario, no relacional) | PostgreSQL (multiusuario, consultable, auditable) |
| Auditoría | No guarda histórico de simulaciones | Cada simulación y plan queda registrado con timestamp |

## Roadmap — hacia una herramienta más potente

**✅ Ya implementado: modelo de riesgos proporcionales de Cox (covariables del VFD)**

Nuevos endpoints:
- `POST /analisis/cox` — ajusta el modelo con las covariables que elijas (frecuencia de conmutación, THD, temperatura) y devuelve el *hazard ratio* de cada una, traducido a una frase accionable ("cada kHz adicional multiplica el riesgo de falla por 1.27").
- `POST /analisis/cox/escenario` — responde directamente "¿qué pasa si cambio esta condición?": le das un escenario hipotético (ej. subir la frecuencia de 4kHz a 12kHz) y te devuelve la mediana de vida esperada bajo ese escenario.

Esto requiere que cada evento de `historial_fallas` tenga su fila correspondiente en la nueva tabla `covariables_evento` (frecuencia, THD, temperatura al momento del evento) — sin eso, Cox no tiene con qué trabajar y el endpoint avisa explícitamente cuántos datos faltan en vez de inventar un número.

**Validado:** el modelo fue probado con datos sintéticos antes de integrarlo — con una relación real entre frecuencia/THD/temperatura y tiempo de vida, el modelo correctamente detectó hazard ratios de 1.27 (frecuencia), 1.33 (THD) y 1.08 (temperatura), con un índice de concordancia de 0.81 (0.5 = azar, 1.0 = perfecto).

**Diferencia clave vs. Weibull simple:**

| | Weibull simple | Cox con covariables |
|---|---|---|
| Pregunta que responde | "¿Cuándo va a fallar en promedio?" | "¿Qué pasa si cambio esta condición de operación?" |
| Datos mínimos requeridos | 5 fallas | 20 observaciones con covariables completas |
| Uso típico | Planeación de intervalo de mantenimiento | Justificar una decisión de ingeniería (ej. bajar la frecuencia de conmutación) |

---

Extensiones aún no implementadas, ordenadas por impacto:

1. **Aprendizaje a nivel de flota** — cuando un motor individual tiene pocas fallas propias, usar datos de motores del mismo modelo/fabricante en toda la planta (o entre plantas) para un ajuste Bayesiano jerárquico más robusto que el fallback fijo actual.
2. **Ingesta en tiempo real** — conectar `historial_operativo` y `covariables_evento` a un histórico de PLC/SCADA (OPC-UA) para que la vibración, temperatura y frecuencia entren automáticamente, en vez de captura manual.
3. **Alertas predictivas activas** — un job periódico (Celery + Redis) que recorra motores cuya `horas_operacion_acumuladas` se acerque al intervalo óptimo o al B10, y dispare notificación antes de llegar ahí.
4. **Detección de anomalías en vibración** — un modelo simple (Isolation Forest o autoencoder) sobre las series de `vibracion_mm_s` para detectar desviaciones antes de que crucen el umbral fijo de ISO 10816.
5. **Dashboard multi-planta** — vista consolidada de NPR y salud de flota entre múltiples sitios, con priorización de presupuesto de mantenimiento entre plantas.

Ninguna de estas es necesaria para que la herramienta funcione — son las palancas reales para seguir haciéndola más potente con datos genuinos de operación, no solo con más código.
