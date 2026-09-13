import streamlit as st

from engine import MotorFinanciero


def render(motor: MotorFinanciero) -> None:
    st.title("📊 Liquidez Real y Cajas de Reserva")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💧 Liquidez Real (Disponible)", f"${motor.liquidez_real:,.2f}")
    col2.metric("🏦 Total en Posesión", f"${motor.total_posesion:,.2f}")
    col3.metric("🔒 Ahorro Intocable (10%)", f"${motor.caja_ahorro_intocable:,.2f}")
    col4.metric("📦 Prorrateo Acumulado", f"${motor.total_prorrateo_acumulado:,.2f}")

    st.divider()

    col_f, col_d = st.columns(2)
    col_f.info(f"💵 **Saldo Físico (Efectivo):** ${motor.saldo_fisico:,.2f}")
    col_d.info(f"💳 **Saldo Digital (Bancos/App):** ${motor.saldo_digital:,.2f}")

    st.subheader("📋 Metas de Prorrateo Activas")
    metas_activas = [m for m in motor.metas_prorrateo.values() if m.activa]
    if metas_activas:
        tabla_metas = [
            {
                "Nombre": m.nombre,
                "Tipo": m.tipo_meta.capitalize(),
                "Monto Total": f"${m.monto_total:,.2f}",
                "Acumulado Guardado": f"${m.acumulado_actual:,.2f}",
                "Pendiente Por Guardar": f"${m.monto_restante:,.2f}",
                "Cuota Sugerida": f"${m.cuota_mensual_sugerida:,.2f}",
                "Fecha Límite": m.fecha_limite,
                "Estado": ("✅ Cubierto" if m.esta_cubierto_ciclo else "⏳ En Proceso"),
            }
            for m in metas_activas
        ]
        st.dataframe(tabla_metas, use_container_width=True)
    else:
        st.info("No hay metas de prorrateo activas.")

    st.subheader("📜 Historial de Transacciones")
    if motor.historial:
        st.dataframe(
            [t.__dict__ for t in reversed(motor.historial)],
            use_container_width=True,
        )
