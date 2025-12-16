# views/admin_panel.py
import streamlit as st
from database.models import Week, MenuItem, Office 
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

    # --- TAB 2: MENÚ ---
    with tab2:
        st.subheader("Cargar opciones")
        open_weeks = db.query(Week).filter(Week.is_open == True).all()
        if not open_weeks: st.warning("No hay semanas abiertas.")
        else:
            week_opts = {w.title: w.id for w in open_weeks}
            sel_week_title = st.selectbox("Semana", list(week_opts.keys()))
            sel_week_id = week_opts[sel_week_title]
            
            # (Aquí iría tu formulario de add_item_form que ya tienes en el original)
            st.info("Utiliza el formulario habitual para cargar platos.") 
            # Si necesitas el código del menú, avísame, pero dijiste que solo querías la estructura actualizada

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
                # Botón de borrar con validación (manejada en el servicio)
                if c2.button("Borrar", key=f"del_off_{off.id}"):
                    ok, msg = delete_office(db, off.id)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
        else:
            st.info("No hay oficinas creadas. Crea una (ej: Las Tórtolas).")

    # --- TAB 4: CIERRE Y EXPORTACIÓN (ACTUALIZADO) ---
    with tab4:
        st.subheader("📊 Centro de Exportación")
        
        # Seleccionar Semana
        all_weeks = db.query(Week).order_by(Week.start_date.desc()).all()
        
        if not all_weeks:
            st.info("No hay semanas registradas.")
        else:
            week_map = {f"{w.title} ({'Abierta' if w.is_open else 'Cerrada'})": w.id for w in all_weeks}
            sel_week_ex_label = st.selectbox("Seleccionar Semana para Exportar", list(week_map.keys()))
            sel_week_ex_id = week_map[sel_week_ex_label]
            
            st.markdown("---")
            st.write("### 📥 Descargar Reportes")

            # Obtenemos todas las oficinas para generar botones
            all_offices = get_all_offices(db)
            
            if not all_offices:
                st.warning("No hay oficinas configuradas.")
            
            # Iteramos oficinas para crear un botón por cada una
            st.info("Generar reporte individual por oficina:")
            
            for office in all_offices:
                col_btn, col_dl = st.columns([1, 1])
                with col_btn:
                    # Botón para generar/descargar de una oficina específica
                    if st.button(f"📄 {office.name}", key=f"btn_exp_{office.id}_{sel_week_ex_id}", use_container_width=True):
                        path, msg = export_week_to_excel(db, sel_week_ex_id, office.id)
                        if path:
                            st.session_state[f"last_export_{office.id}"] = path
                            st.success(msg)
                        else:
                            st.error(msg)
                
                # Mostrar botón de descarga si el archivo fue generado
                with col_dl:
                    if f"last_export_{office.id}" in st.session_state:
                        path = st.session_state[f"last_export_{office.id}"]
                        if os.path.exists(path):
                            with open(path, "rb") as f:
                                st.download_button(
                                    label=f"⬇️ Descargar {office.name}",
                                    data=f,
                                    file_name=path.split("/")[-1],
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    key=f"dl_{office.id}_{sel_week_ex_id}"
                                )

            st.markdown("---")
            # Botón para exportar TODO junto (Backup)
            if st.button("📦 Exportar TODAS las Oficinas (Consolidado)", type="primary"):
                path, msg = export_week_to_excel(db, sel_week_ex_id, None)
                if path:
                    with open(path, "rb") as f:
                        st.download_button("⬇️ Descargar Consolidado", f, file_name=path.split("/")[-1])
            
            # --- SECCIÓN DE CIERRE (ZONA DE PELIGRO) ---
            w_obj = db.query(Week).filter(Week.id == sel_week_ex_id).first()
            if w_obj and w_obj.is_open:
                st.markdown("---")
                st.error("🚫 Zona de Cierre")
                st.caption("Al cerrar la semana, se generarán automáticamente los pedidos vacíos para usuarios que no ordenaron.")
                
                if st.button("🔒 CERRAR SEMANA FINALMENTE"):
                    path, msg = finalize_week_logic(db, sel_week_ex_id)
                    st.success("Semana cerrada. Se ha generado el reporte global.")
                    st.rerun()

    db.close()
