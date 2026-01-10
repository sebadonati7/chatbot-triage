"""
UI Components for SIRAYA Health Navigator
Landing Page, Terms of Use, and Conditional Triage Logic
"""
import streamlit as st
import os
from pathlib import Path


def render_landing_page():
    """
    Renders the landing page with logo, terms of use, and acceptance gate.
    Returns True if user has accepted terms, False otherwise.
    """
    # Initialize session state for terms acceptance
    if 'terms_accepted' not in st.session_state:
        st.session_state.terms_accepted = False
    
    # If already accepted, skip landing page
    if st.session_state.terms_accepted:
        return True
    
    # Landing Page UI
    st.markdown('<div class="landing-container">', unsafe_allow_html=True)
    
    # Logo
    st.markdown('<div class="logo-container">', unsafe_allow_html=True)
    
    # Try to load SVG logo
    logo_path = Path("assets/logo.svg")
    if logo_path.exists():
        with open(logo_path, 'r', encoding='utf-8') as f:
            logo_svg = f.read()
        st.markdown(f'<div style="display: flex; justify-content: center;">{logo_svg}</div>', 
                    unsafe_allow_html=True)
    else:
        # Fallback: Text logo
        st.markdown("""
        <div style="font-size: 4em; font-weight: 300; letter-spacing: 0.2em; color: #4A90E2; margin: 40px 0;">
            SIRAYA
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Tagline
    st.markdown("""
    <div style="font-size: 1.2em; color: #6b7280; margin-bottom: 40px;">
        Health Navigator · AI-Powered Pre-Triage
    </div>
    """, unsafe_allow_html=True)
    
    # Terms of Use Expander
    with st.expander("📄 Condizioni di Utilizzo (clicca per leggere)", expanded=False):
        terms_path = Path("assets/terms_of_use.md")
        if terms_path.exists():
            with open(terms_path, 'r', encoding='utf-8') as f:
                terms_content = f.read()
            st.markdown(terms_content)
        else:
            # Fallback terms
            st.markdown("""
            ### Condizioni di Utilizzo
            
            **IMPORTANTE**: Questo servizio NON sostituisce la valutazione medica professionale.
            
            - ⚠️ In caso di emergenza, chiamare il **118**
            - 🩺 Le informazioni fornite sono indicative
            - 💊 Non prescrive farmaci o diagnosi
            - 📊 Basato su AI, può contenere imprecisioni
            
            Utilizzando il servizio, accetti che:
            - Le informazioni sono a scopo orientativo
            - La responsabilità clinica rimane del professionista sanitario
            - I dati sono trattati secondo GDPR
            """)
    
    st.markdown('<div style="height: 30px;"></div>', unsafe_allow_html=True)
    
    # Acceptance Checkbox and Button
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        accept_checkbox = st.checkbox(
            "Ho letto e accetto le condizioni di utilizzo",
            key="terms_checkbox"
        )
        
        st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)
        
        if st.button(
            "✓ Accetta e Procedi",
            disabled=not accept_checkbox,
            use_container_width=True,
            key="accept_terms_button"
        ):
            st.session_state.terms_accepted = True
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Footer
    st.markdown("""
    <div style="position: fixed; bottom: 20px; left: 0; right: 0; text-align: center; color: #9ca3af; font-size: 0.85em;">
        Servizio Sanitario Regionale Emilia-Romagna · v2.1 · Gennaio 2026
    </div>
    """, unsafe_allow_html=True)
    
    return False


def detect_medical_intent(user_input: str, orchestrator=None) -> bool:
    """
    Detects if user input contains medical/triage intent.
    Returns True if medical assistance is needed, False for general queries.
    
    Args:
        user_input: User's message
        orchestrator: ModelOrchestrator instance (optional, for AI-based detection)
    
    Returns:
        bool: True if medical intent detected
    """
    if not user_input:
        return False
    
    user_input_lower = user_input.lower()
    
    # Medical keywords (Italian)
    medical_keywords = [
        # Symptoms
        'dolore', 'male', 'febbre', 'tosse', 'nausea', 'vomito', 'diarrea',
        'vertigini', 'capogiro', 'svenimento', 'sangue', 'emorragia',
        'respiro', 'affanno', 'palpitazioni', 'convulsioni', 'trauma',
        'caduta', 'incidente', 'bruciore', 'prurito', 'gonfiore', 'eruzione',
        'cefalea', 'emicrania', 'dispnea', 'tachicardia', 'bradicardia',
        
        # Body parts
        'testa', 'petto', 'torace', 'addome', 'pancia', 'stomaco', 'cuore',
        'polmoni', 'gola', 'orecchio', 'occhio', 'naso', 'bocca', 'denti',
        'braccio', 'gamba', 'schiena', 'collo', 'spalla', 'ginocchio',
        
        # Medical terms
        'sintomo', 'sintomi', 'malattia', 'infezione', 'allergia', 'asma',
        'diabete', 'ipertensione', 'pressione', 'glicemia', 'temperatura',
        
        # Triage-related
        'urgente', 'emergenza', 'grave', 'acuto', 'cronico', 'peggiorato',
        'medico', 'dottore', 'ospedale', 'pronto soccorso', 'ambulanza',
        'visita', 'consulto', 'diagnosi', 'cura', 'terapia', 'farmaco'
    ]
    
    # Check for medical keywords
    medical_match_count = sum(1 for keyword in medical_keywords if keyword in user_input_lower)
    
    # Threshold: 2+ medical keywords = likely medical intent
    if medical_match_count >= 2:
        return True
    
    # Single strong medical keyword
    strong_keywords = ['dolore', 'sangue', 'emergenza', 'urgente', 'febbre', 'trauma', 'svenimento']
    if any(keyword in user_input_lower for keyword in strong_keywords):
        return True
    
    # Questions about symptoms or health
    health_questions = ['sto male', 'non sto bene', 'mi sento', 'ho bisogno di aiuto', 
                        'cosa devo fare', 'devo andare', 'è grave', 'è normale']
    if any(phrase in user_input_lower for phrase in health_questions):
        return True
    
    # Default: not medical
    return False


def get_bot_avatar():
    """
    Returns the bot avatar (SIRAYA logo S).
    Returns path to image or emoji fallback.
    """
    logo_path = Path("assets/logo.svg")
    if logo_path.exists():
        return str(logo_path)
    else:
        # Fallback to emoji
        return "🩺"


def render_triage_controls(show_controls: bool = True):
    """
    Renders triage control buttons conditionally.
    Only shown when medical intent is detected.
    
    Args:
        show_controls: Whether to show the triage controls
    """
    if not show_controls:
        return
    
    st.markdown('<div class="triage-controls">', unsafe_allow_html=True)
    st.markdown("**Controlli Triage**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📋 Triage", key="btn_triage_main", use_container_width=True):
            st.session_state.show_triage_mode = True
            st.rerun()
    
    with col2:
        if st.button("⏭️ Avanti", key="btn_next_step", use_container_width=True):
            # Logic to advance step
            pass
    
    with col3:
        if st.button("🔄 Reset", key="btn_reset_session", use_container_width=True):
            # Logic to reset session
            pass
    
    st.markdown('</div>', unsafe_allow_html=True)


def apply_siraya_branding():
    """
    Applies SIRAYA brand styling to the app.
    Call this after st.set_page_config().
    """
    st.markdown("""
    <style>
    /* SIRAYA Brand Identity */
    :root {
        --siraya-blue: #4A90E2;
        --siraya-dark-blue: #357ABD;
        --siraya-light-gray: #f9fafb;
        --siraya-border: #e5e7eb;
    }
    
    /* Clean professional look */
    .main {
        background-color: #ffffff;
    }
    
    /* Button styling */
    .stButton>button {
        border-radius: 8px;
        border: 1px solid var(--siraya-border);
        font-weight: 500;
        transition: all 0.2s;
    }
    
    .stButton>button:hover {
        border-color: var(--siraya-blue);
        box-shadow: 0 2px 8px rgba(74, 144, 226, 0.15);
    }
    
    /* Chat message styling */
    .stChatMessage {
        border-radius: 8px;
        padding: 12px;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: var(--siraya-light-gray);
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

