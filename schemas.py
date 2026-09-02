"""
Esquemas Pydantic — contrato de la API
"""
from datetime import date, datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


class MotorCreate(BaseModel):
    tag_equipo: str
    potencia_kw: float = Field(gt=0)
    voltaje_v: int
    corriente_nominal_a: Optional[float] = None
    rpm_nominal: int
    tipo_rodamiento_de: Optional[str] = None
    tipo_rodamiento_nde: Optional[str] = None
    clase_aislamiento: Optional[str] = None
    id_variador: Optional[UUID] = None
    criticidad: str = Field(pattern="^[ABC]$")
    fecha_instalacion: date


class MotorOut(MotorCreate):
    id_motor: UUID
    activo: bool
    class Config:
        from_attributes = True


class FallaCreate(BaseModel):
    id_motor: UUID
    id_modo: int
    horas_operacion_al_evento: float = Field(ge=0)
    censurado: bool = False
    fecha_falla: Optional[datetime] = None
    fecha_fin_reparacion: Optional[datetime] = None
    causa_raiz: Optional[str] = None


class FallaOut(FallaCreate):
    id_falla: UUID
    class Config:
        from_attributes = True


class AmefEntryOut(BaseModel):
    id_modo: int
    nombre: str
    severidad: int
    ocurrencia: int
    ocurrencia_es_calculada: bool
    deteccion: int
    npr: int
    tecnica_deteccion: str


class SimulacionRequest(BaseModel):
    id_modo: int
    id_motor: Optional[UUID] = None  # None = análisis a nivel de flota (todos los motores)
    n_iteraciones: int = Field(default=10000, ge=1000, le=200000)
    mttr_sigma: float = Field(default=0.5, gt=0)


class SimulacionResult(BaseModel):
    id_simulacion: UUID
    beta: float
    eta: float
    beta_ic_inferior: Optional[float]
    beta_ic_superior: Optional[float]
    n_fallas_usadas: int
    n_censurados_usados: int
    mtbf_simulado: float
    mtbf_ic_90: List[float]
    mttr_simulado: float
    b10_life: float
    interpretacion: str
    curva_ft: List[dict]        # [{t: float, f_pct: float}, ...]
    histograma_ttf: List[dict]  # [{bin_inicio: float, frecuencia: int}, ...]


class RcmPlanRequest(BaseModel):
    id_simulacion: UUID
    id_motor: UUID
    costo_hora_preventivo: float
    costo_falla_catastrofica: float
    costo_hora_parada_produccion: float


class RcmPlanResult(BaseModel):
    id_plan: UUID
    npr_calculado: int
    intervalo_optimo_horas: float
    costo_total_esperado: float
    estrategia: str
    curva_costo: List[dict]     # [{t: float, costo: float}, ...]
    rutina: List[dict]          # [{rango_pct, rango_horas, accion, detalle}, ...]


class CoxAnalysisRequest(BaseModel):
    id_modo: int
    covariables: List[str] = Field(default=["frecuencia_khz", "thd_pct", "temperatura_promedio_c"])


class CoxAnalysisResult(BaseModel):
    id_modelo: UUID
    hazard_ratios: dict
    interpretaciones: List[str]
    concordance_index: float
    n_observaciones: int
    n_eventos: int
    aviso: Optional[str] = None


class CoxEscenarioRequest(BaseModel):
    id_modo: int
    covariables: List[str]
    escenario: dict   # ej. {"frecuencia_khz": 12, "thd_pct": 5, "temperatura_promedio_c": 50}


class CoxEscenarioResult(BaseModel):
    mediana_vida_horas: float
    escenario_evaluado: dict
