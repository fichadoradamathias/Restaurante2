# views/user_management.py
import streamlit as st
from database.models import User
from services.auth import create_user, update_user_details, reset_user_password
from services.admin_service import get_all_offices # Importamos función para obtener oficinas
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

    # Pre-cargamos las oficinas disponibles
    offices_list = get_all_offices(db)
    # Diccionario Nombre -> ID para facilitar los selectbox
    office_map = {o.name: o.id for o in offices_list} if offices_list else {}

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
            # Mostramos Login, Nombre, Rol y Oficina
            user_data = []
            for u in users:
                off_name = u.office.name if u.office else "Sin Oficina"
                user_data.append({
                    "ID": u.id, 
                    "Usuario (Login)": u.username, 
                    "Nombre": u.full_name, 
                    "Rol": u.role, 
                    "Oficina": off_name,
                    "Activo": u.is_active
                })
            
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
                
                c1, c2 = st.columns(2)
                new_username = c1.text_input("Usuario (Login)", value=target_user.username, help="Nombre para iniciar sesión")
                new_name = c2.text_input("Nombre Completo", value=target_user.full_name)
                
                c3, c4 = st.columns(2)
                new_role = c3.selectbox("Rol", ["user", "admin"], index=0 if target_user.role == "user" else 1)
                
                # Selector de Oficina con valor actual por defecto
                current_off_index = 0
                if target_user.office and target_user.office.name in office_map:
                    keys_list = list(office_map.keys())
                    current_off_index = keys_list.index(target_user.office.name)
                
                selected_office_name = c4.selectbox("Oficina", list(office_map.keys()), index=current_off_index)
                selected_office_id = office_map.get(selected_office_name)

                new_status = st.toggle("Usuario Activo", value=target_user.is_active)
                
                if st.form_submit_button("💾 Guardar Cambios"):
                    # Llamamos a update_user_details pasando el office_id
                    success, msg = update_user_details(db, target_id, new_username, new_name, selected_office_id, new_role, new_status)
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
                        success, msg = reset_user_password(db, target_id, new_pass_reset, actor_id) 
                        if success: st.success(msg)
                        else: st.error(msg)
                    else:
                        st.warning("Escribe una contraseña.")

    # --- TAB 2: CREAR NUEVO ---
    with tab_create:
        st.subheader("Registrar Nuevo Usuario")
        with st.form("create_user_form_main", clear_on_submit=True):
            c1, c2 = st.columns(2)
            new_user = c1.text_input("Usuario (Login)")
            new_pass = c2.text_input("Contraseña Inicial", type="password")
            
            c3, c4 = st.columns(2)
            new_name = c3.text_input("Nombre Completo")
            new_role = c4.selectbox("Rol", ["user", "admin"])
            
            # Selector de Oficina para nuevo usuario
            if not office_map:
                st.warning("⚠️ No hay oficinas creadas. Ve a 'Gestionar Semanas/Menú' -> Pestaña Oficinas para crear una.")
                sel_office_id_new = None
            else:
                sel_office_name_new = st.selectbox("Oficina Asignada", list(office_map.keys()))
                sel_office_id_new = office_map.get(sel_office_name_new)
            
            if st.form_submit_button("Crear Usuario"):
                if new_user and new_pass and new_name and sel_office_id_new:
                    # Pasamos el office_id a la función create_user
                    success, msg = create_user(db, new_user, new_name, new_pass, sel_office_id_new, new_role)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("Todos los campos son obligatorios (incluyendo Oficina).")

    db.close()
