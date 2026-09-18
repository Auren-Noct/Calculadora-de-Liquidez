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
                descripcion=f"Baja de meta '{meta.nombre}'. Reintegro a Liquidez Real.",
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
                self.aportar_a_reserva_interna(
                    meta_id, monto_cuota, f"Distribución de ingreso: {descripcion}"
                )

    def aportar_a_reserva_interna(
        self, meta_id: str, monto: float, descripcion: str = "Reserva manual"
    ) -> None:
        """Mueve dinero de la Liquidez Real a la caja de la meta sin afectar la posesión total."""
        assert (
            monto <= self.liquidez_real
        ), f"Liquidez Real insuficiente. Tenés libres: ${self.liquidez_real:,.2f}"
        assert meta_id in self.metas_prorrateo, "Meta no encontrada."
        meta = self.metas_prorrateo[meta_id]
        meta.acumulado_actual += monto

        self.historial.append(
            Transaccion(
                id=f"tx_{len(self.historial) + 1}",
                fecha=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                tipo="CUOTA_PRORRATEO",
                monto=monto,
                medio="digital",
                descripcion=f"Aporte a reserva de '{meta.nombre}' ({descripcion})",
                meta_id=meta_id,
                meta_nombre=meta.nombre,
            )
        )

    def registrar_gasto_corriente(
        self, monto: float, medio: TipoMedio, descripcion: str
    ) -> None:
        if medio == "fisico":
            assert (
                monto <= self.saldo_fisico
            ), f"Saldo físico insuficiente en billetera (Tenés ${self.saldo_fisico:,.2f})."
            self.saldo_fisico -= monto
        else:
            assert (
                monto <= self.saldo_digital
            ), f"Saldo digital insuficiente en banco/app (Tenés ${self.saldo_digital:,.2f})."
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

        saldo_disponible = (
            self.saldo_fisico if medio == "fisico" else self.saldo_digital
        )
        assert (
            saldo_disponible >= monto_pago
        ), f"Saldo real insuficiente en medio '{medio}' (${saldo_disponible:,.2f})."

        if medio == "fisico":
            self.saldo_fisico -= monto_pago
        else:
            self.saldo_digital -= monto_pago

        # Actualizamos la reserva ANTES de asentar el pago
        meta.acumulado_actual -= monto_reserva_usado
        meta.registrar_pago(monto=monto_pago, medio=medio, modalidad=modalidad)

        tx_id = f"tx_{len(self.historial) + 1}"
        self.historial.append(
            Transaccion(
                id=tx_id,
                fecha=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                tipo="PAGO_META",
                monto=monto_pago,
                medio=medio,
                descripcion=(
                    f"Pago a '{meta.nombre}' ({modalidad}). "
                    f"[Reserva: ${monto_reserva_usado:,.2f} | Liquidez/Emergencia: ${monto_liquidez_usado:,.2f}]"
                ),
                meta_id=meta_id,
                meta_nombre=meta.nombre,
            )
        )

        # Procesar las obligaciones financieras cubiertas por el pago
        if meta.tipo_meta in ["gasto_ciclico", "pago_cuotas"]:
            while True:
                exigencia_financiera = meta.valor_cuota_financiera(
                    meta.ciclos_pagados + 1
                )
                if exigencia_financiera > 0 and meta.pagado_ciclo_actual >= (
                    exigencia_financiera - 0.01
                ):
                    meta.renovar_ciclo()
                else:
                    break

        # 2. ¿La meta se terminó de pagar globalmente? La desactivamos.
        # (El gasto_ciclico infinito no pasa por acá)
        if meta.tipo_meta in [
            "ahorro_objetivo",
            "pago_cuotas",
        ] and meta.monto_historico_pagado >= (meta.monto_total - 0.01):
            meta.activa = False

    def revertir_transaccion(self, tx_id: str) -> None:
        tx_original = next((t for t in self.historial if t.id == tx_id), None)
        assert tx_original is not None, "Transacción no encontrada."
        assert not tx_original.es_revertida, "Ya fue revertida."
        assert tx_original.tipo != "REVERSION", "No se revierte una reversión."

        if tx_original.tipo == "INGRESO":
            if tx_original.medio == "fisico":
                self.saldo_fisico -= tx_original.monto
            else:
                self.saldo_digital -= tx_original.monto
        elif tx_original.tipo == "CUOTA_PRORRATEO":
            meta = self.metas_prorrateo.get(tx_original.meta_id or "")
            if meta:
                meta.acumulado_actual = max(
                    0.0, meta.acumulado_actual - tx_original.monto
                )
        elif tx_original.tipo == "GASTO_CORRIENTE":
            if tx_original.medio == "fisico":
                self.saldo_fisico += tx_original.monto
            else:
                self.saldo_digital += tx_original.monto
        elif tx_original.tipo == "PAGO_META":
            if tx_original.medio == "fisico":
                self.saldo_fisico += tx_original.monto
            else:
                self.saldo_digital += tx_original.monto
            meta = self.metas_prorrateo.get(tx_original.meta_id or "")
            if meta:
                # Delegamos la reversión exacta de ciclos y saldos al modelo
                meta.revertir_pago_externo(tx_original.monto)
        elif tx_original.tipo == "LIBERACION_RESERVA":
            meta = self.metas_prorrateo.get(tx_original.meta_id or "")
            if meta:
                meta.acumulado_actual += tx_original.monto
                meta.activa = True

        tx_original.es_revertida = True
        tx_rev = Transaccion(
            id=f"tx_{len(self.historial) + 1}",
            fecha=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            tipo="REVERSION",
            monto=tx_original.monto,
            medio=tx_original.medio,
            descripcion=f"Reversión de {tx_original.id}",
            meta_id=tx_original.meta_id,
            meta_nombre=tx_original.meta_nombre,
            tx_origen_id=tx_original.id,
        )
        self.historial.append(tx_rev)
