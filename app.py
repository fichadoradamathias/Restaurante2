# app.py
import streamlit as st
from database.connection import SessionLocal, init_db
from services.auth import authenticate_user
from views.admin_panel import admin_dashboard
from views.user_panel import user_dashboard
from views.user_management import user_management_dashboard
# Importamos la función crítica para el cierre por horario
from services.admin_service import check_and_auto_close_weeks

# Importación opcional para Auditoría (Manejo de error por si el archivo no está listo)
try:
    from views.audit_logs import audit_log_page
except ImportError:
    audit_log_page = None

# Configuración de la página (Debe ser lo primero)
st.set_page_config(
    page_title="Sistema de Pedidos",
    page_icon="🍽️",
    layout="wide"
)

def show_login_screen():
    st.markdown("<h1 style='text-align: center;'>🔐 Iniciar Sesión</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("login_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Entrar", use_container_width=True)
            
            if submitted:
                db = SessionLocal()
                user = authenticate_user(db, username, password)
                db.close()
                
                if user:
                    # Guardar datos en sesión
                    st.session_state.user_id = user.id
                    st.session_state.role = user.role
                    st.session_state.user_name = user.full_name
                    st.success(f"Bienvenido {user.full_name}")
                    st.rerun() # Recargar para entrar al dashboard
                else:
                    st.error("❌ Usuario o contraseña incorrectos")

def main():
    # --- 1. AUTOMATIZACIÓN DE CIERRE (CRÍTICO) ---
    # Se ejecuta antes de cargar la interfaz para asegurar que si la hora pasó, la semana se cierre.
    try:
        db = SessionLocal()
        closed_count = check_and_auto_close_weeks(db)
        db.close()
        if closed_count > 0:
            print(f"⚠️ SISTEMA: Se cerraron {closed_count} semanas automáticamente por horario.")
    except Exception as e:
        print(f"Error en el chequeo de cierre automático: {e}")

    # --- 2. GESTIÓN DE ESTADO DE SESIÓN ---
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "role" not in st.session_state:
        st.session_state.role = None
    if "user_name" not in st.session_state:
        st.session_state.user_name = None

    # --- 3. LOGOUT (SIDEBAR) ---
    if st.session_state.user_id:
        with st.sidebar:
            st.write(f"👤 **{st.session_state.user_name}**")
            st.caption(f"Rol: {st.session_state.role}")
            if st.button("🚪 Cerrar Sesión", use_container_width=True):
                st.session_state.user_id = None
                st.session_state.role = None
                st.session_state.user_name = None
                st.rerun()
            st.divider()

    # --- 4. ROUTER (NAVEGACIÓN) ---
    
    # CASO A: NO LOGUEADO
    if not st.session_state.user_id:
        show_login_screen()
        
    # CASO B: LOGUEADO
    else:
        # --- ROL ADMIN ---
        if st.session_state.role == "admin":
            menu_options = ["Gestionar Semanas/Menú", "Usuarios", "Mi Pedido (Vista Usuario)"]
            
            # Solo agregamos Auditoría si el módulo cargó correctamente
            if audit_log_page:
                menu_options.insert(2, "Auditoría")

            menu_admin = st.sidebar.radio("Navegación Admin", menu_options)
            
            if menu_admin == "Gestionar Semanas/Menú":
                admin_dashboard(SessionLocal)
            elif menu_admin == "Usuarios":
                user_management_dashboard(SessionLocal)
            elif menu_admin == "Auditoría" and audit_log_page:
                audit_log_page(SessionLocal, st.session_state.user_name)
            elif menu_admin == "Mi Pedido (Vista Usuario)":
                st.subheader("👤 Modo de Prueba: Realizar Pedido")
                # CORRECCIÓN: user_dashboard no recibe user_id como argumento, lo toma de session_state
                user_dashboard(SessionLocal)
                
        # --- ROL USER ---
        elif st.session_state.role == "user":
            user_dashboard(SessionLocal)
        
        else:
            st.error("Rol de usuario desconocido. Contacte soporte.")

if __name__ == "__main__":
    init_db() # Asegura que las tablas existan al arrancar
    main()
