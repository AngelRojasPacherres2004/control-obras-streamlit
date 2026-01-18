import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore
from io import BytesIO
from docx import Document
from streamlit_quill import st_quill

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
        d.id: d.to_dict()
        for d in db.collection("obras").stream()
    }

OBRAS = obtener_obras()
ids = list(OBRAS.keys())

if not ids:
    st.warning("No hay obras registradas")
    st.stop()

# Mantener selección global
if "obra_id_global" not in st.session_state:
    st.session_state["obra_id_global"] = ids[0]

obra_id = st.sidebar.selectbox(
    "Seleccionar obra",
    options=ids,
    format_func=lambda x: OBRAS[x]["nombre"],
    index=ids.index(st.session_state["obra_id_global"])
)

st.session_state["obra_id_global"] = obra_id
obra = OBRAS[obra_id]
st.sidebar.success(f"🏗️ Obra activa: **{obra['nombre']}**")

# ================= DATOS REALES (IGUAL QUE OBRAS.PY) =================
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
        "padding": "16px",
        "font-size": "16px",
        "text-align": "center"
    })
    .set_table_styles([
        {"selector": "th", "props": [
            ("border", "2px solid black"),
            ("padding", "16px"),
            ("font-size", "16px"),
            ("text-align", "center")
        ]}
    ])
)

st.subheader(f"MES {mes_actual}")
st.dataframe(df_style, use_container_width=True)

# ================= EXPORTAR EXCEL =================
buffer_excel = BytesIO()
with pd.ExcelWriter(buffer_excel, engine="xlsxwriter") as writer:
    df.to_excel(writer, index=False, sheet_name="Informe Mensual")

buffer_excel.seek(0)

st.download_button(
    label="📥 Descargar informe mensual en Excel",
    data=buffer_excel,
    file_name=f"informe_mensual_{obra['nombre'].replace(' ', '_')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# ================= CARTA DE INFORME =================
st.divider()
st.header("📄 Carta de Informe Mensual (Editable tipo Word)")

fecha_actual = datetime.now().strftime("%d de %B del %Y")

carta_base = f"""
<b>CARTA DE INFORME MENSUAL</b><br><br>
Ventanilla, {fecha_actual}<br><br>

Estimados señores:<br><br>

Por medio de la presente nos dirigimos a ustedes para expresar nuestro
agradecimiento por el apoyo brindado a la construcción del proyecto
<b>{obra['nombre']}</b>.<br><br>

Durante el presente mes se ejecutaron las siguientes actividades principales:<br>
- <br>
- <br><br>

El monto total ejecutado en el período asciende a
<b>S/. {gastos_ejecutados:,.2f}</b>,
manteniendo una gestión responsable.<br><br>

Adjuntamos el informe financiero en formato Excel y el registro fotográfico
del avance de obra.<br><br>

Sin otro particular reiteramos nuestro agradecimiento y quedamos atentos
a cualquier consulta adicional.<br><br>

Atentamente,<br><br>

______________________________<br>
Gerardo Langberg Bacigalupo<br>
Cargo<br>
Cuasi Parroquia Señora de La Paz
"""

contenido = st_quill(
    value=carta_base,
    html=True,
    key="editor_carta"
)

# ================= DESCARGAR WORD =================
if contenido:
    if st.button("📥 Descargar Carta en Word", type="primary"):
        doc = Document()
        texto_plano = contenido.replace("<br>", "\n").replace("<b>", "").replace("</b>", "")
        for linea in texto_plano.split("\n"):
            doc.add_paragraph(linea)

        buffer_word = BytesIO()
        doc.save(buffer_word)
        buffer_word.seek(0)

        st.download_button(
            label="⬇️ Descargar .docx",
            data=buffer_word,
            file_name=f"Carta_Informe_{obra['nombre'].replace(' ', '_')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
