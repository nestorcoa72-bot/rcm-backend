"""
Servicio de confiabilidad: ajuste de Weibull con censura (MLE real) + Montecarlo.

Reemplaza la aproximación de regresión de rango mediano del prototipo por
Máxima Verosimilitud con censura a la derecha, usando la librería `reliability`
(open-source, hecha específicamente para ingeniería de confiabilidad).

pip install reliability numpy scipy
"""
from dataclasses import dataclass
from typing import Optional
import numpy as np
from reliability.Fitters import Fit_Weibull_2P


@dataclass
class WeibullFitResult:
    beta: float
    eta: float
    beta_ic_inferior: Optional[float]
    beta_ic_superior: Optional[float]
    n_fallas: int
    n_censurados: int


# Valores de referencia industrial — fallback cuando no hay datos suficientes
# para un ajuste MLE confiable (regla práctica: mínimo 5 fallas observadas).
FALLBACK_WEIBULL = {
    "rodamientos":    {"beta": 2.2, "eta": 20000},
    "aislamiento":    {"beta": 1.8, "eta": 35000},
    "desalineacion":  {"beta": 2.5, "eta": 15000},
    "desbalanceo":    {"beta": 2.0, "eta": 18000},
    "corrienteseje":  {"beta": 1.6, "eta": 12000},
}
MIN_FALLAS_PARA_MLE = 5


def fit_weibull_censurado(
    horas_falla: list[float],
    horas_censuradas: list[float],
    modo_clave: str,
) -> WeibullFitResult:
    """
    Ajusta Weibull(beta, eta) por Máxima Verosimilitud, incorporando
    correctamente los motores que siguen operando sin haber fallado
    (right-censored data). Esto es lo que distingue un modelo de
    confiabilidad correcto de uno optimista/sesgado.
    """
    n_fallas = len(horas_falla)
    n_censurados = len(horas_censuradas)

    if n_fallas < MIN_FALLAS_PARA_MLE:
        defaults = FALLBACK_WEIBULL.get(modo_clave, {"beta": 2.0, "eta": 15000})
        return WeibullFitResult(
            beta=defaults["beta"], eta=defaults["eta"],
            beta_ic_inferior=None, beta_ic_superior=None,
            n_fallas=n_fallas, n_censurados=n_censurados,
        )

    fit = Fit_Weibull_2P(
        failures=horas_falla,
        right_censored=horas_censuradas if horas_censuradas else None,
        show_probability_plot=False,
        print_results=False,
    )
    return WeibullFitResult(
        beta=fit.beta,
        eta=fit.alpha,
        beta_ic_inferior=fit.beta_lower,
        beta_ic_superior=fit.beta_upper,
        n_fallas=n_fallas,
        n_censurados=n_censurados,
    )


def reliability_f(t: np.ndarray, beta: float, eta: float) -> np.ndarray:
    """Probabilidad acumulada de falla F(t) = 1 - R(t)."""
    return 1 - np.exp(-((t / eta) ** beta))


def b10_life(beta: float, eta: float) -> float:
    """Tiempo al que el 10% de la población ha fallado."""
    return float(eta * (-np.log(0.90)) ** (1 / beta))


def run_monte_carlo(
    beta: float,
    eta: float,
    mttr_mean: float,
    mttr_sigma: float,
    n_iteraciones: int = 10_000,
    seed: Optional[int] = 42,
) -> dict:
    """
    Simulación de Montecarlo por muestreo de transformada inversa.
    Equivalente funcional a lo que Crystal Ball haría sobre una hoja de Excel,
    pero vectorizado con NumPy (10,000 iteraciones corren en milisegundos).
    """
    rng = np.random.default_rng(seed)

    u = rng.uniform(0, 1, n_iteraciones)
    ttf_samples = eta * (-np.log(u)) ** (1 / beta)

    mttr_samples = rng.lognormal(mean=np.log(mttr_mean), sigma=mttr_sigma, size=n_iteraciones)

    mtbf = float(ttf_samples.mean())
    ic_90 = [float(np.percentile(ttf_samples, 5)), float(np.percentile(ttf_samples, 95))]
    mttr_avg = float(mttr_samples.mean())

    return {
        "ttf_samples": ttf_samples,
        "mtbf": mtbf,
        "mtbf_ic_90": ic_90,
        "mttr_avg": mttr_avg,
    }


def build_ft_curve(beta: float, eta: float, n_points: int = 50) -> list[dict]:
    t_max = eta * 2.5
    t_points = np.linspace(1, t_max, n_points)
    f_points = reliability_f(t_points, beta, eta) * 100
    return [{"t": round(float(t), 1), "f_pct": round(float(f), 2)} for t, f in zip(t_points, f_points)]


def build_histogram(ttf_samples: np.ndarray, n_bins: int = 25) -> list[dict]:
    counts, bin_edges = np.histogram(ttf_samples, bins=n_bins)
    return [
        {"bin_inicio": round(float(bin_edges[i]), 1), "frecuencia": int(counts[i])}
        for i in range(n_bins)
    ]


def interpretar_beta(beta: float, n_fallas: int, min_requerido: int = MIN_FALLAS_PARA_MLE) -> str:
    if beta > 1.15:
        base = "Beta > 1: falla dominada por desgaste (edad-dependiente). El mantenimiento programado por horas tiene sentido físico."
    elif beta < 0.9:
        base = "Beta < 1: patrón de mortalidad infantil (fallas tempranas). Revisar procedimiento de instalación o calidad de repuestos, no solo el desgaste."
    else:
        base = "Beta ≈ 1: fallas mayormente aleatorias, poco relacionadas con la edad del componente. El mantenimiento predictivo por condición aporta más valor que el basado en tiempo fijo."

    if n_fallas < min_requerido:
        base += f" (Aviso: solo {n_fallas} fallas registradas, por debajo del mínimo recomendado de {min_requerido} — se usaron valores de referencia industrial. Registra más eventos para un ajuste propio confiable.)"
    return base
