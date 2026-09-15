from collections.abc import Callable
from typing import cast

import streamlit as st

from engine import MotorFinanciero
from models import TipoMedio


def render(
    motor: MotorFinanciero, guardar_cb: Callable[[], None] = lambda: None
) -> None:
    st.title("🎯 Salida de Dinero: Pago a Proveedor")

    metas_activas = [m for m in motor.metas_prorrateo.values() if m.activa]
    if not metas_activas:
        st.info("No hay metas activas disponibles para saldar.")
        return

    meta_obj = st.selectbox(
        "Seleccionar compromiso / meta a saldar:",
        options=metas_activas,
        format_func=lambda m: (
            f"{m.nombre} | Tipo: {m.tipo_meta.replace('_', ' ').title()} | Reserva actual: ${m.acumulado_actual:,.2f}"
        ),
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("📦 Reserva en Caja", f"${meta_obj.acumulado_actual:,.2f}")
    col2.metric("💧 Liquidez Real Libre", f"${motor.liquidez_real:,.2f}")
    col3.metric("🎯 Monto Total / Cuota Base", f"${meta_obj.monto_total:,.2f}")

    # Definimos opciones según la naturaleza de la meta
    if meta_obj.tipo_meta == "ahorro_objetivo":
        modalidad_opcion = st.radio(
            "Modalidad de pago:",
            [
                "Romper caja de reserva y usar lo ahorrado",
                "Pagar 100% de mi bolsillo (mantener el ahorro intacto)",
            ],
        )
        modalidad_key = (
            "reserva_y_liquidez" if "Romper" in modalidad_opcion else "liquidez_pura"
        )
    else:
        # Para pago de cuotas o gastos cíclicos
        st.info(
            "💡 Este compromiso descuenta preferentemente el dinero reservado para este ciclo."
        )
        modalidad_key = "reserva_y_liquidez"

    monto_sugerido = (
        meta_obj.acumulado_actual
        if meta_obj.acumulado_actual > 0
        else meta_obj.monto_total
    )

    monto_pago = st.number_input(
        "Monto real a abonar al proveedor ($):",
        min_value=0.01,
        value=float(monto_sugerido),
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

    st.markdown("##### 📌 Desglose Estimado de la Salida")
    st.write(f"• Consumo de Reserva Acumulada: **${reserva_usada:,.2f}**")
    st.write(f"• Consumo de Liquidez / Bolsillo: **${liquidez_usada:,.2f}**")

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
