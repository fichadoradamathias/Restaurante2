# views/admin_panel.py
import streamlit as st
from database.models import Week, MenuItem, Office 
from services.admin_service import (
    create_week, finalize_week_logic, update_menu_item, delete_menu_item, 
    export_week_to_excel, get_all_offices, create_office, delete_office,
    update_week_closed_days # <--- Importación clave para feriados
)
from services.logic import delete_week_data 
from sqlalchemy.orm import Session
from datetime import datetime, time, timedelta
import pandas as pd
import os

def admin_dashboard(db_session_maker):
    st.title("📋 Gestión Semanal y Oficinas")
    
    # Definición de pestañas
    tab1, tab2, tab3, tab4 = st.tabs(["📅 Semanas", "🍔 Menú y Feriados", "🏢 Oficinas", "🔒 Cierre/Exportación"])
    
    db: Session = db_session_maker() 

    # --- TAB 1: SEMANAS ---
    with tab1:
        st.subheader("Habilitar nueva semana")
        with st.form("new_week_form"):
            title = st.text_input("Título (ej. Semana 3 Diciembre)")
            c1, c2 = st.columns(2)
            start_d = c1.date_input("Inicio de Semana (Lunes)", datetime.today())
            
            # CONFIGURACIÓN DE CIERRE
            st.markdown("**Configuración de Cierre (UTC-3)**")
            c3, c4 = st.columns(2)
            # Default: Cierre el Jueves (3 días después del inicio) a las 12:00
            end_d = c3.date_input("Fecha de Cierre", datetime.today() + timedelta(days=3))
            end_t = c4.time_input("Hora de Cierre", time(12, 00))
            
            if st.form_submit_button("Crear Semana"):
                try:
                    # Combinamos fecha y hora para el cierre exacto
                    end_datetime = datetime.combine(end_d, end_t)
                    create_week(db, title, start_d, end_datetime)
                    st.success(f"Semana creada. Cierra el {end_datetime.strftime('%d/%m %H:%M')}")
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")

        st.markdown("---")
        st.markdown("### 📅 Semanas Existentes")
        weeks = db.query(Week).order_by(Week.start_date.desc()).all()
        if weeks:
            for week in weeks:
                # Mostrar fecha y hora de cierre formateada
                end_fmt = week.end_date.strftime("%d/%m/%Y %H:%M") if week.end_date else "Sin fecha"
                with st.expander(f"**{week.title}** (Cierre: {end_fmt})"):
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"Estado: {'🟢 Abierta' if week.is_open else '🔴 Cerrada'}")
                    if c2.button("🗑️ Eliminar", key=f"del_{week.id}"):
                        delete_week_data(db, week.id)
                        st.rerun()
        else: st.info("No hay semanas.")

    # --- TAB 2: MENÚ Y FERIADOS (ACTUALIZADO) ---
    with tab2:
        st.subheader("🍔 Gestión de Menú y Feriados")
        
        open_weeks = db.query(Week).filter(Week.is_open == True).all()
        
        if not open_weeks: 
            st.warning("No hay semanas abiertas.")
        else:
            week_opts = {w.title: w.id for w in open_weeks}
            sel_week_title = st.selectbox("Seleccionar Semana", list(week_opts.keys()))
            sel_week_id = week_opts[sel_week_title]
            
            # Obtenemos el objeto semana para ver sus feriados actuales
            current_week_obj = db.query(Week).filter(Week.id == sel_week_id).first()
            current_closed = current_week_obj.closed_days if current_week_obj.closed_days else []

            st.divider()
            
            # --- ZONA DE FERIADOS ---
            st.markdown("### 📅 Configurar Días Sin Servicio (Feriados)")
            st.caption("Marca los días que NO habrá comida (ej: Feriados). El usuario verá un aviso y no podrá pedir.")
            
            cols_days = st.columns(5)
            days_map = [
                ("monday", "Lunes"), ("tuesday", "Martes"), ("wednesday", "Miércoles"),
                ("thursday", "Jueves"), ("friday", "Viernes")
            ]
            
            new_closed_days = []
            
            # Creamos los checkboxes
            for i, (d_code, d_name) in enumerate(days_map):
                is_checked = d_code in current_closed
                # Usamos un key único combinando semana y día para evitar conflictos
                if cols_days[i].checkbox(d_name, value=is_checked, key=f"chk_{sel_week_id}_{d_code}"):
                    new_closed_days.append(d_code)
            
            # Botón para guardar feriados
            if st.button("💾 Actualizar Feriados"):
                ok, msg = update_week_closed_days(db, sel_week_id, new_closed_days)
                if ok: st.success(msg); st.rerun()
                else: st.error(msg)
            
            st.divider()

            # --- ZONA DE MENÚ (Standard) ---
            st.info("Utiliza el formulario habitual para cargar platos en los días habilitados.")
            # (Aquí iría tu formulario de Add Item original si lo necesitas restaurar)

    # --- TAB 3: OFICINAS ---
    with tab3:
        st.subheader("Gestión de Oficinas")
        
        # Formulario de creación
        with st.form("create_office"):
            new_off_name = st.text_input("Nombre de Nueva Oficina")
            if st.form_submit_button("Crear Oficina"):
                if new_off_name:
                    ok, msg = create_office(db, new_off_name)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
        
        st.divider()
        
        # Listado de oficinas
        offices = get_all_offices(db)
        if offices:
            for off in offices:
                c1, c2 = st.columns([3, 1])
                c1.write(f"🏢 **{off.name}**")
                # Botón de borrar con validación de usuarios vinculados
                if c2.button("Borrar", key=f"del_off_{off.id}"):
                    ok, msg = delete_office(db, off.id)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
        else: st.info("No hay oficinas configuradas.")

    # --- TAB 4: CIERRE Y EXPORTACIÓN ---
    with tab4:
        st.subheader("📊 Centro de Exportación")
        all_weeks = db.query(Week).order_by(Week.start_date.desc()).all()
        
        if not all_weeks:
            st.info("No hay semanas registradas.")
        else:
            week_map = {f"{w.title} ({'Abierta' if w.is_open else 'Cerrada'})": w.id for w in all_weeks}
            sel_week_ex_label = st.selectbox("Seleccionar Semana para Exportar", list(week_map.keys()))
            sel_week_ex_id = week_map[sel_week_ex_label]
            
            st.markdown("---")
            
            # Selección de Oficina para reporte individual
            all_offices = get_all_offices(db)
            if not all_offices: st.warning("No hay oficinas configuradas.")
            
            st.info("Generar reporte individual por oficina:")
            for office in all_offices:
                col_btn, col_dl = st.columns([1, 1])
                with col_btn:
                    # Generar Excel filtrado
                    if st.button(f"📄 {office.name}", key=f"btn_exp_{office.id}_{sel_week_ex_id}", use_container_width=True):
                        path, msg = export_week_to_excel(db, sel_week_ex_id, office.id)
                        if path: 
                            st.session_state[f"last_export_{office.id}"] = path
                            st.success(msg)
                        else: st.error(msg)
                
                # Botón de descarga si se generó el archivo
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
            # Exportación Consolidada (Todas las oficinas)
            if st.button("📦 Exportar TODAS las Oficinas (Consolidado)", type="primary"):
                path, msg = export_week_to_excel(db, sel_week_ex_id, None)
                if path:
                    with open(path, "rb") as f: st.download_button("⬇️ Descargar Consolidado", f, file_name=path.split("/")[-1])
            
            # Zona de Cierre Manual
            w_obj = db.query(Week).filter(Week.id == sel_week_ex_id).first()
            if w_obj and w_obj.is_open:
                st.markdown("---")
                st.error("🚫 Zona de Cierre Manual")
                st.caption("Fuerza el cierre de la semana y genera pedidos vacíos para quienes no ordenaron.")
                if st.button("🔒 CERRAR SEMANA AHORA"):
                    path, msg = finalize_week_logic(db, sel_week_ex_id)
                    st.success("Semana cerrada."); st.rerun()
    
    db.close()
