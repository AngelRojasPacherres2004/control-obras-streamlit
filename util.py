import base64
import streamlit as st

def set_background(image_file, mobile_image_file=None):
    """
    Aplica imagen de fondo con soporte para versión móvil
    
    Args:
        image_file: Imagen para escritorio
        mobile_image_file: Imagen opcional para móviles
    """
    with open(image_file, "rb") as image:
        encoded_desktop = base64.b64encode(image.read()).decode()
    
    # Si hay imagen móvil, cargarla
    if mobile_image_file:
        with open(mobile_image_file, "rb") as mobile_image:
            encoded_mobile = base64.b64encode(mobile_image.read()).decode()
    else:
        encoded_mobile = encoded_desktop

    css = f"""
    <style>
    /* Imagen de escritorio por defecto */
    .stApp {{
        background-image: url("data:image/jpg;base64,{encoded_desktop}");
        background-size: cover;
        background-repeat: no-repeat;
        background-attachment: fixed;
        background-position: center top;
    }}
    
    /* Imagen específica para móviles */
    @media (max-width: 768px) {{
        .stApp {{
            background-image: url("data:image/jpg;base64,{encoded_mobile}");
            background-size: cover;
            background-position: center center;
        }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)