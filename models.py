import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Literal

TipoMeta = Literal["ahorro_objetivo", "pago_cuotas", "gasto_ciclico"]
TipoMedio = Literal["fisico", "digital"]
TipoTx = Literal[
    "INGRESO",
    "GASTO_CORRIENTE",
    "CUOTA_PRORRATEO",
    "PAGO_META",
    "LIBERACION_RESERVA",
    "REVERSION",
]

__all__ = [
    "MetaProrrateo",
    "RegistroPagoMeta",
    "TipoMedio",
    "TipoMeta",
    "TipoTx",
    "Transaccion",
]


@dataclass
class RegistroPagoMeta:
    fecha: str
    monto: float
    medio: TipoMedio
    modalidad: str
    ciclo_limite: str


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
    es_revertida: bool = False
    tx_origen_id: str | None = None


@dataclass
class MetaProrrateo:
    id: str
    nombre: str
    monto_total: float
    fecha_limite: str  # YYYY-MM-DD
    fecha_inicio: str = ""  # YYYY-MM-DD
    tipo_meta: TipoMeta = "ahorro_objetivo"
    intervalo_meses_recurrencia: int = 12
    acumulado_actual: float = 0.0
    pagado_ciclo_actual: float = 0.0
    monto_historico_pagado: float = 0.0
    activa: bool = True
    historial_pagos: list[dict] = field(default_factory=list)

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
    def meses_totales(self) -> int:
        inicio = self.dt_inicio
        limite = self.dt_limite
        dif = (limite.year - inicio.year) * 12 + (limite.month - inicio.month)
        return max(1, dif)

    @property
    def meses_transcurridos(self) -> int:
        hoy = datetime.now(timezone.utc).date()
        inicio = self.dt_inicio
        dif = (hoy.year - inicio.year) * 12 + (hoy.month - inicio.month)
        return max(0, dif)

    @property
    def cuota_fija(self) -> float:
        """La cuota estática calculada desde el día 1, sin fluctuar."""
        if self.tipo_meta == "gasto_ciclico":
            return self.monto_total
        return round(self.monto_total / self.meses_totales, 2)

    @property
    def estado_mensual(self) -> dict:
        """
        Compara la fecha de hoy con el avance del plan.
        Retorna si estás al día, atrasado, y cuánto te exige poner este mes.
        """
        if self.tipo_meta == "gasto_ciclico":
            pendiente = max(
                0.0, self.monto_total - self.pagado_ciclo_actual - self.acumulado_actual
            )
            estado = "al_dia" if pendiente == 0 else "pendiente"
            return {"estado": estado, "pendiente_mes": pendiente}

        # Para pago en cuotas y ahorros (compara el paso del tiempo)
        meses_a_cubrir = min(self.meses_transcurridos + 1, self.meses_totales)
        esperado_acumulado = self.cuota_fija * meses_a_cubrir

        aportado_total = self.acumulado_actual + self.monto_historico_pagado
        diferencia = aportado_total - esperado_acumulado

        estado = "al_dia"
        if diferencia <= -1.0:  # Margen de error por redondeo
            estado = "atrasado"
        elif diferencia >= self.cuota_fija - 1.0:
            estado = "adelantado"

        monto_exigido_hoy = max(0.0, esperado_acumulado - aportado_total)

        return {
            "estado": estado,
            "esperado": esperado_acumulado,
            "aportado_real": aportado_total,
            "pendiente_mes": monto_exigido_hoy,
            "diferencia": diferencia,
        }

    @property
    def esta_cubierto_ciclo(self) -> bool:
        """Determina si ya se juntó/pagó la totalidad del dinero exigido para el ciclo actual."""
        return (self.acumulado_actual + self.pagado_ciclo_actual) >= self.monto_total

    def posponer_cuota(self) -> None:
        """Patea la fecha límite un mes hacia adelante si decidís saltarte un mes."""
        limite_actual = self.dt_limite
        nuevo_mes = (limite_actual.month % 12) + 1
        nuevo_anio = limite_actual.year + (1 if limite_actual.month == 12 else 0)
        max_dias = calendar.monthrange(nuevo_anio, nuevo_mes)[1]
        nueva_fecha = date(nuevo_anio, nuevo_mes, min(limite_actual.day, max_dias))
        self.fecha_limite = nueva_fecha.strftime("%Y-%m-%d")

    def registrar_pago(self, monto: float, medio: TipoMedio, modalidad: str) -> None:
        self.monto_historico_pagado += monto
        self.pagado_ciclo_actual += monto
        self.historial_pagos.append(
            {
                "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "monto": monto,
                "medio": medio,
                "modalidad": modalidad,
                "ciclo_limite": self.fecha_limite,
            }
        )

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
        self.pagado_ciclo_actual = 0.0
