from collections.abc import Callable
from typing import cast

import streamlit as st

from engine import MotorFinanciero
from models import TipoMedio


def render(motor: MotorFinanciero, guardar_cb: Callable[[], None]) -> None:
    st.title("🎯 Salida de Dinero: Pago a Proveedor")

    metas_activas = [m for m in motor.metas_prorrateo.values() if m.activa]
    if not metas_activas:
        st.info("No hay metas activas disponibles para saldar.")
        return

    meta_obj = st.selectbox(
        "Seleccionar meta a saldar:",
        options=metas_activas,
        format_func=lambda m: (
            f"{m.nombre} | Reserva: ${m.acumulado_actual:,.2f} | Total: ${m.monto_total:,.2f}"
        ),
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("📦 Acumulado en Reserva", f"${meta_obj.acumulado_actual:,.2f}")
    col2.metric("💧 Liquidez Real Libre", f"${motor.liquidez_real:,.2f}")
    col3.metric("🎯 Monto Objetivo Meta", f"${meta_obj.monto_total:,.2f}")

    modalidad_opcion = st.radio(
        "Modalidad de débito:",
        [
            "Usar Reserva Acumulada (Diferencia desde Liquidez Real si falta)",
            "Amortización Extraordinaria (Usar 100% Liquidez Real)",
        ],
    )
    modalidad_key = (
        "reserva_y_liquidez" if "Reserva" in modalidad_opcion else "liquidez_pura"
    )

    monto_pago = st.number_input(
        "Monto a pagar al proveedor ($):",
        min_value=0.01,
        value=float(
            meta_obj.acumulado_actual
            if meta_obj.acumulado_actual > 0
            else meta_obj.monto_total
        ),
        step=500.0,
    )

    medio_pago_str = st.selectbox("Medio real de salida:", ["digital", "fisico"])
    medio_pago = cast(TipoMedio, medio_pago_str)

    reserva_usada = (
        min(meta_obj.acumulado_actual, monto_pago)
        if modalidad_key == "reserva_y_liquidez"
        else 0.0
    )
    liquidez_usada = max(0.0, monto_pago - reserva_usada)

    st.markdown("##### 📌 Desglose de la Salida de Fondos")
    st.write(f"• Consumo de Reserva Guardada: **${reserva_usada:,.2f}**")
    st.write(f"• Consumo de Liquidez Libre: **${liquidez_usada:,.2f}**")

    if st.button("Efectuar Pago"):
        try:
            motor.ejecutar_pago_meta(
                meta_id=meta_obj.id,
                medio=medio_pago,
                monto_pago=monto_pago,
                modalidad=modalidad_key,
            )
            guardar_cb()
            st.success(f"Pago registrado correctamente para '{meta_obj.nombre}'.")
            st.rerun()
        except AssertionError as e:
            st.error(str(e))
