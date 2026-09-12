from datetime import datetime, timezone

from models import MetaProrrateo, TipoMedio, Transaccion


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
            m.acumulado_actual for m in self.metas_prorrateo.values() if m.activa
        )

    @property
    def liquidez_real(self) -> float:
        return (
            self.total_posesion
            - self.caja_ahorro_intocable
            - self.total_prorrateo_acumulado
        )

    def agregar_meta(self, meta: MetaProrrateo) -> None:
        self.metas_prorrateo[meta.id] = meta

    def calcular_propuesta_ingreso(
        self, monto_ingreso: float
    ) -> tuple[float, dict[str, float]]:
        ahorro_intocable = monto_ingreso * self.pct_ahorro
        distribucion_metas: dict[str, float] = {}

        for meta_id, meta in self.metas_prorrateo.items():
            if meta.activa and not meta.esta_cubierto_ciclo:
                cuota = min(meta.cuota_mensual_sugerida, meta.monto_restante)
                distribucion_metas[meta_id] = round(cuota, 2)

        return ahorro_intocable, distribucion_metas

    def confirmar_ingreso(
        self,
        monto: float,
        medio: TipoMedio,
        descripcion: str,
        monto_ahorro: float,
        distribucion_metas: dict[str, float],
    ) -> None:
        if medio == "fisico":
            self.saldo_fisico += monto
        else:
            self.saldo_digital += monto

        self.caja_ahorro_intocable += monto_ahorro

        tx_id = f"tx_{len(self.historial) + 1}"
        fecha_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        self.historial.append(
            Transaccion(
                id=tx_id,
                fecha=fecha_now,
                tipo="INGRESO",
                monto=monto,
                medio=medio,
                descripcion=descripcion,
            )
        )

        for meta_id, monto_cuota in distribucion_metas.items():
            if meta_id in self.metas_prorrateo and monto_cuota > 0:
                self.metas_prorrateo[meta_id].acumulado_actual += monto_cuota
                self.historial.append(
                    Transaccion(
                        id=f"tx_{len(self.historial) + 1}",
                        fecha=fecha_now,
                        tipo="CUOTA_PRORRATEO",
                        monto=monto_cuota,
                        medio=medio,
                        descripcion=f"Reserva para {self.metas_prorrateo[meta_id].nombre}",
                        meta_id=meta_id,
                    )
                )

    def registrar_gasto_corriente(
        self, monto: float, medio: TipoMedio, descripcion: str
    ) -> None:
        assert (
            monto <= self.liquidez_real
        ), f"Gasto no permitido: supera la liquidez libre (${self.liquidez_real:,.2f})"

        if medio == "fisico":
            assert monto <= self.saldo_fisico, "Saldo físico insuficiente en billetera."
            self.saldo_fisico -= monto
        else:
            assert (
                monto <= self.saldo_digital
            ), "Saldo digital insuficiente en banco/app."
            self.saldo_digital -= monto

        tx_id = f"tx_{len(self.historial) + 1}"
        self.historial.append(
            Transaccion(
                id=tx_id,
                fecha=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                tipo="GASTO_CORRIENTE",
                monto=monto,
                medio=medio,
                descripcion=descripcion,
            )
        )

    def ejecutar_pago_meta(self, meta_id: str, medio: TipoMedio) -> None:
        assert meta_id in self.metas_prorrateo, "Meta no encontrada."
        meta = self.metas_prorrateo[meta_id]
        monto_pago = meta.monto_total

        if medio == "fisico":
            assert (
                self.saldo_fisico >= monto_pago
            ), "Efectivo insuficiente para efectuar el pago de esta meta."
            self.saldo_fisico -= monto_pago
        else:
            assert (
                self.saldo_digital >= monto_pago
            ), "Saldo digital insuficiente para efectuar el pago de esta meta."
            self.saldo_digital -= monto_pago

        self.historial.append(
            Transaccion(
                id=f"tx_{len(self.historial) + 1}",
                fecha=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                tipo="PAGO_META",
                monto=monto_pago,
                medio=medio,
                descripcion=f"Pago definitivo de meta: {meta.nombre}",
                meta_id=meta_id,
            )
        )

        if meta.tipo_meta == "recurrente":
            meta.renovar_ciclo()
        else:
            meta.activa = False
