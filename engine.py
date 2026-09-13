from datetime import datetime, timezone

from models import MetaProrrateo, TipoMedio, Transaccion


class MotorFinanciero:

    def __init__(self, pct_ahorro: float = 0.10) -> None:
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

    def modificar_meta(
        self,
        meta_id: str,
        nombre: str,
        monto_total: float,
        fecha_limite: str,
        tipo_meta: str,
        intervalo_meses_recurrencia: int,
    ) -> None:
        assert meta_id in self.metas_prorrateo, "Meta no encontrada."
        meta = self.metas_prorrateo[meta_id]
        meta.nombre = nombre
        meta.monto_total = monto_total
        meta.fecha_limite = fecha_limite
        meta.tipo_meta = tipo_meta  # type: ignore
        meta.intervalo_meses_recurrencia = intervalo_meses_recurrencia

    def eliminar_meta(self, meta_id: str) -> float:
        assert meta_id in self.metas_prorrateo, "Meta no encontrada."
        meta = self.metas_prorrateo.pop(meta_id)
        monto_reintegrado = meta.acumulado_actual

        tx_id = f"tx_{len(self.historial) + 1}"
        fecha_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        self.historial.append(
            Transaccion(
                id=tx_id,
                fecha=fecha_now,
                tipo="LIBERACION_RESERVA",
                monto=monto_reintegrado,
                medio="digital",
                descripcion=f"Baja de meta '{meta.nombre}'. Reintegro de reserva a Liquidez Real.",
                meta_id=meta_id,
                meta_nombre=meta.nombre,
            )
        )

        return monto_reintegrado

    def confirmar_ingreso(
        self,
        monto: float,
        medio: TipoMedio,
        descripcion: str,
        monto_ahorro: float,
        distribucion_metas: dict[str, float],
        modalidades_aporte: dict[str, bool] | None = None,
    ) -> None:
        if modalidades_aporte is None:
            modalidades_aporte = {}

        if medio == "fisico":
            self.saldo_fisico += monto
        else:
            self.saldo_digital += monto

        self.caja_ahorro_intocable += monto_ahorro

        fecha_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        self.historial.append(
            Transaccion(
                id=f"tx_{len(self.historial) + 1}",
                fecha=fecha_now,
                tipo="INGRESO",
                monto=monto,
                medio=medio,
                descripcion=descripcion,
            )
        )

        for meta_id, monto_cuota in distribucion_metas.items():
            if meta_id in self.metas_prorrateo and monto_cuota > 0:
                meta = self.metas_prorrateo[meta_id]
                es_adelanto = modalidades_aporte.get(meta_id, False)

                meta.acumulado_actual += monto_cuota

                self.historial.append(
                    Transaccion(
                        id=f"tx_{len(self.historial) + 1}",
                        fecha=fecha_now,
                        tipo="CUOTA_PRORRATEO",
                        monto=monto_cuota,
                        medio=medio,
                        descripcion=f"Reserva para '{meta.nombre}' ({'Adelanto' if es_adelanto else 'Cuota Regular'})",
                        meta_id=meta_id,
                        meta_nombre=meta.nombre,
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

    def ejecutar_pago_meta(
        self,
        meta_id: str,
        medio: TipoMedio,
        monto_pago: float,
        modalidad: str = "reserva_y_liquidez",
    ) -> None:
        assert meta_id in self.metas_prorrateo, "Meta no encontrada."
        meta = self.metas_prorrateo[meta_id]

        monto_reserva_usado = 0.0
        monto_liquidez_usado = 0.0

        if modalidad == "reserva_y_liquidez":
            monto_reserva_usado = min(meta.acumulado_actual, monto_pago)
            monto_liquidez_usado = max(0.0, monto_pago - monto_reserva_usado)
        else:
            monto_liquidez_usado = monto_pago

        if monto_liquidez_usado > 0:
            assert (
                monto_liquidez_usado <= self.liquidez_real
            ), f"Liquidez Real insuficiente para cubrir la diferencia (${self.liquidez_real:,.2f})."

        saldo_disponible = (
            self.saldo_fisico if medio == "fisico" else self.saldo_digital
        )
        assert (
            saldo_disponible >= monto_pago
        ), f"Saldo insuficiente en medio '{medio}' (${saldo_disponible:,.2f}) para abonar ${monto_pago:,.2f}."

        if medio == "fisico":
            self.saldo_fisico -= monto_pago
        else:
            self.saldo_digital -= monto_pago

        meta.monto_historico_pagado += monto_pago
        meta.acumulado_actual -= monto_reserva_usado

        tx_id = f"tx_{len(self.historial) + 1}"
        fecha_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        self.historial.append(
            Transaccion(
                id=tx_id,
                fecha=fecha_now,
                tipo="PAGO_META",
                monto=monto_pago,
                medio=medio,
                descripcion=(
                    f"Pago a '{meta.nombre}' ({modalidad}). "
                    f"[Reserva: ${monto_reserva_usado:,.2f} | Liquidez: ${monto_liquidez_usado:,.2f}]"
                ),
                meta_id=meta_id,
                meta_nombre=meta.nombre,
            )
        )

        if meta.tipo_meta == "recurrente":
            if (
                meta.monto_historico_pagado >= meta.monto_total
                or meta.esta_cubierto_ciclo
            ):
                meta.renovar_ciclo()
        elif meta.monto_historico_pagado >= meta.monto_total:
            meta.activa = False
