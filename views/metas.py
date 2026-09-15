from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import cast

import streamlit as st

from engine import MotorFinanciero
from models import MetaProrrateo, TipoMeta

TIPO_META_OPCIONES = {
    "🎯 Ahorro Objetivo (Ej: Viaje, Compra al contado)": "ahorro_objetivo",
    "💳 Pago en Cuotas (Ej: Heladera en cuotas fijas)": "pago_cuotas",
    "🔄 Gasto Cíclico / Suscripción (Ej: Seguro, Netflix)": "gasto_ciclico",
}


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
            "Monto Total a alcanzar o Cuota Base ($):",
            min_value=1.0,
            step=1000.0,
            key="c_monto",
        )
        fecha_limite = st.date_input(
            "Fecha límite (o de próximo vencimiento):", value=hoy, key="c_fecha"
        )

        tipo_key = st.selectbox(
            "Naturaleza financiera del compromiso:",
            list(TIPO_META_OPCIONES.keys()),
            key="c_tipo",
        )
        tipo = cast(TipoMeta, TIPO_META_OPCIONES[tipo_key])

        intervalo = st.number_input(
            "Frecuencia del ciclo (en meses):",
            min_value=1,
            max_value=60,
            value=1,
            help="1 = Mensual, 2 = Bimestral, 12 = Anual",
            key="c_int",
        )

        if st.button("Guardar Meta", key="btn_c"):
            if fecha_limite <= hoy:
                st.error("La fecha debe ser posterior al día de hoy.")
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
                "Seleccionar meta a editar (Se muestran todas, incluso inactivas):",
                metas,
                format_func=lambda m: f"{m.nombre} (${m.monto_total:,.2f})",
                key="e_sel",
            )
            nuevo_nombre = st.text_input("Nombre:", value=sel.nombre, key="e_nom")
            nuevo_monto = st.number_input(
                "Monto total o Cuota Base ($):",
                min_value=1.0,
                value=float(sel.monto_total),
                key="e_mon",
            )
            dt_limite = date.fromisoformat(sel.fecha_limite)
            nueva_fecha = st.date_input(
                "Fecha límite (o próximo vencimiento):", value=dt_limite, key="e_fec"
            )

            tipo_actual_label = next(
                (k for k, v in TIPO_META_OPCIONES.items() if v == sel.tipo_meta),
                next(iter(TIPO_META_OPCIONES.keys())),
            )
            idx_tipo = list(TIPO_META_OPCIONES.keys()).index(tipo_actual_label)

            nuevo_tipo_key = st.selectbox(
                "Naturaleza financiera:",
                list(TIPO_META_OPCIONES.keys()),
                index=idx_tipo,
                key="e_tipo",
            )
            nuevo_tipo = cast(TipoMeta, TIPO_META_OPCIONES[nuevo_tipo_key])

            nuevo_intervalo = st.number_input(
                "Frecuencia del ciclo (en meses):",
                min_value=1,
                max_value=60,
                value=sel.intervalo_meses_recurrencia,
                key="e_int",
            )

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
                        nuevo_tipo,
                        int(nuevo_intervalo),
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
                "Seleccionar meta a cancelar/eliminar:",
                metas,
                format_func=lambda m: (
                    f"{m.nombre} — Reserva actual retenida este mes: ${m.acumulado_actual:,.2f}"
                ),
                key="d_sel",
            )
            st.warning(
                f"Al eliminar '{sel_del.nombre}', los **${sel_del.acumulado_actual:,.2f}** "
                "que habías separado y retenido para este ciclo en particular se cancelarán y volverán "
                "inmediatamente a tu saldo libre (Liquidez Real)."
            )
            if st.button("🔴 Cancelar Meta y Liberar Reserva", key="btn_d"):
                monto_devuelto = motor.eliminar_meta(sel_del.id)
                guardar_cb()
                st.success(
                    f"Meta eliminada. Se reintegraron ${monto_devuelto:,.2f} a tu Liquidez Libre."
                )
                st.rerun()
        else:
            st.info("No hay metas para eliminar.")
