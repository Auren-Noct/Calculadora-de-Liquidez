from datetime import datetime, timedelta, timezone
from typing import cast

import streamlit as st

from engine import MotorFinanciero
from models import MetaProrrateo, TipoMedio, TipoMeta
from repository import RepositorioLocal

st.set_page_config(
    page_title="Control Financiero - Liquidez y Prorrateo", layout="wide"
)

repo = RepositorioLocal("datos.json")
if "motor" not in st.session_state:
    st.session_state.motor = repo.cargar()

motor: MotorFinanciero = st.session_state.motor


def guardar_cambios() -> None:
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

with st.sidebar.expander("❓ ¿Cómo funciona la lógica de dinero?"):
    st.markdown("""
    - **Total en Posesión:** El dinero total real en tu mano o cuentas.
    - **Ahorro Intocable:** Fondo reservado (10%) que no debe tocarse bajo ningún concepto.
    - **Prorrateos:** Fondos que *ya están prometidos* a compromisos futuros.
    - **Liquidez Real:** Tu saldo **libre verdadero** para gastar en el día a día sin comprometer el futuro.
    """)

# --- VISTA 1: PANEL PRINCIPAL ---
if opcion == "📊 Panel Principal":
    st.title("📊 Liquidez Real y Cajas de Reserva")
    st.caption(
        "Monitoreo en tiempo real de tu disponible operativo y las reservas asignadas."
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "💧 Liquidez Real",
        f"${motor.liquidez_real:,.2f}",
        help="Dinero totalmente disponible para gastos diarios sin afectar metas ni ahorros.",
    )
    col2.metric(
        "🏦 Total en Posesión",
        f"${motor.total_posesion:,.2f}",
        help="Suma total de tu saldo disponible físico y digital.",
    )
    col3.metric(
        "🔒 Ahorro Intocable",
        f"${motor.caja_ahorro_intocable:,.2f}",
        help="Caja reservada automáticamente por tus porcentajes de ahorro.",
    )
    col4.metric(
        "📦 Prorrateo Acumulado",
        f"${motor.total_prorrateo_acumulado:,.2f}",
        help="Dinero acumulado destinado a pagos futuros o recurrentes.",
    )

    st.divider()

    col_f, col_d = st.columns(2)
    col_f.info(f"💵 **Saldo Físico (Billetera):** ${motor.saldo_fisico:,.2f}")
    col_d.info(f"💳 **Saldo Digital (Bancos / Apps):** ${motor.saldo_digital:,.2f}")

    st.subheader("📋 Metas de Prorrateo Activas")
    st.caption("Estado actual de tus reservas para compromisos periódicos o puntuales.")

    if motor.metas_prorrateo:
        tabla_metas = []
        for m in motor.metas_prorrateo.values():
            if m.activa:
                tabla_metas.append(
                    {
                        "Nombre": m.nombre,
                        "Tipo": (
                            "🔄 Recurrente"
                            if m.tipo_meta == "recurrente"
                            else "📌 Puntual"
                        ),
                        "Fecha Límite": m.fecha_limite,
                        "Meses Faltantes": m.meses_restantes,
                        "Monto Total": f"${m.monto_total:,.2f}",
                        "Acumulado": f"${m.acumulado_actual:,.2f}",
                        "Pendiente": f"${m.monto_restante:,.2f}",
                        "Cuota Sugerida/Mes": f"${m.cuota_mensual_sugerida:,.2f}",
                        "Estado": (
                            "✅ Cubierto"
                            if m.esta_cubierto_ciclo
                            else "⏳ En acumulación"
                        ),
                    }
                )
        st.dataframe(tabla_metas, use_container_width=True)
    else:
        st.write("No tenés metas de prorrateo creadas.")

    st.subheader("📜 Historial de Transacciones")
    if motor.historial:
        st.dataframe(
            [t.__dict__ for t in reversed(motor.historial)],
            use_container_width=True,
        )

# --- VISTA 2: REGISTRAR INGRESO CON PROPUESTA ---
elif opcion == "💵 Registrar Ingreso":
    st.title("💵 Registrar Nuevo Ingreso")
    st.caption(
        "Cada vez que entra dinero, el sistema calcula qué porcentaje separar para ahorro y qué cuotas reservar para tus prorrateos."
    )

    monto = st.number_input("Monto del ingreso ($):", min_value=0.0, step=1000.0)
    medio_str = st.selectbox("Medio de recepción:", ["digital", "fisico"])
    medio = cast(TipoMedio, medio_str)
    descripcion = st.text_input(
        "Descripción / Concepto:", value="Cobro o ingreso de dinero"
    )

    if monto > 0:
        ahorro_sugerido, distribucion_metas = motor.calcular_propuesta_ingreso(monto)

        st.info("""
        💡 **¿Qué sucede al confirmar?**
        1. El monto total se suma a tu saldo total (Físico o Digital).
        2. Se apartan los fondos sugeridos a la caja de ahorro intocable.
        3. Se asignan las cuotas a las metas. Esto reduce tu **Liquidez Real**, impidiendo que gastes por accidente dinero destinado a pagos futuros.
        """)

        st.subheader("💡 Propuesta de Distribución Sugerida")
        st.write(f"• **Ahorro Intocable (10% sugerido):** ${ahorro_sugerido:,.2f}")

        st.write("• **Cuotas calculadas según meses restantes:**")
        distribucion_confirmada: dict[str, float] = {}
        for m_id, cuota in distribucion_metas.items():
            meta = motor.metas_prorrateo[m_id]
            val = st.number_input(
                f"Reserva para '{meta.nombre}' (Sugerido mensual: ${meta.cuota_mensual_sugerida:,.2f} | Falta saldar: ${meta.monto_restante:,.2f}):",
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
            st.success(
                "¡Ingreso asentado! Las reservas fueron descontadas de tu Liquidez Real de forma segura."
            )
            st.rerun()

# --- VISTA 3: REGISTRAR GASTO CORRIENTE ---
elif opcion == "🛒 Registrar Gasto Diario":
    st.title("🛒 Registrar Gasto Diario")
    st.caption(
        "Usá este apartado únicamente para compras de consumo diario (comida, transporte, ocio)."
    )

    st.warning(
        f"Tu Liquidez Real disponible para gastar sin comprometer metas es: **${motor.liquidez_real:,.2f}**"
    )

    monto_gasto = st.number_input("Monto a gastar ($):", min_value=0.0, step=100.0)
    medio_gasto_str = st.selectbox("Medio de pago:", ["digital", "fisico"])
    medio_gasto = cast(TipoMedio, medio_gasto_str)
    desc_gasto = st.text_input("Concepto del gasto:", value="Gasto corriente diario")

    if st.button("Registrar Gasto"):
        try:
            motor.registrar_gasto_corriente(monto_gasto, medio_gasto, desc_gasto)
            guardar_cambios()
            st.success("Gasto registrado exitosamente.")
            st.rerun()
        except AssertionError as e:
            st.error(str(e))

# --- VISTA 4: PAGAR META PRORRATEADA ---
elif opcion == "🎯 Pagar Meta Prorrateada":
    st.title("🎯 Saldar / Pagar Meta Prorrateada")
    st.caption(
        "Efectuá el pago final de una meta acumulada cuando vence o llega el momento de realizar el consumo."
    )

    metas_activas = {k: v.nombre for k, v in motor.metas_prorrateo.items() if v.activa}
    if metas_activas:
        meta_sel_id = st.selectbox(
            "Seleccioná la meta a saldar:",
            list(metas_activas.keys()),
            format_func=lambda x: metas_activas[x],
        )
        meta_obj = motor.metas_prorrateo[meta_sel_id]

        st.info(
            f"Monto total del compromiso: **${meta_obj.monto_total:,.2f}** | Acumulado reservado: **${meta_obj.acumulado_actual:,.2f}**"
        )
        if meta_obj.tipo_meta == "recurrente":
            st.caption(
                "💡 *Nota:* Esta meta es **Recurrente**. Al confirmarla, el sistema liberará lo acumulado y actualizará automáticamente la fecha límite para el siguiente período de "
                f"{meta_obj.intervalo_meses_recurrencia} mes(es)."
            )
        else:
            st.caption(
                "💡 *Nota:* Esta meta es **Puntual**. Al pagarla, se dará por completada y se archivará."
            )

        medio_pago_str = st.selectbox(
            "Medio real desde el que sale el pago:", ["digital", "fisico"]
        )
        medio_pago = cast(TipoMedio, medio_pago_str)

        if st.button("Efectuar Pago"):
            try:
                motor.ejecutar_pago_meta(meta_sel_id, medio_pago)
                guardar_cambios()
                st.success(f"¡Se asentó el pago de '{meta_obj.nombre}'!")
                st.rerun()
            except AssertionError as e:
                st.error(str(e))
    else:
        st.write("No hay metas activas disponibles para pagar.")

# --- VISTA 5: CREAR NUEVA META ---
elif opcion == "➕ Crear Nueva Meta":
    st.title("➕ Crear Meta de Prorrateo")
    st.caption(
        "Definí objetivos o compromisos obligatorios indicando cuándo tenés que pagarlos."
    )

    nombre_meta = st.text_input("Nombre de la meta (ej: Matrícula, Servidor, Regalo):")
    monto_meta = st.number_input(
        "Monto total estimado ($):", min_value=1.0, step=1000.0
    )

    hoy_utc = datetime.now(timezone.utc).date()
    fecha_seleccionada = st.date_input(
        "Fecha límite o de vencimiento:",
        value=hoy_utc + timedelta(days=365),
        min_value=hoy_utc + timedelta(days=1),
    )

    tipo_meta_opcion = st.selectbox(
        "Categoría del gasto:",
        [
            "🔄 Recurrente (se repite al vencer)",
            "📌 Puntual (evento o gasto único)",
        ],
    )
    tipo_meta = cast(
        TipoMeta,
        "recurrente" if "Recurrente" in tipo_meta_opcion else "puntual",
    )

    intervalo_meses = 12
    if tipo_meta == "recurrente":
        intervalo_meses = int(
            st.number_input(
                "Frecuencia de repetición (en meses):",
                min_value=1,
                value=12,
                help="Por ejemplo: 1 para mensual, 12 para anual, 6 para semestral.",
            )
        )

    fecha_str = fecha_seleccionada.strftime("%Y-%m-%d")
    meta_previa = MetaProrrateo(
        id="preview",
        nombre=nombre_meta,
        monto_total=monto_meta,
        fecha_limite=fecha_str,
        tipo_meta=tipo_meta,
        intervalo_meses_recurrencia=intervalo_meses,
    )

    st.info(
        f"📅 **Meses calculados automáticamente:** {meta_previa.meses_restantes} mes(es) hasta el vencimiento.\n\n"
        f"💵 **Cuota mensual sugerida:** ${meta_previa.cuota_mensual_sugerida:,.2f}"
    )

    if st.button("Guardar Meta") and nombre_meta:
        nueva_id = f"meta_{len(motor.metas_prorrateo) + 1}"
        nueva_meta = MetaProrrateo(
            id=nueva_id,
            nombre=nombre_meta,
            monto_total=monto_meta,
            fecha_limite=fecha_str,
            tipo_meta=tipo_meta,
            intervalo_meses_recurrencia=intervalo_meses,
        )
        motor.agregar_meta(nueva_meta)
        guardar_cambios()
        st.success(f"Meta '{nombre_meta}' creada con éxito.")
        st.rerun()
