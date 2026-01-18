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

# ================= FUNCIONES =================
def obtener_obras():
    return {
        d.id: d.to_dict().get("nombre", d.id)
        for d in db.collection("obras").stream()
    }

def obtener_datos_obra(obra_id):
    doc = db.collection("obras").document(obra_id).get()
    return doc.to_dict() if doc.exists else {}

# ================= UI =================
st.title("📊 Informes Mensuales")

# ---------- Selector de obra (IGUAL que materiales.py) ----------
OBRAS = obtener_obras()
ids = list(OBRAS.keys())

if "obra_id_global" not in st.session_state and ids:
    st.session_state["obra_id_global"] = ids[0]

indice = ids.index(st.session_state["obra_id_global"])

obra_id = st.sidebar.selectbox(
    "Seleccionar obra",
    options=ids,
    format_func=lambda x: OBRAS[x],
    index=indice
)

st.session_state["obra_id_global"] = obra_id
st.sidebar.success(f"🏗️ Obra activa: **{OBRAS[obra_id]}**")

# ================= DATOS =================
obra = obtener_datos_obra(obra_id)

presupuesto_total = float(obra.get("presupuesto_total", 0))
gasto_materiales = float(obra.get("gasto_acumulado", 0))
gasto_mano_obra = float(obra.get("gasto_mano_obra", 0))
gastos_adicionales = float(obra.get("gastos_adicionales", 0))

gastos_ejecutados = gasto_materiales + gasto_mano_obra + gastos_adicionales
saldo_final = presupuesto_total - gastos_ejecutados

# ================= MATRIZ =================
mes = datetime.now().strftime("%B").upper()

data = [
    ["Saldo inicial", presupuesto_total, presupuesto_total],
    ["Donaciones recibidas", 0.0, presupuesto_total],
    ["Total ingresos", presupuesto_total, presupuesto_total],
    ["Gastos ejecutados", gastos_ejecutados, gastos_ejecutados],
    ["Saldo final", saldo_final, saldo_final],
]

df = pd.DataFrame(
    data,
    columns=[f"MES {mes} - Concepto", "Mes (S/)", "Acumulado (S/)"]
)

# ================= ESTILO =================
def formato_soles(x):
    return f"S/ {x:,.2f}"

styled = (
    df.style
    .format(formato_soles, subset=["Mes (S/)", "Acumulado (S/)"])
    .set_properties(**{
        "border": "2px solid black",
        "padding": "14px",
        "font-size": "16px"
    })
    .set_table_styles([
        {"selector": "th", "props": [
            ("border", "2px solid black"),
            ("font-size", "16px"),
            ("padding", "14px"),
            ("background-color", "#f0f0f0")
        ]}
    ])
)

st.dataframe(styled, use_container_width=True)

# ================= EXCEL =================
buffer = BytesIO()
df_excel = df.copy()
df_excel["Mes (S/)"] = df_excel["Mes (S/)"].astype(float)
df_excel["Acumulado (S/)"] = df_excel["Acumulado (S/)"].astype(float)

with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df_excel.to_excel(writer, index=False, sheet_name="Informe Mensual")

buffer.seek(0)

st.download_button(
    "📥 Descargar Excel",
    data=buffer,
    file_name=f"informe_mensual_{OBRAS[obra_id]}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
