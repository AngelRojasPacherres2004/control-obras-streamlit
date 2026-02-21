"informes.py"
import streamlit as st
import pandas as pd
from datetime import datetime
from firebase_admin import firestore
from io import BytesIO
from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from datetime import timezone
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

# ================= SELECCIÓN DE MES =================
st.sidebar.divider()
st.sidebar.subheader("📅 Seleccionar Mes del Informe")

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

col1, col2 = st.sidebar.columns(2)

anio_actual = col1.number_input(
    "Año",
    min_value=2020,
    max_value=2100,
    value=datetime.now().year,
    step=1
)

mes_numero = col2.selectbox(
    "Mes",
    options=list(MESES.keys()),
    format_func=lambda x: MESES[x],
    index=datetime.now().month - 1
)

mes_nombre = MESES[mes_numero]

# ================= RANGO DE FECHA =================
# ================= RANGO DE FECHA =================
inicio_mes = datetime(anio_actual, mes_numero, 1, tzinfo=timezone.utc)

if mes_numero == 12:
    fin_mes = datetime(anio_actual + 1, 1, 1, tzinfo=timezone.utc)
else:
    fin_mes = datetime(anio_actual, mes_numero + 1, 1, tzinfo=timezone.utc)


# ================= MATERIAL (FILTRADO REAL) =================
# ================= MATERIAL (FILTRADO REAL) =================
# ================= MATERIAL (ROBUSTO) =================
materiales_ref = db.collection("obras").document(obra_id).collection("materiales")

gasto_materiales_mes = 0

for doc_mat in materiales_ref.stream():
    data = doc_mat.to_dict()
    fecha = data.get("fecha")
    parcial = float(
    data.get("parcial") or
    data.get("monto") or
    data.get("importe") or
    data.get("total") or
    0
    )


    if not fecha:
        continue

    try:
        # Timestamp Firestore
        if hasattr(fecha, "to_datetime"):
            fecha_dt = fecha.to_datetime()

        # datetime normal
        elif isinstance(fecha, datetime):
            fecha_dt = fecha

        # string tipo 2026-02-15
        elif "-" in fecha:
            fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")

        # string tipo 15/02/2026
        elif "/" in fecha:
            fecha_dt = datetime.strptime(fecha, "%d/%m/%Y")

        else:
            continue

        if inicio_mes.replace(tzinfo=None) <= fecha_dt.replace(tzinfo=None) < fin_mes.replace(tzinfo=None):
            gasto_materiales_mes += parcial

    except:
        continue



# ================= MANO DE OBRA (FILTRADO REAL) =================
# ================= MANO DE OBRA (ROBUSTO) =================
mo_ref = db.collection("obras").document(obra_id).collection("mano_obra")

gasto_mo_mes = 0

for doc_mo in mo_ref.stream():
    data = doc_mo.to_dict()
    fecha = data.get("fecha")
    parcial = float(
    data.get("parcial") or
    data.get("monto") or
    data.get("importe") or
    data.get("total") or
    0
    )


    if not fecha:
        continue

    try:
        if hasattr(fecha, "to_datetime"):
            fecha_dt = fecha.to_datetime()
        elif isinstance(fecha, datetime):
            fecha_dt = fecha
        elif "-" in fecha:
            fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
        elif "/" in fecha:
            fecha_dt = datetime.strptime(fecha, "%d/%m/%Y")
        else:
            continue

        if inicio_mes.replace(tzinfo=None) <= fecha_dt.replace(tzinfo=None) < fin_mes.replace(tzinfo=None):
            gasto_mo_mes += parcial

    except:
        continue


# ================= TOTAL MES =================
gasto_total_mes = gasto_materiales_mes + gasto_mo_mes






# ================= PARTIDAS (SECCIONES REALES) =================
# ================= PARTIDAS (DETALLADO) =================
partidas_ref = db.collection("obras").document(obra_id).collection("partidas")

secciones_terminadas = []
secciones_iniciadas = []
secciones_proceso = []

for doc_sec in partidas_ref.stream():
    s = doc_sec.to_dict()

    nombre = s.get("nombre", "Sin nombre")
    valor_meta = float(s.get("valor_rendimiento", 0))
    rendimiento_acumulado = float(s.get("rendimiento_acumulado", 0))

    porcentaje = (rendimiento_acumulado / valor_meta * 100) if valor_meta > 0 else 0

    detalle = (
        f"{nombre} | "
        f"Meta: {valor_meta:,.2f} | "
        f"Avance: {rendimiento_acumulado:,.2f} | "
        f"Cumplimiento: {porcentaje:.1f}%"
    )

    fecha_creacion = s.get("fecha_creacion")

    fecha_dt = None
    if fecha_creacion:
        if hasattr(fecha_creacion, "to_datetime"):
            fecha_dt = fecha_creacion.to_datetime()
        elif isinstance(fecha_creacion, datetime):
            fecha_dt = fecha_creacion

    # 🔹 Iniciadas en el mes
    if fecha_dt and inicio_mes <= fecha_dt < fin_mes:
        secciones_iniciadas.append(detalle)

    # 🔹 Terminadas
    if porcentaje >= 100:
        secciones_terminadas.append(detalle)

    # 🔹 En proceso
    if 0 < porcentaje < 100:
        secciones_proceso.append(detalle)



# ================= GENERAR PDF =================
st.divider()
st.subheader("📑 Generar Informe Profesional")

if st.button("📥 Descargar Informe Mensual PDF"):

    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=A4)
    elementos = []
    styles = getSampleStyleSheet()

    # -------- TÍTULO --------
    elementos.append(Paragraph("<b>INFORME MENSUAL DE OBRA</b>", styles["Title"]))
    elementos.append(Spacer(1, 20))

    elementos.append(Paragraph(f"<b>Obra:</b> {obra['nombre']}", styles["Normal"]))
    elementos.append(Paragraph(f"<b>Mes:</b> {mes_nombre} {anio_actual}", styles["Normal"]))
    elementos.append(Spacer(1, 20))

    # -------- RESUMEN FINANCIERO --------
    elementos.append(Paragraph("<b>RESUMEN FINANCIERO</b>", styles["Heading2"]))
    elementos.append(Spacer(1, 10))

    tabla_data = [
        ["Concepto", "Monto (S/)"],
        ["Materiales", f"S/ {gasto_materiales_mes:,.2f}"],
        ["Mano de Obra", f"S/ {gasto_mo_mes:,.2f}"],
        ["TOTAL EJECUTADO", f"S/ {gasto_total_mes:,.2f}"],
    ]

    tabla = Table(tabla_data, colWidths=[250, 150])
    tabla.setStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
    ])

    elementos.append(tabla)
    elementos.append(Spacer(1, 30))

    # -------- SECCIONES TERMINADAS --------
    elementos.append(Paragraph("<b>SECCIONES TERMINADAS</b>", styles["Heading2"]))
    elementos.append(Spacer(1, 10))

    if secciones_terminadas:
        for s in secciones_terminadas:
            elementos.append(Paragraph(f"• {s}", styles["Normal"]))
    else:
        elementos.append(Paragraph("Ninguna sección terminada este mes.", styles["Normal"]))

    elementos.append(Spacer(1, 20))

    # -------- SECCIONES INICIADAS --------
    elementos.append(Paragraph("<b>SECCIONES INICIADAS</b>", styles["Heading2"]))
    elementos.append(Spacer(1, 10))

    if secciones_iniciadas:
        for s in secciones_iniciadas:
            elementos.append(Paragraph(f"• {s}", styles["Normal"]))
    else:
        elementos.append(Paragraph("Ninguna sección iniciada este mes.", styles["Normal"]))

    elementos.append(Spacer(1, 20))

    # -------- SECCIONES EN PROCESO --------
    elementos.append(Paragraph("<b>SECCIONES EN PROCESO</b>", styles["Heading2"]))
    elementos.append(Spacer(1, 10))

    if secciones_proceso:
        for s in secciones_proceso:
            elementos.append(Paragraph(f"• {s}", styles["Normal"]))
    else:
        elementos.append(Paragraph("No hay secciones en proceso.", styles["Normal"]))

    elementos.append(Spacer(1, 40))
    elementos.append(Paragraph("__________________________________", styles["Normal"]))
    elementos.append(Paragraph("Gerardo Langberg Bacigalupo", styles["Normal"]))
    elementos.append(Paragraph("Director de Proyecto", styles["Normal"]))

    pdf.build(elementos)
    buffer.seek(0)

    st.download_button(
        "⬇️ Descargar PDF",
        buffer,
        f"Informe_{obra['nombre']}_{mes_nombre}_{anio_actual}.pdf",
        "application/pdf"
    )
