import streamlit as st
from database.connection import SessionLocal
from services.auth import authenticate_user
from views.admin_panel import admin_dashboard
from views.user_panel import user_dashboard
from views.audit_logs import audit_log_page # Opcional, si quieres una vista separada
from views.user_management import user_management_dashboard # Opcional

# Configuración de la página (Debe ser lo primero)
st.set_page_config(
    page_title="Sistema de Pedidos",
    page_icon="🍽️",
    layout="wide"
)

def main():
    # 1. Inicializar variables de sesión si no existen
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "role" not in st.session_state:
        st.session_state.role = None
    if "user_name" not in st.session_state:
        st.session_state.user_name = None

    # 2. Lógica de Logout (Botón en la barra lateral si está logueado)
    if st.session_state.user_id:
        with st.sidebar:
            st.write(f"👤 **{st.session_state.user_name}**")
            st.write(f"Rol: {st.session_state.role}")
            if st.button("🚪 Cerrar Sesión"):
                st.session_state.user_id = None
                st.session_state.role = None
                st.session_state.user_name = None
                st.rerun()

    # 3. CONTROL DE FLUJO PRINCIPAL (Router)
    
    # CASO A: NO LOGUEADO -> MOSTRAR LOGIN
    if not st.session_state.user_id:
        show_login_screen()
        

    # CASO B: LOGUEADO -> MOSTRAR PANEL SEGÚN ROL
    else:
        # Check if the user is an admin
        if st.session_state.role == "admin":
            
            # --- BLOQUE ACTUALIZADO DE NAVEGACIÓN ---
            menu_admin = st.sidebar.radio(
                "Navegación Admin", 
                # Se añade la opción "Mi Pedido (Vista Usuario)"
                ["Gestionar Semanas/Menú", "Usuarios", "Auditoría", "Mi Pedido (Vista Usuario)"] 
            )
            # --- FIN BLOQUE ACTUALIZADO ---
            
            if menu_admin == "Gestionar Semanas/Menú":
                admin_dashboard(SessionLocal)
            elif menu_admin == "Usuarios":
                user_management_dashboard(SessionLocal)
            elif menu_admin == "Auditoría":
                audit_log_page(SessionLocal, st.session_state.user_name)
            
            # --- NUEVA LÓGICA PARA VER EL PANEL DE USUARIO ---
            elif menu_admin == "Mi Pedido (Vista Usuario)":
                st.subheader("👤 Modo de Prueba: Realizar Pedido")
                # Se llama la función del panel de usuario, permitiendo al admin ordenar para sí mismo.
                user_dashboard(SessionLocal, st.session_state.user_id)
                
        # If the user is a regular user
        elif st.session_state.role == "user":
            user_dashboard(SessionLocal, st.session_state.user_id)
        
        else:
            st.error("Rol desconocido. Contacte soporte.")

# --- PANTALLA DE LOGIN ---
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
                    st.rerun() # Recargar la página para entrar al dashboard
                else:
                    st.error("❌ Usuario o contraseña incorrectos")

if __name__ == "__main__":
    main()