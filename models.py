"""
SQLAlchemy ORM models — reflejan schema.sql
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, Date, ForeignKey,
    CheckConstraint, SmallInteger, Numeric, Text, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Variador(Base):
    __tablename__ = "variadores_vfd"
    id_variador = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    marca_modelo = Column(String(120), nullable=False)
    frecuencia_portadora_khz = Column(Float)
    filtro_dv_dt = Column(Boolean, default=False)
    filtro_modo_comun = Column(Boolean, default=False)
    creado_en = Column(DateTime, default=datetime.utcnow)

    motores = relationship("Motor", back_populates="variador")


class Motor(Base):
    __tablename__ = "motores"
    id_motor = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tag_equipo = Column(String(50), unique=True, nullable=False)
    potencia_kw = Column(Float, nullable=False)
    voltaje_v = Column(Integer, nullable=False)
    corriente_nominal_a = Column(Float)
    rpm_nominal = Column(Integer, nullable=False)
    tipo_rodamiento_de = Column(String(60))
    tipo_rodamiento_nde = Column(String(60))
    clase_aislamiento = Column(String(5))
    id_variador = Column(UUID(as_uuid=True), ForeignKey("variadores_vfd.id_variador", ondelete="SET NULL"))
    criticidad = Column(String(1), nullable=False)
    fecha_instalacion = Column(Date, nullable=False)
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (CheckConstraint("criticidad IN ('A','B','C')"),)

    variador = relationship("Variador", back_populates="motores")
    fallas = relationship("HistorialFalla", back_populates="motor")
    costos = relationship("Costo", back_populates="motor", uselist=False)


class CatalogoModoFalla(Base):
    __tablename__ = "catalogo_modos_falla"
    id_modo = Column(Integer, primary_key=True)
    clave = Column(String(30), unique=True, nullable=False)
    nombre = Column(String(150), nullable=False)
    severidad_default = Column(SmallInteger, nullable=False)
    deteccion_default = Column(SmallInteger, nullable=False)
    tecnica_deteccion = Column(String(200))


class HistorialFalla(Base):
    __tablename__ = "historial_fallas"
    id_falla = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_motor = Column(UUID(as_uuid=True), ForeignKey("motores.id_motor", ondelete="CASCADE"), nullable=False)
    id_modo = Column(Integer, ForeignKey("catalogo_modos_falla.id_modo"), nullable=False)
    fecha_falla = Column(DateTime, nullable=True)
    horas_operacion_al_evento = Column(Float, nullable=False)
    fecha_fin_reparacion = Column(DateTime, nullable=True)
    causa_raiz = Column(Text)
    censurado = Column(Boolean, nullable=False, default=False)
    creado_en = Column(DateTime, default=datetime.utcnow)

    motor = relationship("Motor", back_populates="fallas")
    modo = relationship("CatalogoModoFalla")


class AmefOverride(Base):
    __tablename__ = "amef_overrides"
    id_motor = Column(UUID(as_uuid=True), ForeignKey("motores.id_motor", ondelete="CASCADE"), primary_key=True)
    id_modo = Column(Integer, ForeignKey("catalogo_modos_falla.id_modo"), primary_key=True)
    severidad = Column(SmallInteger)
    ocurrencia_manual = Column(SmallInteger)
    deteccion = Column(SmallInteger)
    actualizado_en = Column(DateTime, default=datetime.utcnow)


class Costo(Base):
    __tablename__ = "costos"
    id_motor = Column(UUID(as_uuid=True), ForeignKey("motores.id_motor", ondelete="CASCADE"), primary_key=True)
    costo_hora_preventivo = Column(Numeric(12, 2), nullable=False)
    costo_hora_correctivo = Column(Numeric(12, 2), nullable=False)
    costo_hora_parada_produccion = Column(Numeric(12, 2), nullable=False)
    costo_mano_obra_hora = Column(Numeric(12, 2))
    actualizado_en = Column(DateTime, default=datetime.utcnow)

    motor = relationship("Motor", back_populates="costos")


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
    id_motor = Column(UUID(as_uuid=True), ForeignKey("motores.id_motor", ondelete="CASCADE"), nullable=False)
    id_modo = Column(Integer, ForeignKey("catalogo_modos_falla.id_modo"), nullable=False)
    npr_calculado = Column(Integer, nullable=False)
    intervalo_optimo_horas = Column(Float, nullable=False)
    costo_total_esperado = Column(Numeric(14, 2), nullable=False)
    estrategia = Column(String(60), nullable=False)
    vigente = Column(Boolean, default=True)
    generado_en = Column(DateTime, default=datetime.utcnow)


class CovariableEvento(Base):
    __tablename__ = "covariables_evento"
    id_falla = Column(UUID(as_uuid=True), ForeignKey("historial_fallas.id_falla", ondelete="CASCADE"), primary_key=True)
    frecuencia_khz = Column(Float)
    thd_pct = Column(Float)
    temperatura_promedio_c = Column(Float)
    carga_relativa_pct = Column(Float)


class ModeloCox(Base):
    __tablename__ = "modelos_cox"
    id_modelo = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_modo = Column(Integer, ForeignKey("catalogo_modos_falla.id_modo"), nullable=False)
    covariables_usadas = Column(ARRAY(String), nullable=False)
    hazard_ratios = Column(JSONB, nullable=False)
    p_values = Column(JSONB, nullable=False)
    concordance_index = Column(Float, nullable=False)
    n_observaciones = Column(Integer, nullable=False)
    n_eventos = Column(Integer, nullable=False)
    ejecutado_en = Column(DateTime, default=datetime.utcnow)
