"""
Esquemas Pydantic — contrato de la API v2 (campos completos)
"""
from datetime import date, datetime
from typing import Optional, List, Any
from uuid import UUID
from pydantic import BaseModel, Field


class MotorCreate(BaseModel):
    tag: Optional[str] = None
    fabricante: Optional[str] = None
    modelo: Optional[str] = None
    serial: str
    anio: Optional[int] = None
    equipo_accionado: Optional[str] = None
    macolla: Optional[str] = None
    pozo: Optional[str] = None
    unidad: Optional[str] = None
    division: Optional[str] = None
    potencia_hp: Optional[float] = None
    tension: Optional[float] = None
    corriente: Optional[float] = None
    frecuencia: Optional[float] = None
    fases: Optional[str] = None
    fp: Optional[float] = None
    eficiencia: Optional[float] = None
    conexion: Optional[str] = None
    sf: Optional[float] = None
    rpm: Optional[float] = None
    polos: Optional[int] = None
    montaje: Optional[str] = None
    frame: Optional[str] = None
    rodamiento_de: Optional[str] = None
    rodamiento_nde: Optional[str] = None
    eje: Optional[str] = None
    peso: Optional[float] = None
    aislamiento: Optional[str] = None
    ip: Optional[str] = None
    regimen: Optional[str] = None
    temp_ambiente: Optional[float] = None
    altitud: Optional[float] = None
    clase_nema: Optional[str] = None
    corriente_arranque: Optional[str] = None
    fecha_ultima_prueba: Optional[date] = None
    resistencia_aislamiento: Optional[float] = None
    indice_polarizacion: Optional[float] = None
    vibracion_ref: Optional[float] = None
    temp_rodamientos_ref: Optional[float] = None
    cabezal: Optional[str] = None
    criticidad: str = Field(pattern="^[ABC]$")


class MotorUpdate(MotorCreate):
    serial: Optional[str] = None
    criticidad: Optional[str] = Field(default=None, pattern="^[ABC]$")


class MotorOut(MotorCreate):
    id_motor: UUID
    activo: bool
    class Config:
        from_attributes = True


class FallaCreate(BaseModel):
    id_motor: UUID
    modo: str  # clave del modo, ej. "rodamientos"
    fecha: Optional[date] = None
    componente_especifico: Optional[str] = None
    orden_trabajo: Optional[str] = None
    reportado_por: Optional[str] = None
    causa_raiz: Optional[str] = None
    categoria_causa: Optional[str] = None
    metodo_analisis: Optional[str] = None
    accion_correctiva: Optional[str] = None
    accion_preventiva: Optional[str] = None
    recurrente: Optional[str] = None
    horas_operacion_al_evento: float = Field(ge=0)
    carga_pct: Optional[float] = None
    temperatura_registrada: Optional[float] = None
    vibracion_registrada: Optional[float] = None
    corriente_registrada: Optional[float] = None
    mttr: Optional[float] = None
    horas_parada_produccion: Optional[float] = None
    costo_reparacion: Optional[float] = None
    produccion_perdida_bbl: Optional[float] = None
    repuesto_utilizado: Optional[str] = None
    censurado: bool = False


class FallaUpdate(FallaCreate):
    id_motor: Optional[UUID] = None
    modo: Optional[str] = None
    horas_operacion_al_evento: Optional[float] = None


class FallaOut(FallaCreate):
    id_falla: UUID
    id_modo: int
    class Config:
        from_attributes = True


class AmefOverrideIn(BaseModel):
    id_modo: int
    severidad: Optional[int] = Field(default=None, ge=1, le=10)
    ocurrencia_manual: Optional[int] = Field(default=None, ge=1, le=10)
    deteccion: Optional[int] = Field(default=None, ge=1, le=10)


class AmefEntryOut(BaseModel):
    id_modo: int
    clave: str
    nombre: str
    severidad: int
    ocurrencia: int
    ocurrencia_es_calculada: bool
    deteccion: int
    npr: int
    tecnica_deteccion: str
    iso_modo: Optional[str] = None
    iso_mecanismo: Optional[str] = None


class InventarioCreate(BaseModel):
    nombre: str
    modo: str
    stock: int = 0
    punto_reorden: int = 0
    lead_time_dias: int = 0
    costo_unitario: Optional[float] = None


class InventarioOut(InventarioCreate):
    id_repuesto: UUID
    class Config:
        from_attributes = True


class SimulacionRequest(BaseModel):
    modo: str
    id_motor: Optional[UUID] = None
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
    curva_ft: List[dict]
    histograma_ttf: List[dict]


class RcmPlanRequest(BaseModel):
    id_simulacion: UUID
    id_motor: Optional[UUID] = None
    costo_hora_preventivo: float
    costo_falla_catastrofica: float
    costo_hora_parada_produccion: float


class RcmPlanResult(BaseModel):
    id_plan: UUID
    npr_calculado: int
    intervalo_optimo_horas: float
    costo_total_esperado: float
    estrategia: str
    estado: str
    curva_costo: List[dict]
    rutina: List[dict]


class PlanAccionRequest(BaseModel):
    comentario: Optional[str] = None


class PlanOut(BaseModel):
    id_plan: UUID
    id_modo: int
    npr_calculado: int
    intervalo_optimo_horas: float
    costo_total_esperado: float
    estrategia: str
    estado: str
    historial: List[dict]
    generado_en: datetime
    class Config:
        from_attributes = True
