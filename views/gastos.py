from collections.abc import Callable
from typing import cast

import streamlit as st

from engine import MotorFinanciero
from models import TipoMedio


def render(motor: MotorFinanciero, guardar_cb: Callable[[], None]) -> None:
    st.title("🛒 Registro de Gasto Corriente")

    col_liq, col_fis, col_dig = st.columns(3)
    col_liq.metric("💧 Liquidez Real Libre", f"${motor.liquidez_real:,.2f}")
    col_fis.metric("💵 Saldo Físico", f"${motor.saldo_fisico:,.2f}")
    col_dig.metric("💳 Saldo Digital", f"${motor.saldo_digital:,.2f}")

    monto = st.number_input("Monto del gasto ($):", min_value=0.01, step=100.0)
    medio_str = st.selectbox("Medio de pago:", ["digital", "fisico"])
    medio = cast(TipoMedio, medio_str)
    descripcion = st.text_input("Descripción del gasto:")

    if st.button("Registrar Gasto"):
        if not descripcion.strip():
            st.error("Por favor, ingrese una descripción para el gasto.")
        else:
            try:
                motor.registrar_gasto_corriente(
                    monto=monto, medio=medio, descripcion=descripcion
                )
                guardar_cb()
                st.success("Gasto registrado correctamente.")
                st.rerun()
            except AssertionError as e:
                st.error(str(e))
