import calendar
import math
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
    fecha_limite: str
    fecha_inicio: str = ""
    tipo_meta: TipoMeta = "ahorro_objetivo"
    intervalo_meses_recurrencia: int = 1
    acumulado_actual: float = 0.0
    pagado_ciclo_actual: float = 0.0
    monto_historico_pagado: float = 0.0
    ciclos_pagados: int = 0
    activa: bool = True
    historial_pagos: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.fecha_inicio:
            limite = date.fromisoformat(self.fecha_limite)
            if self.tipo_meta == "gasto_ciclico":
                nuevo_mes = (
                    limite.month - 1 - self.intervalo_meses_recurrencia
                ) % 12 + 1
                nuevo_anio = (
                    limite.year
                    + (limite.month - 1 - self.intervalo_meses_recurrencia) // 12
                )
                max_dias = calendar.monthrange(nuevo_anio, nuevo_mes)[1]
                self.fecha_inicio = date(
                    nuevo_anio, nuevo_mes, min(limite.day, max_dias)
                ).strftime("%Y-%m-%d")
            else:
                self.fecha_inicio = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    @property
    def dt_limite(self) -> date:
        return date.fromisoformat(self.fecha_limite)

    @property
    def dt_inicio(self) -> date:
        return date.fromisoformat(self.fecha_inicio)

    @property
    def cuota_fija(self) -> float:
        """La exigencia dura de un ciclo (lo que define si cumpliste o no)."""
        if self.tipo_meta == "gasto_ciclico":
            return self.monto_total

        # Para pago_cuotas y ahorro_objetivo: La cuota base calculada desde el día 1
        dif = (self.dt_limite.year - self.dt_inicio.year) * 12 + (
            self.dt_limite.month - self.dt_inicio.month
        )
        meses_totales = max(1, dif)

        # math.ceil asegura que los remanentes de meses exijan una cuota adicional
        ciclos_totales = max(
            1, math.ceil(meses_totales / max(1, self.intervalo_meses_recurrencia))
        )
        return round(self.monto_total / ciclos_totales, 2)

    @property
    def meses_restantes(self) -> int:
        hoy = datetime.now(timezone.utc).date()
        limite = self.dt_limite
        dif = (limite.year - hoy.year) * 12 + (limite.month - hoy.month)
        return max(1, dif)

    @property
    def monto_restante(self) -> float:
        # Refleja el progreso global (Dimensión 1)
        aportado_total = self.acumulado_actual + self.monto_historico_pagado
        return max(0.0, self.monto_total - aportado_total)

    @property
    def meses_restantes_ciclo(self) -> int:
        """Calcula cuántos meses calendarios le quedan al ciclo vigente."""
        hoy = datetime.now(timezone.utc).date()
        limite = self.fecha_vencimiento_actual
        dif = (limite.year - hoy.year) * 12 + (limite.month - hoy.month)
        return max(1, dif)

    @property
    def cuota_sugerida(self) -> float:
        """El ritmo necesario desde hoy para alcanzar la meta o cubrir el ciclo actual."""
        if self.tipo_meta == "gasto_ciclico":
            restante_ciclo = max(
                0.0, self.monto_total - self.acumulado_actual - self.pagado_ciclo_actual
            )
            if restante_ciclo <= 0:
                return 0.0
            # Prorratea el saldo del ciclo por los meses que le quedan a ESE ciclo
            return round(restante_ciclo / self.meses_restantes_ciclo, 2)

        if self.monto_restante <= 0:
            return 0.0
        return round(self.monto_restante / self.meses_restantes, 2)

    @property
    def inicio_ciclo_actual(self) -> date:
        if self.ciclos_pagados == 0:
            return self.dt_inicio
        meses_a_sumar = self.ciclos_pagados * self.intervalo_meses_recurrencia
        nuevo_mes = (self.dt_inicio.month - 1 + meses_a_sumar) % 12 + 1
        nuevo_anio = (
            self.dt_inicio.year + (self.dt_inicio.month - 1 + meses_a_sumar) // 12
        )
        max_dias = calendar.monthrange(nuevo_anio, nuevo_mes)[1]
        return date(nuevo_anio, nuevo_mes, min(self.dt_inicio.day, max_dias))

    @property
    def fecha_vencimiento_actual(self) -> date:
        meses_a_sumar = (self.ciclos_pagados + 1) * self.intervalo_meses_recurrencia
        nuevo_mes = (self.dt_inicio.month - 1 + meses_a_sumar) % 12 + 1
        nuevo_anio = (
            self.dt_inicio.year + (self.dt_inicio.month - 1 + meses_a_sumar) // 12
        )
        max_dias = calendar.monthrange(nuevo_anio, nuevo_mes)[1]
        return date(nuevo_anio, nuevo_mes, min(self.dt_inicio.day, max_dias))

    @property
    def esta_cubierto_ciclo(self) -> bool:
        """¿El ciclo actual tiene todo el dinero requerido?"""
        return (self.acumulado_actual + self.pagado_ciclo_actual) >= self.cuota_fija

    @property
    def estado_periodo(self) -> dict:
        """¿La exigencia del período actual está cubierta? Si no, ¿cuánto falta? (Dimensión 2)"""
        hoy = datetime.now(timezone.utc).date()

        if self.tipo_meta == "ahorro_objetivo":
            # Para ahorro puro: ¿cuánto debería haber acumulado GLOBALMENTE hasta hoy?
            dif = (hoy.year - self.dt_inicio.year) * 12 + (
                hoy.month - self.dt_inicio.month
            )
            meses_transcurridos = max(0, dif)
            dif_totales = (self.dt_limite.year - self.dt_inicio.year) * 12 + (
                self.dt_limite.month - self.dt_inicio.month
            )
            meses_totales = max(1, dif_totales)

            # El + 1 determina que la primera cuota es exigible desde el día de creación
            cuotas_exigibles = min(meses_transcurridos + 1, meses_totales)
            esperado_global = self.cuota_fija * cuotas_exigibles

            aportado_global = self.acumulado_actual + self.monto_historico_pagado
            pendiente = max(0.0, esperado_global - aportado_global)

            return {
                "estado": "cubierto" if pendiente <= 0 else "pendiente",
                "pendiente_periodo": pendiente,
            }
        else:
            # Para cuotas y suscripciones: se rige estrictamente por el ciclo temporal
            if hoy < self.inicio_ciclo_actual:
                return {"estado": "cubierto", "pendiente_periodo": 0.0}

            aportado_ciclo = self.acumulado_actual + self.pagado_ciclo_actual
            pendiente = max(0.0, self.cuota_fija - aportado_ciclo)

            return {
                "estado": "cubierto" if pendiente <= 0 else "pendiente",
                "pendiente_periodo": pendiente,
            }

    def posponer_cuota(self) -> None:
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
                "ciclo_limite": self.fecha_vencimiento_actual.strftime("%Y-%m-%d"),
            }
        )

    def renovar_ciclo(self) -> None:
        """Avanza al siguiente período conservando el dinero sobrante (si se pagó de más)."""
        self.ciclos_pagados += 1
        self.pagado_ciclo_actual = round(
            max(0.0, self.pagado_ciclo_actual - self.cuota_fija), 2
        )

    def revertir_pago_externo(self, monto: float) -> None:
        """Retrocede el historial, los ciclos y los saldos al revertir un pago de manera simétrica."""
        self.monto_historico_pagado = round(
            max(0.0, self.monto_historico_pagado - monto), 2
        )

        restante_a_revertir = monto
        while restante_a_revertir > 0.01:
            if self.pagado_ciclo_actual >= restante_a_revertir:
                self.pagado_ciclo_actual = round(
                    self.pagado_ciclo_actual - restante_a_revertir, 2
                )
                restante_a_revertir = 0.0
            else:
                restante_a_revertir = round(
                    restante_a_revertir - self.pagado_ciclo_actual, 2
                )
                if self.ciclos_pagados > 0:
                    self.ciclos_pagados -= 1
                    self.pagado_ciclo_actual = self.cuota_fija
                else:
                    self.pagado_ciclo_actual = 0.0
                    restante_a_revertir = 0.0

        self.activa = True
