import streamlit as st

def load_styles():
    st.markdown("""
    <style>
    /* ===== LOGIN TEXTOS ===== */

    .stTextInput label {
        color: #000000 !important;
        font-weight: 600;
    }

    .stTextInput input {
        color: #000000 !important;
    }

    .stTextInput input::placeholder {
        color: rgba(0, 0, 0, 0.5);
    }

    /* ===== TITULO LOGIN ===== */
    h1#control-de-obras-2025 {
        color: #000000  !important;
    }
                
    /* ===== TEXTO DENTRO INPUT ===== */
    .stTextInput input {
        color: #ffffff !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ================= ESTILOS =================
def set_login_background():
    img_url = "https://res.cloudinary.com/ddqe5f2br/image/upload/v1766781058/logo_xevz4h.jpg"

    st.markdown(
        f"""
        <style>
        html, body {{
            width: 100%;
            height: 100%;
            margin: 0;
        }}

        /* CONTENEDOR PRINCIPAL */
        .stApp {{
            min-height: 100vh;
            display: flex;
            flex-direction: row;
            background: #0e1117;
        }}

        /* PANEL IZQUIERDO (LOGIN) */
        div[data-testid="stVerticalBlock"] {{
            width: 40%;
             min-height: 90vh;
            min-width: 420px;
            background: rgba(255,255,255,0.96);
            padding: 4rem;
            margin: auto 0 auto 5%;
            border-radius: 0px;
            box-shadow: 0 20px 50px rgba(0,0,0,.5);
        }}

        /* PANEL DERECHO (IMAGEN) */
        .stApp::after {{
            content: "";
             position: absolute;      /* ⬅️ necesario */
             top: 13%;                /* ⬅️ mueve la imagen hacia abajo */
             right: 460;    
            width: 90%;    /* ⬅️ más ancho contenedor */  
            height: 90vh;
            background-image: url("{img_url}");
            background-repeat: no-repeat;
            background-size: contain;
 pointer-events: none;  /* ⚡ permite clics en los inputs */
            background-position:  center right;
             background-position: right top ;
          
        }}

        /* TEXTO */
        h1, label {{
            color: #000000 !important;
        }}

  
        </style>
        """,
        unsafe_allow_html=True
    )
