# views/admin_panel.py
import streamlit as st
from database.models import Week, MenuItem, Office 
from services.admin_service import (
    create_week, finalize_week_logic, update_menu_item, delete_menu_item, 
    export_week_to_excel, get_all_offices, create_office, delete_office,
    update_week_closed_days, create_menu_item # <--- AGREGAMOS create_menu_item
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
            end_d = c3.date_input("Fecha de Cierre", datetime.today() + timedelta(days=3))
            end_t = c4.time_input("Hora de Cierre", time(12, 00))
            
            if st.form_submit_button("Crear Semana"):
                try:
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
                end_fmt = week.end_date.strftime("%d/%m/%Y %H:%M") if week.end_date else "Sin fecha"
                with st.expander(f"**{week.title}** (Cierre: {end_fmt})"):
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"Estado: {'🟢 Abierta' if week.is_open else '🔴 Cerrada'}")
                    if c2.button("🗑️ Eliminar", key=f"del_{week.id}"):
                        delete_week_data(db, week.id)
                        st.rerun()
        else: st.info("No hay semanas.")

    # --- TAB 2: MENÚ Y FERIADOS (CORREGIDO) ---
    with tab2:
        st.subheader("🍔 Gestión de Menú y Feriados")
        
        open_weeks = db.query(Week).filter(Week.is_open == True).all()
        
        if not open_weeks: 
            st.warning("No hay semanas abiertas.")
        else:
            week_opts = {w.title: w.id for w in open_weeks}
            sel_week_title = st.selectbox("Seleccionar Semana", list(week_opts.keys()))
            sel_week_id = week_opts[sel_week_title]
            
            # Recuperar feriados actuales
            current_week_obj = db.query(Week).filter(Week.id == sel_week_id).first()
            current_closed = current_week_obj.closed_days if current_week_obj.closed_days else []

            st.divider()
            
            # 1. ZONA DE FERIADOS
            st.markdown("### 📅 1. Configurar Feriados (Días sin menú)")
            cols_days = st.columns(5)
            days_map = [
                ("monday", "Lunes"), ("tuesday", "Martes"), ("wednesday", "Miércoles"),
                ("thursday", "Jueves"), ("friday", "Viernes")
            ]
            new_closed_days = []
            for i, (d_code, d_name) in enumerate(days_map):
                is_checked = d_code in current_closed
                if cols_days[i].checkbox(d_name, value=is_checked, key=f"chk_{sel_week_id}_{d_code}"):
                    new_closed_days.append(d_code)
            
            if st.button("💾 Guardar Feriados"):
                ok, msg = update_week_closed_days(db, sel_week_id, new_closed_days)
                if ok: st.success(msg); st.rerun()
                else: st.error(msg)
            
            st.divider()

            # 2. ZONA DE CARGA DE PLATOS (RESTAURADA)
            st.markdown("### 🍽️ 2. Cargar Platos al Menú")
            
            with st.form("add_item_form"):
                c1, c2 = st.columns(2)
                # Filtramos los días para que primero salgan los nombres en español
                day_options = {d[1]: d[0] for d in days_map} # {'Lunes': 'monday', ...}
                
                sel_day_label = c1.selectbox("Día", list(day_options.keys()))
                sel_day_code = day_options[sel_day_label]
                
                # Advertencia visual si el día es feriado
                if sel_day_code in new_closed_days:
                    st.warning(f"⚠️ Atención: Estás cargando comida para el {sel_day_label}, pero está marcado como FERIADO.")

                sel_type_label = c2.selectbox("Tipo", ["Plato Principal", "Acompañamiento", "Ensalada"])
                type_map = {"Plato Principal": "principal", "Acompañamiento": "side", "Ensalada": "salad"}
                sel_type_code = type_map[sel_type_label]
                
                c3, c4 = st.columns([1, 3])
                opt_num = c3.number_input("Opción #", min_value=1, value=1)
                desc = c4.text_input("Descripción del Plato", placeholder="Ej: Milanesa con puré")
                
                if st.form_submit_button("➕ Agregar Plato"):
                    if desc:
                        ok, msg = create_menu_item(db, sel_week_id, sel_day_code, sel_type_code, opt_num, desc)
                        if ok: st.success(msg); st.rerun()
                        else: st.error(msg)
                    else:
                        st.error("Falta la descripción del plato.")

            # 3. LISTADO DE PLATOS EXISTENTES
            st.markdown("---")
            st.markdown("#### 📋 Platos cargados en esta semana")
            
            items = db.query(MenuItem).filter(MenuItem.week_id == sel_week_id).order_by(MenuItem.day, MenuItem.type, MenuItem.option_number).all()
            
            if items:
                for item in items:
                    # Traducción visual
                    d_es = next((d[1] for d in days_map if d[0] == item.day), item.day)
                    t_es = next((k for k, v in type_map.items() if v == item.type), item.type)
                    
                    col_txt, col_del = st.columns([4, 1])
                    col_txt.text(f"[{d_es}] {t_es} #{item.option_number}: {item.description}")
                    
                    if col_del.button("❌", key=f"del_item_{item.id}"):
                        delete_menu_item(db, item.id)
                        st.rerun()
            else:
                st.info("Aún no hay platos cargados.")

    # --- TAB 3: OFICINAS ---
    with tab3:
        st.subheader("Gestión de Oficinas")
        with st.form("create_office"):
            new_off_name = st.text_input("Nombre de Nueva Oficina")
            if st.form_submit_button("Crear Oficina"):
                if new_off_name:
                    ok, msg = create_office(db, new_off_name)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
        st.divider()
        offices = get_all_offices(db)
        if offices:
            for off in offices:
                c1, c2 = st.columns([3, 1])
                c1.write(f"🏢 **{off.name}**")
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
            
            all_offices = get_all_offices(db)
            if not all_offices: st.warning("No hay oficinas configuradas.")
            
            st.info("Generar reporte individual por oficina:")
            for office in all_offices:
                col_btn, col_dl = st.columns([1, 1])
                with col_btn:
                    if st.button(f"📄 {office.name}", key=f"btn_exp_{office.id}_{sel_week_ex_id}", use_container_width=True):
                        path, msg = export_week_to_excel(db, sel_week_ex_id, office.id)
                        if path: 
                            st.session_state[f"last_export_{office.id}"] = path
                            st.success(msg)
                        else: st.error(msg)
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
            if st.button("📦 Exportar TODAS las Oficinas (Consolidado)", type="primary"):
                path, msg = export_week_to_excel(db, sel_week_ex_id, None)
                if path:
                    with open(path, "rb") as f: st.download_button("⬇️ Descargar Consolidado", f, file_name=path.split("/")[-1])
            
            w_obj = db.query(Week).filter(Week.id == sel_week_ex_id).first()
            if w_obj and w_obj.is_open:
                st.markdown("---")
                st.error("🚫 Zona de Cierre Manual")
                if st.button("🔒 CERRAR SEMANA AHORA"):
                    path, msg = finalize_week_logic(db, sel_week_ex_id)
                    st.success("Semana cerrada."); st.rerun()
    
    db.close()
