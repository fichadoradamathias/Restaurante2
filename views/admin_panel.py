# views/admin_panel.py
import streamlit as st
from database.models import Week, MenuItem, Office # Importar Office
# Importamos funciones nuevas
from services.admin_service import (
    create_week, finalize_week_logic, update_menu_item, delete_menu_item, 
    export_week_to_excel, get_all_offices, create_office, delete_office
)
from services.logic import delete_week_data 
from sqlalchemy.orm import Session
import datetime
import pandas as pd
import os

def admin_dashboard(db_session_maker):
    st.title("📋 Gestión Semanal y Oficinas")
    
    # Agregamos pestaña de Oficinas
    tab1, tab2, tab3, tab4 = st.tabs(["📅 Semanas", "🍔 Menú", "🏢 Oficinas", "🔒 Cierre/Exportación"])

    db: Session = db_session_maker() 

    # --- TAB 1: SEMANAS ---
    with tab1:
        st.subheader("Habilitar nueva semana")
        with st.form("new_week_form"):
            title = st.text_input("Título (ej. Semana 3 Diciembre)")
            c1, c2 = st.columns(2)
            start = c1.date_input("Inicio", datetime.date.today())
            end = c2.date_input("Fin", datetime.date.today() + datetime.timedelta(days=4))
            if st.form_submit_button("Crear Semana"):
                try:
                    create_week(db, title, start, end)
                    st.success("Semana creada.")
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")

        st.markdown("---")
        st.markdown("### 📅 Semanas Existentes")
        weeks = db.query(Week).order_by(Week.start_date.desc()).all()
        if weeks:
            for week in weeks:
                with st.expander(f"**{week.title}** ({week.start_date} - {week.end_date})"):
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"Estado: {'🟢 Abierta' if week.is_open else '🔴 Cerrada'}")
                    if c2.button("🗑️ Eliminar", key=f"del_{week.id}"):
                        delete_week_data(db, week.id)
                        st.rerun()
        else: st.info("No hay semanas.")

    # --- TAB 2: MENÚ (Sin cambios grandes, solo lo esencial) ---
    with tab2:
        st.subheader("Cargar opciones")
        open_weeks = db.query(Week).filter(Week.is_open == True).all()
        if not open_weeks: st.warning("No hay semanas abiertas.")
        else:
            week_opts = {w.title: w.id for w in open_weeks}
            sel_week_title = st.selectbox("Semana", list(week_opts.keys()))
            sel_week_id = week_opts[sel_week_title]
            
            # ... (Lógica de agregar platos igual que antes) ...
            # Por brevedad, asumo que mantienes tu lógica de formulario aquí
            # Solo asegúrate de que el código siga ahí si copias y pegas.
            # Si quieres, puedo pegarte el bloque completo de menú de nuevo.
            # Para este ejemplo, enfoco en lo nuevo:
            
            st.info("Utiliza el formulario habitual para cargar platos.") 
            # (Aquí iría tu formulario de add_item_form y la tabla editable del mensaje anterior)

    # --- TAB 3: OFICINAS (NUEVO) ---
    with tab3:
        st.subheader("Gestión de Oficinas")
        
        # Crear Oficina
        with st.form("create_office"):
            new_off_name = st.text_input("Nombre de Nueva Oficina")
            if st.form_submit_button("Crear Oficina"):
                if new_off_name:
                    ok, msg = create_office(db, new_off_name)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
        
        st.divider()
        st.subheader("Oficinas Existentes")
        offices = get_all_offices(db)
        if offices:
            for off in offices:
                c1, c2 = st.columns([3, 1])
                c1.write(f"🏢 **{off.name}**")
                if c2.button("Borrar", key=f"del_off_{off.id}"):
                    ok, msg = delete_office(db, off.id)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
        else:
            st.info("No hay oficinas creadas. Crea una (ej: Las Tórtolas).")

    # --- TAB 4: CIERRE Y EXPORTACIÓN ---
    with tab4:
        st.subheader("Exportación Avanzada")
        
        # Selector de Oficina para Exportar
        all_offices = get_all_offices(db)
        # Diccionario nombre -> ID. None es "Todas"
        office_opts = {"📦 TODAS LAS OFICINAS": None}
        for o in all_offices:
            office_opts[o.name] = o.id
            
        selected_office_label = st.selectbox("Filtrar por Oficina:", list(office_opts.keys()))
        selected_office_id = office_opts[selected_office_label]

        st.markdown("---")
        st.write("### Semanas para Exportar")
        
        # Listar todas las semanas (abiertas o cerradas) para permitir re-exportar
        all_weeks = db.query(Week).order_by(Week.start_date.desc()).all()
        
        if all_weeks:
            week_map = {f"{w.title} ({'Abierta' if w.is_open else 'Cerrada'})": w.id for w in all_weeks}
            sel_week_ex_label = st.selectbox("Seleccionar Semana", list(week_map.keys()))
            sel_week_ex_id = week_map[sel_week_ex_label]
            
            # Botón de Generar Excel
            btn_label = f"📄 Generar Excel ({selected_office_label})"
            if st.button(btn_label):
                path, msg = export_week_to_excel(db, sel_week_ex_id, selected_office_id)
                if path:
                    with open(path, "rb") as f:
                        st.download_button("📥 Descargar Archivo", f, file_name=path.split("/")[-1])
                    st.success(msg)
                else:
                    st.error(msg)
            
            # Botón de Cerrar Semana (Solo si está abierta)
            # Buscamos el objeto semana para ver si está abierto
            w_obj = db.query(Week).filter(Week.id == sel_week_ex_id).first()
            if w_obj and w_obj.is_open:
                st.divider()
                st.warning("Zona de Peligro")
                if st.button("⛔ CERRAR SEMANA (Finalizar)"):
                    # Al cerrar, usa el filtro por defecto (Todas) o null
                    path, msg = finalize_week_logic(db, sel_week_ex_id)
                    st.success("Semana cerrada exitosamente.")
                    st.rerun()

    db.close()