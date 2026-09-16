import streamlit as st

from engine import MotorFinanciero
from repository import RepositorioFinanciero
from views import gastos, ingresos, metas, panel

st.set_page_config(
    page_title="Control Financiero - Liquidez y Prorrateo", layout="wide"
)

repo = RepositorioFinanciero("estado_financiero.json")

if "motor" not in st.session_state:
    st.session_state.motor = repo.cargar()

motor: MotorFinanciero = st.session_state.motor


def guardar_cambios() -> None:
    repo.guardar(motor)


st.sidebar.title("⚙️ Operaciones")
opcion = st.sidebar.radio(
    "Seleccioná una acción:",
    [
        "📊 Panel Principal",
        "💵 Registrar Ingreso",
        "🛒 Registrar Gasto Diario",
        "⚙️ Gestión de Metas",
    ],
)

VISTAS = {
    "📊 Panel Principal": lambda: panel.render(motor, guardar_cambios),
    "💵 Registrar Ingreso": lambda: ingresos.render(motor, guardar_cambios),
    "🛒 Registrar Gasto Diario": lambda: gastos.render(motor, guardar_cambios),
    "⚙️ Gestión de Metas": lambda: metas.render(motor, guardar_cambios),
}

VISTAS[opcion]()
