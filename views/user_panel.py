import streamlit as st
from sqlalchemy.orm import Session
from database.models import Week, MenuItem, Order
from services.admin_service import get_now_utc3
import time

# --- FUNCIONES DE BLOQUEO MUTUO PARA STREAMLIT ---
def seleccionar_combinado(dia_code):
    st.session_state[f"widget_completo_{dia_code}"] = "Ninguno"

def seleccionar_completo(dia_code):
    st.session_state[f"widget_proteina_{dia_code}"] = "Ninguno"
    st.session_state[f"widget_guarnicion_{dia_code}"] = "Ninguno"

# --- FUNCIONES AUXILIARES ---
def get_full_week_menu(db: Session, week_id: int):
    items = db.query(MenuItem).filter(MenuItem.week_id == week_id).all()
    menu_structure = {day: {'Proteína': [], 'Guarnición': [], 'Plato Completo': []} 
                      for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']}
    
    for item in items:
        if item.day in menu_structure and item.type in menu_structure[item.day]:
            menu_structure[item.day][item.type].append(item)
    return menu_structure

def get_item_name_by_id(menu_structure, day_code, item_type, item_id):
    if not item_id: return None
    items = menu_structure.get(day_code, {}).get(item_type, [])
    for item in items:
        if item.id == item_id:
            return item.description
    return "Plato no encontrado"

def save_weekly_order_to_db(db: Session, user_id: int, week_id: int, collected_data: dict):
    try:
        existing_order = db.query(Order).filter(
            Order.user_id == user_id, 
            Order.week_id == week_id
        ).first()

        if existing_order:
            existing_order.details = collected_data
            existing_order.status = "actualizado"
            msg = "✅ Pedido actualizado correctamente."
        else:
            new_order = Order(
                user_id=user_id,
                week_id=week_id,
                status="confirmado",
                details=collected_data
            )
            db.add(new_order)
            msg = "🚀 Pedido creado exitosamente."
        
        db.commit()
        return True, msg
    except Exception as e:
        db.rollback()
        return False, f"Error al guardar: {e}"

# --- INTERFAZ DE USUARIO ---
def user_dashboard(db_session_maker):
    if 'user_id' not in st.session_state:
        st.error("Por favor inicia sesión.")
        return

    user_id = st.session_state.user_id
    db: Session = db_session_maker()

    try:
        now_utc3 = get_now_utc3()
        current_week = db.query(Week).filter(
            Week.is_open == True, 
            Week.end_date > now_utc3
        ).order_by(Week.start_date.desc()).first()

        if not current_week:
            st.info("🚫 No hay semanas habilitadas para pedidos.")
            db.close()
            return

        closed_days = current_week.closed_days if current_week.closed_days else []
        days_keys = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        days_labels = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

        existing_order = db.query(Order).filter(
            Order.user_id == user_id, 
            Order.week_id == current_week.id
        ).first()

        if "is_editing_order" not in st.session_state:
            st.session_state.is_editing_order = False

        if not existing_order:
            st.session_state.is_editing_order = True

        full_menu = get_full_week_menu(db, current_week.id)

        # FIX: Forzar la recarga de datos cuando se edita para evitar el "Olvido" de Streamlit
        if not st.session_state.get("week_data_loaded") or st.session_state.get("current_week_id") != current_week.id:
            saved_details = existing_order.details if existing_order else {}
            for d in days_keys:
                day_details = saved_details.get(d, {})
                tipo = day_details.get("tipo", "nada")
                
                prot_val = "Ninguno"
                guar_val = "Ninguno"
                comp_val = "Ninguno"

                if tipo == "completo":
                    comp_id = day_details.get("plato_id")
                    comp_name = get_item_name_by_id(full_menu, d, 'Plato Completo', comp_id)
                    if comp_name: comp_val = comp_name
                elif tipo == "combinado":
                    prot_id = day_details.get("proteina_id")
                    guar_id = day_details.get("guarnicion_id")
                    prot_name = get_item_name_by_id(full_menu, d, 'Proteína', prot_id)
                    guar_name = get_item_name_by_id(full_menu, d, 'Guarnición', guar_id)
                    if prot_name: prot_val = prot_name
                    if guar_name: guar_val = guar_name

                st.session_state[f"widget_proteina_{d}"] = prot_val
                st.session_state[f"widget_guarnicion_{d}"] = guar_val
                st.session_state[f"widget_completo_{d}"] = comp_val
                st.session_state[f"widget_note_{d}"] = day_details.get("note", "")
            
            st.session_state.week_data_loaded = True
            st.session_state.current_week_id = current_week.id

        # 3. HEADER Y TEXTO DE INSTRUCCIONES
        st.title(f"🍽️ Menú: {current_week.title}")
        
        st.info("ℹ️ **Información:** Solo puedes llenar una de las dos secciones (Plato Combinado o Plato Completo). Para Plato Combinado necesitas pedir **obligatoriamente** Proteína y Guarnición, no es posible enviar uno solo.")

        # ---------------------------------------------------------
        # VISTA 1: RESUMEN DE PEDIDO (Solo lectura)
        # ---------------------------------------------------------
        if existing_order and not st.session_state.is_editing_order:
            st.success("✅ Ya has enviado tu pedido para esta semana.")
            st.markdown("### 📋 Tu Selección Confirmada:")
            
            details = existing_order.details
            hay_pedidos = False

            with st.container(border=True):
                for i, d_key in enumerate(days_keys):
                    day_details = details.get(d_key, {})
                    tipo = day_details.get("tipo", "nada")
                    note = day_details.get("note", "")

                    if tipo != "nada":
                        hay_pedidos = True
                        day_name = days_labels[i]
                        st.markdown(f"**📅 {day_name}**")

                        if tipo == "completo":
                            comp_name = get_item_name_by_id(full_menu, d_key, 'Plato Completo', day_details.get("plato_id"))
                            st.markdown(f"- 🍲 **Plato Completo:** {comp_name}")
                        elif tipo == "combinado":
                            prot_name = get_item_name_by_id(full_menu, d_key, 'Proteína', day_details.get("proteina_id"))
                            guar_name = get_item_name_by_id(full_menu, d_key, 'Guarnición', day_details.get("guarnicion_id"))
                            if prot_name: st.markdown(f"- 🥩 **Proteína:** {prot_name}")
                            if guar_name: st.markdown(f"- 🍟 **Guarnición:** {guar_name}")

                        st.divider()
            
            if not hay_pedidos:
                st.warning("Tu pedido consta de 'No Pedido' para todos los días.")

            st.markdown("---")
            col_change, col_dummy = st.columns([1, 2])
            with col_change:
                if st.button("✏️ CAMBIAR / ACTUALIZAR PEDIDO", use_container_width=True):
                    st.session_state.is_editing_order = True
                    # FIX: Forzamos la recarga al volver a editar para que traiga los "Ninguno" correctos
                    st.session_state.week_data_loaded = False 
                    st.rerun()

        # ---------------------------------------------------------
        # VISTA 2: FORMULARIO DE EDICIÓN
        # ---------------------------------------------------------
        else:
            tabs = st.tabs(days_labels)
            
            for i, tab in enumerate(tabs):
                current_day_code = days_keys[i]
                current_day_name = days_labels[i]
                
                with tab:
                    st.subheader(f"📅 {current_day_name}")
                    day_items = full_menu.get(current_day_code)
                    
                    if current_day_code in closed_days:
                        st.error(f"⛔ {current_day_name}: FERIADO / SIN SERVICIO")
                        continue
                    
                    if not day_items or (not day_items['Proteína'] and not day_items['Plato Completo']):
                        st.warning("⚠️ El menú de este día aún no ha sido cargado completamente.")
                        continue

                    # Preparar opciones
                    prot_opts = {p.description: p.id for p in day_items.get('Proteína', [])}
                    prot_opts["Ninguno"] = None
                    prot_list = list(prot_opts.keys())
                    
                    guar_opts = {g.description: g.id for g in day_items.get('Guarnición', [])}
                    guar_opts["Ninguno"] = None
                    guar_list = list(guar_opts.keys())
                    
                    comp_opts = {c.description: c.id for c in day_items.get('Plato Completo', [])}
                    comp_opts["Ninguno"] = None
                    comp_list = list(comp_opts.keys())

                    # FIX: Índices blindados. Si Streamlit olvida el valor, busca 'Ninguno' por defecto
                    curr_prot = st.session_state.get(f"widget_proteina_{current_day_code}", "Ninguno")
                    curr_guar = st.session_state.get(f"widget_guarnicion_{current_day_code}", "Ninguno")
                    curr_comp = st.session_state.get(f"widget_completo_{current_day_code}", "Ninguno")

                    idx_prot = prot_list.index(curr_prot) if curr_prot in prot_list else prot_list.index("Ninguno")
                    idx_guar = guar_list.index(curr_guar) if curr_guar in guar_list else guar_list.index("Ninguno")
                    idx_comp = comp_list.index(curr_comp) if curr_comp in comp_list else comp_list.index("Ninguno")

                    col_tarjeta_a, col_tarjeta_b = st.columns(2)
                    
                    with col_tarjeta_a:
                        with st.container(border=True):
                            st.markdown("### 🥗 Plato Combinado")
                            st.selectbox(
                                "Elige tu Proteína:", 
                                options=prot_list, 
                                index=idx_prot,
                                key=f"widget_proteina_{current_day_code}",
                                on_change=seleccionar_combinado,
                                args=(current_day_code,)
                            )
                            st.selectbox(
                                "Elige tu Guarnición:", 
                                options=guar_list, 
                                index=idx_guar,
                                key=f"widget_guarnicion_{current_day_code}",
                                on_change=seleccionar_combinado,
                                args=(current_day_code,)
                            )

                    with col_tarjeta_b:
                        with st.container(border=True):
                            st.markdown("### 🍲 Plato Completo")
                            st.selectbox(
                                "Plato del Día:", 
                                options=comp_list,
                                index=idx_comp,
                                key=f"widget_completo_{current_day_code}",
                                on_change=seleccionar_completo,
                                args=(current_day_code,)
                            )
                    
                    st.text_area("Nota especial (Opcional, no se exporta):", key=f"widget_note_{current_day_code}", height=70)

            # --- BOTONES DE ACCIÓN (Enviar o Cancelar) ---
            st.markdown("---")
            
            if existing_order:
                col_cancel, col_save = st.columns([1, 2])
                with col_cancel:
                    if st.button("❌ Cancelar Cambios", use_container_width=True):
                        st.session_state.is_editing_order = False
                        st.session_state.week_data_loaded = False # Limpia para volver a leer la BD
                        st.rerun()
            else:
                col_save = st.container()

            with col_save:
                btn_text = "💾 ACTUALIZAR PEDIDO" if existing_order else "🚀 ENVIAR PEDIDO SEMANAL"
                if st.button(btn_text, type="primary", use_container_width=True):
                    final_data_payload = {}
                    count_meals = 0
                    validation_error = False 
                    
                    for i, d in enumerate(days_keys):
                        d_items = full_menu.get(d, {})
                        p_opts = {p.description: p.id for p in d_items.get('Proteína', [])}
                        g_opts = {g.description: g.id for g in d_items.get('Guarnición', [])}
                        c_opts = {c.description: c.id for c in d_items.get('Plato Completo', [])}

                        prot_name = st.session_state.get(f"widget_proteina_{d}")
                        guar_name = st.session_state.get(f"widget_guarnicion_{d}")
                        comp_name = st.session_state.get(f"widget_completo_{d}")
                        nota = st.session_state.get(f"widget_note_{d}", "")
                        
                        prot_id = p_opts.get(prot_name) if prot_name and prot_name != "Ninguno" else None
                        guar_id = g_opts.get(guar_name) if guar_name and guar_name != "Ninguno" else None
                        comp_id = c_opts.get(comp_name) if comp_name and comp_name != "Ninguno" else None

                        if comp_id is not None:
                            final_data_payload[d] = {"tipo": "completo", "plato_id": comp_id, "note": nota}
                            count_meals += 1
                        elif prot_id is not None or guar_id is not None:
                            # CONDICIONAL: Obligar a que lleguen ambos campos
                            if prot_id is None or guar_id is None:
                                st.error(f"⚠️ En **{days_labels[i]}**: Para pedir el Plato Combinado debes elegir obligatoriamente Proteína y Guarnición. ¡Te falta seleccionar una opción!")
                                validation_error = True
                                break
                            
                            final_data_payload[d] = {"tipo": "combinado", "proteina_id": prot_id, "guarnicion_id": guar_id, "note": nota}
                            count_meals += 1
                        else:
                            final_data_payload[d] = {"tipo": "nada"}
                    
                    if not validation_error:
                        if count_meals == 0:
                            st.warning("⚠️ No has seleccionado ningún plato para ningún día.")
                        else:
                            success, msg = save_weekly_order_to_db(db, user_id, current_week.id, final_data_payload)
                            if success:
                                st.balloons()
                                st.success(msg)
                                st.session_state.is_editing_order = False
                                st.session_state.week_data_loaded = False # Limpia estado al guardar exitosamente
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error(msg)

    except Exception as e:
        st.error(f"Ocurrió un error inesperado: {e}")
    finally:
        db.close()