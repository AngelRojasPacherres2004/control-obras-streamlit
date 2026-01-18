import streamlit as st
import pandas as pd
from firebase_admin import firestore
from io import BytesIO
from datetime import datetime

# ================= DB =================
db = firestore.client()

# ================= SEGURIDAD =================
if "auth" not in st.session_state:
    st.error("Inicia sesión")
    st.stop()

if st.session_state["auth"]["role"] != "jefe":
    st.warning("Sin permisos")
    st.stop()

# ================= UI =================
st.title("📊 Informes Mensuales")

# ================= OBRAS =================
def obtener_obras():
    return {
        d.id: d.to_dict().get("nombre", d.id)
        for d in db.collection("obras").stream()
    }

OBRAS = obtener_obras()
lista_ids = list(OBRAS.keys())

if not lista_ids:
    st.warning("No hay obras registradas")
    st.stop()

# Selección persistente
if "obra_id_global" not in st.session_state:
    st.session_state["obra_id_global"] = lista_ids[0]

indice = lista_ids.index(st.session_state["obra_id_global"])

obra_id = st.sidebar.selectbox(
    "Seleccionar obra",
    options=lista_ids,
    format_func=lambda x: OBRAS.get(x, x),
    index=indice
)

st.session_state["obra_id_global"] = obra_id
st.sidebar.success(f"🏗️ Obra activa: **{OBRAS.get(obra_id)}**")

# ================= DATOS DE OBRA =================
obra = db.collection("obras").document(obra_id).get().to_dict()

presupuesto_total = float(obra.get("presupuesto_total", 0))
gasto_materiales = float(obra.get("gasto_acumulado", 0))
gasto_mano_obra = float(obra.get("gasto_mano_obra", 0))
gastos_adicionales = float(obra.get("gastos_adicionales", 0))

gastos_ejecutados = (
    gasto_materiales +
    gasto_mano_obra +
    gastos_adicionales
)

saldo_final = presupuesto_total - gastos_ejecutados

# ================= MATRIZ =================
mes_actual = datetime.now().strftime("%B").upper()

data = [
    ["Saldo inicial", presupuesto_total, presupuesto_total],
    ["Donaciones recibidas", 0, presupuesto_total],
    ["Total ingresos", presupuesto_total, presupuesto_total],
    ["Gastos ejecutados", gastos_ejecutados, gastos_ejecutados],
    ["Saldo final", saldo_final, saldo_final],
]

df = pd.DataFrame(
    data,
    columns=[
        f"MES {mes_actual} – Concepto",
        "Mes (S/)",
        "Acumulado (S/)"
    ]
)

# ================= MOSTRAR =================
st.subheader("📋 Resumen financiero mensual")
st.dataframe(df, use_container_width=True)

# ================= EXCEL =================
buffer = BytesIO()
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df.to_excel(writer, index=False, sheet_name="Informe Mensual")

buffer.seek(0)

st.download_button(
    label="📥 Descargar informe en Excel",
    data=buffer,
    file_name=f"informe_{OBRAS.get(obra_id)}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# ================= CERRAR SESIÓN =================
with st.sidebar:
    st.divider()
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()
