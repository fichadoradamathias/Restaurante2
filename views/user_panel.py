# views/user_panel.py
import streamlit as st
from sqlalchemy.orm import Session
from database.models import Week, MenuItem, Order
from datetime import datetime, timedelta

# Importamos la utilidad de hora UTC-3 para estar sincronizados con el Admin
from services.admin_service import get_now_utc3

def get_menu_options(db: Session, week_id: int):
    """Obtiene los ítems del menú organizados por día y tipo."""
    items = db.query(MenuItem).filter(MenuItem.week_id == week_id).all()
    menu = {}
    days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    types = ["principal", "side", "salad"]
    
    # Inicializar estructura
    for d in days:
        menu[d] = {t: [] for t in types}
        
    for item in items:
        if item.day in menu and item.type in menu[item.day]:
            menu[item.day][item.type].append(item)
            
    return menu

def save_order_logic(db: Session, user_id: int, week_id: int, order_data: dict):
    """Guarda o actualiza el pedido del usuario."""
    try:
        # Verificar si ya existe orden
        existing_order = db.query(Order).filter(
            Order.user_id == user_id, 
            Order.week_id == week_id
        ).first()

        if existing_order:
            existing_order.details = order_data
            existing_order.status = "actualizado"
            msg = "✅ Pedido actualizado correctamente."
        else:
            new_order = Order(
                user_id=user_id,
                week_id=week_id,
                status="confirmado",
                details=order_data
            )
            db.add(new_order)
            msg = "✅ Pedido enviado exitosamente."
        
        db.commit()
        return True, msg
    except Exception as e:
        db.rollback()
        return False, f"Error al guardar: {e}"

def user_dashboard(db_session_maker):
    # Verificación de seguridad básica
    if 'user_id' not in st.session_state:
        st.error("Por favor inicia sesión.")
        return

    user_id = st.session_state.user_id
    db: Session = db_session_maker()

    # 1. OBTENER SEMANA ACTIVA
    # Buscamos semana abierta Y que el tiempo actual (UTC-3) sea menor a la fecha de cierre
    now_utc3 = get_now_utc3()
    
    current_week = db.query(Week).filter(
        Week.is_open == True, 
        Week.end_date > now_utc3
    ).order_by(Week.start_date.desc()).first()

    # --- SI NO HAY SEMANA DISPONIBLE ---
    if not current_week:
        st.info(f"🚫 No hay semanas habilitadas para pedidos en este momento.")
        # Mostramos la hora del servidor para que el usuario entienda por qué
        st.caption(f"Hora actual del sistema (UTC-3): {now_utc3.strftime('%d/%m/%Y %H:%M')}")
        db.close()
        return

    # --- 2. CONTADOR REGRESIVO ---
    st.title(f"🍽️ Menú: {current_week.title}")
    
    # Cálculos de tiempo restante
    time_left = current_week.end_date - now_utc3
    days = time_left.days
    seconds = time_left.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    time_str = f"{days} días, {hours} horas y {minutes} minutos"
    
    # Lógica Visual: Alerta Roja si falta poco (menos de 2 horas y 0 días)
    if days == 0 and hours < 2:
        st.error(f"🔥 ¡Atención! Cierre inminente. Quedan: {hours}h {minutes}m")
    else:
        st.info(f"⏳ Tienes tiempo para pedir. Cierre en: {time_str}")

    st.markdown("---")

    # --- 3. FORMULARIO DE PEDIDO ---
    
    # Recuperar pedido existente si lo hay para pre-llenar
    existing_order = db.query(Order).filter(
        Order.user_id == user_id, 
        Order.week_id == current_week.id
    ).first()

    current_details = existing_order.details if existing_order else {}
    
    if existing_order:
        st.success(f"📋 Ya tienes un pedido registrado (Estado: {existing_order.status}). Puedes modificarlo abajo.")

    # Obtener opciones del menú desde la DB
    menu_data = get_menu_options(db, current_week.id)
    
    day_labels = {
        "monday": "Lunes", "tuesday": "Martes", "wednesday": "Miércoles",
        "thursday": "Jueves", "friday": "Viernes"
    }

    # Inicio del Formulario
    with st.form("order_form"):
        user_selections = {}
        
        for day_code, day_name in day_labels.items():
            st.subheader(f"📅 {day_name}")
            
            # --- PLATO PRINCIPAL ---
            mains = menu_data.get(day_code, {}).get("principal", [])
            # Creamos un diccionario {Texto a mostrar : ID}
            main_opts = {f"Opción {m.option_number}: {m.description}": m.id for m in mains}
            main_opts["❌ No comeré hoy"] = None
            
            # Lógica para pre-seleccionar lo que el usuario ya había pedido
            prev_main = current_details.get(f"{day_code}_principal")
            idx_main = 0 # Default: primera opción
            
            # Buscamos el índice correspondiente al valor guardado
            if prev_main:
                # Si el valor guardado está en las opciones actuales
                if prev_main in main_opts.values():
                    # Truco para obtener el índice basado en el valor
                    values_list = list(main_opts.values())
                    idx_main = values_list.index(prev_main)
                else:
                    # Si el plato ya no existe, volvemos al default
                    idx_main = 0 
            else:
                # Si prev_main es None o no existe, seleccionamos la opción "No comeré hoy" (la última) si queremos que sea default,
                # o la primera opción si queremos incentivar comer.
                # Aquí dejamos logicamente la primera opción del menú como default visual, o la ultima si queremos 'No comer'.
                # Generalmente Streamlit selecciona el index 0.
                pass

            sel_main_label = st.radio(
                f"Plato Principal ({day_name})", 
                list(main_opts.keys()), 
                index=idx_main,
                key=f"{day_code}_main",
                horizontal=False
            )
            user_selections[f"{day_code}_principal"] = main_opts[sel_main_label]

            # --- ACOMPAÑAMIENTOS Y ENSALADAS ---
            # Solo mostramos selects si el usuario eligió un plato (ID no es None)
            if user_selections[f"{day_code}_principal"] is not None:
                c1, c2 = st.columns(2)
                
                # Side (Guarnición)
                sides = menu_data.get(day_code, {}).get("side", [])
                if sides:
                    side_opts = {f"{s.description}": s.id for s in sides}
                    side_opts["Ninguno"] = None
                    
                    prev_side = current_details.get(f"{day_code}_side")
                    # Index logic
                    idx_side = 0
                    if prev_side in side_opts.values():
                        idx_side = list(side_opts.values()).index(prev_side)
                    else:
                        idx_side = len(side_opts) - 1 # Default a Ninguno

                    sel_side = c1.selectbox(f"Acompañamiento ({day_name})", list(side_opts.keys()), index=idx_side)
                    user_selections[f"{day_code}_side"] = side_opts[sel_side]
                else:
                    user_selections[f"{day_code}_side"] = None

                # Salad (Ensalada)
                salads = menu_data.get(day_code, {}).get("salad", [])
                if salads:
                    salad_opts = {f"{s.description}": s.id for s in salads}
                    salad_opts["Ninguna"] = None
                    
                    prev_salad = current_details.get(f"{day_code}_salad")
                    # Index logic
                    idx_salad = 0
                    if prev_salad in salad_opts.values():
                        idx_salad = list(salad_opts.values()).index(prev_salad)
                    else:
                        idx_salad = len(salad_opts) - 1 # Default a Ninguna
                    
                    sel_salad = c2.selectbox(f"Ensalada ({day_name})", list(salad_opts.keys()), index=idx_salad)
                    user_selections[f"{day_code}_salad"] = salad_opts[sel_salad]
                else:
                    user_selections[f"{day_code}_salad"] = None
            else:
                # Si eligió "No comeré hoy", forzamos None en los extras
                user_selections[f"{day_code}_side"] = None
                user_selections[f"{day_code}_salad"] = None
            
            st.divider()

        # Botón de envío
        submitted = st.form_submit_button("💾 Enviar Pedido Completo", type="primary")
        
        if submitted:
            success, msg = save_order_logic(db, user_id, current_week.id, user_selections)
            if success:
                st.success(msg)
                st.balloons()
                # Recargar para mostrar estado actualizado
                st.rerun()
            else:
                st.error(msg)

    db.close()
