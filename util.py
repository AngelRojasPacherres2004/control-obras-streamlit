import base64
import streamlit as st

def set_background(image_file):
    """Establece imagen de fondo para una sola imagen"""
    with open(image_file, "rb") as image:
        encoded = base64.b64encode(image.read()).decode()

    css = f"""
    <style>
    .stApp {{
        background-image: url("data:image/jpg;base64,{encoded}");
        background-size: cover;
        background-position: center center;
        background-attachment: scroll;
        background-repeat: no-repeat;
        min-height: 100vh;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

def set_background_responsive(desktop_image, mobile_image):
    """Establece imágenes diferentes para desktop y móvil"""
    with open(desktop_image, "rb") as f:
        desktop_data = base64.b64encode(f.read()).decode()
    
    with open(mobile_image, "rb") as f:
        mobile_data = base64.b64encode(f.read()).decode()
    
    st.markdown(f"""
    <style>
    /* ===== Desktop ===== */
    .stApp {{
        background-image: url("data:image/jpg;base64,{desktop_data}");
        background-size: cover;
        background-position: center 40%;
        background-repeat: no-repeat;
        background-attachment: scroll;
        min-height: 100vh;
    }}

    /* ===== Móvil ===== */
    @media (max-width: 768px) {{
        .stApp {{
            background-image: url("data:image/jpg;base64,{mobile_data}") !important;
            background-size: cover !important;        /* 🔥 cover, no contain */
            background-position: center top !important;
            background-attachment: scroll !important;
            background-repeat: no-repeat !important;
        }}
    }}
    </style>
    """, unsafe_allow_html=True)