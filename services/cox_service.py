"""
Modelo de riesgos proporcionales de Cox — incorpora covariables del VFD
(frecuencia de conmutación, THD, temperatura) al modelo de confiabilidad.

Diferencia clave frente a Weibull simple:
  Weibull solo responde "¿cuándo va a fallar en promedio?"
  Cox responde "¿cómo cambia el riesgo si modifico una condición de operación?"

Modelo: h(t | X) = h0(t) * exp(b1*X1 + b2*X2 + ... + bn*Xn)

  h0(t)     = riesgo base (forma de la curva en el tiempo, no paramétrica)
  exp(bi)   = "hazard ratio" — cuánto multiplica el riesgo cada unidad de Xi

pip install lifelines pandas
"""
from dataclasses import dataclass
import pandas as pd
from lifelines import CoxPHFitter


@dataclass
class CoxFitResult:
    hazard_ratios: dict          # {covariable: hazard_ratio}
    p_values: dict                # {covariable: p_value}
    concordance_index: float      # calidad del modelo (0.5 = azar, 1.0 = perfecto)
    n_observaciones: int
    n_eventos: int


MIN_OBSERVACIONES_COX = 20  # Cox necesita más datos que Weibull simple (más parámetros)


def fit_cox_model(
    registros: list[dict],
    covariables: list[str],
) -> CoxFitResult:
    """
    registros: lista de dicts, uno por motor/evento, con las claves:
        'duration'        -> horas de operación (al fallar o al último dato si censurado)
        'event_observed'  -> 1 si falló, 0 si sigue operando (censurado)
        + una clave por cada covariable en `covariables`
        (ej. 'frecuencia_khz', 'thd_pct', 'temperatura_c')

    Requiere un mínimo razonable de observaciones: con pocas covariables
    y pocos datos, los intervalos de confianza son demasiado anchos para
    ser accionables — mejor mostrar esa advertencia que un número falso.
    """
    if len(registros) < MIN_OBSERVACIONES_COX:
        raise ValueError(
            f"Se necesitan al menos {MIN_OBSERVACIONES_COX} registros para un modelo de Cox "
            f"confiable (hay {len(registros)}). Con menos datos, usa el modelo Weibull simple."
        )

    df = pd.DataFrame(registros)
    cph = CoxPHFitter()
    cph.fit(df, duration_col="duration", event_col="event_observed")

    return CoxFitResult(
        hazard_ratios=cph.hazard_ratios_.to_dict(),
        p_values=cph.summary["p"].to_dict(),
        concordance_index=cph.concordance_index_,
        n_observaciones=len(df),
        n_eventos=int(df["event_observed"].sum()),
    )


def predecir_vida_mediana(
    registros: list[dict],
    escenario: dict,
) -> float:
    """
    Dado un escenario hipotético de covariables (ej. subir la frecuencia
    de conmutación), predice la mediana de vida esperada bajo ese escenario,
    manteniendo todo lo demás constante. Esto es lo que responde
    "¿qué pasa si cambio X?" que Weibull simple no puede contestar.
    """
    df = pd.DataFrame(registros)
    cph = CoxPHFitter()
    cph.fit(df, duration_col="duration", event_col="event_observed")

    escenario_df = pd.DataFrame([escenario])
    mediana = cph.predict_median(escenario_df)
    valor = float(mediana.iloc[0]) if hasattr(mediana, "iloc") else float(mediana)
    return valor


def interpretar_hazard_ratio(covariable: str, hr: float, p_value: float) -> str:
    """
    Traduce un hazard ratio numérico a una frase accionable para el
    ingeniero de mantenimiento, incluyendo la advertencia de significancia
    estadística cuando corresponde.
    """
    if hr > 1:
        pct = (hr - 1) * 100
        frase = f"Cada unidad adicional de {covariable} multiplica el riesgo de falla por {hr:.2f} (+{pct:.0f}%)."
    else:
        pct = (1 - hr) * 100
        frase = f"Cada unidad adicional de {covariable} reduce el riesgo de falla en {pct:.0f}% (protector)."

    if p_value > 0.05:
        frase += f" ⚠ No es estadísticamente significativo (p={p_value:.2f}) — no tomar decisiones solo con esta variable todavía; se necesitan más datos."
    return frase
