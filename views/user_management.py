import streamlit as st
from database.models import User
from services.auth import create_user, update_user_details, reset_user_password
from sqlalchemy.orm import Session
import pandas as pd

def user_management_dashboard(db_session_maker):
    st.title("👥 Gestión de Usuarios")
    
    # 1. Validación de sesión para obtener el ID del ACTOR (Admin logueado)
    if 'user_id' not in st.session_state:
        st.error("Error de sesión: ID de actor (Admin) no encontrado.")
        return
        
    # El ID del administrador logueado
    actor_id = st.session_state.user_id 

    db = db_session_maker()

    # Usamos Tabs para separar Crear de Editar
    tab_list, tab_create = st.tabs(["🛠️ Administrar Existentes", "➕ Crear Nuevo"])

    # --- TAB 1: LISTADO Y EDICIÓN ---
    with tab_list:
        st.subheader("Directorio de Usuarios")
        
        # 1. Listado rápido (Dataframe)
        users = db.query(User).all()
        if not users:
            st.info("No hay usuarios registrados.")
        else:
            # Mostramos el Login y el Nombre real
            user_data = [{"ID": u.id, "Usuario (Login)": u.username, "Nombre": u.full_name, "Rol": u.role, "Activo": u.is_active} for u in users]
            st.dataframe(pd.DataFrame(user_data), use_container_width=True)

        st.divider()
        
        # 2. Selector para Editar
        st.subheader("✏️ Modificar Usuario")
        user_options = {f"{u.username} ({u.full_name})": u.id for u in users}
        selected_label = st.selectbox("Seleccione usuario a editar", list(user_options.keys()))
        
        if selected_label:
            target_id = user_options[selected_label]
            target_user = db.query(User).filter(User.id == target_id).first()
            
            # Formulario de Edición de Datos
            with st.form("edit_user_form"):
                st.subheader(f"Editando a: {target_user.full_name}")
                
                # COLUMNAS ACTUALIZADAS: Agregamos el campo Usuario (Login) editable
                c1, c2 = st.columns(2)
                new_username = c1.text_input("Usuario (Login)", value=target_user.username, help="Este es el nombre para iniciar sesión")
                new_name = c2.text_input("Nombre Completo", value=target_user.full_name)
                
                c3, c4 = st.columns(2)
                new_role = c3.selectbox("Rol", ["user", "admin"], index=0 if target_user.role == "user" else 1)
                new_status = c4.toggle("Usuario Activo", value=target_user.is_active)
                
                if st.form_submit_button("💾 Guardar Cambios"):
                    # Pasamos el new_username a la función actualizada
                    success, msg = update_user_details(db, target_id, new_username, new_name, new_role, new_status)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            
            # Sección Peligrosa: Reset Password
            with st.expander(f"🔐 Resetear Contraseña para {target_user.username}"):
                st.warning("Esta acción cambiará la contraseña inmediatamente.")
                new_pass_reset = st.text_input("Nueva Contraseña Provisoria", type="password", key=f"reset_{target_id}")
                if st.button("Confirmar Cambio de Contraseña"):
                    if new_pass_reset:
                        # 💥 LOGICA DE AUDITORÍA: Llamada a la función con el actor_id
                        success, msg = reset_user_password(db, target_id, new_pass_reset, actor_id) 
                        
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                    else:
                        st.warning("Escribe una contraseña.")

    # --- TAB 2: CREAR NUEVO ---
    with tab_create:
        st.subheader("Registrar Nuevo Usuario")
        with st.form("create_user_form_main", clear_on_submit=True):
            c1, c2 = st.columns(2)
            new_user = c1.text_input("Usuario (Login)")
            new_pass = c2.text_input("Contraseña Inicial", type="password")
            new_name = st.text_input("Nombre Completo")
            new_role = st.selectbox("Rol", ["user", "admin"])
            
            if st.form_submit_button("Crear Usuario"):
                if new_user and new_pass and new_name:
                    success, msg = create_user(db, new_user, new_name, new_pass, new_role)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("Todos los campos son obligatorios.")

    db.close()