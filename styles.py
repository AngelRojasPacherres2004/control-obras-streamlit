"""
Módulo de estilos CSS para la aplicación
Contiene estilos responsive para móviles y tablets
"""

import streamlit as st


def aplicar_estilos_responsive():
    """
    Aplica estilos CSS para que la app se vea bien en dispositivos móviles
    """
    st.markdown("""
    <style>
    /* ========== ESTILOS RESPONSIVE PARA MÓVIL ========== */
    
    @media (max-width: 768px) {
        /* Botones más grandes y legibles en móvil */
        .stButton button {
            font-size: 16px !important;
            padding: 12px 20px !important;
            width: 100% !important;
        }
        
        /* Títulos más pequeños */
        h1 {
            font-size: 24px !important;
        }
        
        h2 {
            font-size: 20px !important;
        }
        
        /* Inputs de texto más grandes */
        .stTextInput input {
            font-size: 16px !important;
            padding: 12px !important;
        }
        
        /* Reducir padding general */
        .main .block-container {
            padding: 1rem !important;
        }
        
        /* Hacer columnas apilables en móvil */
        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
        }
    }
    
    /* ========== TABLETS (768px - 1024px) ========== */
    
    @media (min-width: 768px) and (max-width: 1024px) {
        .stButton button {
            font-size: 18px !important;
        }
        
        h1 {
            font-size: 28px !important;
        }
    }
    
    </style>
    """, unsafe_allow_html=True)


def aplicar_estilos_pantalla_inicial():
    """
    Estilos específicos para la pantalla inicial con logo
    """
    st.markdown("""
    <style>
    /* Logo responsive */
    @media (max-width: 768px) {
        /* Reducir espaciado en móvil */
        .main .block-container {
            padding-top: 2rem !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)