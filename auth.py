import streamlit as st
import streamlit_authenticator as stauth
from firebase_admin import firestore

def login_screen(db):

    users_ref = db.collection("users").stream()

    usernames = []
    names = []
    passwords = []
    roles = {}
    obras = {}

    for doc in users_ref:
        u = doc.to_dict()
        usernames.append(u["username"])
        names.append(u.get("name", u["username"]))
        passwords.append(u["password"])
        roles[u["username"]] = u["role"]
        obras[u["username"]] = u.get("obra")

    authenticator = stauth.Authenticate(
        credentials={
            "usernames": {
                usernames[i]: {
                    "name": names[i],
                    "password": passwords[i]
                }
                for i in range(len(usernames))
            }
        },
        cookie_name="control_obras_auth",
        key="secure_auth",
        cookie_expiry_days=7
    )

    name, auth_status, username = authenticator.login("Iniciar sesión", "main")

    if auth_status is False:
        st.error("Usuario o contraseña incorrectos")

    if auth_status is None:
        st.warning("Ingrese sus credenciales")

    if auth_status:
        st.session_state["auth"] = {
            "username": username,
            "name": name,
            "role": roles[username],
            "obra": obras[username]
        }

        return authenticator

    return None
