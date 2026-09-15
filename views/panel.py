from collections.abc import Callable

import streamlit as st

from engine import MotorFinanciero


def render(
    motor: MotorFinanciero, guardar_cb: Callable[[], None] = lambda: None
) -> None:
    st.title("📊 Liquidez Real y Cajas de Reserva")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💧 Liquidez Real Libre", f"${motor.liquidez_real:,.2f}")
    col2.metric("🏦 Total en Posesión", f"${motor.total_posesion:,.2f}")
    col3.metric("🔒 Ahorro Intocable (10%)", f"${motor.caja_ahorro_intocable:,.2f}")
    col4.metric("📦 Prorrateo Acumulado", f"${motor.total_prorrateo_acumulado:,.2f}")

    st.divider()

    col_f, col_d = st.columns(2)
    # Mostramos saldo rojo si hay sobregiro/emergencia
    if motor.saldo_fisico < 0:
        col_f.error(
            f"💵 **Saldo Físico (Efectivo):** ${motor.saldo_fisico:,.2f} (SOBREGIRADO)"
        )
    else:
        col_f.info(f"💵 **Saldo Físico (Efectivo):** ${motor.saldo_fisico:,.2f}")

    if motor.saldo_digital < 0:
        col_d.error(
            f"💳 **Saldo Digital (Bancos/App):** ${motor.saldo_digital:,.2f} (SOBREGIRADO)"
        )
    else:
        col_d.info(f"💳 **Saldo Digital (Bancos/App):** ${motor.saldo_digital:,.2f}")

    st.divider()

    # --- NUEVA SECCIÓN: ASISTENTE SEMIAUTOMÁTICO ---
    st.subheader("🔔 Alertas y Deducciones del Mes")
    hay_alertas = False

    for meta in motor.metas_prorrateo.values():
        if meta.activa:
            estado = meta.estado_mensual
            pendiente = estado.get("pendiente_mes", 0.0)

            if pendiente > 0:
                hay_alertas = True
                col_texto, col_btn = st.columns([3, 1])
                with col_texto:
                    if meta.tipo_meta == "gasto_ciclico":
                        st.warning(
                            f"🔴 **{meta.nombre}**: Toca separar **${pendiente:,.2f}** para el ciclo actual."
                        )
                    else:
                        st.warning(
                            f"🔴 **{meta.nombre}**: Venís atrasado. Faltan **${pendiente:,.2f}** para ponerte al día."
                        )
                with col_btn:
                    if st.button(
                        f"Separar ${pendiente:,.2f}", key=f"btn_reserva_{meta.id}"
                    ):
                        try:
                            motor.aportar_a_reserva_interna(
                                meta.id,
                                pendiente,
                                "Reserva automática sugerida del mes",
                            )
                            guardar_cb()
                            st.success(f"¡Reserva apartada para {meta.nombre}!")
                            st.rerun()
                        except AssertionError as e:
                            st.error(str(e))

    if not hay_alertas:
        st.success(
            "🟢 ¡Todo al día! No tenés cuotas ni reservas atrasadas para separar hoy."
        )

    st.divider()

    # --- TABLA CON SEMÁFORO DE SALUD ---
    st.subheader("📋 Estado de Metas y Compromisos")
    metas_activas = [m for m in motor.metas_prorrateo.values() if m.activa]
    if metas_activas:
        tabla_metas = []
        for m in metas_activas:
            est_data = m.estado_mensual
            if est_data["estado"] == "al_dia":
                semaforo = "🟢 Al día"
            elif est_data["estado"] == "atrasado":
                semaforo = "🔴 Atrasado"
            else:
                semaforo = "🔵 Adelantado"

            tabla_metas.append(
                {
                    "Nombre": m.nombre,
                    "Tipo": m.tipo_meta.replace("_", " ").title(),
                    "Total / Cuota Base": f"${m.monto_total:,.2f} / ${m.cuota_fija:,.2f}",
                    "Acumulado en Caja": f"${m.acumulado_actual:,.2f}",
                    "Fecha Límite": m.fecha_limite,
                    "Salud": semaforo,
                }
            )
        st.dataframe(tabla_metas, use_container_width=True)
    else:
        st.info("No hay metas configuradas.")

    st.subheader("📜 Historial de Transacciones y Reversión")
    if motor.historial:
        st.dataframe(
            [t.__dict__ for t in reversed(motor.historial)],
            use_container_width=True,
        )

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
