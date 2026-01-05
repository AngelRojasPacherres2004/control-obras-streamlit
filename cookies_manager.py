import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager

cookies = EncryptedCookieManager(
    prefix="control_obras_",
    password="clave-super-secreta-123"  # 🔐 puedes cambiarla
)

if not cookies.ready():
    st.stop()
