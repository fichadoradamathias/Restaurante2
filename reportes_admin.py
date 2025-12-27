import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from database.connection import SessionLocal
# Importamos modelos
from database.models import User, Order, Week, Office
from services.admin_service import get_now_utc3

# --- IMPORTACIÓN DIRECTA DE SEGURIDAD ---
# Usamos esto directamente para evitar problemas de importación con services.auth
from passlib.context import CryptContext

# Configuramos el encriptador igual que en tu app principal
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Monitor Admin Seguro", page_icon="🔐", layout="wide")

# --- GESTIÓN DE SESIÓN ---
if 'admin_logged_in' not in st.session_state:
    st.session_state.admin_logged_in = False
if 'admin_name' not in st.session_state:
    st.session_state.admin_name = ""

# --- FUNCIONES DE SEGURIDAD CON DEBUG ---
def verify_password_direct(plain_password, hashed_password):
    """Verifica contraseña usando la librería directamente."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        st.error(f"Error técnico en la librería de encriptación: {e}")
        return False

def check_login_debug(username, password):
    """Verifica credenciales con mensajes de diagnóstico en pantalla."""
    db = SessionLocal()
    try:
        # 1. BÚSQUEDA DE USUARIO
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            return False, f"❌ El usuario '{username}' NO existe en la base de datos."
        
        # 2. DIAGNÓSTICO DE HASH (Solo visible si falla)
        # Mostramos los primeros 10 caracteres del hash para ver si está encriptado
        hash_preview = str(user.password_hash)[:15] + "..."
        
        # 3. VERIFICACIÓN DE CONTRASEÑA
        is_correct = verify_password_direct(password, user.password_hash)
        
        if not is_correct:
            # Mensaje detallado para ti (el admin)
            return False, (f"❌ Contraseña incorrecta.\n\n"
                           f"Diagnóstico:\n"
                           f"- Usuario encontrado: SÍ\n"
                           f"- Hash en DB empieza con: '{hash_preview}'\n"
                           f"- ¿Es bcrypt?: {'Sí' if hash_preview.startswith('$2b$') else 'No/Dudoso'}")

        # 4. VERIFICACIÓN DE ROL
        if user.role != 'admin':
            return False, f"⛔ Usuario '{username}' encontrado, pero su rol es '{user.role}' (Se requiere 'admin')."
            
        return True, user.full_name
        
    except Exception as e:
        return False, f"Error CRÍTICO de conexión DB: {e}"
    finally:
        db.close()

# --- PANTALLAS ---
def show_login_screen():
    st.markdown("### 🔐 Monitor de Cumplimiento (Modo Diagnóstico)")
    st.info("Ingresa tus datos. Si falla, verás un mensaje técnico detallado.")
    
    with st.form("login_satelite"):
        user_input = st.text_input("Usuario")
        pass_input = st.text_input("Contraseña", type="password")
        
        submitted = st.form_submit_button("Ingresar")
        
        if submitted:
            # Limpieza estándar
            clean_user = user_input.strip().lower()
            # La contraseña va CRUDDA (sin strip) por si tiene espacios
            raw_pass = pass_input 
            
            is_valid, msg = check_login_debug(clean_user, raw_pass)
            
            if is_valid:
                st.session_state.admin_logged_in = True
                st.session_state.admin_name = msg
                st.success("✅ Acceso concedido.")
                st.rerun()
            else:
                st.error(msg)

def show_dashboard():
    # --- CABECERA ---
    col_head, col_out = st.columns([6, 1])
    with col_head:
        st.title("🕵️ Monitor de Pedidos")
        st.caption(f"Conectado como: {st.session_state.admin_name}")
    with col_out:
        if st.button("Cerrar Sesión"):
            st.session_state.admin_logged_in = False
            st.rerun()
    st.markdown("---")
    
    # --- LOGICA DE DATOS ---
    db = SessionLocal()
    try:
        now = get_now_utc3()
        
        # 1. SEMANAS
        active_week = db.query(Week).filter(Week.is_open == True, Week.end_date > now).first()
        all_weeks = db.query(Week).order_by(Week.start_date.desc()).all()
        
        if not all_weeks:
            st.warning("No hay semanas registradas.")
            return

        week_options = {f"{w.title} ({w.start_date})" : w.id for w in all_weeks}
        
        # Filtros
        c_filter1, c_filter2 = st.columns(2)
        with c_filter1:
            def_index = 0
            if active_week:
                label_active = f"{active_week.title} ({active_week.start_date})"
                if label_active in week_options:
                    def_index = list(week_options.keys()).index(label_active)
            
            sel_week_label = st.selectbox("Seleccionar Semana", list(week_options.keys()), index=def_index)
            sel_week_id = week_options[sel_week_label]
            selected_week_obj = db.query(Week).filter(Week.id == sel_week_id).first()

        # 2. DATA
        users = db.query(User).filter(User.is_active == True, User.role != 'admin').all()
        orders = db.query(Order).filter(Order.week_id == sel_week_id).all()
        orders_map = {o.user_id: o.details for o in orders}

        # 3. FILTRO OFICINA
        unique_offices = set()
        for u in users:
            if u.office: unique_offices.add(u.office.name)
            else: unique_offices.add("Sin Oficina")
        
        office_list = sorted(list(unique_offices))
        office_list.insert(0, "Todas las Oficinas")
        
        with c_filter2:
            sel_office = st.selectbox("Filtrar por Oficina", office_list)

        # 4. PROCESAR LISTAS
        list_no_order = []
        list_incomplete = []
        days_map = {"monday": "Lunes", "tuesday": "Martes", "wednesday": "Miércoles", "thursday": "Jueves", "friday": "Viernes"}
        closed_days_list = selected_week_obj.closed_days if selected_week_obj.closed_days else []

        for user in users:
            u_office = user.office.name if user.office else "Sin Oficina"
            if sel_office != "Todas las Oficinas" and u_office != sel_office: continue

            if user.id not in orders_map:
                list_no_order.append({"Nombre": user.full_name, "Usuario": user.username, "Oficina": u_office})
            else:
                details = orders_map[user.id]
                missing_days = []
                for key_day, label_day in days_map.items():
                    if key_day in closed_days_list: continue
                    if details.get(f"{key_day}_principal") is None:
                        missing_days.append(label_day)
                if missing_days:
                    list_incomplete.append({"Nombre": user.full_name, "Oficina": u_office, "Días Faltantes": ", ".join(missing_days)})

        # 5. MOSTRAR
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.error(f"🔴 Sin Pedido ({len(list_no_order)})")
            if list_no_order: st.dataframe(pd.DataFrame(list_no_order), use_container_width=True, hide_index=True)
            else: st.success("¡Todos pidieron!")
        with col2:
            st.warning(f"🟡 Incompletos ({len(list_incomplete)})")
            if list_incomplete: st.dataframe(pd.DataFrame(list_incomplete), use_container_width=True, hide_index=True)
            else: st.success("¡Pedidos completos!")

    except Exception as e:
        st.error(f"Error procesando datos: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    if not st.session_state.admin_logged_in:
        show_login_screen()
    else:
        show_dashboard()
