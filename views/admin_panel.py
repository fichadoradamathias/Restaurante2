# views/admin_panel.py
import streamlit as st
from database.models import Week, MenuItem
# Asegúrate de que estas funciones estén importadas de donde las tengas definidas
from services.admin_service import create_week, finalize_week_logic
from services.logic import delete_week_data # <-- Nueva función de borrado
from sqlalchemy.orm import Session
import datetime
import pandas as pd

def admin_dashboard(db_session_maker):
    st.title("📋 Gestión Semanal")
    
    # --- Pestañas de Navegación ---
    tab1, tab2, tab3 = st.tabs(["📅 Crear/Gestionar Semana", "🍔 Gestión Menú", "🔒 Cierre y Exportación"])

    # Abrir la sesión de base de datos
    db = db_session_maker()

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
                with st.expander(f"{week.title} ({week.start_date} - {week.end_date})"):
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


    # --- TAB 2: GESTIÓN MENÚ ---
    with tab2:
        st.subheader("Cargar opciones de comida")
        open_weeks = db.query(Week).filter(Week.is_open == True).all()
        week_opts = {w.title: w.id for w in open_weeks}
        
        if not week_opts:
            st.warning("No hay semanas abiertas. Crea una primero.")
        else:
            selected_week_title = st.selectbox("Seleccionar Semana", list(week_opts.keys()))
            selected_week_id = week_opts[selected_week_title]

            meal_type_map = {
                "Plato Principal": "principal",
                "Ensalada": "salad",
                "Acompañamiento": "side"
            }

            with st.form("add_item_form"):
                
                # CAMPOS DE SELECCIÓN
                c0, c1, c2 = st.columns([2, 1, 1])
                day = c0.selectbox("Día", ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"])
                
                type_label = c1.selectbox("Tipo de Opción", list(meal_type_map.keys()))
                meal_type = meal_type_map[type_label]
                
                opt_num = c2.number_input("Opción #", min_value=1, max_value=10, value=1)
                
                desc = st.text_area("Descripción", placeholder="Ej. Pollo al horno con ensalada / Ensalada de la casa / Arroz o Puré")
                
                if st.form_submit_button("Agregar Plato"):
                    
                    # --- VALIDACIÓN 1: NÚMERO DE OPCIÓN ÚNICO ---
                    existing_opt = db.query(MenuItem).filter(
                        MenuItem.week_id == selected_week_id,
                        MenuItem.day == day,
                        MenuItem.type == meal_type,  # <-- CORRECCIÓN 1
                        MenuItem.option_number == opt_num
                    ).first()

                    if existing_opt:
                        st.error(f"❌ Error: La Opción #{opt_num} ya existe para {day} en '{type_label}'. Por favor, elija otro número de opción.")
                        return
                    
                    # --- VALIDACIÓN 2: DESCRIPCIÓN ÚNICA POR DÍA/TIPO ---
                    existing_desc = db.query(MenuItem).filter(
                        MenuItem.week_id == selected_week_id,
                        MenuItem.day == day,
                        MenuItem.type == meal_type,  # <-- CORRECCIÓN 2
                        MenuItem.description == desc
                    ).first()

                    if existing_desc:
                        st.error(f"❌ Error: El plato '{desc}' ya fue agregado como Opción #{existing_desc.option_number} para {day} en '{type_label}'. Evite duplicados.")
                        return

                    # SI PASA LAS VALIDACIONES, SE GUARDA
                    new_item = MenuItem(
                        week_id=selected_week_id,
                        day=day,
                        type=meal_type,  # <-- CORRECCIÓN 3
                        option_number=opt_num,
                        description=desc
                    )
                    db.add(new_item)
                    db.commit()
                    st.success(f"Agregado: {day} - {type_label} Opción {opt_num}")

            st.write("---")
            st.write("Items cargados en esta semana:")
            
            # MOSTRAR LA TABLA COMPLETA CON TIPO DE PLATO
            items = db.query(MenuItem).filter(MenuItem.week_id == selected_week_id).all()
            if items:
                df = pd.DataFrame([
                    {'Día': i.day, 'Tipo': next(k for k, v in meal_type_map.items() if v == i.type), 'Opción #': i.option_number, 'Descripción': i.description} # <-- CORRECCIÓN 4
                    for i in items
                ])
                # Mapeo inverso para mostrar etiquetas amigables
                df['Tipo'] = df['Tipo'].map({v: k for k, v in meal_type_map.items()})
                st.dataframe(df.sort_values(by=['Día', 'Opción #']), use_container_width=True)
            else:
                st.info("Aún no hay platos cargados para esta semana.")


    # --- TAB 3: CIERRE Y EXPORTACIÓN ---
    with tab3:
        st.subheader("Finalizar Semana")
        st.warning("⚠️ Esto cerrará la semana y generará el Excel.")
        
        # Mostrar solo semanas abiertas para el cierre
        open_weeks = db.query(Week).filter(Week.is_open == True).all()
        week_opts_close = {w.title: w.id for w in open_weeks}
        
        if not week_opts_close:
            st.info("No hay semanas pendientes de cierre.")
        else:
            to_close = st.selectbox("Seleccionar semana a cerrar", list(week_opts_close.keys()), key="close_sel")
            
            if st.button("⛔ FINALIZAR Y EXPORTAR"):
                path, msg = finalize_week_logic(db, week_opts_close[to_close])
                if path:
                    st.success(msg)
                    with open(path, "rb") as f:
                        st.download_button("📥 Descargar Excel Final", f, file_name=path.split("/")[-1])
                else:
                    st.error(msg)

    # Cerrar la sesión de base de datos al final de la función
    db.close()
