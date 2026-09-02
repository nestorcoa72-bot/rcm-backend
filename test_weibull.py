from reliability.Fitters import Fit_Weibull_2P
import numpy as np

# Simular datos reales: motores con rodamientos fallados y motores aun operando (censurados)
fallas_horas = [8200, 9800, 11500, 13100, 15200, 10400, 16800]
censurados_horas = [7000, 12000, 5000, 9000]  # motores vivos, aun sin fallar

fit = Fit_Weibull_2P(failures=fallas_horas, right_censored=censurados_horas, show_probability_plot=False, print_results=True)
print("\nBeta:", fit.beta, "Eta:", fit.alpha)
