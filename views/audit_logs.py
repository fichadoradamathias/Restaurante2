import streamlit as st
import pandas as pd
from database.models import AuditLog

def audit_log_page(SessionLocal, current_user_name):
    # 1. Seguridad: Verificamos el ROL en session_state, no solo el nombre pasado
    if st.session_state.get("role") != "admin":
        st.error("⛔ Acceso denegado. Se requieren permisos de Administrador.")
        return

    st.title("🛡️ Registro de Auditoría (Admin Logs)") 
    st.info(f"Sesión activa: {current_user_name}")

    db = SessionLocal()

    try:
        # 2. Obtener logs (el nuevo modelo ya tiene actor_id como String con el nombre)
        audit_logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
        
        if audit_logs:
            
            # 3. Función para formatear el detalle (RECUPERADA DE TU CÓDIGO)
            def format_change(log):
                # Si hay valores de antes y después, los mostramos bonito
                if log.old_value or log.new_value:
                    detail_text = log.details if log.details else "Modificación"
                    return f"**{detail_text}**\nDe: `{log.old_value}`\nA: `{log.new_value}`"
                
                # Si no, mostramos solo los detalles o la acción
                return log.details or log.action

            # 4. Convertir a lista de diccionarios
            log_data = []
            for log in audit_logs:
                log_data.append({
                    "Fecha/Hora": log.timestamp.strftime("%Y-%m-%d %H:%M"),
                    "Actor": log.actor_id, # Ahora es un String, muestra el nombre directo
                    "Acción": log.action,
                    "Target": log.target_username,
                    "Detalles del Cambio": format_change(log)
                })

            df_logs = pd.DataFrame(log_data)
            
            # 5. Mostrar tabla con configuración visual (RECUPERADA)
            st.dataframe(
                df_logs, 
                use_container_width=True, 
                height=500, 
                hide_index=True,
                column_config={
                    "Fecha/Hora": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
                    "Detalles del Cambio": st.column_config.TextColumn("Detalles", width="large"),
                    "Actor": st.column_config.TextColumn("Admin/Actor", width="small"),
                }
            )
            
            if st.button("🔄 Actualizar Tabla"):
                st.rerun()
            
        else:
            st.info("📭 No se encontraron registros de auditoría aún.")

    except Exception as e:
        st.error(f"Error al cargar logs: {e}")
    finally:
        db.close()