from collections.abc import Callable
from typing import cast

import streamlit as st

from engine import MotorFinanciero
from models import TipoMedio


def render(
    motor: MotorFinanciero, guardar_cb: Callable[[], None] = lambda: None
) -> None:
    st.title("📊 Panel de Control y Cajas de Reserva")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💧 Liquidez Libre", f"${motor.liquidez_real:,.2f}")
    col2.metric("🏦 Posesión Total", f"${motor.total_posesion:,.2f}")
    col3.metric("🔒 Ahorro (10%)", f"${motor.caja_ahorro_intocable:,.2f}")
    col4.metric("📦 En Reservas", f"${motor.total_prorrateo_acumulado:,.2f}")

    st.divider()

    # Mostramos saldo rojo si hay sobregiro/emergencia
    col_f, col_d = st.columns(2)
    if motor.saldo_fisico < 0:
        col_f.error(f"💵 **Saldo Físico:** ${motor.saldo_fisico:,.2f} (SOBREGIRADO)")
    else:
        col_f.info(f"💵 **Saldo Físico:** ${motor.saldo_fisico:,.2f}")

    if motor.saldo_digital < 0:
        col_d.error(f"💳 **Saldo Digital:** ${motor.saldo_digital:,.2f} (SOBREGIRADO)")
    else:
        col_d.info(f"💳 **Saldo Digital:** ${motor.saldo_digital:,.2f}")

    st.divider()

    # --- NUEVA SECCIÓN: TARJETAS DE ACCIÓN DIRECTA ---
    st.subheader("📋 Estado de Metas y Compromisos")
    metas_activas = [m for m in motor.metas_prorrateo.values() if m.activa]

    if not metas_activas:
        st.success("🟢 No tenés compromisos activos. ¡Todo el dinero libre es tuyo!")
    else:
        for meta in metas_activas:
            est = meta.estado_periodo
            estado_txt = est.get("estado", "")
            # 1. Leemos el déficit real del nuevo contrato
            deficit = float(est.get("deficit_exigible", 0.0))

            with st.container(border=True):
                col_info, col_acc = st.columns([3, 2])

                with col_info:
                    st.markdown(f"#### {meta.nombre}")
                    tipo_limpio = meta.tipo_meta.replace("_", " ").title()

                    # 2. Claridad temporal según la naturaleza de la meta
                    if meta.tipo_meta == "ahorro_objetivo":
                        st.caption(
                            f"**Tipo:** {tipo_limpio} | "
                            f"**Progreso evaluado:** {meta.dt_inicio.strftime('%d/%m/%Y')} al {meta.dt_limite.strftime('%d/%m/%Y')} | "
                            f"**Objetivo Final:** ${meta.monto_total:,.2f}"
                        )
                    else:
                        st.caption(
                            f"**Tipo:** {tipo_limpio} | "
                            f"**Ventana actual:** {meta.inicio_ciclo_actual.strftime('%d/%m/%Y')} al {meta.fecha_vencimiento_actual.strftime('%d/%m/%Y')} | "
                            f"**Exigencia de ventana:** ${meta.cuota_fija:,.2f}"
                        )

                    # 3. Estados desacoplados del calendario
                    if estado_txt == "cubierto":
                        if meta.tipo_meta == "ahorro_objetivo":
                            st.success(
                                f"🟢 **Ahorro al Día.** Tu progreso supera el tiempo transcurrido. (Caja: **${meta.acumulado_actual:,.2f}**)"
                            )
                        elif meta.acumulado_actual >= meta.cuota_fija:
                            st.success(
                                f"🟢 **Reserva Completa.** Separaste el dinero de esta ventana. (Caja: **${meta.acumulado_actual:,.2f}**)"
                            )
                        else:
                            st.success(
                                f"🎉 **Pagado / Al día.** Obligación temporal cubierta. (Caja: **${meta.acumulado_actual:,.2f}**)"
                            )
                    else:
                        st.warning(
                            f"🔴 **Déficit actual:** Faltan **${deficit:,.2f}**. (Caja: ${meta.acumulado_actual:,.2f})"
                        )

                with col_acc:
                    # 4. Formulario de reserva con condicionales planos (and)
                    monto_reserva = st.number_input(
                        "📥 Ritmo sugerido a reservar:",
                        min_value=0.0,
                        value=float(meta.cuota_sugerida),
                        step=500.0,
                        key=f"res_in_{meta.id}",
                    )

                    btn_reservar = st.button(
                        "Confirmar Aporte",
                        key=f"res_btn_{meta.id}",
                        use_container_width=True,
                    )

                    if btn_reservar and monto_reserva > 0:
                        try:
                            motor.aportar_a_reserva_interna(
                                meta.id, monto_reserva, f"Reserva para {meta.nombre}"
                            )
                            guardar_cb()
                            st.success("¡Reserva apartada!")
                            st.rerun()
                        except AssertionError as e:
                            st.error(str(e))
                    elif btn_reservar and monto_reserva == 0:
                        st.info("Aporte de $0. No se movió dinero.")

                    # 5. Formulario de pago/retiro
                    label_expander = (
                        "💸 Retirar Fondos"
                        if meta.tipo_meta == "ahorro_objetivo"
                        else "💸 Pagar al Proveedor"
                    )
                    with st.expander(label_expander):
                        if meta.tipo_meta == "ahorro_objetivo":
                            sugerido_pago = (
                                meta.acumulado_actual
                                if meta.acumulado_actual > 0
                                else 0.01
                            )
                        else:
                            sugerido_pago = (
                                meta.acumulado_actual
                                if meta.acumulado_actual > 0
                                else meta.cuota_fija
                            )

                        monto_pago = st.number_input(
                            "Monto de salida:",
                            min_value=0.01,
                            value=float(sugerido_pago),
                            step=500.0,
                            key=f"mon_{meta.id}",
                        )
                        medio_str = st.selectbox(
                            "Medio de salida real:",
                            ["digital", "fisico"],
                            key=f"med_{meta.id}",
                        )

                        if st.button(
                            "Confirmar Salida", key=f"pag_{meta.id}", type="primary"
                        ):
                            try:
                                motor.ejecutar_pago_meta(
                                    meta_id=meta.id,
                                    medio=cast(TipoMedio, medio_str),
                                    monto_pago=monto_pago,
                                    modalidad="reserva_y_liquidez",
                                )
                                guardar_cb()
                                st.success(
                                    f"Salida asentada. '{meta.nombre}' actualizado."
                                )
                                st.rerun()
                            except AssertionError as e:
                                st.error(str(e))

    st.divider()

    # --- HISTORIAL Y REVERSIÓN ---
    st.subheader("📜 Historial de Transacciones y Reversión")
    if motor.historial:
        # Se elimina el use_container_width problemático
        st.dataframe([t.__dict__ for t in reversed(motor.historial)])

        st.markdown("#### ↩️ Deshacer Operación")
        txs_revertibles = [
            t
            for t in reversed(motor.historial)
            if not t.es_revertida and t.tipo != "REVERSION"
        ]

        if txs_revertibles:
            col_sel, col_btn = st.columns([3, 1])
            with col_sel:
                tx_sel = st.selectbox(
                    "Seleccioná la transacción a deshacer:",
                    options=txs_revertibles,
                    format_func=lambda t: f"{t.fecha} | {t.tipo} | ${t.monto:,.2f} | {t.descripcion}",
                )
            with col_btn:
                st.write("")
                st.write("")
                if st.button("🔴 Revertir Transacción") and tx_sel:
                    try:
                        motor.revertir_transaccion(tx_sel.id)
                        guardar_cb()
                        st.success(
                            f"Transacción '{tx_sel.id}' deshecha. Dinero y estados devueltos."
                        )
                        st.rerun()
                    except AssertionError as e:
                        st.error(str(e))
        else:
            st.info("No hay transacciones que se puedan revertir actualmente.")
    else:
        st.info("Aún no hay movimientos en el historial.")
