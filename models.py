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
                self.fecha_inicio = (
                    datetime.now(timezone.utc).date().strftime("%Y-%m-%d")
                )

    @property
    def dt_limite(self) -> date:
        return date.fromisoformat(self.fecha_limite)

    @property
    def dt_inicio(self) -> date:
        return date.fromisoformat(self.fecha_inicio)

    @property
    def ciclos_totales_estructurales(self) -> int:
        # Ahorro y Gasto Cíclico no tienen estructura discreta de múltiples cuotas finitas
        if self.tipo_meta in ["gasto_ciclico", "ahorro_objetivo"]:
            return 1

        ciclos = 0
        meses_sumados = 0
        fin = self.dt_inicio
        while fin < self.dt_limite:
            ciclos += 1
            meses_sumados += self.intervalo_meses_recurrencia
            nuevo_mes = (self.dt_inicio.month - 1 + meses_sumados) % 12 + 1
            nuevo_anio = (
                self.dt_inicio.year + (self.dt_inicio.month - 1 + meses_sumados) // 12
            )
            max_dias = calendar.monthrange(nuevo_anio, nuevo_mes)[1]
            fin = date(nuevo_anio, nuevo_mes, min(self.dt_inicio.day, max_dias))
        return max(1, ciclos)

    @property
    def cuota_base(self) -> float:
        """La división matemática cruda del prorrateo."""
        if self.tipo_meta in ["gasto_ciclico", "ahorro_objetivo"]:
            return self.monto_total
        return round(self.monto_total / self.ciclos_totales_estructurales, 2)

    def _obtener_info_ciclo_actual(self) -> tuple[date, date, int]:
        hoy = datetime.now(timezone.utc).date()

        def calcular_fin(inicio_dt: date, meses: int) -> date:
            nuevo_mes = (inicio_dt.month - 1 + meses) % 12 + 1
            nuevo_anio = inicio_dt.year + (inicio_dt.month - 1 + meses) // 12
            max_dias = calendar.monthrange(nuevo_anio, nuevo_mes)[1]
            return date(nuevo_anio, nuevo_mes, min(inicio_dt.day, max_dias))

        if hoy < self.dt_inicio:
            fin_calc = calcular_fin(self.dt_inicio, self.intervalo_meses_recurrencia)
            return self.dt_inicio, fin_calc, 1

        inicio = self.dt_inicio
        meses_sumados = self.intervalo_meses_recurrencia
        ciclo = 1

        while True:
            fin_real = calcular_fin(self.dt_inicio, meses_sumados)
            # Regla B aplicada: Eliminado el truncamiento min(fin_calc, dt_limite). Las ventanas son exactas.
            if hoy < fin_real or fin_real >= self.dt_limite:
                return inicio, fin_real, ciclo

            inicio = fin_real
            meses_sumados += self.intervalo_meses_recurrencia
            ciclo += 1

    @property
    def inicio_ciclo_actual(self) -> date:
        if self.tipo_meta in ["gasto_ciclico", "ahorro_objetivo"]:
            return self.dt_inicio
        return self._obtener_info_ciclo_actual()[0]

    @property
    def fecha_vencimiento_actual(self) -> date:
        if self.tipo_meta in ["gasto_ciclico", "ahorro_objetivo"]:
            return self.dt_limite
        return self._obtener_info_ciclo_actual()[1]

    def valor_cuota_financiera(self, numero_ciclo: int) -> float:
        """Calcula el valor exacto de una obligación estructural específica (1-indexed)."""
        if self.tipo_meta in ["gasto_ciclico", "ahorro_objetivo"]:
            return self.cuota_base

        totales = self.ciclos_totales_estructurales
        if numero_ciclo >= totales:
            return round(self.monto_total - (self.cuota_base * (totales - 1)), 2)
        return self.cuota_base

    @property
    def cuota_fija(self) -> float:
        """Exigencia de la ventana cronológica actual."""
        ciclo_cronologico = self._obtener_info_ciclo_actual()[2]
        return self.valor_cuota_financiera(ciclo_cronologico)

    @property
    def monto_restante(self) -> float:
        aportado_total = self.acumulado_actual + self.monto_historico_pagado
        return max(0.0, self.monto_total - aportado_total)

    @property
    def estado_periodo(self) -> dict:
        hoy = datetime.now(timezone.utc).date()
        aportado_global = self.acumulado_actual + self.monto_historico_pagado

        if self.tipo_meta == "ahorro_objetivo":
            if hoy < self.dt_inicio:
                proporcion = 0.0
            elif hoy >= self.dt_limite:
                proporcion = 1.0
            else:
                dias_totales = max(1, (self.dt_limite - self.dt_inicio).days)
                dias_transcurridos = (hoy - self.dt_inicio).days
                proporcion = dias_transcurridos / dias_totales

            esperado_global = self.monto_total * proporcion
            pendiente = max(0.0, esperado_global - aportado_global)

        elif self.tipo_meta == "pago_cuotas":
            if hoy < self.dt_inicio:
                esperado_global = 0.0
            else:
                ciclo_cronologico = self._obtener_info_ciclo_actual()[2]
                ciclo_cronologico = min(
                    ciclo_cronologico, self.ciclos_totales_estructurales
                )

                if ciclo_cronologico == self.ciclos_totales_estructurales:
                    esperado_global = self.monto_total
                else:
                    esperado_global = ciclo_cronologico * self.cuota_base

            pendiente = max(0.0, esperado_global - aportado_global)

        else:  # gasto_ciclico
            if hoy < self.dt_inicio:
                return {"estado": "cubierto", "deficit_exigible": 0.0}

            aportado_ciclo = self.acumulado_actual + self.pagado_ciclo_actual
            pendiente = max(0.0, self.cuota_fija - aportado_ciclo)

        return {
            "estado": "cubierto" if pendiente <= 0.01 else "pendiente",
            "deficit_exigible": round(pendiente, 2),
        }

    @property
    def cuota_sugerida(self) -> float:
        hoy = datetime.now(timezone.utc).date()

        if self.tipo_meta in ["gasto_ciclico", "pago_cuotas"]:
            restante_financiero = float(self.estado_periodo["deficit_exigible"])
            dias_restantes = (self.fecha_vencimiento_actual - hoy).days
        else:
            restante_financiero = self.monto_restante
            dias_restantes = (self.dt_limite - hoy).days

        if restante_financiero <= 0:
            return 0.0

        dias_restantes = max(1, dias_restantes)
        ritmo_diario = restante_financiero / dias_restantes
        return round(ritmo_diario * 30, 2)

    def registrar_pago(self, monto: float, medio: TipoMedio, modalidad: str) -> None:
        self.monto_historico_pagado = round(self.monto_historico_pagado + monto, 2)
        self.pagado_ciclo_actual = round(self.pagado_ciclo_actual + monto, 2)
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
        # 1. Identificamos la obligación financiera exacta que estamos cerrando
        cuota_completada = self.valor_cuota_financiera(self.ciclos_pagados + 1)

        if self.tipo_meta == "gasto_ciclico":
            self.fecha_inicio = self.fecha_limite

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
            self.fecha_limite = nueva_fecha.strftime("%Y-%m-%d")

        self.ciclos_pagados += 1
        self.pagado_ciclo_actual = round(
            max(0.0, self.pagado_ciclo_actual - cuota_completada), 2
        )

    def revertir_pago_externo(self, monto: float) -> None:
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
                    # Recuperamos el valor exacto de la cuota financiera que estamos deshaciendo
                    cuota_restaurada = self.valor_cuota_financiera(self.ciclos_pagados)
                    self.ciclos_pagados -= 1
                    self.pagado_ciclo_actual = cuota_restaurada

                    if self.tipo_meta == "gasto_ciclico":
                        self.fecha_limite = self.fecha_inicio

                        inicio_actual = self.dt_inicio
                        nuevo_mes = (
                            inicio_actual.month - 1 - self.intervalo_meses_recurrencia
                        ) % 12 + 1
                        nuevo_anio = (
                            inicio_actual.year
                            + (
                                inicio_actual.month
                                - 1
                                - self.intervalo_meses_recurrencia
                            )
                            // 12
                        )
                        max_dias = calendar.monthrange(nuevo_anio, nuevo_mes)[1]
                        self.fecha_inicio = date(
                            nuevo_anio, nuevo_mes, min(inicio_actual.day, max_dias)
                        ).strftime("%Y-%m-%d")
                else:
                    self.pagado_ciclo_actual = 0.0
                    restante_a_revertir = 0.0

        self.activa = True
