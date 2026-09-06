"""
SQLAlchemy ORM models — reflejan schema_v2.sql (ficha técnica completa)
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, Date, ForeignKey,
    CheckConstraint, SmallInteger, Numeric, Text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class CatalogoModoFalla(Base):
    __tablename__ = "catalogo_modos_falla"
    id_modo = Column(Integer, primary_key=True)
    clave = Column(String(30), unique=True, nullable=False)
    nombre = Column(String(150), nullable=False)
    severidad_default = Column(SmallInteger, nullable=False)
    deteccion_default = Column(SmallInteger, nullable=False)
    tecnica_deteccion = Column(String(200))
    iso_modo = Column(String(10))
    iso_mecanismo = Column(String(150))


class Motor(Base):
    __tablename__ = "motores"
    id_motor = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tag = Column(String(50))
    fabricante = Column(String(100))
    modelo = Column(String(100))
    serial = Column(String(100), unique=True, nullable=False)
    anio = Column(Integer)
    equipo_accionado = Column(String(150))
    macolla = Column(String(50))
    pozo = Column(String(50))
    unidad = Column(String(50))
    division = Column(String(50))
    potencia_hp = Column(Float)
    tension = Column(Float)
    corriente = Column(Float)
    frecuencia = Column(Float)
    fases = Column(String(5))
    fp = Column(Float)
    eficiencia = Column(Float)
    conexion = Column(String(30))
    sf = Column(Float)
    rpm = Column(Float)
    polos = Column(Integer)
    montaje = Column(String(30))
    frame = Column(String(30))
    rodamiento_de = Column(String(60))
    rodamiento_nde = Column(String(60))
    eje = Column(String(60))
    peso = Column(Float)
    aislamiento = Column(String(5))
    ip = Column(String(10))
    regimen = Column(String(5))
    temp_ambiente = Column(Float)
    altitud = Column(Float)
    clase_nema = Column(String(30))
    corriente_arranque = Column(String(30))
    fecha_ultima_prueba = Column(Date)
    resistencia_aislamiento = Column(Float)
    indice_polarizacion = Column(Float)
    vibracion_ref = Column(Float)
    temp_rodamientos_ref = Column(Float)
    cabezal = Column(String(20))
    criticidad = Column(String(1), nullable=False)
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (CheckConstraint("criticidad IN ('A','B','C')"),)

    fallas = relationship("HistorialFalla", back_populates="motor")


class HistorialFalla(Base):
    __tablename__ = "historial_fallas"
    id_falla = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_motor = Column(UUID(as_uuid=True), ForeignKey("motores.id_motor", ondelete="CASCADE"), nullable=False)
    id_modo = Column(Integer, ForeignKey("catalogo_modos_falla.id_modo"), nullable=False)
    fecha = Column(Date)
    componente_especifico = Column(String(150))
    orden_trabajo = Column(String(50))
    reportado_por = Column(String(100))
    causa_raiz = Column(Text)
    categoria_causa = Column(String(30))
    metodo_analisis = Column(String(30))
    accion_correctiva = Column(Text)
    accion_preventiva = Column(Text)
    recurrente = Column(String(5))
    horas_operacion_al_evento = Column(Float, nullable=False)
    carga_pct = Column(Float)
    temperatura_registrada = Column(Float)
    vibracion_registrada = Column(Float)
    corriente_registrada = Column(Float)
    mttr = Column(Float)
    horas_parada_produccion = Column(Float)
    costo_reparacion = Column(Numeric(12, 2))
    produccion_perdida_bbl = Column(Float)
    repuesto_utilizado = Column(String(150))
    censurado = Column(Boolean, nullable=False, default=False)
    creado_en = Column(DateTime, default=datetime.utcnow)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    motor = relationship("Motor", back_populates="fallas")
    modo_ref = relationship("CatalogoModoFalla")


class AmefOverride(Base):
    __tablename__ = "amef_overrides"
    id_modo = Column(Integer, ForeignKey("catalogo_modos_falla.id_modo"), primary_key=True)
    severidad = Column(SmallInteger)
    ocurrencia_manual = Column(SmallInteger)
    deteccion = Column(SmallInteger)
    actualizado_en = Column(DateTime, default=datetime.utcnow)


class InventarioRepuesto(Base):
    __tablename__ = "inventario_repuestos"
    id_repuesto = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(150), nullable=False)
    id_modo = Column(Integer, ForeignKey("catalogo_modos_falla.id_modo"))
    stock = Column(Integer, default=0)
    punto_reorden = Column(Integer, default=0)
    lead_time_dias = Column(Integer, default=0)
    costo_unitario = Column(Numeric(12, 2))
    creado_en = Column(DateTime, default=datetime.utcnow)


class SimulacionWeibull(Base):
    __tablename__ = "simulaciones_weibull"
    id_simulacion = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_modo = Column(Integer, ForeignKey("catalogo_modos_falla.id_modo"), nullable=False)
    id_motor = Column(UUID(as_uuid=True), ForeignKey("motores.id_motor", ondelete="CASCADE"))
    beta = Column(Float, nullable=False)
    eta = Column(Float, nullable=False)
    beta_ic_inferior = Column(Float)
    beta_ic_superior = Column(Float)
    n_fallas_usadas = Column(Integer, nullable=False)
    n_censurados_usados = Column(Integer, nullable=False)
    mtbf_simulado = Column(Float)
    mttr_simulado = Column(Float)
    b10_life = Column(Float)
    n_iteraciones = Column(Integer, nullable=False)
    ejecutado_en = Column(DateTime, default=datetime.utcnow)


class PlanRCM(Base):
    __tablename__ = "planes_rcm"
    id_plan = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_simulacion = Column(UUID(as_uuid=True), ForeignKey("simulaciones_weibull.id_simulacion"), nullable=False)
    id_motor = Column(UUID(as_uuid=True), ForeignKey("motores.id_motor", ondelete="CASCADE"))
    id_modo = Column(Integer, ForeignKey("catalogo_modos_falla.id_modo"), nullable=False)
    npr_calculado = Column(Integer, nullable=False)
    intervalo_optimo_horas = Column(Float, nullable=False)
    costo_total_esperado = Column(Numeric(14, 2), nullable=False)
    estrategia = Column(String(60), nullable=False)
    estado = Column(String(20), nullable=False, default="Borrador")
    historial = Column(JSONB, nullable=False, default=list)
    generado_en = Column(DateTime, default=datetime.utcnow)
