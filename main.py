"""
RCM Motores — API principal.

Ejecutar localmente:
    uvicorn main:app --reload --port 8000

Documentación interactiva autogenerada en /docs
"""
from typing import List, Optional
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session

import models
import schemas
from services import reliability_service as rel
from services import rcm_service as rcm
from services import cox_service as cox

import os

DATABASE_URL = os.environ.get( "DATABASE_URL", "postgresql://rcm_user:rcm_pass@localhost:5432/rcm_motores" )
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

app = FastAPI(
    title="RCM Motores API",
    description="Gestión y análisis de confiabilidad de motores eléctricos con VFD",
    version="1.0.0",
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# MOTORES
# ============================================================

@app.post("/motores", response_model=schemas.MotorOut, status_code=201)
def crear_motor(motor: schemas.MotorCreate, db: Session = Depends(get_db)):
    db_motor = models.Motor(**motor.model_dump())
    db.add(db_motor)
    db.commit()
    db.refresh(db_motor)
    return db_motor


@app.get("/motores", response_model=List[schemas.MotorOut])
def listar_motores(criticidad: Optional[str] = None, db: Session = Depends(get_db)):
    query = select(models.Motor).where(models.Motor.activo == True)  # noqa: E712
    if criticidad:
        query = query.where(models.Motor.criticidad == criticidad)
    return db.scalars(query).all()


@app.get("/motores/{id_motor}", response_model=schemas.MotorOut)
def obtener_motor(id_motor: UUID, db: Session = Depends(get_db)):
    motor = db.get(models.Motor, id_motor)
    if not motor:
        raise HTTPException(404, "Motor no encontrado")
    return motor


# ============================================================
# HISTORIAL DE FALLAS
# ============================================================

@app.post("/fallas", response_model=schemas.FallaOut, status_code=201)
def registrar_falla(falla: schemas.FallaCreate, db: Session = Depends(get_db)):
    if not falla.censurado and falla.fecha_falla is None:
        raise HTTPException(422, "fecha_falla es obligatoria cuando censurado=False")
    db_falla = models.HistorialFalla(**falla.model_dump())
    db.add(db_falla)
    db.commit()
    db.refresh(db_falla)
    return db_falla


@app.get("/fallas", response_model=List[schemas.FallaOut])
def listar_fallas(id_modo: Optional[int] = None, id_motor: Optional[UUID] = None, db: Session = Depends(get_db)):
    query = select(models.HistorialFalla)
    if id_modo:
        query = query.where(models.HistorialFalla.id_modo == id_modo)
    if id_motor:
        query = query.where(models.HistorialFalla.id_motor == id_motor)
    return db.scalars(query).all()


# ============================================================
# AMEF (matriz viva)
# ============================================================

@app.get("/amef", response_model=List[schemas.AmefEntryOut])
def obtener_amef(id_motor: Optional[UUID] = None, db: Session = Depends(get_db)):
    """
    Devuelve la matriz AMEF con NPR recalculado: Ocurrencia se deriva
    de la tasa de fallas real cuando hay suficientes datos; si no,
    cae al valor manual/default.
    """
    modos = db.scalars(select(models.CatalogoModoFalla)).all()
    resultado = []
    for modo in modos:
        fallas_query = select(models.HistorialFalla).where(models.HistorialFalla.id_modo == modo.id_modo)
        if id_motor:
            fallas_query = fallas_query.where(models.HistorialFalla.id_motor == id_motor)
        todas_fallas = db.scalars(fallas_query).all()

        eventos_falla = [f for f in todas_fallas if not f.censurado]
        total_horas = sum(f.horas_operacion_al_evento for f in todas_fallas)

        ocurrencia_calculada = None
        if len(eventos_falla) >= 2 and total_horas > 0:
            tasa = (len(eventos_falla) / total_horas) * 1000
            ocurrencia_calculada = rcm.occurrence_rating_from_rate(tasa)

        override = None
        if id_motor:
            override = db.get(models.AmefOverride, (id_motor, modo.id_modo))

        severidad = override.severidad if (override and override.severidad) else modo.severidad_default
        deteccion = override.deteccion if (override and override.deteccion) else modo.deteccion_default
        ocurrencia = ocurrencia_calculada if ocurrencia_calculada is not None else (
            override.ocurrencia_manual if (override and override.ocurrencia_manual) else 5
        )

        resultado.append(schemas.AmefEntryOut(
            id_modo=modo.id_modo,
            nombre=modo.nombre,
            severidad=severidad,
            ocurrencia=ocurrencia,
            ocurrencia_es_calculada=ocurrencia_calculada is not None,
            deteccion=deteccion,
            npr=rcm.compute_npr(severidad, ocurrencia, deteccion),
            tecnica_deteccion=modo.tecnica_deteccion,
        ))
    return resultado


# ============================================================
# SIMULACIÓN WEIBULL + MONTECARLO
# ============================================================

@app.post("/simulaciones/weibull-montecarlo", response_model=schemas.SimulacionResult)
def ejecutar_simulacion(req: schemas.SimulacionRequest, db: Session = Depends(get_db)):
    query = select(models.HistorialFalla).where(models.HistorialFalla.id_modo == req.id_modo)
    if req.id_motor:
        query = query.where(models.HistorialFalla.id_motor == req.id_motor)
    eventos = db.scalars(query).all()

    horas_falla = [e.horas_operacion_al_evento for e in eventos if not e.censurado]
    horas_censuradas = [e.horas_operacion_al_evento for e in eventos if e.censurado]

    modo = db.get(models.CatalogoModoFalla, req.id_modo)
    if not modo:
        raise HTTPException(404, "Modo de falla no encontrado")

    fit = rel.fit_weibull_censurado(horas_falla, horas_censuradas, modo.clave)

    mttr_values = [
        (e.fecha_fin_reparacion - e.fecha_falla).total_seconds() / 3600
        for e in eventos if e.fecha_falla and e.fecha_fin_reparacion
    ]
    mttr_mean = sum(mttr_values) / len(mttr_values) if mttr_values else 6.0

    mc = rel.run_monte_carlo(fit.beta, fit.eta, mttr_mean, req.mttr_sigma, req.n_iteraciones)
    b10 = rel.b10_life(fit.beta, fit.eta)

    simulacion = models.SimulacionWeibull(
        id_modo=req.id_modo, id_motor=req.id_motor,
        beta=fit.beta, eta=fit.eta,
        beta_ic_inferior=fit.beta_ic_inferior, beta_ic_superior=fit.beta_ic_superior,
        n_fallas_usadas=fit.n_fallas, n_censurados_usados=fit.n_censurados,
        mtbf_simulado=mc["mtbf"], mttr_simulado=mc["mttr_avg"],
        b10_life=b10, n_iteraciones=req.n_iteraciones,
    )
    db.add(simulacion)
    db.commit()
    db.refresh(simulacion)

    return schemas.SimulacionResult(
        id_simulacion=simulacion.id_simulacion,
        beta=fit.beta, eta=fit.eta,
        beta_ic_inferior=fit.beta_ic_inferior, beta_ic_superior=fit.beta_ic_superior,
        n_fallas_usadas=fit.n_fallas, n_censurados_usados=fit.n_censurados,
        mtbf_simulado=mc["mtbf"], mtbf_ic_90=mc["mtbf_ic_90"], mttr_simulado=mc["mttr_avg"],
        b10_life=b10,
        interpretacion=rel.interpretar_beta(fit.beta, fit.n_fallas),
        curva_ft=rel.build_ft_curve(fit.beta, fit.eta),
        histograma_ttf=rel.build_histogram(mc["ttf_samples"]),
    )


# ============================================================
# PLAN RCM
# ============================================================

@app.post("/rcm/plan", response_model=schemas.RcmPlanResult)
def generar_plan_rcm(req: schemas.RcmPlanRequest, db: Session = Depends(get_db)):
    simulacion = db.get(models.SimulacionWeibull, req.id_simulacion)
    if not simulacion:
        raise HTTPException(404, "Simulación no encontrada. Ejecuta /simulaciones/weibull-montecarlo primero.")

    amef_entries = obtener_amef(id_motor=req.id_motor, db=db)
    entry = next((e for e in amef_entries if e.id_modo == simulacion.id_modo), None)
    if not entry:
        raise HTTPException(404, "Modo de falla no encontrado en AMEF")

    optim = rcm.optimal_maintenance_interval(
        beta=simulacion.beta, eta=simulacion.eta,
        costo_preventivo=req.costo_hora_preventivo,
        costo_falla_catastrofica=req.costo_falla_catastrofica,
        costo_hora_parada=req.costo_hora_parada_produccion,
        mttr_esperado=simulacion.mttr_simulado or 6.0,
    )

    rutina = rcm.generar_rutina(simulacion.beta, simulacion.eta, entry.tecnica_deteccion, optim["t_optimo"])
    estrategia = rcm.estrategia_por_npr(entry.npr)

    plan = models.PlanRCM(
        id_simulacion=req.id_simulacion, id_motor=req.id_motor, id_modo=simulacion.id_modo,
        npr_calculado=entry.npr, intervalo_optimo_horas=optim["t_optimo"],
        costo_total_esperado=optim["costo_optimo"], estrategia=estrategia,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    return schemas.RcmPlanResult(
        id_plan=plan.id_plan,
        npr_calculado=entry.npr,
        intervalo_optimo_horas=optim["t_optimo"],
        costo_total_esperado=optim["costo_optimo"],
        estrategia=estrategia,
        curva_costo=optim["curva"],
        rutina=rutina,
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


# ============================================================
# COX — MODELO DE COVARIABLES (extensión avanzada)
# ============================================================

def _construir_registros_cox(db: Session, id_modo: int, covariables: list[str]) -> list[dict]:
    """
    Arma la tabla de entrada para Cox: una fila por evento (falla o censura)
    con su duración, si fue observado, y sus covariables al momento del evento.
    """
    query = (
        select(models.HistorialFalla, models.CovariableEvento)
        .join(models.CovariableEvento, models.CovariableEvento.id_falla == models.HistorialFalla.id_falla, isouter=True)
        .where(models.HistorialFalla.id_modo == id_modo)
    )
    filas = db.execute(query).all()

    registros = []
    for falla, covar in filas:
        if covar is None:
            continue  # sin covariables registradas, no se puede usar en Cox
        fila = {
            "duration": falla.horas_operacion_al_evento,
            "event_observed": 0 if falla.censurado else 1,
        }
        for c in covariables:
            valor = getattr(covar, c, None)
            if valor is None:
                break
            fila[c] = valor
        else:
            registros.append(fila)
    return registros


@app.post("/analisis/cox", response_model=schemas.CoxAnalysisResult)
def analizar_covariables(req: schemas.CoxAnalysisRequest, db: Session = Depends(get_db)):
    """
    Ajusta un modelo de Cox con las covariables del VFD (frecuencia,
    THD, temperatura) para entender qué condiciones de operación
    aceleran o retrasan la falla — más allá de "cuándo falla en promedio".
    """
    registros = _construir_registros_cox(db, req.id_modo, req.covariables)

    if len(registros) < cox.MIN_OBSERVACIONES_COX:
        return schemas.CoxAnalysisResult(
            id_modelo=UUID(int=0), hazard_ratios={}, interpretaciones=[],
            concordance_index=0.0, n_observaciones=len(registros), n_eventos=0,
            aviso=f"Solo hay {len(registros)} eventos con covariables completas. "
                  f"Se necesitan al menos {cox.MIN_OBSERVACIONES_COX} para un modelo de Cox confiable. "
                  f"Usa /simulaciones/weibull-montecarlo mientras se acumulan más datos.",
        )

    fit = cox.fit_cox_model(registros, req.covariables)
    interpretaciones = [
        cox.interpretar_hazard_ratio(cov, fit.hazard_ratios[cov], fit.p_values[cov])
        for cov in req.covariables
    ]

    modelo = models.ModeloCox(
        id_modo=req.id_modo, covariables_usadas=req.covariables,
        hazard_ratios=fit.hazard_ratios, p_values=fit.p_values,
        concordance_index=fit.concordance_index,
        n_observaciones=fit.n_observaciones, n_eventos=fit.n_eventos,
    )
    db.add(modelo)
    db.commit()
    db.refresh(modelo)

    return schemas.CoxAnalysisResult(
        id_modelo=modelo.id_modelo, hazard_ratios=fit.hazard_ratios,
        interpretaciones=interpretaciones, concordance_index=fit.concordance_index,
        n_observaciones=fit.n_observaciones, n_eventos=fit.n_eventos,
    )


@app.post("/analisis/cox/escenario", response_model=schemas.CoxEscenarioResult)
def evaluar_escenario(req: schemas.CoxEscenarioRequest, db: Session = Depends(get_db)):
    """
    Responde directamente "¿qué pasa si cambio esta condición de operación?"
    Ej: {"frecuencia_khz": 12, "thd_pct": 5, "temperatura_promedio_c": 50}
    -> mediana de vida esperada bajo ese escenario específico.
    """
    registros = _construir_registros_cox(db, req.id_modo, req.covariables)
    if len(registros) < cox.MIN_OBSERVACIONES_COX:
        raise HTTPException(422, f"Datos insuficientes ({len(registros)}/{cox.MIN_OBSERVACIONES_COX} mínimo).")

    mediana = cox.predecir_vida_mediana(registros, req.escenario)
    return schemas.CoxEscenarioResult(mediana_vida_horas=mediana, escenario_evaluado=req.escenario)
