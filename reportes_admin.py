import streamlit as st
import pandas as pd
from sqlalchemy.orm import Session
from database.connection import SessionLocal
# Importamos tus modelos TAL CUAL los definiste
from database.models import User, Order, Week, Office
# Asumo que verify_password existe en services.auth (como indicaste antes)
from services.auth import verify_password
from services.admin_service import get_now_utc3

# --- CONFIGURACIÓN DE PÁGINA (Aislada de la app principal) ---
st.set_page_config(page_title="Monitor Admin Seguro", page_icon="🔐", layout="wide")

# --- GESTIÓN DE SESIÓN INDEPENDIENTE ---
if 'admin_logged_in' not in st.session_state:
    st.session_state.admin_logged_in = False
if 'admin_name' not in st.session_state:
    st.session_state.admin_name = ""

# --- FUNCIONES DE SEGURIDAD ---
def check_login(username, password):
    """Verifica credenciales contra la base de datos real."""
    db = SessionLocal()
    try:
        # Buscamos usuario
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            return False, "Usuario no encontrado"
        
        # Verificamos hash (Usando tu lógica existente)
        if not verify_password(password, user.password_hash):
            return False, "Contraseña incorrecta"
            
        # Verificamos ROL (Solo admins pueden entrar aquí)
        if user.role != 'admin':
            return False, "Acceso denegado: No tienes permisos de administrador."
            
        return True, user.full_name
    except Exception as e:
        return False, f"Error de conexión: {e}"
    finally:
        db.close()

# --- PANTALLAS ---
def show_login_screen():
    """Login exclusivo para este reporte"""
    st.markdown("### 🔐 Acceso al Monitor de Cumplimiento")
    st.caption("Usa tus credenciales de Administrador actuales.")
    
    with st.form("login_satelite"):
        user_input = st.text_input("Usuario")
        pass_input = st.text_input("Contraseña", type="password")
        
        submitted = st.form_submit_button("Ingresar")
        
        if submitted:
            # Limpieza de inputs (Sanitization)
            clean_user = user_input.strip().lower()
            clean_pass = pass_input.strip()
            
            is_valid, msg = check_login(clean_user, clean_pass)
            if is_valid:
                st.session_state.admin_logged_in = True
                st.session_state.admin_name = msg
                st.success("Acceso concedido.")
                st.rerun()
            else:
                st.error(msg)

def show_dashboard():
    """El Panel de Control de Datos"""
    
    # Header con Logout
    col_head, col_out = st.columns([6, 1])
    with col_head:
        st.title("🕵️ Monitor de Pedidos por Oficina")
        st.caption(f"Sesión activa: {st.session_state.admin_name}")
    with col_out:
        if st.button("Cerrar Sesión"):
            st.session_state.admin_logged_in = False
            st.rerun()
            
    st.markdown("---")
    
    db = SessionLocal()
    try:
        now = get_now_utc3()
        
        # 1. OBTENER SEMANAS
        active_week = db.query(Week).filter(Week.is_open == True, Week.end_date > now).first()
        all_weeks = db.query(Week).order_by(Week.start_date.desc()).all()
        
        if not all_weeks:
            st.warning("No hay semanas registradas.")
            return

        week_options = {f"{w.title} ({w.start_date})" : w.id for w in all_weeks}
        
        # Filtros Superiores
        c_filter1, c_filter2 = st.columns(2)
        
        with c_filter1:
            # Seleccionar semana (Intenta poner la activa por defecto)
            def_index = 0
            if active_week:
                label_active = f"{active_week.title} ({active_week.start_date})"
                if label_active in week_options:
                    def_index = list(week_options.keys()).index(label_active)
            
            sel_week_label = st.selectbox("Seleccionar Semana", list(week_options.keys()), index=def_index)
            sel_week_id = week_options[sel_week_label]
            
            # Objeto de la semana seleccionada (para ver días cerrados)
            selected_week_obj = db.query(Week).filter(Week.id == sel_week_id).first()

        # 2. OBTENER DATOS DE LA DB
        # Usuarios activos y que NO sean admins (nos interesa auditar empleados)
        users = db.query(User).filter(User.is_active == True, User.role != 'admin').all()
        
        # Pedidos de la semana seleccionada
        orders = db.query(Order).filter(Order.week_id == sel_week_id).all()
        # Mapa para búsqueda rápida: {user_id: details_json}
        orders_map = {o.user_id: o.details for o in orders}

        # 3. FILTRO DE OFICINAS DINÁMICO
        # Extraemos oficinas únicas de los usuarios encontrados
        unique_offices = set()
        for u in users:
            if u.office:
                unique_offices.add(u.office.name)
            else:
                unique_offices.add("Sin Oficina")
        
        office_list = sorted(list(unique_offices))
        office_list.insert(0, "Todas las Oficinas")
        
        with c_filter2:
            sel_office = st.selectbox("Filtrar por Oficina", office_list)

        # 4. PROCESAMIENTO LÓGICO
        list_no_order = []
        list_incomplete = []
        
        days_map = {
            "monday": "Lunes", "tuesday": "Martes", "wednesday": "Miércoles", 
            "thursday": "Jueves", "friday": "Viernes"
        }
        
        # Días que NO se deben exigir (Feriados configurados en la semana)
        closed_days_list = selected_week_obj.closed_days if selected_week_obj.closed_days else []

        for user in users:
            # A. Filtro de Oficina
            u_office = user.office.name if user.office else "Sin Oficina"
            if sel_office != "Todas las Oficinas" and u_office != sel_office:
                continue # Saltar este usuario si no es de la oficina seleccionada

            # B. Verificar si tiene pedido
            if user.id not in orders_map:
                # -> NO PIDIÓ NADA
                list_no_order.append({
                    "Nombre": user.full_name,
                    "Usuario": user.username,
                    "Oficina": u_office
                })
            else:
                # -> SÍ PIDIÓ, VERIFICAR COMPLETITUD
                details = orders_map[user.id]
                missing_days = []
                
                for key_day, label_day in days_map.items():
                    # Si el día está cerrado en la configuración de la semana, lo ignoramos
                    if key_day in closed_days_list:
                        continue
                        
                    # Verificamos si seleccionó plato principal
                    val = details.get(f"{key_day}_principal")
                    
                    # Si es None, es que no seleccionó nada (ni siquiera "No comer")
                    if val is None:
                        missing_days.append(label_day)
                
                if missing_days:
                    list_incomplete.append({
                        "Nombre": user.full_name,
                        "Oficina": u_office,
                        "Días Faltantes": ", ".join(missing_days)
                    })

        # 5. RESULTADOS VISUALES
        st.divider()
        
        col_res1, col_res2 = st.columns(2)
        
        with col_res1:
            st.error(f"🔴 Sin Pedido ({len(list_no_order)})")
            if list_no_order:
                st.dataframe(pd.DataFrame(list_no_order), use_container_width=True, hide_index=True)
            else:
                st.success("¡Excelente! Todos en esta oficina han pedido.")

        with col_res2:
            st.warning(f"🟡 Pedido Incompleto ({len(list_incomplete)})")
            st.caption("Usuarios que guardaron pedido pero dejaron días sin seleccionar.")
            if list_incomplete:
                st.dataframe(pd.DataFrame(list_incomplete), use_container_width=True, hide_index=True)
            else:
                st.success("¡Todos los pedidos están completos!")

    except Exception as e:
        st.error(f"Error al procesar datos: {e}")
    finally:
        db.close()

# --- ENTRY POINT ---
if __name__ == "__main__":
    if not st.session_state.admin_logged_in:
        show_login_screen()
    else:
        show_dashboard()
