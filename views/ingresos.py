from collections.abc import Callable
from typing import cast

import streamlit as st

from engine import MotorFinanciero
from models import TipoMedio


def render(motor: MotorFinanciero, guardar_cb: Callable[[], None]) -> None:
    st.title("💵 Entrada de Dinero: Registrar Ingreso")

    monto_ingreso = st.number_input(
        "Monto total del ingreso ($):", min_value=0.01, step=1000.0
    )
    medio_str = st.selectbox("Medio de recepción:", ["digital", "fisico"])
    medio = cast(TipoMedio, medio_str)
    descripcion = st.text_input("Descripción / Origen del ingreso:")

    ahorro_sugerido = round(monto_ingreso * motor.pct_ahorro, 2)
    st.info(
        f"🔒 **Ahorro Intocable automático ({int(motor.pct_ahorro * 100)}%):** ${ahorro_sugerido:,.2f}"
    )

    metas_activas = [m for m in motor.metas_prorrateo.values() if m.activa]
    distribucion: dict[str, float] = {}
    modalidades: dict[str, bool] = {}

    if metas_activas:
        st.subheader("🎯 Asignación a Metas de Prorrateo")
        for meta in metas_activas:
            # Se calcula cuánto falta exclusivamente para cubrir este mes/ciclo
            faltante_ciclo = max(
                0.0, meta.monto_total - meta.acumulado_actual - meta.pagado_ciclo_actual
            )

            col_m, col_val, col_adelanto = st.columns([2, 2, 1])
            with col_m:
                st.write(f"**{meta.nombre}**")
                st.caption(
                    f"Cuota mensual: ${meta.cuota_fija:,.2f} | Faltante del ciclo: ${faltante_ciclo:,.2f}"
                )
            with col_val:
                monto_aporte = st.number_input(
                    f"Aporte ($) - {meta.nombre}",
                    min_value=0.0,
                    max_value=float(faltante_ciclo) if faltante_ciclo > 0 else 0.0,
                    value=float(min(meta.cuota_fija, faltante_ciclo)),
                    key=f"ingreso_meta_{meta.id}",
                )
                if monto_aporte > 0:
                    distribucion[meta.id] = monto_aporte
            with col_adelanto:
                es_adelanto = st.checkbox(
                    "Adelanto",
                    key=f"adelanto_meta_{meta.id}",
                    help="Marca si este valor abonado amortiza cuotas futuras",
                )
                if monto_aporte > 0:
                    modalidades[meta.id] = es_adelanto

    if st.button("Confirmar e Ingresar Dinero"):
        if not descripcion.strip():
            st.error("Por favor, ingrese una descripción para el registro.")
        else:
            motor.confirmar_ingreso(
                monto=monto_ingreso,
                medio=medio,
                descripcion=descripcion,
                monto_ahorro=ahorro_sugerido,
                distribucion_metas=distribucion,
                modalidades_aporte=modalidades,
            )
            guardar_cb()
            st.success("Ingreso registrado correctamente.")
            st.rerun()
