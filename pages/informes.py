"informes.py"
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
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
# ================= CÁLCULOS REALES DESDE FIRESTORE =================
presupuesto_total = float(obra.get("presupuesto_total", 0))

# 🔹 TOTAL MATERIALES (REAL)
materiales_ref_total = db.collection("obras").document(obra_id).collection("materiales")
gasto_materiales_total = 0

for doc_mat in materiales_ref_total.stream():
    data = doc_mat.to_dict()
    parcial = float(
        data.get("parcial") or
        data.get("monto") or
        data.get("importe") or
        data.get("total") or
        0
    )
    gasto_materiales_total += parcial

# 🔹 TOTAL MANO DE OBRA (REAL)
mo_ref_total = db.collection("obras").document(obra_id).collection("mano_obra")
gasto_mano_obra_total = 0

for doc_mo in mo_ref_total.stream():
    data = doc_mo.to_dict()
    parcial = float(
        data.get("parcial") or
        data.get("monto") or
        data.get("importe") or
        data.get("total") or
        0
    )
    gasto_mano_obra_total += parcial

# 🔹 ADICIONALES
gastos_adicionales = float(obra.get("gastos_adicionales", 0))

# 🔹 TOTAL EJECUTADO REAL
gastos_ejecutados = gasto_materiales_total + gasto_mano_obra_total + gastos_adicionales

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
# ================= MATERIAL (MENSUAL CORREGIDO) =================
# ================= GASTO MENSUAL IGUAL QUE OBRAS.PY =================

from collections import defaultdict
import pytz

local_tz = pytz.timezone("America/Lima")

gasto_materiales_mes = 0.0
gasto_mo_mes = 0.0
gasto_caja_mes = 0.0

obra_ref = db.collection("obras").document(obra_id)

# 🔥 OJO: igual que obras.py → recorrer PARTIDAS → AVANCES
partidas_ref = obra_ref.collection("partidas").stream()

for partida in partidas_ref:
    avances_ref = partida.reference.collection("avances").stream()

    for av in avances_ref:
        data = av.to_dict()

        fecha = data.get("fecha") or data.get("timestamp")

        if not fecha:
            continue

        # Normalizar fecha
        if hasattr(fecha, "to_datetime"):
            fecha_dt = fecha.to_datetime()
        elif isinstance(fecha, datetime):
            fecha_dt = fecha
        else:
            continue

        if fecha_dt.tzinfo is None:
            fecha_dt = fecha_dt.replace(tzinfo=pytz.UTC)

        fecha_dt = fecha_dt.astimezone(local_tz)

        # 🔥 FILTRO POR MES EXACTAMENTE IGUAL
        if fecha_dt.year == anio_actual and fecha_dt.month == mes_numero:

            subtotal_materiales = float(data.get("subtotal_materiales", 0))
            subtotal_mano_obra = float(data.get("subtotal_mano_obra", 0))
            gasto_caja = float(data.get("gasto_caja_chica", 0) or 0)

            gasto_materiales_mes += subtotal_materiales
            gasto_mo_mes += subtotal_mano_obra
            gasto_caja_mes += gasto_caja

# TOTAL MES EXACTO COMO LA GRÁFICA
gasto_total_mes = gasto_materiales_mes + gasto_mo_mes + gasto_caja_mes



####

# ================= GASTO SEMANAL DEL MES =================
presupuesto_semanal = obra.get("presupuesto_materiales_semanal", [])

gastos_semanales_mes = []

if presupuesto_semanal:

    fecha_inicio_obra = obra.get("fecha_inicio")
    if hasattr(fecha_inicio_obra, "to_datetime"):
        fecha_inicio_obra = fecha_inicio_obra.to_datetime()

    if fecha_inicio_obra:
        fecha_inicio_obra = fecha_inicio_obra.replace(tzinfo=None)

        # Ajustar al lunes base
        lunes_base = fecha_inicio_obra - timedelta(days=fecha_inicio_obra.weekday())

        for sem in presupuesto_semanal:
            num_sem = sem.get("semana")
            gasto_real = float(sem.get("gasto_real", 0))

            fecha_inicio_sem = lunes_base + timedelta(days=(num_sem - 1) * 7)
            fecha_fin_sem = fecha_inicio_sem + timedelta(days=6)

            # Si la semana cae dentro del mes seleccionado
            if (
                fecha_inicio_sem.year == anio_actual and fecha_inicio_sem.month == mes_numero
            ) or (
                fecha_fin_sem.year == anio_actual and fecha_fin_sem.month == mes_numero
            ):
                gastos_semanales_mes.append([
                    f"Semana {num_sem}",
                    fecha_inicio_sem.strftime("%d/%m"),
                    fecha_fin_sem.strftime("%d/%m"),
                    f"S/ {gasto_real:,.2f}"
                ])





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
        ["Caja Chica", f"S/ {gasto_caja_mes:,.2f}"],
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


    # -------- GASTOS POR SEMANA --------
    if gastos_semanales_mes:

        elementos.append(Paragraph("<b>GASTOS POR SEMANA</b>", styles["Heading2"]))
        elementos.append(Spacer(1, 10))

        tabla_semanal_data = [
            ["Semana", "Inicio", "Fin", "Gasto (S/)"]
        ] + gastos_semanales_mes

        tabla_semanal = Table(tabla_semanal_data, colWidths=[80, 80, 80, 100])

        tabla_semanal.setStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#244062")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ("ALIGN", (3,1), (-1,-1), "RIGHT"),
        ])

        elementos.append(tabla_semanal)
        elementos.append(Spacer(1, 25))






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

    elementos.append(Spacer(1, 30))

    # =========================================================
    # 📚 HISTORIAL DE AVANCES POR SECCIÓN
    # =========================================================
    elementos.append(Paragraph("<b>HISTORIAL DE AVANCES</b>", styles["Heading1"]))
    elementos.append(Spacer(1, 15))

    partidas_stream = obra_ref.collection("partidas").stream()

    for partida in partidas_stream:

        partida_data = partida.to_dict()
        nombre_partida = partida_data.get("nombre", "Sin nombre")
        codigo_partida = partida_data.get("codigo", "")

        elementos.append(Paragraph(
            f"<b>🧱 {codigo_partida} - {nombre_partida}</b>",
            styles["Heading2"]
        ))
        elementos.append(Spacer(1, 10))

        avances_stream = (
            partida.reference
            .collection("avances")
            .order_by("fecha", direction=firestore.Query.DESCENDING)
            .stream()
        )

        avances_lista = list(avances_stream)

        if not avances_lista:
            elementos.append(Paragraph("No tiene avances registrados.", styles["Normal"]))
            elementos.append(Spacer(1, 10))
            continue

        for av in avances_lista:

            av_data = av.to_dict()
            fecha = av_data.get("fecha")
            usuario = av_data.get("usuario", "N/D")
            fecha_txt = "Fecha no disponible"

            if fecha:
                if hasattr(fecha, "to_datetime"):
                    fecha = fecha.to_datetime()

                if isinstance(fecha, datetime):
                    fecha_txt = fecha.strftime("%d/%m/%Y")
            else:
                fecha_txt = "Fecha no disponible"

            elementos.append(Paragraph(
                f"<b>Fecha:</b> {fecha_txt} | <b>Usuario:</b> {usuario}",
                styles["Normal"]
            ))
            elementos.append(Spacer(1, 5))
            elementos.append(Spacer(1, 8))
            descripcion = av_data.get("descripcion", "")
            if descripcion:
                elementos.append(Paragraph(descripcion, styles["Normal"]))
                elementos.append(Spacer(1, 5))

            # 🔹 RESUMEN ECONÓMICO DEL AVANCE
            # =====================================================
            # 🔹 DETALLE DE MANO DE OBRA
            # =====================================================

            mano_obra_lista = av_data.get("mano_obra_detalle", [])

            if mano_obra_lista:
                elementos.append(Spacer(1, 8))
                elementos.append(Paragraph("<b>Detalle Mano de Obra</b>", styles["Heading3"]))
                elementos.append(Spacer(1, 6))

                tabla_mo = [["Tipo", "Trabajador", "Rend.", "Precio", "Cant.", "Parcial (S/)"]]

                subtotal_mo = 0

                for trabajador in mano_obra_lista:

                    tipo = trabajador.get("Tipo", "")
                    nombre_trab = trabajador.get("Descripción", "")
                    precio = float(trabajador.get("Precio", 0))
                    cantidad = float(trabajador.get("Cantidad", 0))
                    parcial = float(trabajador.get("Parcial", 0))
                    rendimiento = float(trabajador.get("Rendimiento", 0))

                    subtotal_mo += parcial

                    tabla_mo.append([
                        tipo,
                        nombre_trab,
                        f"{rendimiento:.2f}",
                        f"S/ {precio:,.2f}",
                        f"{cantidad:.2f}",
                        f"S/ {parcial:,.2f}"
                    ])

                tabla_mo.append(["", "", "", "", "TOTAL", f"S/ {subtotal_mo:,.2f}"])

                tabla_mano = Table(tabla_mo, colWidths=[80, 100, 50, 60, 50, 70])

                tabla_mano.setStyle([
                    ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                    ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                    ("BACKGROUND", (0,-1), (-1,-1), colors.whitesmoke),
                    ("ALIGN", (2,1), (-1,-1), "RIGHT"),
                ])

                elementos.append(tabla_mano)
                elementos.append(Spacer(1, 10))
            else:
                subtotal_mo = float(av_data.get("subtotal_mano_obra", 0))
            # =====================================================
            # 🔹 RESUMEN GENERAL DEL AVANCE
            # =====================================================

            subtotal_mat = float(av_data.get("subtotal_materiales", 0))
            total_avance = subtotal_mo + subtotal_mat

            tabla_resumen = [
                ["Concepto", "Monto (S/)"],
                ["Mano de Obra", f"S/ {subtotal_mo:,.2f}"],
                ["Materiales", f"S/ {subtotal_mat:,.2f}"],
                ["Total Avance", f"S/ {total_avance:,.2f}"],
            ]

            tabla_detalle = Table(tabla_resumen, colWidths=[250, 150])
            tabla_detalle.setStyle([
                ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                ("ALIGN", (1,1), (-1,-1), "RIGHT"),
            ])

            elementos.append(tabla_detalle)
            elementos.append(Spacer(1, 15))

           

            # 🔹 RENDIMIENTO
            rendimiento_real = float(av_data.get("rendimiento_real", 0))
            porcentaje = float(av_data.get("porcentaje_rendimiento", 0)) * 100

            elementos.append(Paragraph(
                f"Rendimiento: {rendimiento_real:.2f} "
                f"({porcentaje:.1f}% del plan)",
                styles["Normal"]
            ))
            elementos.append(Spacer(1, 15))

        elementos.append(Spacer(1, 20))

    # =========================================================
    # FIRMA
    # =========================================================
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
