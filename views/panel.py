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
            # Actualizado: Ahora lee "pendiente_periodo" del modelo
            pendiente = float(est.get("pendiente_periodo", 0.0))

            with st.container(border=True):
                col_info, col_acc = st.columns([3, 2])

                with col_info:
                    st.markdown(f"#### {meta.nombre}")
                    tipo_limpio = meta.tipo_meta.replace("_", " ").title()

                    # 1. Claridad temporal: Mostramos exactamente qué ciclo se está evaluando
                    st.caption(
                        f"**Tipo:** {tipo_limpio} | "
                        f"**Período evaluado:** {meta.inicio_ciclo_actual.strftime('%d/%m/%Y')} al {meta.fecha_vencimiento_actual.strftime('%d/%m/%Y')} | "
                        f"**Exigencia:** ${meta.cuota_fija:,.2f}"
                    )

                    # 2. Diferenciación de estados: Reservado vs Pagado
                    if estado_txt == "cubierto":
                        # Si hay plata en la reserva que cubre la cuota, está "Reservado"
                        if meta.acumulado_actual >= meta.cuota_fija:
                            st.success(
                                f"🟢 **Reserva Completa.** Ya separaste el dinero de este ciclo. "
                                f"Podés dejarlo guardado o pagarle al proveedor. (Caja retenida: **${meta.acumulado_actual:,.2f}**)"
                            )
                        # Si está cubierto pero la caja está vacía (o casi vacía), significa que ya pagaste y el calendario avanzó
                        else:
                            st.success(
                                f"🎉 **Pagado / Al día.** No debés nada por ahora. El próximo ciclo "
                                f"arranca el {meta.inicio_ciclo_actual.strftime('%d/%m/%Y')}. "
                                f"(Caja retenida: **${meta.acumulado_actual:,.2f}**)"
                            )
                    else:
                        st.warning(
                            f"🔴 **Falta separar dinero:** Faltan **${pendiente:,.2f}** para este período. "
                            f"(En caja: ${meta.acumulado_actual:,.2f})"
                        )

                with col_acc:
                    # 1. FORMULARIO DE RESERVA LIBRE (Valor sugerido dinámico por defecto)
                    monto_reserva = st.number_input(
                        "📥 Reservar Liquidez:",
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

                    # Aplanado: Usamos "and" en vez de if anidados
                    if btn_reservar and monto_reserva > 0:
                        try:
                            motor.aportar_a_reserva_interna(
                                meta.id,
                                monto_reserva,
                                f"Reserva del mes para {meta.nombre}",
                            )
                            guardar_cb()
                            st.success("¡Reserva apartada!")
                            st.rerun()
                        except AssertionError as e:
                            st.error(str(e))
                    elif btn_reservar and monto_reserva == 0:
                        st.info(
                            "Aporte de $0. No se movió dinero (mes saltado/ignorado)."
                        )

                    # 2. EXPANDER PARA PAGAR (Salida real hacia el proveedor)
                    with st.expander("💸 Pagar al Proveedor"):
                        sugerido_pago = (
                            meta.acumulado_actual
                            if meta.acumulado_actual > 0
                            else meta.cuota_fija
                        )

                        monto_pago = st.number_input(
                            "Monto a transferir:",
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
                                medio = cast(TipoMedio, medio_str)
                                motor.ejecutar_pago_meta(
                                    meta_id=meta.id,
                                    medio=medio,
                                    monto_pago=monto_pago,
                                    modalidad="reserva_y_liquidez",
                                )
                                guardar_cb()
                                st.success(
                                    f"Pago asentado. Ciclo de '{meta.nombre}' actualizado."
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
