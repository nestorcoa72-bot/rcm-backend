import pandas as pd
import numpy as np
from lifelines import CoxPHFitter

np.random.seed(1)
n = 60

# Simular motores: frecuencia de conmutacion (khz), THD (%), temperatura promedio (C)
frecuencia_khz = np.random.uniform(2, 16, n)
thd_pct = np.random.uniform(2, 12, n)
temperatura_c = np.random.uniform(35, 75, n)

# Tiempo hasta falla: mientras mas alta la frecuencia y el THD, menor la vida (mas hazard)
# simulacion con relacion realista (mayor freq/THD -> menor tiempo de vida)
base_life = 15000
riesgo = 0.15*frecuencia_khz + 0.25*thd_pct + 0.05*(temperatura_c-35)
tiempo_vida = base_life * np.exp(-riesgo/10) * np.random.weibull(2, n)

# Censura: 30% de los motores siguen operando (no han fallado aun)
censurado = np.random.choice([0,1], n, p=[0.7,0.3])  # 1 = evento observado (fallo), 0 = censurado... ojo convencion
# en lifelines: event_observed=1 significa que SI ocurrio el evento (fallo)
evento_observado = 1 - censurado

df = pd.DataFrame({
    'duration': tiempo_vida,
    'event_observed': evento_observado,
    'frecuencia_khz': frecuencia_khz,
    'thd_pct': thd_pct,
    'temperatura_c': temperatura_c
})

cph = CoxPHFitter()
cph.fit(df, duration_col='duration', event_col='event_observed')
cph.print_summary()

print("\n--- Hazard ratios (exp(coef)) ---")
print(cph.hazard_ratios_)

# Predecir: si subo la frecuencia de conmutacion de 4khz a 12khz mantendo lo demas fijo, como cambia la mediana de vida?
escenario_bajo = pd.DataFrame({'frecuencia_khz':[4], 'thd_pct':[5], 'temperatura_c':[50]})
escenario_alto = pd.DataFrame({'frecuencia_khz':[12], 'thd_pct':[5], 'temperatura_c':[50]})

median_bajo = cph.predict_median(escenario_bajo)
median_alto = cph.predict_median(escenario_alto)
print(f"\nMediana de vida con 4kHz: {median_bajo.values[0]:.0f} horas")
print(f"Mediana de vida con 12kHz: {median_alto.values[0]:.0f} horas")
