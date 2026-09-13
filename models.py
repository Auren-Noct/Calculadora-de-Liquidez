import calendar
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal

TipoMeta = Literal["recurrente", "puntual"]
TipoMedio = Literal["fisico", "digital"]
TipoTx = Literal[
    "INGRESO",
    "GASTO_CORRIENTE",
    "CUOTA_PRORRATEO",
    "PAGO_META",
    "LIBERACION_RESERVA",
]

__all__ = [
    "MetaProrrateo",
    "TipoMedio",
    "TipoMeta",
    "TipoTx",
    "Transaccion",
]


@dataclass
class Transaccion:
    id: str
    fecha: str
    tipo: TipoTx
    monto: float
    medio: TipoMedio
    descripcion: str
    meta_id: str | None = None
    meta_nombre: str | None = None


@dataclass
class MetaProrrateo:
    id: str
    nombre: str
    monto_total: float
    fecha_limite: str  # Formato ISO 'YYYY-MM-DD'
    fecha_inicio: str = ""  # Formato ISO 'YYYY-MM-DD'
    tipo_meta: TipoMeta = "puntual"
    intervalo_meses_recurrencia: int = 12
    acumulado_actual: float = 0.0
    monto_historico_pagado: float = 0.0
    activa: bool = True

    def __post_init__(self) -> None:
        if not self.fecha_inicio:
            self.fecha_inicio = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    @property
    def dt_limite(self) -> date:
        return date.fromisoformat(self.fecha_limite)

    @property
    def dt_inicio(self) -> date:
        return date.fromisoformat(self.fecha_inicio)

    @property
    def meses_restantes(self) -> int:
        hoy = datetime.now(timezone.utc).date()
        limite = self.dt_limite
        diferencia = (limite.year - hoy.year) * 12 + (limite.month - hoy.month)
        return max(1, diferencia)

    @property
    def monto_restante(self) -> float:
        return max(0.0, self.monto_total - self.acumulado_actual)

    @property
    def cuota_mensual_sugerida(self) -> float:
        if self.monto_restante <= 0:
            return 0.0
        return round(self.monto_restante / self.meses_restantes, 2)

    @property
    def esta_cubierto_ciclo(self) -> bool:
        return self.acumulado_actual >= self.monto_total

    def renovar_ciclo(self) -> None:
        hoy_dt = datetime.now(timezone.utc).date()
        limite_actual = self.dt_limite

        nuevo_mes = (
            limite_actual.month - 1 + self.intervalo_meses_recurrencia
        ) % 12 + 1
        nuevo_anio = (
            limite_actual.year
            + (limite_actual.month - 1 + self.intervalo_meses_recurrencia) // 12
        )
        max_dias = calendar.monthrange(nuevo_anio, nuevo_mes)[1]
        nueva_fecha = date(nuevo_anio, nuevo_mes, min(limite_actual.day, max_dias))

        if nueva_fecha <= hoy_dt:
            nuevo_mes_hoy = (
                hoy_dt.month - 1 + self.intervalo_meses_recurrencia
            ) % 12 + 1
            nuevo_anio_hoy = (
                hoy_dt.year
                + (hoy_dt.month - 1 + self.intervalo_meses_recurrencia) // 12
            )
            max_dias_hoy = calendar.monthrange(nuevo_anio_hoy, nuevo_mes_hoy)[1]
            nueva_fecha = date(
                nuevo_anio_hoy, nuevo_mes_hoy, min(hoy_dt.day, max_dias_hoy)
            )

        self.fecha_inicio = hoy_dt.strftime("%Y-%m-%d")
        self.fecha_limite = nueva_fecha.strftime("%Y-%m-%d")
        self.acumulado_actual = 0.0
