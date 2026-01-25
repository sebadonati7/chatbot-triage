"""
SIRAYA Health Navigator - UI Components & Admin Tools
V4.0: Componenti riutilizzabili per UI e strumenti admin
"""

import streamlit as st
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd

# ============================================================================
# ADMIN TOOLS
# ============================================================================

def show_admin_logs(limit: int = 50):
    """
    Visualizza log recenti da Supabase per debugging.
    Mostra gli ultimi N record in un dataframe interattivo.
    
    Args:
        limit: Numero massimo di log da visualizzare (default 50)
    """
    st.markdown("### 🔍 Admin Panel - Recent Logs")
    st.caption(f"Ultimi {limit} log da Supabase")
    
    try:
        from session_storage import get_logger
        
        logger = get_logger()
        
        if not logger.client:
            st.error("❌ Connessione Supabase non disponibile")
            st.info("💡 Verifica che le credenziali SUPABASE_URL e SUPABASE_KEY siano configurate in st.secrets")
            return
        
        # Recupera log
        with st.spinner("Caricamento log da Supabase..."):
            logs = logger.get_recent_logs(limit=limit)
        
        if not logs:
            st.warning("⚠️ Nessun log disponibile")
            return
        
        # Converti a DataFrame per visualizzazione
        df_data = []
        for log in logs:
            # Parse metadata JSON
            try:
                metadata = json.loads(log.get('metadata', '{}'))
            except:
                metadata = {}
            
            df_data.append({
                'Session ID': log.get('session_id', 'N/A')[:8],  # Prime 8 char
                'Timestamp': log.get('timestamp', 'N/A'),
                'User Input': log.get('user_input', '')[:50],  # Prime 50 char
                'Bot Response': log.get('bot_response', '')[:50],
                'Duration (ms)': log.get('duration_ms', 0),
                'Triage Step': metadata.get('triage_step', 'N/A'),
                'Urgency Code': metadata.get('urgency_code', 'N/A')
            })
        
        df = pd.DataFrame(df_data)
        
        # Statistiche rapide
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📊 Total Logs", len(logs))
        with col2:
            unique_sessions = len(set(log.get('session_id') for log in logs))
            st.metric("👥 Unique Sessions", unique_sessions)
        with col3:
            avg_duration = sum(log.get('duration_ms', 0) for log in logs) / len(logs) if logs else 0
            st.metric("⚡ Avg Response (ms)", f"{avg_duration:.0f}")
        
        st.divider()
        
        # Dataframe interattivo
        st.dataframe(
            df,
            use_container_width=True,
            height=400
        )
        
        # Export JSON completo (espandibile)
        with st.expander("📥 Export Raw JSON"):
            st.json(logs)
        
    except ImportError as e:
        st.error(f"❌ Errore import: {e}")
        st.info("💡 Assicurati che session_storage.py sia presente nel progetto")
    except Exception as e:
        st.error(f"❌ Errore visualizzazione log: {e}")


def show_session_stats(session_id: str):
    """
    Visualizza statistiche dettagliate per una sessione specifica.
    
    Args:
        session_id: ID sessione da analizzare
    """
    st.markdown(f"### 📊 Session Analytics: `{session_id}`")
    
    try:
        from session_storage import get_logger
        
        logger = get_logger()
        
        if not logger.client:
            st.error("❌ Connessione Supabase non disponibile")
            return
        
        # Recupera log sessione
        logs = logger.get_recent_logs(limit=1000, session_id=session_id)
        
        if not logs:
            st.warning(f"⚠️ Nessun log trovato per sessione {session_id}")
            return
        
        # Analisi sessione
        total_interactions = len(logs)
        total_duration = sum(log.get('duration_ms', 0) for log in logs)
        avg_duration = total_duration / total_interactions if total_interactions > 0 else 0
        
        # Estrai metadata
        triage_steps = []
        urgency_codes = []
        for log in logs:
            try:
                metadata = json.loads(log.get('metadata', '{}'))
                if metadata.get('triage_step'):
                    triage_steps.append(metadata['triage_step'])
                if metadata.get('urgency_code'):
                    urgency_codes.append(metadata['urgency_code'])
            except:
                continue
        
        # Metriche
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("💬 Interazioni", total_interactions)
        with col2:
            st.metric("⏱️ Durata Totale", f"{total_duration/1000:.1f}s")
        with col3:
            st.metric("⚡ Risposta Media", f"{avg_duration:.0f}ms")
        with col4:
            final_code = urgency_codes[-1] if urgency_codes else "N/A"
            st.metric("🏥 Codice Finale", final_code)
        
        # Timeline interazioni
        st.markdown("#### 📈 Timeline Interazioni")
        for i, log in enumerate(logs, 1):
            with st.expander(f"Interazione {i} - {log.get('timestamp', 'N/A')}"):
                st.markdown(f"**👤 User:** {log.get('user_input', 'N/A')}")
                st.markdown(f"**🤖 Bot:** {log.get('bot_response', 'N/A')}")
                st.caption(f"Duration: {log.get('duration_ms', 0)}ms")
        
    except Exception as e:
        st.error(f"❌ Errore analisi sessione: {e}")


# ============================================================================
# UI COMPONENTS RIUTILIZZABILI
# ============================================================================

def render_metric_card(title: str, value: str, delta: Optional[str] = None, icon: str = "📊"):
    """
    Renderizza card metrica stilizzata.
    
    Args:
        title: Titolo metrica
        value: Valore principale
        delta: Variazione (opzionale)
        icon: Icona (default 📊)
    """
    delta_html = f"<div style='color: #10b981; font-size: 0.9em;'>{delta}</div>" if delta else ""
    
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 20px; border-radius: 15px; color: white; margin-bottom: 15px;'>
        <div style='font-size: 2em; margin-bottom: 5px;'>{icon}</div>
        <div style='font-size: 0.9em; opacity: 0.9;'>{title}</div>
        <div style='font-size: 2em; font-weight: bold; margin: 10px 0;'>{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def render_status_badge(status: str, color: str = "#3b82f6"):
    """
    Renderizza badge di stato inline.
    
    Args:
        status: Testo badge
        color: Colore hex (default blu)
    """
    st.markdown(f"""
    <span style='background-color: {color}; color: white; padding: 4px 12px; 
                 border-radius: 12px; font-size: 0.85em; font-weight: 500;'>
        {status}
    </span>
    """, unsafe_allow_html=True)


def render_info_box(title: str, content: str, type: str = "info"):
    """
    Renderizza box informativo stilizzato.
    
    Args:
        title: Titolo box
        content: Contenuto
        type: Tipo (info, warning, error, success)
    """
    colors = {
        "info": {"bg": "#dbeafe", "border": "#3b82f6", "text": "#1e40af"},
        "warning": {"bg": "#fef3c7", "border": "#f59e0b", "text": "#92400e"},
        "error": {"bg": "#fee2e2", "border": "#ef4444", "text": "#991b1b"},
        "success": {"bg": "#d1fae5", "border": "#10b981", "text": "#065f46"}
    }
    
    theme = colors.get(type, colors["info"])
    
    st.markdown(f"""
    <div style='background-color: {theme["bg"]}; border-left: 4px solid {theme["border"]}; 
                padding: 15px; border-radius: 8px; margin: 15px 0;'>
        <div style='color: {theme["text"]}; font-weight: 600; margin-bottom: 8px;'>{title}</div>
        <div style='color: {theme["text"]};'>{content}</div>
    </div>
    """, unsafe_allow_html=True)


def render_loading_state(message: str = "Caricamento in corso..."):
    """
    Renderizza stato di caricamento personalizzato.
    
    Args:
        message: Messaggio da visualizzare
    """
    st.markdown(f"""
    <div style='text-align: center; padding: 40px;'>
        <div style='font-size: 3em; animation: pulse 2s infinite;'>⏳</div>
        <div style='color: #6b7280; margin-top: 15px;'>{message}</div>
    </div>
    <style>
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
    </style>
    """, unsafe_allow_html=True)


def render_empty_state(title: str = "Nessun dato disponibile", 
                        description: str = "Inizia una nuova sessione per visualizzare i dati",
                        icon: str = "📭"):
    """
    Renderizza stato vuoto stilizzato.
    
    Args:
        title: Titolo
        description: Descrizione
        icon: Icona
    """
    st.markdown(f"""
    <div style='text-align: center; padding: 60px 20px; color: #6b7280;'>
        <div style='font-size: 4em; margin-bottom: 20px;'>{icon}</div>
        <div style='font-size: 1.5em; font-weight: 600; margin-bottom: 10px; color: #374151;'>
            {title}
        </div>
        <div style='font-size: 1em;'>{description}</div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# NAVIGATION HELPERS
# ============================================================================

def render_navigation_sidebar():
    """
    Renderizza sidebar di navigazione unificata.
    DEVE essere chiamata all'interno di st.sidebar context.
    
    Returns:
        str: Pagina selezionata ("Chatbot" o "Analytics")
    """
    st.markdown("""
    <div style="text-align: center; padding: 20px 0;">
        <div style="font-size: 2em; font-weight: 300; letter-spacing: 0.15em; color: #4A90E2;">
            SIRAYA
        </div>
        <div style="font-size: 0.85em; color: #6b7280; margin-top: 5px;">
            Health Navigator
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # Navigation Radio
    page = st.radio(
        "🧭 Navigazione",
        ["🤖 Chatbot Triage", "📊 Analytics Dashboard"],
        label_visibility="collapsed"
    )
    
    st.divider()
    
    # Connection Status
    st.markdown("**📡 Stato Sistema**")
    
    # Check Supabase connection
    try:
        from session_storage import get_logger
        logger = get_logger()
        if logger.client:
            st.success("✅ Database Connesso")
        else:
            st.warning("⚠️ Database Offline")
    except:
        st.error("❌ Errore Sistema")
    
    return page
