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

# ================= FUNCIONES =================
def obtener_obras():
    return {d.id: d.to_dict().get("nombre", d.id)
            for d in db.collection("obras").stream()}

def obtener_datos_obra(obra_id):
    doc = db.collection("obras").document(obra_id).get()
    return doc.to_dict() if doc.exists else {}

def formatear_moneda(v):
    return f"S/ {float(v):,.2f}"

# ================= ESTADO =================
OBRAS = obtener_obras()
lista_ids = list(OBRAS.keys())

if "obra_id_global" not in st.session_state and lista_ids:
    st.session_state["obra_id_global"] = lista_ids[0]

indice_actual = lista_ids.index(st.session_state["obra_id_global"])

# ================= SIDEBAR =================
with st.sidebar:
    obra_id = st.selectbox(
        "Seleccionar obra",
        options=lista_ids,
        format_func=lambda x: OBRAS.get(x, x),
        index=indice_actual
    )

    st.session_state["obra_id_global"] = obra_id
    st.success(f"🏗️ Obra activa: **{OBRAS.get(obra_id)}**")

    st.divider()
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ================= DATOS =================
obra = obtener_datos_obra(obra_id)

presupuesto_total = float(obra.get("presupuesto_total", 0))
gasto_materiales = float(obra.get("gasto_acumulado", 0))
gasto_mano_obra = float(obra.get("gasto_mano_obra", 0))
gastos_adicionales = float(obra.get("gastos_adicionales", 0))

gastos_ejecutados = gasto_materiales + gasto_mano_obra + gastos_adicionales
saldo_final = presupuesto_total - gastos_ejecutados

# ================= MATRIZ =================
mes_actual = datetime.now().strftime("%B").upper()

data = [
    ["Saldo inicial", presupuesto_total, presupuesto_total],
    ["Donaciones recibidas", 0, 0],
    ["Total ingresos", presupuesto_total, presupuesto_total],
    ["Gastos ejecutados", gastos_ejecutados, gastos_ejecutados],
    ["Saldo final", saldo_final, saldo_final],
]

df = pd.DataFrame(
    data,
    columns=["Concepto", "Mes (S/)", "Acumulado (S/)"]
)

# ================= DISEÑO =================
st.title("📊 Informe Mensual")

st.subheader(f"MES {mes_actual}")

styled = (
    df.style
    .format({
        "Mes (S/)": lambda x: f"{x:,.2f}",
        "Acumulado (S/)": lambda x: f"{x:,.2f}",
    })
    .set_properties(**{
        "border": "1px solid black",
        "padding": "14px",
        "font-size": "15px"
    })
    .set_table_styles([
        {"selector": "th", "props": [
            ("border", "1px solid black"),
            ("padding", "16px"),
            ("background-color", "#f2f2f2"),
            ("font-weight", "bold")
        ]},
        {"selector": "td", "props": [
            ("border", "1px solid black")
        ]},
        {"selector": "table", "props": [
            ("border-collapse", "collapse"),
            ("width", "100%")
        ]}
    ])
)

st.dataframe(styled, use_container_width=True, hide_index=True)

# ================= EXPORTAR EXCEL =================
st.divider()
st.subheader("📥 Descargar informe mensual")

buffer = BytesIO()
df_excel = df.copy()
df_excel["Mes (S/)"] = df_excel["Mes (S/)"].astype(float)
df_excel["Acumulado (S/)"] = df_excel["Acumulado (S/)"].astype(float)

with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df_excel.to_excel(writer, index=False, sheet_name="Informe Mensual")
    workbook = writer.book
    worksheet = writer.sheets["Informe Mensual"]

    formato = workbook.add_format({
        "border": 1,
        "num_format": "#,##0.00",
        "align": "left"
    })

    worksheet.set_column("A:A", 28)
    worksheet.set_column("B:C", 18, formato)

buffer.seek(0)

st.download_button(
    "📥 Descargar Excel",
    data=buffer,
    file_name=f"informe_mensual_{obra_id}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
