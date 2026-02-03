"informes.py"
import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore
from io import BytesIO
from docx import Document


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
ids = list(OBRAS.keys())

if not ids:
    st.warning("No hay obras registradas")
    st.stop()

# ================= CONTROL CORRECTO DE CAMBIO =================
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

# ================= SELECCIÓN DE OBRA =================
indice_actual = 0
if "obra_id_global" in st.session_state and st.session_state["obra_id_global"] in lista_ids:
    indice_actual = lista_ids.index(st.session_state["obra_id_global"])

obra_id = st.sidebar.selectbox(
    "Seleccionar obra",
    options=lista_ids,
    format_func=lambda x: OBRAS.get(x, x),
    index=indice_actual,
    key="selector_global"
)

# Guardar selección global (para TODAS las páginas)
st.session_state["obra_id_global"] = obra_id


# ================= DATOS OBRA (SIEMPRE FRESCOS) =================
obra = db.collection("obras").document(obra_id).get().to_dict()

st.sidebar.success(f"🏗️ Obra activa: **{obra['nombre']}**")

# ================= CÁLCULOS =================
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
    ["Donaciones recibidas", 0.0, 0.0],
    ["Total ingresos", presupuesto_total, presupuesto_total],
    ["Gastos ejecutados", gastos_ejecutados, gastos_ejecutados],
    ["Saldo final", saldo_final, saldo_final],
]

df = pd.DataFrame(
    data,
    columns=["Concepto", "Mes (S/)", "Acumulado (S/)"]
)

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
        "padding": "16px",
        "font-size": "16px",
        "text-align": "center"
    })
)

st.subheader(f"MES {mes_actual}")
st.dataframe(df_style, use_container_width=True)

# ================= EXCEL =================
buffer_excel = BytesIO()
with pd.ExcelWriter(buffer_excel, engine="xlsxwriter") as writer:
    df.to_excel(writer, index=False, sheet_name="Informe Mensual")

buffer_excel.seek(0)

st.download_button(
    "📥 Descargar Excel",
    buffer_excel,
    f"informe_{obra['nombre'].replace(' ', '_')}.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# ================= CARTA WORD =================
st.divider()
st.header("📄 Carta de Informe Mensual")

fecha_actual = datetime.now().strftime("%d de %B del %Y")

carta_base = f"""
<b>CARTA DE INFORME MENSUAL</b><br><br>
Ventanilla, {fecha_actual}<br><br>
Estimados señores:<br><br>
Por medio de la presente nos dirigimos a ustedes para expresar nuestro
agradecimiento por el apoyo brindado a la construcción del proyecto
<b>{obra['nombre']}</b>.<br><br>
Durante el presente mes se ejecutaron las siguientes actividades principales:<br>
- <br>- <br><br>
El monto total ejecutado en el período asciende a
<b>S/. {gastos_ejecutados:,.2f}</b>.<br><br>
Atentamente,<br><br>
______________________________<br>
Gerardo Langberg Bacigalupo
"""

contenido = st.text_area(
    "Contenido de la carta",
    value=carta_base.replace("<br>", "\n").replace("<b>", "").replace("</b>", ""),
    height=350
)


if st.button("📥 Descargar Carta Word"):
    doc = Document()
    texto = contenido.replace("<br>", "\n").replace("<b>", "").replace("</b>", "")
    for linea in texto.split("\n"):
        doc.add_paragraph(linea)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    st.download_button(
        "⬇️ Descargar .docx",
        buffer,
        f"Carta_{obra['nombre'].replace(' ', '_')}.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
