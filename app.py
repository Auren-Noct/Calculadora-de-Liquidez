from typing import Literal, cast

import streamlit as st

from engine import MotorFinanciero
from models import MetaProrrateo
from repository import RepositorioLocal

TipoCiclo = Literal["cerrado_mensual", "abierto_anual", "temporal"]
TipoMedio = Literal["fisico", "digital"]

# Configuración inicial de la pantalla
st.set_page_config(
    page_title="Control Financiero - Liquidez y Prorrateo", layout="wide"
)

# Inicialización del sistema y carga del JSON local
repo = RepositorioLocal("datos.json")
if "motor" not in st.session_state:
    st.session_state.motor = repo.cargar()

motor: MotorFinanciero = st.session_state.motor


def guardar_cambios():
    repo.guardar(motor)


# --- NAVEGACIÓN LATERAL ---
st.sidebar.title("⚙️ Operaciones")
opcion = st.sidebar.radio(
    "Seleccioná una acción:",
    [
        "📊 Panel Principal",
        "💵 Registrar Ingreso",
        "🛒 Registrar Gasto Diario",
        "🎯 Pagar Meta Prorrateada",
        "➕ Crear Nueva Meta",
    ],
)

# --- VISTA 1: PANEL PRINCIPAL (MÉTRICAS) ---
if opcion == "📊 Panel Principal":
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
    if motor.metas_prorrateo:
        tabla_metas = []
        for m in motor.metas_prorrateo.values():
            if m.activa:
                tabla_metas.append(
                    {
                        "Nombre": m.nombre,
                        "Tipo Ciclo": m.tipo_ciclo,
                        "Monto Total": f"${m.monto_total:,.2f}",
                        "Acumulado": f"${m.acumulado_actual:,.2f}",
                        "Pendiente": f"${m.monto_restante:,.2f}",
                        "Cuota Sugerida": f"${m.cuota_mensual_sugerida:,.2f}",
                        "Estado": (
                            "✅ Cubierto" if m.esta_cubierto_ciclo else "⏳ Pendiente"
                        ),
                    }
                )
        st.dataframe(tabla_metas, use_container_width=True)
    else:
        st.write("No hay metas de prorrateo creadas.")

    st.subheader("📜 Historial de Transacciones")
    if motor.historial:
        st.dataframe(
            [t.__dict__ for t in reversed(motor.historial)],
            use_container_width=True,
        )

# --- VISTA 2: REGISTRAR INGRESO CON PROPUESTA DE PRORRATEO ---
elif opcion == "💵 Registrar Ingreso":
    st.title("💵 Registrar Nuevo Ingreso")

    monto = st.number_input("Monto del ingreso ($):", min_value=0.0, step=1000.0)
    medio_str = st.selectbox("Medio de recepción:", ["digital", "fisico"])
    medio = cast(TipoMedio, medio_str)
    descripcion = st.text_input("Descripción / Concepto:", value="Ingreso de dinero")

    if monto > 0:
        ahorro_sugerido, distribucion_metas = motor.calcular_propuesta_ingreso(monto)
        st.subheader("💡 Propuesta de Distribución Activa")
        st.write(f"• **Ahorro Intocable (10%):** ${ahorro_sugerido:,.2f}")

        st.write("• **Asignación a Prorrateos:**")
        distribucion_confirmada = {}
        for m_id, cuota in distribucion_metas.items():
            meta = motor.metas_prorrateo[m_id]
            val = st.number_input(
                f"Cuota para '{meta.nombre}' (Sugerido: ${cuota:,.2f}):",
                min_value=0.0,
                max_value=float(meta.monto_restante),
                value=float(cuota),
                key=m_id,
            )
            distribucion_confirmada[m_id] = val

        if st.button("Confirmar e Ingresar Dinero"):
            motor.confirmar_ingreso(
                monto,
                medio,
                descripcion,
                ahorro_sugerido,
                distribucion_confirmada,
            )
            guardar_cambios()
            st.success("¡Ingreso asentado y cajas reservadas correctamente!")
            st.rerun()

# --- VISTA 3: REGISTRAR GASTO CORRIENTE ---
elif opcion == "🛒 Registrar Gasto Diario":
    st.title("🛒 Registrar Gasto Diario")

    st.warning(
        f"Liquidez Real disponible para gastar hoy: **${motor.liquidez_real:,.2f}**"
    )
    monto_gasto = st.number_input("Monto a gastar ($):", min_value=0.0, step=100.0)
    medio_gasto_str = st.selectbox("Medio de pago:", ["digital", "fisico"])
    medio_gasto = cast(TipoMedio, medio_gasto_str)
    desc_gasto = st.text_input("Concepto del gasto:", value="Compra diaria")

    if st.button("Registrar Gasto"):
        try:
            motor.registrar_gasto_corriente(monto_gasto, medio_gasto, desc_gasto)
            guardar_cambios()
            st.success("Gasto asentado correctamente.")
            st.rerun()
        except AssertionError as e:
            st.error(str(e))

# --- VISTA 4: PAGAR META PRORRATEADA ---
elif opcion == "🎯 Pagar Meta Prorrateada":
    st.title("🎯 Saldar / Pagar Meta Prorrateada")

    metas_activas = {k: v.nombre for k, v in motor.metas_prorrateo.items() if v.activa}
    if metas_activas:
        meta_sel_id = st.selectbox(
            "Seleccionar meta a pagar:",
            list(metas_activas.keys()),
            format_func=lambda x: metas_activas[x],
        )
        meta_obj = motor.metas_prorrateo[meta_sel_id]

        st.info(
            f"Monto total a saldar: **${meta_obj.monto_total:,.2f}** (Acumulado en caja: ${meta_obj.acumulado_actual:,.2f})"
        )
        medio_pago_str = st.selectbox(
            "Medio desde el que se realiza el pago real:", ["digital", "fisico"]
        )
        medio_pago = cast(TipoMedio, medio_pago_str)

        if st.button("Efectuar Pago"):
            try:
                motor.ejecutar_pago_meta(meta_sel_id, medio_pago)
                guardar_cambios()
                st.success(f"¡Se registró el pago de {meta_obj.nombre}!")
                st.rerun()
            except AssertionError as e:
                st.error(str(e))
    else:
        st.write("No hay metas activas disponibles para pagar.")

# --- VISTA 5: CREAR NUEVA META ---
elif opcion == "➕ Crear Nueva Meta":
    st.title("➕ Alta de Meta de Prorrateo")

    nombre_meta = st.text_input("Nombre de la meta / gasto futuro:")
    monto_meta = st.number_input(
        "Monto total estimado ($):", min_value=1.0, step=1000.0
    )
    meses_meta = st.number_input("Plazo en meses:", min_value=1, value=12)

    tipo_meta_str = st.selectbox(
        "Tipo de ciclo:",
        ["abierto_anual", "cerrado_mensual", "temporal"],
    )
    tipo_meta = cast(TipoCiclo, tipo_meta_str)

    if st.button("Guardar Meta") and nombre_meta:
        nueva_id = f"meta_{len(motor.metas_prorrateo) + 1}"
        nueva_meta = MetaProrrateo(
            id=nueva_id,
            nombre=nombre_meta,
            monto_total=monto_meta,
            meses_plazo=meses_meta,
            tipo_ciclo=tipo_meta,
        )
        motor.agregar_meta(nueva_meta)
        guardar_cambios()
        st.success(f"Meta '{nombre_meta}' agregada con éxito.")
        st.rerun()
