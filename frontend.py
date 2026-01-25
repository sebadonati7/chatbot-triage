import streamlit as st
import asyncio
import time
from datetime import datetime

# --- CUSTOM MODULES ---
# Gestione sicura degli import per evitare crash totali
try:
    from session_storage import init_session_state, log_interaction_supabase
    from ui_components import render_navigation_sidebar, show_admin_logs
    import backend
    from model_orchestrator_v2 import Orchestrator
except ImportError as e:
    st.error(f"CRITICAL SYSTEM ERROR: Moduli mancanti. {e}")
    st.stop()

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="SIRAYA Health Navigator",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS STYLES (INLINE) ---
st.markdown("""
<style>
    /* Blue Sidebar Style */
    [data-testid="stSidebar"] {
        background-color: #f0f4f8;
        background-image: linear-gradient(180deg, #E3F2FD 0%, #FFFFFF 100%);
        border-right: 1px solid #d1d5db;
    }
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] p {
        color: #1f2937 !important;
    }
    /* Hide default header */
    .st-emotion-cache-15zrgzn {display: none;}
</style>
""", unsafe_allow_html=True)

# --- MAIN APP LOGIC ---
def main():
    # 1. Inizializzazione Sessione
    init_session_state()

    # 2. Sidebar & Navigazione
    with st.sidebar:
        try:
            selected_page = render_navigation_sidebar()
        except Exception as e:
            st.error(f"Errore Navigazione: {e}")
            selected_page = "Chatbot"

    # 3. Routing
    if selected_page == "Analytics":
        try:
            backend.render_dashboard()
        except Exception as e:
            st.error(f"Errore caricamento Analytics: {e}")
        return  # Stop execution here for Analytics

    # --- CHATBOT INTERFACE ---
    
    # Header
    st.title("🏥 SIRAYA Health Navigator")
    st.markdown("---")

    # Verifica Privacy
    if not st.session_state.get("privacy_accepted", False):
        st.info("Per continuare, accetta l'informativa sulla privacy nella barra laterale.")
        return

    # Inizializza Orchestrator
    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = Orchestrator()

    # Visualizza Cronologia Chat
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]
        with st.chat_message(role):
            st.markdown(content)

    # Input Utente
    if prompt := st.chat_input("Descrivi i tuoi sintomi..."):
        # 1. Mostra messaggio utente
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Generazione Risposta AI
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            # Spinner durante l'elaborazione
            with st.spinner("Analisi in corso..."):
                try:
                    # Chiamata asincrona all'orchestrator
                    response_generator = st.session_state.orchestrator.process_message(
                        prompt, 
                        st.session_state.session_id
                    )
                    
                    # Stream della risposta (se iterabile) o risposta diretta
                    if hasattr(response_generator, '__iter__'):
                        for chunk in response_generator:
                            full_response += chunk
                            message_placeholder.markdown(full_response + "▌")
                    else:
                        full_response = str(response_generator)
                    
                    message_placeholder.markdown(full_response)
                
                except Exception as e:
                    full_response = "Mi dispiace, si è verificato un errore tecnico. Riprova tra poco."
                    message_placeholder.error(f"Errore: {e}")
                    st.error(e) # Debug visibile

        # 3. Aggiornamento Stato
        st.session_state.messages.append({"role": "assistant", "content": full_response})

        # 4. Salvataggio Log (Supabase)
        # Eseguito UNA volta sola alla fine del ciclo
        try:
            log_interaction_supabase(
                user_input=prompt,
                bot_response=full_response,
                metadata={
                    "step": str(st.session_state.get("current_step", "Unknown")),
                    "specialization": st.session_state.get("specialization", "Generale"),
                    "location": st.session_state.get("location", "N/D")
                },
                duration_ms=0 # Implementare timer se necessario
            )
        except Exception as log_error:
            print(f"Log Error (Non-blocking): {log_error}")

# --- ENTRY POINT ---
if __name__ == "__main__":
    main()
