import streamlit as st
from database.connection import SessionLocal, init_db
from services.auth import authenticate_user 
from views.user_panel import user_dashboard
from views.admin_panel import admin_dashboard
from views.user_management import user_management_dashboard 
from views.audit_logs import audit_log_page # ⬅️ Importación necesaria
import os
from database.connection import init_db

# --- AUTO-SETUP PARA LA NUBE ---
# Si no existe la carpeta data, la creamos
if not os.path.exists('data'):
    os.makedirs('data')

# Si no existe la DB, la inicializamos
if not os.path.exists('data/db.sqlite'):
    init_db()
    # Opcional: Aquí podrías llamar a tu seed si quisieras
# -------------------------------

# Configuración inicial
st.set_page_config(page_title="Basdonax Food", layout="wide")

init_db()

# Aseguramos que todas las claves de sesión necesarias existan
if "token" not in st.session_state:
    st.session_state.token = None
    st.session_state.user = None
    st.session_state.user_id = None # Aseguramos que el ID exista
    st.session_state.role = None
    st.session_state.nav_index = 0

def main():
    # --- LOGIN ---
    if not st.session_state.token:
        st.title("🔒 Techline – Menú Semanal")
        col1, col2 = st.columns([1,2])
        with col1:
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            if st.button("Entrar"):
                db = SessionLocal()
                user = authenticate_user(db, username, password) 
                db.close()
                
                if user:
                    st.session_state.token = True
                    st.session_state.user = user.username
                    st.session_state.user_id = user.id
                    st.session_state.role = user.role
                    st.session_state.name = user.full_name # Usaremos el nombre completo en la sidebar
                    st.rerun()
                else:
                    st.error("Credenciales inválidas")
        return

    # --- SIDEBAR (USUARIO LOGUEADO) ---
    
    # Usamos st.session_state.user para el nombre de usuario
    st.sidebar.title(f"Hola, {st.session_state.user} 👋") 
    
    # ----------------------------------------------------
    # --- LÓGICA DE NAVEGACIÓN ACTUALIZADA ---
    # ----------------------------------------------------
    
    # 1. Definir opciones base
    navigation_options = ["🏠 Menú Semanal"] # Opción base para todos (User Panel)
    
    # 2. Agregar opciones de Admin
    if st.session_state.role == "admin":
        navigation_options.append("📋 Panel de Gestión")
        navigation_options.append("👥 Gestión Usuarios")
        navigation_options.append("📊 Admin Logs") # ⬅️ AÑADIMOS LA NUEVA PÁGINA
        
    # 3. Opción de cierre al final
    navigation_options.append("🚪 Cerrar Sesión") 
    
    # 4. Mostrar radio button y mantener el índice
    selection = st.sidebar.radio("Navegación", navigation_options, index=st.session_state.get('nav_index', 0))
    st.session_state['nav_index'] = navigation_options.index(selection)

    st.sidebar.markdown("---")
    
    # ----------------------------------------------------
    # --- ROUTING BASADO EN LA SELECCIÓN ---
    # ----------------------------------------------------
    
    if selection == "🚪 Cerrar Sesión":
        st.session_state.clear()
        st.rerun()
        
    elif selection == "🏠 Menú Semanal":
        # Todos (Admin y User) ven la vista del usuario por defecto
        user_dashboard(SessionLocal, st.session_state.user_id)

    # Vistas exclusivas de Admin
    elif st.session_state.role == "admin":
        
        if selection == "📋 Panel de Gestión":
            admin_dashboard(SessionLocal)
            
        elif selection == "👥 Gestión Usuarios":
            user_management_dashboard(SessionLocal)
            
        elif selection == "📊 Admin Logs":
            # ⬅️ VISTA DE LOGS DE AUDITORÍA
            audit_log_page(SessionLocal, st.session_state.user) 
            
    # Si por alguna razón no es admin y no seleccionó el menú, mostramos el panel de usuario
    else:
        user_dashboard(SessionLocal, st.session_state.user_id)


if __name__ == "__main__":
    main()