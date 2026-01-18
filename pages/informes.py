import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore
from io import BytesIO

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

# mantener selección
if "obra_id_global" not in st.session_state:
    st.session_state["obra_id_global"] = lista_ids[0]

indice = lista_ids.index(st.session_state["obra_id_global"])

obra_id = st.sidebar.selectbox(
    "Seleccionar obra",
    options=lista_ids,
    index=indice,
    format_func=lambda x: OBRAS[x]
)

st.session_state["obra_id_global"] = obra_id
st.sidebar.success(f"🏗️ Obra activa: **{OBRAS[obra_id]}**")

# ================= DATOS OBRA =================
obra = db.collection("obras").document(obra_id).get().to_dict()

presupuesto_total = float(obra.get("presupuesto_total", 0))
presupuesto_materiales = float(obra.get("presupuesto_materiales", 0))
presupuesto_mano_obra = float(obra.get("presupuesto_mano_obra", 0))
presupuesto_caja = float(obra.get("presupuesto_caja_chica", 0))

gasto_materiales = float(obra.get("gasto_acumulado", 0))
gasto_mano_obra = float(obra.get("gasto_mano_obra", 0))
gastos_adicionales = float(obra.get("gastos_adicionales", 0))

gastos_ejecutados = gasto_materiales + gasto_mano_obra + gastos_adicionales
saldo_final = presupuesto_total - gastos_ejecutados

# ================= MATRIZ =================
mes_actual = datetime.now().strftime("%B").upper()

data = [
    ["Saldo inicial", presupuesto_total, presupuesto_total],
    ["Donaciones recibidas", 0.0, 0.0],
    ["Total ingresos", presupuesto_total, presupuesto_total],
    ["Gastos ejecutados", gastos_ejecutados, gastos_ejecutados],
    ["Saldo final", saldo_final, saldo_final],
]

df = pd.DataFrame(
    data,
    columns=["Concepto", "Mes (S/)", "Acumulado (S/)"]
)

# ================= DISEÑO MATRIZ =================
def formato_soles(x):
    return f"S/ {x:,.2f}"

df_style = (
    df.style
    .format({
        "Mes (S/)": formato_soles,
        "Acumulado (S/)": formato_soles
    })
    .set_properties(**{
        "border": "2px solid black",
        "padding": "14px",
        "font-size": "16px"
    })
    .set_table_styles([
        {"selector": "th", "props": [
            ("border", "2px solid black"),
            ("padding", "14px"),
            ("font-size", "16px")
        ]}
    ])
)

st.subheader(f"MES {mes_actual}")
st.dataframe(df_style, use_container_width=True)

# ================= EXPORTAR EXCEL =================
buffer = BytesIO()

with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df_excel = df.copy()
    df_excel.to_excel(writer, index=False, sheet_name="Informe Mensual")

buffer.seek(0)

st.download_button(
    label="📥 Descargar informe mensual en Excel",
    data=buffer,
    file_name=f"informe_{OBRAS[obra_id].replace(' ', '_')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
