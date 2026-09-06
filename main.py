"""
RCM Motores — API principal v2 (ficha completa + edición + inventario + aprobación).

Ejecutar localmente:
    uvicorn main:app --reload --port 8000

Documentación interactiva autogenerada en /docs
"""
import os
from typing import List, Optional
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session

import models
import schemas
from services import reliability_service as rel
from services import rcm_service as rcm

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://rcm_user:rcm_pass@localhost:5432/rcm_motores"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

app = FastAPI(
    title="RCM Motores API",
    description="Gestión y análisis de confiabilidad de motores eléctricos con VFD",
    version="2.0.0",
)

# Permite que la interfaz visual (hospedada en otro dominio) llame a esta API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_modo_or_404(db: Session, clave: str) -> models.CatalogoModoFalla:
    modo = db.scalar(select(models.CatalogoModoFalla).where(models.CatalogoModoFalla.clave == clave))
    if not modo:
        raise HTTPException(404, f"Modo de falla '{clave}' no encontrado")
    return modo


def orm_to_dict(obj) -> dict:
    """Convierte un objeto ORM a dict plano por sus columnas — evita choques
    entre relaciones de SQLAlchemy y campos de texto del mismo nombre en Pydantic."""
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


# ============================================================
# MOTORES
# ============================================================

@app.post("/motores", response_model=schemas.MotorOut, status_code=201)
def crear_motor(motor: schemas.MotorCreate, db: Session = Depends(get_db)):
    existente = db.scalar(select(models.Motor).where(models.Motor.serial == motor.serial))
    if existente:
        raise HTTPException(409, f"Ya existe un motor con serial '{motor.serial}'")
    db_motor = models.Motor(**motor.model_dump())
    db.add(db_motor)
    db.commit()
    db.refresh(db_motor)
    return db_motor


@app.get("/motores", response_model=List[schemas.MotorOut])
def listar_motores(
    criticidad: Optional[str] = None,
    macolla: Optional[str] = None,
    pozo: Optional[str] = None,
    division: Optional[str] = None,
    unidad: Optional[str] = None,
    cabezal: Optional[str] = None,
    texto: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = select(models.Motor).where(models.Motor.activo == True)  # noqa: E712
    if criticidad:
        query = query.where(models.Motor.criticidad == criticidad)
    if macolla:
        query = query.where(models.Motor.macolla == macolla)
    if pozo:
        query = query.where(models.Motor.pozo == pozo)
    if division:
        query = query.where(models.Motor.division == division)
    if unidad:
        query = query.where(models.Motor.unidad == unidad)
    if cabezal:
        query = query.where(models.Motor.cabezal == cabezal)
    if texto:
        like = f"%{texto}%"
        query = query.where(
            (models.Motor.tag.ilike(like)) |
            (models.Motor.fabricante.ilike(like)) |
            (models.Motor.modelo.ilike(like)) |
            (models.Motor.serial.ilike(like))
        )
    return db.scalars(query).all()


@app.get("/motores/{id_motor}", response_model=schemas.MotorOut)
def obtener_motor(id_motor: UUID, db: Session = Depends(get_db)):
    motor = db.get(models.Motor, id_motor)
    if not motor:
        raise HTTPException(404, "Motor no encontrado")
    return motor


@app.put("/motores/{id_motor}", response_model=schemas.MotorOut)
def editar_motor(id_motor: UUID, cambios: schemas.MotorUpdate, db: Session = Depends(get_db)):
    motor = db.get(models.Motor, id_motor)
    if not motor:
        raise HTTPException(404, "Motor no encontrado")
    for key, value in cambios.model_dump(exclude_unset=True).items():
        setattr(motor, key, value)
    db.commit()
    db.refresh(motor)
    return motor


@app.delete("/motores/{id_motor}", status_code=204)
def eliminar_motor(id_motor: UUID, db: Session = Depends(get_db)):
    motor = db.get(models.Motor, id_motor)
    if not motor:
        raise HTTPException(404, "Motor no encontrado")
    db.delete(motor)
    db.commit()


# ============================================================
# HISTORIAL DE FALLAS
# ============================================================

@app.post("/fallas", response_model=schemas.FallaOut, status_code=201)
def registrar_falla(falla: schemas.FallaCreate, db: Session = Depends(get_db)):
    modo = get_modo_or_404(db, falla.modo)
    datos = falla.model_dump(exclude={"modo"})
    db_falla = models.HistorialFalla(id_modo=modo.id_modo, **datos)
    db.add(db_falla)
    db.commit()
    db.refresh(db_falla)
    out_dict = orm_to_dict(db_falla)
    out_dict["modo"] = modo.clave
    return schemas.FallaOut(**out_dict)


@app.get("/fallas", response_model=List[schemas.FallaOut])
def listar_fallas(
    modo: Optional[str] = None,
    id_motor: Optional[UUID] = None,
    categoria_causa: Optional[str] = None,
    recurrente: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = select(models.HistorialFalla)
    if modo:
        modo_obj = get_modo_or_404(db, modo)
        query = query.where(models.HistorialFalla.id_modo == modo_obj.id_modo)
    if id_motor:
        query = query.where(models.HistorialFalla.id_motor == id_motor)
    if categoria_causa:
        query = query.where(models.HistorialFalla.categoria_causa == categoria_causa)
    if recurrente:
        query = query.where(models.HistorialFalla.recurrente == recurrente)
    fallas = db.scalars(query).all()
    resultado = []
    for f in fallas:
        out_dict = orm_to_dict(f)
        out_dict["modo"] = f.modo_ref.clave
        resultado.append(schemas.FallaOut(**out_dict))
    return resultado


@app.put("/fallas/{id_falla}", response_model=schemas.FallaOut)
def editar_falla(id_falla: UUID, cambios: schemas.FallaUpdate, db: Session = Depends(get_db)):
    falla = db.get(models.HistorialFalla, id_falla)
    if not falla:
        raise HTTPException(404, "Evento de falla no encontrado")
    datos = cambios.model_dump(exclude_unset=True)
    if "modo" in datos:
        modo = get_modo_or_404(db, datos.pop("modo"))
        falla.id_modo = modo.id_modo
    for key, value in datos.items():
        setattr(falla, key, value)
    db.commit()
    db.refresh(falla)
    out_dict = orm_to_dict(falla)
    out_dict["modo"] = falla.modo_ref.clave
    return schemas.FallaOut(**out_dict)


@app.delete("/fallas/{id_falla}", status_code=204)
def eliminar_falla(id_falla: UUID, db: Session = Depends(get_db)):
    falla = db.get(models.HistorialFalla, id_falla)
    if not falla:
        raise HTTPException(404, "Evento de falla no encontrado")
    db.delete(falla)
    db.commit()


# ============================================================
# AMEF (matriz viva y editable)
# ============================================================

def occurrence_rating_from_rate(fallas_por_1000h: float) -> int:
    r = fallas_por_1000h
    thresholds = [0, 0.01, 0.05, 0.1, 0.3, 0.6, 1, 2, 4]
    for rating, threshold in enumerate(thresholds, start=1):
        if r < threshold:
            return rating
    return 10


@app.get("/amef", response_model=List[schemas.AmefEntryOut])
def obtener_amef(id_motor: Optional[UUID] = None, db: Session = Depends(get_db)):
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
            ocurrencia_calculada = occurrence_rating_from_rate(tasa)

        override = db.get(models.AmefOverride, modo.id_modo)
        severidad = override.severidad if (override and override.severidad) else modo.severidad_default
        deteccion = override.deteccion if (override and override.deteccion) else modo.deteccion_default
        ocurrencia = ocurrencia_calculada if ocurrencia_calculada is not None else (
            override.ocurrencia_manual if (override and override.ocurrencia_manual) else 5
        )

        resultado.append(schemas.AmefEntryOut(
            id_modo=modo.id_modo, clave=modo.clave, nombre=modo.nombre,
            severidad=severidad, ocurrencia=ocurrencia,
            ocurrencia_es_calculada=ocurrencia_calculada is not None,
            deteccion=deteccion, npr=severidad * ocurrencia * deteccion,
            tecnica_deteccion=modo.tecnica_deteccion,
            iso_modo=modo.iso_modo, iso_mecanismo=modo.iso_mecanismo,
        ))
    return resultado


@app.put("/amef/override", response_model=schemas.AmefEntryOut)
def editar_amef_override(cambios: schemas.AmefOverrideIn, db: Session = Depends(get_db)):
    modo = db.get(models.CatalogoModoFalla, cambios.id_modo)
    if not modo:
        raise HTTPException(404, "Modo de falla no encontrado")
    override = db.get(models.AmefOverride, cambios.id_modo)
    if not override:
        override = models.AmefOverride(id_modo=cambios.id_modo)
        db.add(override)
    if cambios.severidad is not None:
        override.severidad = cambios.severidad
    if cambios.ocurrencia_manual is not None:
        override.ocurrencia_manual = cambios.ocurrencia_manual
    if cambios.deteccion is not None:
        override.deteccion = cambios.deteccion
    db.commit()

    severidad = override.severidad or modo.severidad_default
    deteccion = override.deteccion or modo.deteccion_default
    ocurrencia = override.ocurrencia_manual or 5
    return schemas.AmefEntryOut(
        id_modo=modo.id_modo, clave=modo.clave, nombre=modo.nombre,
        severidad=severidad, ocurrencia=ocurrencia, ocurrencia_es_calculada=False,
        deteccion=deteccion, npr=severidad * ocurrencia * deteccion,
        tecnica_deteccion=modo.tecnica_deteccion, iso_modo=modo.iso_modo, iso_mecanismo=modo.iso_mecanismo,
    )


# ============================================================
# INVENTARIO DE REPUESTOS
# ============================================================

@app.post("/inventario", response_model=schemas.InventarioOut, status_code=201)
def crear_repuesto(item: schemas.InventarioCreate, db: Session = Depends(get_db)):
    modo = get_modo_or_404(db, item.modo)
    datos = item.model_dump(exclude={"modo"})
    db_item = models.InventarioRepuesto(id_modo=modo.id_modo, **datos)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    out_dict = orm_to_dict(db_item)
    out_dict["modo"] = modo.clave
    return schemas.InventarioOut(**out_dict)


@app.get("/inventario", response_model=List[schemas.InventarioOut])
def listar_inventario(modo: Optional[str] = None, db: Session = Depends(get_db)):
    query = select(models.InventarioRepuesto)
    if modo:
        modo_obj = get_modo_or_404(db, modo)
        query = query.where(models.InventarioRepuesto.id_modo == modo_obj.id_modo)
    items = db.scalars(query).all()
    resultado = []
    for it in items:
        out_dict = orm_to_dict(it)
        modo_obj = db.get(models.CatalogoModoFalla, it.id_modo)
        out_dict["modo"] = modo_obj.clave if modo_obj else ""
        resultado.append(schemas.InventarioOut(**out_dict))
    return resultado


@app.delete("/inventario/{id_repuesto}", status_code=204)
def eliminar_repuesto(id_repuesto: UUID, db: Session = Depends(get_db)):
    item = db.get(models.InventarioRepuesto, id_repuesto)
    if not item:
        raise HTTPException(404, "Repuesto no encontrado")
    db.delete(item)
    db.commit()


# ============================================================
# SIMULACIÓN WEIBULL + MONTECARLO
# ============================================================

@app.post("/simulaciones/weibull-montecarlo", response_model=schemas.SimulacionResult)
def ejecutar_simulacion(req: schemas.SimulacionRequest, db: Session = Depends(get_db)):
    modo = get_modo_or_404(db, req.modo)

    query = select(models.HistorialFalla).where(models.HistorialFalla.id_modo == modo.id_modo)
    if req.id_motor:
        query = query.where(models.HistorialFalla.id_motor == req.id_motor)
    eventos = db.scalars(query).all()

    horas_falla = [e.horas_operacion_al_evento for e in eventos if not e.censurado]
    horas_censuradas = [e.horas_operacion_al_evento for e in eventos if e.censurado]

    fit = rel.fit_weibull_censurado(horas_falla, horas_censuradas, modo.clave)

    mttr_values = [e.mttr for e in eventos if e.mttr]
    mttr_mean = sum(mttr_values) / len(mttr_values) if mttr_values else 6.0

    mc = rel.run_monte_carlo(fit.beta, fit.eta, mttr_mean, req.mttr_sigma, req.n_iteraciones)
    b10 = rel.b10_life(fit.beta, fit.eta)

    simulacion = models.SimulacionWeibull(
        id_modo=modo.id_modo, id_motor=req.id_motor,
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
# PLAN RCM + FLUJO DE APROBACIÓN
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
        estado="Borrador", historial=[{"accion": "Creado como Borrador"}],
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    return schemas.RcmPlanResult(
        id_plan=plan.id_plan, npr_calculado=entry.npr,
        intervalo_optimo_horas=optim["t_optimo"], costo_total_esperado=optim["costo_optimo"],
        estrategia=estrategia, estado=plan.estado,
        curva_costo=optim["curva"], rutina=rutina,
    )


@app.get("/rcm/planes", response_model=List[schemas.PlanOut])
def listar_planes(estado: Optional[str] = None, db: Session = Depends(get_db)):
    query = select(models.PlanRCM).order_by(models.PlanRCM.generado_en.desc())
    if estado:
        query = query.where(models.PlanRCM.estado == estado)
    return db.scalars(query).all()


@app.post("/rcm/planes/{id_plan}/enviar", response_model=schemas.PlanOut)
def enviar_a_aprobacion(id_plan: UUID, db: Session = Depends(get_db)):
    plan = db.get(models.PlanRCM, id_plan)
    if not plan:
        raise HTTPException(404, "Plan no encontrado")
    plan.estado = "Pendiente"
    plan.historial = plan.historial + [{"accion": "Enviado a aprobación"}]
    db.commit()
    db.refresh(plan)
    return plan


@app.post("/rcm/planes/{id_plan}/aprobar", response_model=schemas.PlanOut)
def aprobar_plan(id_plan: UUID, body: schemas.PlanAccionRequest, db: Session = Depends(get_db)):
    plan = db.get(models.PlanRCM, id_plan)
    if not plan:
        raise HTTPException(404, "Plan no encontrado")
    plan.estado = "Aprobado"
    plan.historial = plan.historial + [{"accion": "Aprobado", "comentario": body.comentario or ""}]
    db.commit()
    db.refresh(plan)
    return plan


@app.post("/rcm/planes/{id_plan}/rechazar", response_model=schemas.PlanOut)
def rechazar_plan(id_plan: UUID, body: schemas.PlanAccionRequest, db: Session = Depends(get_db)):
    plan = db.get(models.PlanRCM, id_plan)
    if not plan:
        raise HTTPException(404, "Plan no encontrado")
    if not body.comentario:
        raise HTTPException(422, "Se requiere un comentario para rechazar un plan")
    plan.estado = "Rechazado"
    plan.historial = plan.historial + [{"accion": "Rechazado", "comentario": body.comentario}]
    db.commit()
    db.refresh(plan)
    return plan


@app.get("/health")
def health_check():
    return {"status": "ok"}
