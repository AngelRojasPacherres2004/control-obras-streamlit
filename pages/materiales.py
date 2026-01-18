"materiales.py"
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

# ================= ESTADO =================
st.session_state.setdefault("mat_global", None)
st.session_state.setdefault("mat_obra", None)
st.session_state.setdefault("vista_materiales_globales", False)

# ================= FUNCIONES DE ACTUALIZACIÓN =================
def recalcular_presupuesto_obra(obra_id):
    """Actualiza el gasto de materiales y el saldo restante en Firebase."""
    # 1. Sumar lo gastado actualmente en la subcolección materiales
    mats_docs = db.collection("obras").document(obra_id).collection("materiales").stream()
    total_gastado_mats = sum(float(d.to_dict().get("subtotal", 0)) for d in mats_docs)
    
    # 2. Obtener la obra para ver su presupuesto base
    obra_ref = db.collection("obras").document(obra_id)
    obra_data = obra_ref.get().to_dict()
    
    # 3. Guardar el 'techo' inicial si no existe (para tener referencia)
    p_mats_inicial = float(obra_data.get("presupuesto_materiales_inicial", obra_data.get("presupuesto_materiales", 0)))
    
    # 4. Calcular saldo que queda
    saldo_disponible_mats = p_mats_inicial - total_gastado_mats
    
    # 5. Actualizar Firebase
    obra_ref.update({
        "presupuesto_materiales_inicial": round(p_mats_inicial, 2), # Techo inicial
        "presupuesto_materiales": round(saldo_disponible_mats, 2),   # Saldo que baja
        "gasto_materiales": round(total_gastado_mats, 2),           # Lo consumido
        "presupuesto_actualizado": datetime.now()
    })
    return saldo_disponible_mats
def cargar_materiales():
    return [{"id": d.id, **d.to_dict()}
            for d in db.collection("materiales").order_by("nombre").stream()]

def obtener_obras():
    return {d.id: d.to_dict().get("nombre", d.id)
            for d in db.collection("obras").stream()}

def cargar_materiales_obra(obra_id):
    return [{"id": d.id, **d.to_dict()}
            for d in db.collection("obras")
            .document(obra_id)
            .collection("materiales")
            .order_by("fecha", direction=firestore.Query.DESCENDING)
            .stream()]

def reset():
    st.session_state.mat_global = None
    st.session_state.mat_obra = None
    st.rerun()

# ================= UI =================
st.title("🧱 Materiales y Presupuesto")

if not st.session_state["vista_materiales_globales"]:
    if st.button("📦 Materiales globales"):
        st.session_state["vista_materiales_globales"] = True
        st.rerun()

# ================= SELECCIÓN DE OBRA SINCRONIZADA =================
OBRAS = obtener_obras()
lista_ids = list(OBRAS.keys())

# 1. Recuperar la selección global de la sesión
if "obra_id_global" not in st.session_state and lista_ids:
    st.session_state["obra_id_global"] = lista_ids[0]

# 2. Calcular el índice para que el selector aparezca en la obra correcta
indice_actual = 0
if st.session_state["obra_id_global"] in lista_ids:
    indice_actual = lista_ids.index(st.session_state["obra_id_global"])

# 3. Dibujar el selector en el sidebar
obra_id = st.sidebar.selectbox(
    "Seleccionar obra",
    options=lista_ids,
    format_func=lambda x: OBRAS.get(x, x),
    index=indice_actual,
    key="selector_materiales_nav"
)

# 4. Actualizar el estado global por si el usuario cambia de obra aquí mismo
st.session_state["obra_id_global"] = obra_id

# 5. Mostrar confirmación visual de la obra activa
st.sidebar.success(f"🏗️ Obra activa: **{OBRAS.get(obra_id)}**")

if not obra_id:
    st.warning("⚠️ No hay obras registradas. Crea una primero en la sección de Obras.")
    st.stop()
# 🔹 Cargar materiales globales UNA SOLA VEZ
materiales = cargar_materiales()

# ================== SECCIÓN A ==================
if st.session_state["vista_materiales_globales"]:

    st.header("📦 Materiales globales")

   
    df_mat = pd.DataFrame(materiales)

    col1, col2 = st.columns([1.5, 1])

    if st.button("⬅️ Volver"):
        st.session_state["vista_materiales_globales"] = False
        st.rerun()

    # ----- LISTA -----
    with col1:
        busq = st.text_input("Buscar material")
        df_v = df_mat if not busq else df_mat[
            df_mat["nombre"].str.contains(busq, case=False)
        ]

        if not df_v.empty:
            sel = st.dataframe(
                df_v[["nombre", "unidad", "precio_unitario"]],
                hide_index=True,
                use_container_width=True,
                selection_mode="single-row",
                on_select="rerun"
            )
            if sel and sel["selection"]["rows"]:
                st.session_state.mat_global = materiales[
                    df_v.index[sel["selection"]["rows"][0]]
                ]
        else:
            st.info("No hay materiales")

    # ----- FORM CRUD -----
    with col2:
        mat = st.session_state.mat_global
        st.subheader("✏️ Editar" if mat else "➕ Nuevo")

        nombre = st.text_input("Nombre", value=mat["nombre"] if mat else "")
        unidad = st.text_input("Unidad", value=mat["unidad"] if mat else "")
        precio = st.number_input(
            "Precio unitario",
            0.0,
            step=0.01,
            value=float(mat["precio_unitario"]) if mat else 0.0
        )

        if mat:
            if st.button("Actualizar", type="primary", use_container_width=True):
                db.collection("materiales").document(mat["id"]).update({
                    "nombre": nombre,
                    "unidad": unidad,
                    "precio_unitario": precio
                })
                reset()

            if st.button("Eliminar", use_container_width=True):
                db.collection("materiales").document(mat["id"]).delete()
                reset()
        else:
            if st.button("Crear material", type="primary", use_container_width=True):
                if nombre and unidad:
                    db.collection("materiales").add({
                        "nombre": nombre,
                        "unidad": unidad,
                        "precio_unitario": precio,
                        "creado": datetime.now()
                    })
                    reset()
                else:
                    st.error("Campos obligatorios")

    # ⛔ IMPORTANTE: corta aquí
    st.stop()


# ================== SECCIÓN B ==================
st.divider()
st.header("➕ Asignar material a la obra")

# Obtener datos de la obra para validar presupuesto
obra_info = db.collection("obras").document(obra_id).get().to_dict()
saldo_mats = float(obra_info.get("presupuesto_materiales", 0))

st.info(f"💰 Saldo disponible para materiales: S/ {saldo_mats:,.2f}")

if materiales:
    mat_sel = st.selectbox(
        "Material",
        options=materiales,
        format_func=lambda x: f"{x['nombre']} ({x['unidad']})"
    )
    cantidad = st.number_input("Cantidad", min_value=1.0, step=1.0)
    costo_total = cantidad * mat_sel["precio_unitario"]

    if st.button("Asignar a obra", type="primary"):
        if costo_total > saldo_mats:
            st.error(f"❌ Presupuesto insuficiente. El costo es S/ {costo_total:,.2f} y solo tienes S/ {saldo_mats:,.2f}")
        else:
            db.collection("obras").document(obra_id).collection("materiales").add({
                "material_id": mat_sel["id"],
                "nombre": mat_sel["nombre"],
                "unidad": mat_sel["unidad"],
                "cantidad": cantidad,
                "precio_unitario": mat_sel["precio_unitario"],
                "subtotal": round(costo_total, 2),
                "fecha": datetime.now()
            })
            recalcular_presupuesto_obra(obra_id)
            st.success("Material asignado y saldo actualizado")
            st.rerun()
# ================== SECCIÓN C ==================
st.divider()
st.header("🧾 Materiales de la obra")

mats_obra = cargar_materiales_obra(obra_id)

if mats_obra:
    df_obra = pd.DataFrame(mats_obra)
    sel = st.dataframe(
        df_obra[["nombre", "unidad", "cantidad", "precio_unitario", "subtotal"]],
        hide_index=True,
        use_container_width=True,
        selection_mode="single-row",
        on_select="rerun"
    )
    if sel and sel["selection"]["rows"]:
        st.session_state.mat_obra = mats_obra[sel["selection"]["rows"][0]]
else:
    st.info("No hay materiales asignados")

# ----- EDITAR MATERIAL OBRA -----
mat_o = st.session_state.mat_obra
if mat_o:
    st.subheader("✏️ Editar material en obra")
    nueva = st.number_input(
        "Cantidad",
        min_value=1.0,
        value=float(mat_o["cantidad"])
    )

    if st.button("Actualizar cantidad", type="primary"):
        db.collection("obras").document(obra_id) \
            .collection("materiales").document(mat_o["id"]).update({
                "cantidad": nueva,
                "subtotal": round(nueva * mat_o["precio_unitario"], 2),
                "fecha": datetime.now()
            })
        # Actualización automática en Firebase
        recalcular_presupuesto_obra(obra_id)
        reset()

    if st.button("Eliminar de la obra"):
        db.collection("obras").document(obra_id) \
            .collection("materiales").document(mat_o["id"]).delete()
        # Actualización automática en Firebase
        recalcular_presupuesto_obra(obra_id)
        reset()

# ================== SECCIÓN D ==================
st.divider()
st.header("📥 Importar materiales desde Excel")

archivo = st.file_uploader("Subir Excel", type=["xlsx", "xls"])

if archivo:
    df_excel = pd.read_excel(archivo)
    columnas = {"nombre", "unidad", "cantidad", "precio_unitario"}
    if not columnas.issubset(df_excel.columns):
        st.error("El Excel debe tener: nombre, unidad, cantidad, precio_unitario")
    else:
        df_excel["subtotal"] = df_excel["cantidad"] * df_excel["precio_unitario"]
        st.dataframe(df_excel, use_container_width=True)

        if st.button("Importar materiales a la obra", type="primary"):
            for _, r in df_excel.iterrows():
                db.collection("obras").document(obra_id).collection("materiales").add({
                    "nombre": r["nombre"],
                    "unidad": r["unidad"],
                    "cantidad": float(r["cantidad"]),
                    "precio_unitario": float(r["precio_unitario"]),
                    "subtotal": round(float(r["cantidad"] * r["precio_unitario"]), 2),
                    "fecha": datetime.now()
                })
            # Actualización automática masiva en Firebase
            recalcular_presupuesto_obra(obra_id)
            st.success("Materiales importados y presupuesto actualizado")
            st.rerun()

# ================== SECCIÓN E ==================
st.divider()
st.header("💰 Estado del Presupuesto de Materiales")

obra_final = db.collection("obras").document(obra_id).get().to_dict()
inicial = float(obra_final.get("presupuesto_materiales_inicial", 0))
actual = float(obra_final.get("presupuesto_materiales", 0))
gastado = float(obra_final.get("gasto_materiales", 0))

c1, c2, c3 = st.columns(3)
c1.metric("Asignado al inicio", f"S/ {inicial:,.2f}")
c2.metric("Saldo Disponible", f"S/ {actual:,.2f}", delta=f"{-gastado:,.2f}", delta_color="inverse")
c3.metric("Total Gastado", f"S/ {gastado:,.2f}")

if actual < (inicial * 0.15):
    st.warning("⚠️ Atención: Queda menos del 15% del presupuesto para materiales.")
# ================== SECCIÓN X ==================
st.divider()
st.header("📤 Exportar materiales de la obra a Excel")

if mats_obra:
    df_export = pd.DataFrame(mats_obra)
    df_export = df_export[["nombre", "unidad", "precio_unitario", "cantidad", "subtotal"]]

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_export.to_excel(writer, index=False, sheet_name="Materiales")
    buffer.seek(0)

    st.download_button(
        label="📥 Descargar Excel",
        data=buffer,
        file_name=f"materiales_{obra_id}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("No hay materiales para exportar")
