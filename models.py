from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal


@dataclass
class MetaProrrateo:
    id: str
    nombre: str
    monto_total: float
    meses_plazo: int
    acumulado_actual: float = 0.0
    tipo_ciclo: Literal["cerrado_mensual", "abierto_anual", "temporal"] = (
        "abierto_anual"
    )
    meses_transcurridos: int = 0
    activa: bool = True

    @property
    def monto_restante(self) -> float:
        return max(0.0, self.monto_total - self.acumulado_actual)

    @property
    def meses_restantes(self) -> int:
        return max(1, self.meses_plazo - self.meses_transcurridos)

    @property
    def cuota_mensual_sugerida(self) -> float:
        """Calcula la cuota adaptativa según el saldo pendiente y los meses faltantes."""
        if not self.activa or self.esta_cubierto_ciclo:
            return 0.0
        return self.monto_restante / self.meses_restantes

    @property
    def esta_cubierto_ciclo(self) -> bool:
        """Determina si el ciclo actual ya completó su cuota."""
        if self.tipo_ciclo == "cerrado_mensual":
            cuota_esperada_mes = self.monto_total / max(1, self.meses_plazo)
            return self.acumulado_actual >= cuota_esperada_mes
        return self.monto_restante == 0.0

    def registrar_aporte(self, monto: float) -> float:
        """Suma fondos a la meta respetando el tope del monto total."""
        monto_efectivo = min(monto, self.monto_restante)
        self.acumulado_actual += monto_efectivo
        return monto_efectivo

    def reiniciar_ciclo(self) -> None:
        """Reinicia el acumulado al vencer el ciclo si es recurrente."""
        if self.tipo_ciclo in ["cerrado_mensual", "abierto_anual"]:
            self.acumulado_actual = 0.0
            self.meses_transcurridos = 0
        elif self.tipo_ciclo == "temporal":
            self.activa = False


@dataclass
class Transaccion:
    id: str
    tipo: Literal["INGRESO", "GASTO_CORRIENTE", "CUOTA_PRORRATEO", "PAGO_META"]
    monto: float
    medio: Literal["fisico", "digital"]
    descripcion: str
    fecha: str = ""
    meta_id: str | None = None

    def __post_init__(self):
        if not self.fecha:
            self.fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
