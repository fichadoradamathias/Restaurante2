# views/admin_panel.py
import streamlit as st
from database.models import Week, MenuItem
# Importar todas las funciones necesarias, incluyendo las nuevas para la edición
from services.admin_service import create_week, finalize_week_logic, update_menu_item, delete_menu_item
from services.logic import delete_week_data 
from sqlalchemy.orm import Session
import datetime
import pandas as pd

def admin_dashboard(db_session_maker):
    st.title("📋 Gestión Semanal")
    
    # --- Pestañas de Navegación ---
    tab1, tab2, tab3 = st.tabs(["📅 Crear/Gestionar Semana", "🍔 Gestión Menú", "🔒 Cierre y Exportación"])

    # Abrir la sesión de base de datos
    db: Session = db_session_maker() # Usamos tipo hint para la sesión

    # --- TAB 1: CREAR SEMANA Y GESTIONAR LISTA ---
    with tab1:
        st.subheader("Habilitar nueva semana")
        
        # Formulario de Creación
        with st.form("new_week_form"):
            title = st.text_input("Título (ej. Semana 3 Diciembre)")
            c1, c2 = st.columns(2)
            start = c1.date_input("Inicio", datetime.date.today())
            end = c2.date_input("Fin", datetime.date.today() + datetime.timedelta(days=4))
            
            if st.form_submit_button("Crear Semana"):
                try:
                    create_week(db, title, start, end)
                    st.success(f"Semana '{title}' creada exitosamente. Dirígete a 'Gestión Menú'.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        # --- SECCIÓN DE LISTADO Y ELIMINACIÓN ---
        st.markdown("---")
        st.markdown("### 📅 Semanas Existentes")
        
        # Obtener todas las semanas para listarlas
        weeks = db.query(Week).order_by(Week.start_date.desc()).all()

        if weeks:
            for week in weeks:
                # Usamos el expander para agrupar info y el botón de eliminación
                with st.expander(f"**{week.title}** ({week.start_date} - {week.end_date})"):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        # Mostrar el estado
                        st.write(f"Estado: {'🟢 Abierta' if week.is_open else '🔴 Cerrada'}")

                    with col2:
                        # Botón de Eliminar
                        if st.button("🗑️ Eliminar", key=f"del_{week.id}", type="primary"):
                            delete_week_data(db, week.id) # Llama a la función de borrado seguro
                            st.success(f"Semana '{week.title}' eliminada.")
                            st.rerun() # Recarga para actualizar la lista
        else:
            st.info("Aún no hay semanas creadas.")


    # --- TAB 2: GESTIÓN MENÚ (CORREGIDO Y AÑADIDO st.data_editor) ---
    with tab2:
        st.subheader("Cargar opciones de comida")
        open_weeks = db.query(Week).filter(Week.is_open == True).all()
        week_opts = {w.title: w.id for w in open_weeks}
        
        if not week_opts:
            st.warning("No hay semanas abiertas. Crea una primero.")
        else:
            selected_week_title = st.selectbox("Seleccionar Semana", list(week_opts.keys()))
            current_week = db.query(Week).filter(Week.id == week_opts[selected_week_title]).first()
            selected_week_id = current_week.id

            meal_type_map = {
                "Plato Principal": "principal",
                "Ensalada": "salad",
                "Acompañamiento": "side"
            }

            # 1. FORMULARIO DE AGREGAR NUEVO ÍTEM
            with st.form("add_item_form"):
                
                # CAMPOS DE SELECCIÓN
                c0, c1, c2 = st.columns([2, 1, 1])
                day = c0.selectbox("Día", ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"])
                
                type_label = c1.selectbox("Tipo de Opción", list(meal_type_map.keys()))
                meal_type = meal_type_map[type_label]
                
                # Se utiliza el conteo de items existentes para sugerir el siguiente
                existing_count = db.query(MenuItem).filter(
                    MenuItem.week_id == selected_week_id,
                    MenuItem.day == day,
                    MenuItem.type == meal_type
                ).count()
                
                opt_num = c2.number_input("Opción #", min_value=1, max_value=10, value=existing_count + 1)
                
                desc = st.text_area("Descripción", placeholder="Ej. Pollo al horno con ensalada / Ensalada de la casa / Arroz o Puré")
                
                if st.form_submit_button("Agregar Plato"):
                    
                    # --- VALIDACIÓN 1: NÚMERO DE OPCIÓN ÚNICO ---
                    existing_opt = db.query(MenuItem).filter(
                        MenuItem.week_id == selected_week_id,
                        MenuItem.day == day,
                        MenuItem.type == meal_type,
                        MenuItem.option_number == opt_num
                    ).first()

                    if existing_opt:
                        st.error(f"❌ Error: La Opción #{opt_num} ya existe para {day} en '{type_label}'. Por favor, elija otro número de opción.")
                        return
                    
                    # --- VALIDACIÓN 2: DESCRIPCIÓN ÚNICA POR DÍA/TIPO ---
                    existing_desc = db.query(MenuItem).filter(
                        MenuItem.week_id == selected_week_id,
                        MenuItem.day == day,
                        MenuItem.type == meal_type,
                        MenuItem.description == desc
                    ).first()

                    if existing_desc:
                        st.error(f"❌ Error: El plato '{desc}' ya fue agregado como Opción #{existing_desc.option_number} para {day} en '{type_label}'. Evite duplicados.")
                        return

                    # SI PASA LAS VALIDACIONES, SE GUARDA
                    new_item = MenuItem(
                        week_id=selected_week_id,
                        day=day,
                        type=meal_type,
                        option_number=opt_num,
                        description=desc
                    )
                    db.add(new_item)
                    db.commit()
                    st.success(f"Agregado: {day} - {type_label} Opción {opt_num}")
                    st.rerun() # Recargar para que se vea en la tabla

            st.markdown("---")
            st.subheader("📝 Items cargados en esta semana (Editable y Eliminable)")
            
            # 2. TABLA EDITABLE CON DATAFRAME
            # Consulta: Se ordena por DÍA, TIPO y NÚMERO DE OPCIÓN
            all_items = db.query(MenuItem).filter(MenuItem.week_id == selected_week_id).order_by(
                MenuItem.day, MenuItem.type, MenuItem.option_number
            ).all()

            if all_items:
                # Mapeo inverso para mostrar etiquetas amigables
                reverse_meal_map = {v: k for k, v in meal_type_map.items()}
                
                # Preparamos los datos para la tabla editable
                item_data = [{
                    "ID": i.id,
                    "Día": i.day,
                    "Tipo": reverse_meal_map.get(i.type, i.type), # Etiqueta amigable
                    "Opción N°": i.option_number,
                    "Descripción": i.description,
                    "Borrar": False # Columna para eliminar
                } for i in all_items]
                
                df = pd.DataFrame(item_data)
                
                edited_df = st.data_editor(
                    df,
                    column_config={
                        "ID": st.column_config.Column("ID", disabled=True),
                        "Día": st.column_config.Column("Día", disabled=True),
                        "Tipo": st.column_config.Column("Tipo", disabled=True),
                        "Opción N°": st.column_config.NumberColumn("Opción N°", required=True, min_value=1),
                        "Descripción": st.column_config.TextColumn("Descripción", required=True),
                        "Borrar": st.column_config.CheckboxColumn("Borrar")
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="menu_item_editor"
                )
                
                # Lógica de guardado y eliminación
                if st.button("💾 Aplicar Cambios/Eliminar Ítems", key="save_menu_changes"):
                    changes_applied = 0
                    
                    for index, row in edited_df.iterrows():
                        original_id = row['ID']
                        
                        if row['Borrar']:
                            # Eliminar
                            success, msg = delete_menu_item(db, original_id)
                            if success: changes_applied += 1
                        
                        else:
                            # Actualizar si hay cambios en descripción o número de opción
                            original_row = df[df['ID'] == original_id].iloc[0]
                            
                            if (original_row['Descripción'] != row['Descripción'] or 
                                original_row['Opción N°'] != row['Opción N°']):
                                
                                success, msg = update_menu_item(db, original_id, row['Descripción'], int(row['Opción N°']))
                                if success: changes_applied += 1
                                
                    if changes_applied > 0:
                        st.success(f"¡Se aplicaron {changes_applied} cambios al menú!")
                        st.rerun()
                    else:
                        st.info("No se detectaron cambios a aplicar.")
            
            else:
                st.info("Aún no hay platos cargados para esta semana.")


    # --- TAB 3: CIERRE Y EXPORTACIÓN ---
    with tab3:
        st.subheader("Finalizar Semana")
        st.warning("⚠️ Esto cerrará la semana, creará registros 'No Pedido' para usuarios sin elección y generará el Excel.")
        
        # Mostrar solo semanas abiertas para el cierre
        open_weeks_close = db.query(Week).filter(Week.is_open == True).all()
        week_opts_close = {w.title: w.id for w in open_weeks_close}
        
        if not week_opts_close:
            st.info("No hay semanas pendientes de cierre.")
        else:
            to_close = st.selectbox("Seleccionar semana a cerrar", list(week_opts_close.keys()), key="close_sel")
            
            if st.button("⛔ FINALIZAR Y EXPORTAR"):
                # Se llama a la lógica de finalización que incluye la exportación
                path, msg = finalize_week_logic(db, week_opts_close[to_close])
                
                if path:
                    st.success(msg)
                    # La exportación crea un archivo en el path, ahora lo ofrecemos para descargar
                    try:
                        with open(path, "rb") as f:
                            st.download_button(
                                "📥 Descargar Excel Final", 
                                f, 
                                file_name=path.split("/")[-1] # Obtiene el nombre del archivo
                            )
                    except FileNotFoundError:
                        st.error("Error: El archivo de exportación no fue encontrado.")
                else:
                    st.error(msg)
                    
    # Cerrar la sesión de base de datos al final de la función
    db.close()