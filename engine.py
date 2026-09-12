from typing import Literal

from models import MetaProrrateo, Transaccion


class MotorFinanciero:

    def __init__(self, pct_ahorro: float = 0.10):
        self.pct_ahorro = pct_ahorro
        self.saldo_fisico: float = 0.0
        self.saldo_digital: float = 0.0
        self.caja_ahorro_intocable: float = 0.0
        self.metas_prorrateo: dict[str, MetaProrrateo] = {}
        self.historial: list[Transaccion] = []

    @property
    def total_posesion(self) -> float:
        return self.saldo_fisico + self.saldo_digital

    @property
    def total_prorrateo_acumulado(self) -> float:
        return sum(
            meta.acumulado_actual
            for meta in self.metas_prorrateo.values()
            if meta.activa
        )

    @property
    def total_reservado(self) -> float:
        return self.caja_ahorro_intocable + self.total_prorrateo_acumulado

    @property
    def liquidez_real(self) -> float:
        return self.total_posesion - self.total_reservado

    def agregar_meta(self, meta: MetaProrrateo) -> None:
        self.metas_prorrateo[meta.id] = meta

    def calcular_propuesta_ingreso(
        self, monto: float
    ) -> tuple[float, dict[str, float]]:
        """Calcula la sugerencia de distribución antes de aplicar los cambios."""
        monto_ahorro = monto * self.pct_ahorro
        distribucion_metas: dict[str, float] = {}

        for meta_id, meta in self.metas_prorrateo.items():
            if meta.activa and not meta.esta_cubierto_ciclo:
                cuota = meta.cuota_mensual_sugerida
                distribucion_metas[meta_id] = min(cuota, meta.monto_restante)
            else:
                distribucion_metas[meta_id] = 0.0

        return monto_ahorro, distribucion_metas

    def confirmar_ingreso(
        self,
        monto: float,
        medio: Literal["fisico", "digital"],
        descripcion: str,
        monto_ahorro: float,
        distribucion_metas: dict[str, float],
    ) -> None:
        """Aplica la entrada de dinero y ejecuta las reservas confirmadas."""
        assert monto > 0, "El monto del ingreso debe ser positivo."
        assert medio in [
            "fisico",
            "digital",
        ], "El medio debe ser 'fisico' o 'digital'."

        # 1. Acreditar saldo total al medio correspondiente
        if medio == "fisico":
            self.saldo_fisico += monto
        else:
            self.saldo_digital += monto

        # 2. Retención activa del 10%
        self.caja_ahorro_intocable += monto_ahorro

        # 3. Distribución a las cajas de prorrateo
        for meta_id, aporte in distribucion_metas.items():
            if meta_id in self.metas_prorrateo and aporte > 0:
                self.metas_prorrateo[meta_id].registrar_aporte(aporte)

        # 4. Auditoría en historial
        tx = Transaccion(
            id=f"tx_{len(self.historial) + 1}",
            tipo="INGRESO",
            monto=monto,
            medio=medio,
            descripcion=descripcion,
        )
        self.historial.append(tx)

    def registrar_gasto_corriente(
        self,
        monto: float,
        medio: Literal["fisico", "digital"],
        descripcion: str,
    ) -> None:
        """Registra un gasto diario garantizando que no toque fondos reservados."""
        assert monto > 0, "El monto del gasto debe ser mayor a cero."

        saldo_disponible_medio = (
            self.saldo_fisico if medio == "fisico" else self.saldo_digital
        )
        assert saldo_disponible_medio >= monto, f"Saldo insuficiente en medio {medio}."

        # Fail-Fast: Proteger las reservas lógicas (Ahorro 10% + Prorrateos)
        assert (
            self.liquidez_real >= monto
        ), f"Operación bloqueada: Liquidez real insuficiente (${self.liquidez_real:,.2f})."

        if medio == "fisico":
            self.saldo_fisico -= monto
        else:
            self.saldo_digital -= monto

        tx = Transaccion(
            id=f"tx_{len(self.historial) + 1}",
            tipo="GASTO_CORRIENTE",
            monto=monto,
            medio=medio,
            descripcion=descripcion,
        )
        self.historial.append(tx)

    def ejecutar_pago_meta(
        self, meta_id: str, medio: Literal["fisico", "digital"]
    ) -> None:
        """Efectúa el pago final de una meta desde el dinero real y resetea su ciclo."""
        meta = self.metas_prorrateo.get(meta_id)
        assert meta is not None and meta.activa, "Meta no válida o inactiva."

        monto_a_pagar = meta.monto_total
        saldo_medio = self.saldo_fisico if medio == "fisico" else self.saldo_digital
        assert (
            saldo_medio >= monto_a_pagar
        ), f"Saldo insuficiente en medio {medio} para pagar la meta."

        if medio == "fisico":
            self.saldo_fisico -= monto_a_pagar
        else:
            self.saldo_digital -= monto_a_pagar

        meta.reiniciar_ciclo()

        tx = Transaccion(
            id=f"tx_{len(self.historial) + 1}",
            tipo="PAGO_META",
            monto=monto_a_pagar,
            medio=medio,
            descripcion=f"Pago efectuado: {meta.nombre}",
            meta_id=meta_id,
        )
        self.historial.append(tx)
