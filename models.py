import calendar
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal

TipoMeta = Literal["recurrente", "puntual"]
TipoMedio = Literal["fisico", "digital"]
TipoTx = Literal["INGRESO", "GASTO_CORRIENTE", "CUOTA_PRORRATEO", "PAGO_META"]


@dataclass
class MetaProrrateo:
    id: str
    nombre: str
    monto_total: float
    fecha_limite: str  # Formato ISO 'YYYY-MM-DD'
    tipo_meta: TipoMeta = "puntual"
    intervalo_meses_recurrencia: int = 12
    acumulado_actual: float = 0.0
    activa: bool = True

    @property
    def meses_restantes(self) -> int:
        hoy = datetime.now(timezone.utc).date()
        limite = (
            datetime.strptime(self.fecha_limite, "%Y-%m-%d")
            .replace(tzinfo=timezone.utc)
            .date()
        )
        diferencia_meses = (limite.year - hoy.year) * 12 + (limite.month - hoy.month)
        return max(1, diferencia_meses)

    @property
    def monto_restante(self) -> float:
        return max(0.0, self.monto_total - self.acumulado_actual)

    @property
    def cuota_mensual_sugerida(self) -> float:
        if self.monto_restante <= 0:
            return 0.0
        return self.monto_restante / self.meses_restantes

    @property
    def esta_cubierto_ciclo(self) -> bool:
        return self.acumulado_actual >= self.monto_total

    def renovar_ciclo(self) -> None:
        """Avanza la fecha límite según su intervalo de recurrencia si la meta es periódica."""
        limite_actual = (
            datetime.strptime(self.fecha_limite, "%Y-%m-%d")
            .replace(tzinfo=timezone.utc)
            .date()
        )
        nuevo_mes = (
            limite_actual.month - 1 + self.intervalo_meses_recurrencia
        ) % 12 + 1
        nuevo_anio = (
            limite_actual.year
            + (limite_actual.month - 1 + self.intervalo_meses_recurrencia) // 12
        )
        max_dias = calendar.monthrange(nuevo_anio, nuevo_mes)[1]
        nueva_fecha = date(nuevo_anio, nuevo_mes, min(limite_actual.day, max_dias))

        self.fecha_limite = nueva_fecha.strftime("%Y-%m-%d")
        self.acumulado_actual = 0.0


@dataclass
class Transaccion:
    id: str
    fecha: str
    tipo: TipoTx
    monto: float
    medio: TipoMedio
    descripcion: str
    meta_id: str | None = None
