from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import cast

import streamlit as st

from engine import MotorFinanciero
from models import MetaProrrateo, TipoMeta


def render(motor: MotorFinanciero, guardar_cb: Callable[[], None]) -> None:
    st.title("⚙️ Gestión de Metas de Prorrateo")

    tab1, tab2, tab3 = st.tabs(
        ["➕ Crear Meta", "✏️ Modificar Meta", "🗑️ Dar de Baja Meta"]
    )
    hoy = datetime.now(timezone.utc).date()

    with tab1:
        st.subheader("Alta de Nueva Meta")
        nombre = st.text_input("Nombre de la meta:", key="c_nom")
        monto = st.number_input(
            "Monto total ($):", min_value=1.0, step=1000.0, key="c_monto"
        )
        fecha_limite = st.date_input("Fecha límite:", value=hoy, key="c_fecha")
        tipo_str = st.selectbox(
            "Tipo de meta:", ["puntual", "recurrente"], key="c_tipo"
        )
        tipo = cast(TipoMeta, tipo_str)
        intervalo = st.number_input(
            "Frecuencia (meses):",
            min_value=1,
            max_value=60,
            value=12,
            key="c_int",
        )

        if st.button("Guardar Meta", key="btn_c"):
            if fecha_limite <= hoy:
                st.error("La fecha límite debe ser posterior al día de hoy.")
            elif not nombre.strip():
                st.error("El nombre de la meta no puede estar vacío.")
            else:
                meta_id = f"meta_{len(motor.metas_prorrateo) + 1}"
                nueva_meta = MetaProrrateo(
                    id=meta_id,
                    nombre=nombre.strip(),
                    monto_total=monto,
                    fecha_limite=fecha_limite.strftime("%Y-%m-%d"),
                    tipo_meta=tipo,
                    intervalo_meses_recurrencia=int(intervalo),
                )
                motor.agregar_meta(nueva_meta)
                guardar_cb()
                st.success(f"Meta '{nombre.strip()}' agregada con éxito.")
                st.rerun()

    with tab2:
        metas = list(motor.metas_prorrateo.values())
        if metas:
            sel = st.selectbox(
                "Seleccionar meta a editar:",
                metas,
                format_func=lambda m: f"{m.nombre} (${m.monto_total:,.2f})",
                key="e_sel",
            )
            nuevo_nombre = st.text_input("Nombre:", value=sel.nombre, key="e_nom")
            nuevo_monto = st.number_input(
                "Monto total ($):",
                min_value=1.0,
                value=float(sel.monto_total),
                key="e_mon",
            )
            dt_limite = date.fromisoformat(sel.fecha_limite)
            nueva_fecha = st.date_input("Fecha límite:", value=dt_limite, key="e_fec")

            if st.button("Guardar Cambios", key="btn_e"):
                if nueva_fecha <= hoy:
                    st.error("La fecha límite debe ser posterior al día de hoy.")
                elif not nuevo_nombre.strip():
                    st.error("El nombre de la meta no puede estar vacío.")
                else:
                    motor.modificar_meta(
                        sel.id,
                        nuevo_nombre.strip(),
                        nuevo_monto,
                        nueva_fecha.strftime("%Y-%m-%d"),
                        sel.tipo_meta,
                        sel.intervalo_meses_recurrencia,
                    )
                    guardar_cb()
                    st.success("Meta actualizada correctamente.")
                    st.rerun()
        else:
            st.info("No hay metas para modificar.")

    with tab3:
        metas = list(motor.metas_prorrateo.values())
        if metas:
            sel_del = st.selectbox(
                "Seleccionar meta a eliminar:",
                metas,
                format_func=lambda m: (
                    f"{m.nombre} — Reserva actual: ${m.acumulado_actual:,.2f}"
                ),
                key="d_sel",
            )
            st.warning(
                f"Al eliminar '{sel_del.nombre}', los **${sel_del.acumulado_actual:,.2f}** "
                "de su caja de reserva se liberarán e ingresarán inmediatamente a tu Liquidez Real."
            )
            if st.button("🔴 Eliminar Meta y Devolver Dinero", key="btn_d"):
                monto_devuelto = motor.eliminar_meta(sel_del.id)
                guardar_cb()
                st.success(
                    f"Meta eliminada. Se reintegraron ${monto_devuelto:,.2f} a la Liquidez Real."
                )
                st.rerun()
        else:
            st.info("No hay metas para eliminar.")
