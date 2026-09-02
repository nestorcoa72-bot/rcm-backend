"""
Servicio de planeación RCM: cruza NPR (AMEF) con la curva F(t) de Weibull
para determinar el intervalo óptimo de mantenimiento y prescribir la rutina.
"""
import numpy as np
from services.reliability_service import reliability_f, b10_life


def occurrence_rating_from_rate(fallas_por_1000h: float) -> int:
    """
    Mapea una tasa de falla observada a la escala AIAG de Ocurrencia (1-10).
    Reemplaza la estimación estática del AMEF tradicional por un valor
    derivado de datos reales de operación.
    """
    r = fallas_por_1000h
    thresholds = [0, 0.01, 0.05, 0.1, 0.3, 0.6, 1, 2, 4]
    for rating, threshold in enumerate(thresholds, start=1):
        if r < threshold:
            return rating
    return 10


def compute_npr(severidad: int, ocurrencia: int, deteccion: int) -> int:
    return severidad * ocurrencia * deteccion


def estrategia_por_npr(npr: int) -> str:
    if npr >= 200:
        return "Predictivo intensivo (crítico)"
    elif npr >= 100:
        return "Predictivo estándar"
    return "Preventivo basado en tiempo"


def optimal_maintenance_interval(
    beta: float,
    eta: float,
    costo_preventivo: float,
    costo_falla_catastrofica: float,
    costo_hora_parada: float,
    mttr_esperado: float,
    t_min: float = 200,
    t_max_factor: float = 2.5,
    step: float = 200,
) -> dict:
    """
    Barre intervalos candidatos T y calcula el costo total esperado en cada uno:

        Costo(T) = F(T) * Costo_falla_total + (1 - F(T)) * Costo_preventivo

    donde Costo_falla_total incluye tanto el costo directo de la falla
    catastrófica como el costo de producción perdida durante el MTTR.

    Retorna el T que minimiza el costo total esperado del ciclo de vida.
    """
    costo_falla_total = costo_falla_catastrofica + costo_hora_parada * mttr_esperado

    t_candidates = np.arange(t_min, eta * t_max_factor, step)
    f_t = reliability_f(t_candidates, beta, eta)
    costos = f_t * costo_falla_total + (1 - f_t) * costo_preventivo

    idx_optimo = int(np.argmin(costos))

    return {
        "t_optimo": float(t_candidates[idx_optimo]),
        "costo_optimo": float(costos[idx_optimo]),
        "curva": [
            {"t": round(float(t), 1), "costo": round(float(c), 2)}
            for t, c in zip(t_candidates, costos)
        ],
    }


def generar_rutina(beta: float, eta: float, tecnica_deteccion: str, t_optimo: float) -> list[dict]:
    """
    Prescribe la rutina de mantenimiento centrada en confiabilidad,
    mapeando el percentil de vida útil (B10) a acciones concretas.
    """
    b10 = b10_life(beta, eta)
    return [
        {
            "rango_pct": "0% – 60% B10",
            "rango_horas": [0, round(b10 * 0.6)],
            "accion": "Monitoreo pasivo",
            "detalle": "Análisis de vibraciones trimestral. Umbral de alerta según ISO 10816.",
        },
        {
            "rango_pct": "60% – 85% B10",
            "rango_horas": [round(b10 * 0.6), round(b10 * 0.85)],
            "accion": "Monitoreo activo",
            "detalle": f"{tecnica_deteccion} mensual. Registrar tendencia, no solo el valor puntual.",
        },
        {
            "rango_pct": "85% – 100% B10",
            "rango_horas": [round(b10 * 0.85), round(b10)],
            "accion": "Preparación de intervención",
            "detalle": "Alineación de precisión / análisis de aceite-grasa. Tener el repuesto listo en bodega.",
        },
        {
            "rango_pct": "> 100% B10",
            "rango_horas": [round(b10), None],
            "accion": "Reemplazo obligatorio",
            "detalle": "Intervenir antes de esta ventana independientemente de la condición aparente — el riesgo estadístico ya es alto.",
        },
        {
            "rango_pct": "Intervalo óptimo por costo",
            "rango_horas": [round(t_optimo), round(t_optimo)],
            "accion": "Intervención preventiva completa",
            "detalle": "Ejecutar en este punto minimiza el costo total esperado del ciclo de vida para este modo de falla.",
        },
    ]
