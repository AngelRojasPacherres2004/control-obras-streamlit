"""
Módulo de autenticación y pantalla inicial
"""

import streamlit as st
from util import set_background


# ====== PANTALLA INICIAL ======
def mostrar_pantalla_inicial():
    # Usar imagen diferente para móvil
    set_background("Empresalogo.jpg", "Empresalogo_mobile.jpg")

    # CSS para posicionar el botón
    st.markdown("""
    <style>
    /* Ocultar elementos de Streamlit */
    #MainMenu, footer, header {visibility: hidden;}
    
    /* Resetear el contenedor principal */
    .main {
        padding: 0 !important;
    }
    
    /* ========== POSICIÓN VERTICAL (ARRIBA/ABAJO) ========== */
    .block-container {
        padding-top: 36vh !important;  /* 🔽 CAMBIAR AQUÍ PARA MOVER ARRIBA/ABAJO */
                                        /* Valores: 0vh (arriba) a 100vh (abajo) */
                                        /* Ejemplo: 40vh = más arriba, 55vh = más abajo */
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
    }
    
    /* ========== POSICIÓN HORIZONTAL (IZQUIERDA/DERECHA) ========== */
    div[data-testid="stButton"] {
        width: 350px !important;
        max-width: 70% !important;
        margin-left: auto !important;   /* 🔽 CAMBIAR AQUÍ PARA MOVER IZQUIERDA/DERECHA */
        margin-right: auto !important;  /* 🔽 Y AQUÍ */
        
        /* OPCIONES:
           CENTRADO:  margin-left: auto;    margin-right: auto;
           IZQUIERDA: margin-left: 0;       margin-right: auto;
           DERECHA:   margin-left: auto;    margin-right: 0;
           OFFSET:    margin-left: 50px;    margin-right: auto;  (50px desde izquierda)
        */
    }
    
    /* Estilo del botón */
    .stButton button {
        background-color: rgba(0, 0, 0, 0.8) !important;
        color: white !important;
        border: 2px solid white !important;
        font-size: 18px !important;
        padding: 12px 24px !important;
        border-radius: 8px !important;
        width: 100% !important;
    }
    
    /* ========== RESPONSIVE PARA MÓVILES ========== */
    @media (max-width: 768px) {
        /* VERTICAL para móvil */
        .block-container {
            padding-top: 32vh !important;  /* 🔽 CAMBIAR AQUÍ PARA MOVER ARRIBA/ABAJO EN MÓVIL */
        }
        
        /* HORIZONTAL para móvil */
        div[data-testid="stButton"] {
            max-width: 85% !important;
            margin-left: auto !important;   /* 🔽 CAMBIAR AQUÍ PARA MOVER IZQ/DER EN MÓVIL */
            margin-right: auto !important;  /* 🔽 Y AQUÍ */
        }
    }
    </style>
    """, unsafe_allow_html=True)

    if st.button("Iniciar Sesión", use_container_width=True, key="btn_pantalla_inicial"):
        st.session_state.show_login = True
        st.rerun()


# ====== LOGIN CON FIREBASE ======
def verificar_autenticacion(db):
    if "auth" not in st.session_state:
        # Mantener la misma imagen de fondo
        set_background("Empresalogo.jpg", "Empresalogo_mobile.jpg")

        st.markdown("""
        <style>
        /* Ocultar elementos de Streamlit */
        #MainMenu, footer, header {visibility: hidden;}
        
        /* ========== FORMULARIO ESCRITORIO (COMPACTO) ========== */
        .block-container {
            padding-top: 38vh !important;  /* 🖥️ ARRIBA/ABAJO FORMULARIO ESCRITORIO */
            max-width: 450px !important;   /* 🖥️ ANCHO MÁXIMO DEL FORMULARIO */
            margin: 0 auto !important;     /* Centrar horizontalmente */
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
        }
        
        /* Título más compacto */
        h1 {
            color: white !important;
            text-shadow: 2px 2px 8px rgba(0, 0, 0, 0.8) !important;
            text-align: center !important;
            font-size: 20px !important;    /* 🖥️ TAMAÑO TÍTULO */
            margin-bottom: 20px !important;
        }
        
        /* Labels blancos con sombra */
        label {
            color: white !important;
            text-shadow: 1px 1px 4px rgba(0, 0, 0, 0.8) !important;
            font-weight: bold !important;
            font-size: 10px !important;    /* 🖥️ TAMAÑO LABELS */
        }
        
        /* Inputs compactos */
        input {
            background-color: rgba(255, 255, 255, 0.95) !important;
            color: #000000 !important;
            border: 2px solid white !important;
            border-radius: 8px !important;
            padding: 10px !important;      /* 🖥️ PADDING INPUTS */
            font-size: 8px !important;    /* 🖥️ TAMAÑO TEXTO INPUTS */
        }
        
        /* Espaciado entre campos */
        div[data-testid="stTextInput"] {
            margin-bottom: 0px !important;
        }
        
        /* Botón de ingresar */
        .stButton button {
            background-color: rgba(0, 0, 0, 0.8) !important;
            color: white !important;
            border: 2px solid white !important;
            font-size: 8px !important;    /* 🖥️ TAMAÑO BOTÓN */
            padding: 10px 20px !important; /* 🖥️ PADDING BOTÓN */
            border-radius: 8px !important;
            margin-top: 10px !important;
        }
        
        /* Mensajes de error compactos */
        .stAlert {
            background-color: rgba(255, 255, 255, 0.95) !important;
            font-size: 14px !important;
            padding: 10px !important;
        }
        
        /* ========== FORMULARIO MÓVIL (SIN CAMBIOS) ========== */
        @media (max-width: 768px) {
            .block-container {
                padding-top: 38vh !important;  /* 📱 ARRIBA/ABAJO FORMULARIO MÓVIL */
                max-width: 90% !important;     /* Usa más ancho en móvil */
            }
            
            h1 {
                font-size: 24px !important;
            }
            
            input {
                font-size: 16px !important;
            }
            
            .stButton button {
                font-size: 16px !important;
                padding: 14px 20px !important;
            }
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.title("CONTROL DE OBRAS 2025")

        username = st.text_input("Usuario", key="input_user")
        password = st.text_input("Contraseña", type="password", key="input_pass")

        if st.button("INGRESAR", key="btn_login", use_container_width=True):
            user_doc = db.collection("users").document(username).get()

            if not user_doc.exists:
                st.error("Usuario no existe")
                return False

            data = user_doc.to_dict()

            if password != data.get("password"):
                st.error("Contraseña incorrecta")
                return False

            st.session_state["auth"] = {
                "username": data["username"],
                "role": data["role"],
                "obra": data.get("obra")
            }
            st.rerun()

        return False