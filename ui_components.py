"""
SIRAYA UI Components - Professional Medical Grade
Single Consent Flow + Logo Integration + Brand Identity
Version: 3.0 (Professional Refactoring)
"""
import streamlit as st
import base64
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def load_image_base64(image_path: str) -> Optional[str]:
    """Load image and convert to base64 for embedding."""
    try:
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        logger.warning(f"Could not load image {image_path}: {e}")
        return None


def inject_siraya_css():
    """
    Inject comprehensive Medical Professional CSS theme.
    Typography: Inter from Google Fonts
    Palette: Medical Professional (Background #f8fafc, Sidebar #1e293b, Primary #06b6d4, Danger #ef4444)
    """
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* ==================== GLOBAL TYPOGRAPHY ==================== */
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    }
    
    /* ==================== LAYOUT & BACKGROUND ==================== */
    .stApp {
        background-color: #F5F5F5;
    }
    
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* ==================== FIX CHAT OVERLAPPING ==================== */
    .stChatMessage {
        margin-bottom: 20px !important;
        padding: 16px 20px !important;
        border-radius: 12px !important;
    }
    
    .stChatMessage[data-testid="user"] {
        background-color: #ffffff;
        border-left: 3px solid #e5e7eb;
    }
    
    .stChatMessage[data-testid="assistant"] {
        background-color: #fafafa;
        border-left: 3px solid #d1d5db;
    }
    
    /* Fix spacing between chat messages */
    div[data-testid="stChatMessageContainer"] {
        margin-bottom: 24px !important;
    }
    
    /* Fix chat input spacing */
    .stChatInput {
        margin-top: 20px !important;
        padding: 12px !important;
    }
    
    /* ==================== SIDEBAR ==================== */
    section[data-testid="stSidebar"] {
        background-color: #1e293b !important;
    }
    
    section[data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #ffffff !important;
    }
    
    /* ==================== SIDEBAR: COLORI BIANCO/PANNA PER EXPANDER E BOX ==================== */
    /* Expander Header e Content - Bianco/Panna */
    .streamlit-expanderHeader {
        background-color: #FDFCF0 !important;
        color: #1e293b !important;
        border-radius: 8px !important;
        padding: 12px !important;
        margin-bottom: 8px !important;
    }
    
    .streamlit-expanderContent {
        background-color: #FDFCF0 !important;
        color: #1e293b !important;
        border-radius: 8px !important;
        padding: 16px !important;
    }
    
    /* Alert Box evidenziati - Bianco/Panna */
    [data-testid="stSidebar"] [data-testid="stAlert"] {
        background-color: #FDFCF0 !important;
        color: #1e293b !important;
        border-left: 4px solid #06b6d4 !important;
    }
    
    /* Metric Container - Bianco/Panna */
    [data-testid="stSidebar"] [data-testid="stMetricContainer"] {
        background-color: #FDFCF0 !important;
        color: #1e293b !important;
        border-radius: 8px !important;
        padding: 12px !important;
    }
    
    /* Info Box - Bianco/Panna */
    [data-testid="stSidebar"] .stInfo {
        background-color: #FDFCF0 !important;
        color: #1e293b !important;
    }
    
    /* Warning Box - Bianco/Panna con bordo arancione */
    [data-testid="stSidebar"] .stWarning {
        background-color: #FDFCF0 !important;
        color: #1e293b !important;
        border-left: 4px solid #ff9800 !important;
    }
    
    /* Error Box - Bianco/Panna con bordo rosso */
    [data-testid="stSidebar"] .stError {
        background-color: #FDFCF0 !important;
        color: #1e293b !important;
        border-left: 4px solid #ef4444 !important;
    }
    
    /* ==================== METRIC CARDS ==================== */
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
        border-left: 4px solid #06b6d4;
        margin-bottom: 16px;
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transform: translateY(-2px);
    }
    
    .metric-card.primary {
        border-left-color: #06b6d4;
    }
    
    .metric-card.danger {
        border-left-color: #ef4444;
    }
    
    .metric-card.warning {
        border-left-color: #f59e0b;
    }
    
    .metric-card.success {
        border-left-color: #10b981;
    }
    
    .metric-card h3 {
        margin-top: 0;
        font-size: 0.875rem;
        font-weight: 500;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .metric-card .value {
        font-size: 2rem;
        font-weight: 700;
        color: #0f172a;
        margin: 8px 0;
    }
    
    .metric-card .description {
        font-size: 0.875rem;
        color: #64748b;
    }
    
    /* ==================== BUTTONS ==================== */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
        border: none;
        width: 100%;
        padding: 0.5rem 1rem;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(6, 182, 212, 0.3);
    }
    
    /* Primary Button - Grigio chiaro Siraya */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #F5F5F5 0%, #E5E5E5 100%);
        color: #1f2937;
        border: 1px solid #d1d5db;
    }
    
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #E5E5E5 0%, #D4D4D4 100%);
        border-color: #9ca3af;
    }
    
    /* Secondary Button */
    .stButton > button[kind="secondary"] {
        background-color: #f1f5f9;
        color: #475569;
        border: 1px solid #cbd5e1;
    }
    
    .stButton > button[kind="secondary"]:hover {
        background-color: #e2e8f0;
    }
    
    /* ==================== HIDE STREAMLIT BRANDING ==================== */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* ==================== LANDING PAGE ==================== */
    .landing-container {
        max-width: 700px;
        margin: 0 auto;
        padding: 60px 20px;
        text-align: center;
    }
    
    .logo-main {
        margin: 40px auto;
        max-width: 320px;
        animation: fadeInDown 0.8s ease-out;
    }
    
    @keyframes fadeInDown {
        from {
            opacity: 0;
            transform: translateY(-20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .logo-chat {
        position: fixed;
        top: 80px;
        left: 300px;
        width: 50px;
        opacity: 0.85;
        z-index: 999;
        transition: opacity 0.3s;
    }
    
    .logo-chat:hover {
        opacity: 1;
    }
    
    /* ==================== DISCLAIMER BOX ==================== */
    .disclaimer-box {
        background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
        border: 2px solid #f59e0b;
        border-radius: 12px;
        padding: 28px;
        margin: 40px 0;
        text-align: left;
        box-shadow: 0 4px 6px -1px rgba(245, 158, 11, 0.1);
    }
    
    .disclaimer-box h3 {
        color: #ea580c;
        margin-top: 0;
        font-size: 1.25rem;
        font-weight: 600;
    }
    
    .disclaimer-box p {
        color: #92400e;
        line-height: 1.7;
    }
    
    .disclaimer-box ul {
        color: #92400e;
        line-height: 1.9;
        padding-left: 20px;
    }
    
    .disclaimer-box strong {
        color: #7c2d12;
        font-weight: 600;
    }
    
    /* ==================== CHAT STYLING ==================== */
    .stChatMessage {
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
    }
    
    .stChatInput > div > div > input {
        border-radius: 12px;
        border: 2px solid #cbd5e1;
        font-size: 1rem;
    }
    
    .stChatInput > div > div > input:focus {
        border-color: #06b6d4;
        box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.1);
    }
    
    /* ==================== EXPANDER ==================== */
    .streamlit-expanderHeader {
        background-color: #f8fafc;
        border-radius: 8px;
        font-weight: 500;
    }
    
    /* ==================== PROGRESS BAR ==================== */
    .stProgress > div > div > div > div {
        background-color: #06b6d4;
    }
    
    /* ==================== ALERTS ==================== */
    .stAlert {
        border-radius: 8px;
    }
    
    </style>
    """, unsafe_allow_html=True)


def render_landing_page() -> bool:
    """
    Single-step consent flow with SIRAYA branding.
    Professional Medical Grade design.
    
    Returns:
        True if user has accepted terms, False otherwise
    """
    # Initialize session state
    if 'terms_accepted' not in st.session_state:
        st.session_state.terms_accepted = False
    
    # If already accepted, skip landing page
    if st.session_state.terms_accepted:
        return True
    
    # Inject CSS
    inject_siraya_css()
    
    # Landing Page Container
    st.markdown('<div class="landing-container">', unsafe_allow_html=True)
    
    # Logo - Try PNG first, fallback to text
    logo_png_path = Path("siraya_logo.png")
    logo_svg_path = Path("assets/logo.svg")
    
    logo_displayed = False
    
    # Try PNG logo first
    if logo_png_path.exists():
        logo_b64 = load_image_base64(str(logo_png_path))
        if logo_b64:
            st.markdown(f'''
            <div class="logo-main">
                <img src="data:image/png;base64,{logo_b64}" style="width: 100%; height: auto;">
            </div>
            ''', unsafe_allow_html=True)
            logo_displayed = True
    
    # Fallback to SVG logo
    if not logo_displayed and logo_svg_path.exists():
        try:
            with open(logo_svg_path, 'r', encoding='utf-8') as f:
                logo_svg = f.read()
            st.markdown(f'<div class="logo-main">{logo_svg}</div>', unsafe_allow_html=True)
            logo_displayed = True
        except Exception:
            pass
    
    # Final fallback: Text logo
    if not logo_displayed:
        st.markdown('''
        <div class="logo-main">
            <h1 style="font-size: 4.5em; font-weight: 300; letter-spacing: 0.2em; color: #06b6d4; margin: 0;">
                SIRAYA
            </h1>
        </div>
        ''', unsafe_allow_html=True)
    
    # Tagline
    st.markdown('''
    <div style="font-size: 1.4em; color: #64748b; margin: 30px 0 60px 0; font-weight: 300; letter-spacing: 0.02em;">
        Health Navigator · AI-Powered Pre-Triage
    </div>
    ''', unsafe_allow_html=True)
    
    # Disclaimer Box (Single Consent Flow)
    st.markdown('''
    <div class="disclaimer-box">
        <h3>⚠️ Avvertenze Importanti - Leggere Attentamente</h3>
        <p style="margin: 16px 0; line-height: 1.7; font-size: 1.05rem;">
            <strong>SIRAYA NON è un dispositivo medico certificato</strong> e non sostituisce 
            la valutazione di un professionista sanitario qualificato.
        </p>
        <ul style="text-align: left; line-height: 2; margin: 20px 0;">
            <li><strong style="color: #dc2626;">🚨 Emergenze</strong>: In caso di pericolo di vita immediato, chiamare subito il <strong>118</strong></li>
            <li><strong>🩺 Scopo del Servizio</strong>: Fornisce orientamento preliminare, NON diagnosi o prescrizioni mediche</li>
            <li><strong>🤖 Tecnologia AI</strong>: Sistema basato su intelligenza artificiale, può contenere errori o imprecisioni</li>
            <li><strong>📊 Privacy GDPR</strong>: I dati raccolti sono trattati secondo normativa europea sulla privacy</li>
            <li><strong>👨‍⚕️ Responsabilità</strong>: La decisione clinica finale spetta sempre a un medico abilitato</li>
        </ul>
        <p style="margin: 16px 0; font-size: 0.95rem; font-style: italic;">
            Questo strumento è progettato per assistere gli operatori sanitari nel processo di triage iniziale,
            non per sostituire il giudizio clinico professionale.
        </p>
    </div>
    ''', unsafe_allow_html=True)
    
    # Consent Checkbox
    st.markdown('<div style="margin: 40px 0 20px 0;">', unsafe_allow_html=True)
    consent_check = st.checkbox(
        "✓ Ho letto e compreso le avvertenze. Accetto di utilizzare SIRAYA come strumento di orientamento preliminare.",
        key="consent_checkbox_main"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Consent Button (disabled until checkbox is checked)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if consent_check:
            if st.button("✅ Accetto e Inizia", type="primary", use_container_width=True, key="consent_button_active"):
                st.session_state.terms_accepted = True
                logger.info("User accepted terms - redirecting to main application")
                st.rerun()
        else:
            st.button("✅ Accetto e Inizia", type="primary", use_container_width=True, disabled=True, key="consent_button_disabled")
    
    # Footer
    st.markdown('''
    <div style="margin-top: 80px; padding-top: 30px; border-top: 1px solid #e2e8f0; color: #94a3b8; font-size: 0.9em; text-align: center;">
        <p style="margin: 5px 0;">Servizio Sanitario Regionale Emilia-Romagna</p>
        <p style="margin: 5px 0; font-size: 0.85em;">SIRAYA Health Navigator v3.0 · Gennaio 2026</p>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    return False


def render_chat_logo():
    """
    Render small SIRAYA logo in top-left corner of chat interface.
    """
    logo_png_path = Path("siraya_logo.png")
    logo_svg_path = Path("assets/logo.svg")
    
    # Try PNG first
    if logo_png_path.exists():
        logo_b64 = load_image_base64(str(logo_png_path))
        if logo_b64:
            st.markdown(f'''
            <div class="logo-chat">
                <img src="data:image/png;base64,{logo_b64}" style="width: 100%; height: auto; border-radius: 8px;">
            </div>
            ''', unsafe_allow_html=True)
            return
    
    # Fallback to SVG
    if logo_svg_path.exists():
        try:
            with open(logo_svg_path, 'r', encoding='utf-8') as f:
                logo_svg = f.read()
            st.markdown(f'<div class="logo-chat">{logo_svg}</div>', unsafe_allow_html=True)
            return
        except Exception:
            pass


def get_bot_avatar() -> str:
    """
    Return bot avatar - "S" nera stilizzata.
    
    Returns:
        str: Path to SVG file or fallback emoji
    """
    # Try to use SVG "S" nera stilizzata
    svg_path = Path("assets/siraya_s_avatar.svg")
    if svg_path.exists():
        return str(svg_path)
    
    # Fallback: emoji "S" nera (black circle)
    return "⚫"


def detect_medical_intent(user_input: str, orchestrator=None) -> bool:
    """
    Enhanced medical intent detection with keyword analysis.
    Distinguishes between TRIAGE (medical) and INFORMAZIONI (general queries).
    
    Args:
        user_input: User's message text
        orchestrator: ModelOrchestrator instance (optional, for AI-based detection)
    
    Returns:
        bool: True if medical/triage intent detected, False for general information
    """
    if not user_input or len(user_input.strip()) < 3:
        return False
    
    user_lower = user_input.lower()
    
    # ========== INFORMATION KEYWORDS (Non-Medical) ==========
    info_keywords = [
        'orari', 'orario', 'aperto', 'chiuso', 'quando', 'dove',
        'indirizzo', 'telefono', 'numero', 'contatto', 'email',
        'servizio', 'servizi', 'prenotare', 'prenotazione', 'appuntamento',
        'farmacia', 'farmacie', 'guardia medica', 'cup',
        'come arrivare', 'come raggiungere', 'indicazioni'
    ]
    
    # If primarily informational, return False
    info_match_count = sum(1 for keyword in info_keywords if keyword in user_lower)
    if info_match_count >= 2 and 'dolore' not in user_lower and 'male' not in user_lower:
        logger.info(f"Information query detected (not medical): {info_match_count} info keywords")
        return False
    
    # ========== MEDICAL KEYWORDS (Triage Required) ==========
    medical_keywords = {
        # Symptoms
        'dolore', 'male', 'febbre', 'tosse', 'nausea', 'vomito', 'diarrea',
        'vertigini', 'capogiro', 'svenimento', 'sangue', 'emorragia', 'sanguinamento',
        'respiro', 'affanno', 'dispnea', 'palpitazioni', 'convulsioni', 'convulsione',
        'trauma', 'caduta', 'incidente', 'bruciore', 'prurito', 'gonfiore',
        'eruzione', 'rash', 'cefalea', 'emicrania', 'tachicardia', 'brachicardia',
        'sincope', 'collasso', 'shock', 'cianosi', 'pallore', 'sudorazione',
        'tremore', 'rigidità', 'paralisi', 'formicolio', 'intorpidimento',
        
        # Body parts (medical context)
        'testa', 'petto', 'torace', 'addome', 'pancia', 'stomaco', 'cuore',
        'polmoni', 'polmone', 'gola', 'orecchio', 'occhio', 'naso', 'bocca',
        'denti', 'dente', 'braccio', 'gamba', 'schiena', 'collo', 'spalla',
        'ginocchio', 'caviglia', 'mano', 'piede',
        
        # Medical conditions
        'sintomo', 'sintomi', 'malattia', 'infezione', 'allergia', 'asma',
        'diabete', 'ipertensione', 'pressione alta', 'pressione bassa',
        'glicemia', 'temperatura', 'ictus', 'infarto', 'angina',
        
        # Urgency indicators
        'urgente', 'emergenza', 'grave', 'acuto', 'improvviso', 'peggiorato',
        'peggiorando', 'aiuto', 'subito', 'immediato',
        
        # Medical care
        'medico', 'dottore', 'ospedale', 'pronto soccorso', 'ambulanza',
        '118', 'visita', 'consulto', 'diagnosi', 'cura', 'terapia',
        'farmaco', 'medicina'
    }
    
    # Count medical keyword matches
    medical_match_count = sum(1 for keyword in medical_keywords if keyword in user_lower)
    
    # Strong medical keywords (single match = definite medical intent)
    strong_medical = [
        'dolore', 'sangue', 'emergenza', 'urgente', 'febbre', 'trauma',
        'svenimento', 'convulsioni', 'infarto', 'ictus', 'shock', '118',
        'ambulanza', 'pronto soccorso', 'non respiro', 'non riesco a respirare'
    ]
    
    if any(keyword in user_lower for keyword in strong_medical):
        logger.info(f"Strong medical intent detected: {user_lower[:50]}...")
        return True
    
    # Multiple medical keywords = likely medical
    if medical_match_count >= 2:
        logger.info(f"Medical intent detected: {medical_match_count} medical keywords")
        return True
    
    # Health status phrases
    health_phrases = [
        'sto male', 'non sto bene', 'mi sento male', 'ho bisogno di aiuto',
        'cosa devo fare', 'devo andare', 'è grave', 'è pericoloso',
        'ho paura', 'sono preoccupato', 'mi fa male', 'ho un dolore'
    ]
    
    if any(phrase in user_lower for phrase in health_phrases):
        logger.info("Medical intent detected: health status phrase")
        return True
    
    # Use orchestrator for advanced detection if available
    if orchestrator:
        try:
            # Use orchestrator's urgency detection
            from smart_router import SmartRouter
            router = SmartRouter()
            urgency = router.classify_urgency(user_input)
            if urgency.assigned_branch.value == "TRIAGE":
                logger.info("Medical intent detected by SmartRouter")
                return True
        except Exception as e:
            logger.warning(f"Orchestrator detection failed: {e}")
    
    # Default: not medical
    logger.info("No medical intent detected - likely information query")
    return False


def render_metric_card(title: str, value: str, description: str = "", card_type: str = "primary"):
    """
    Render a professional metric card with Medical Professional styling.
    
    Args:
        title: Card header title
        value: Main metric value
        description: Optional description text
        card_type: Card color scheme (primary, danger, warning, success)
    """
    st.markdown(f'''
    <div class="metric-card {card_type}">
        <h3>{title}</h3>
        <div class="value">{value}</div>
        {f'<div class="description">{description}</div>' if description else ''}
    </div>
    ''', unsafe_allow_html=True)


def get_chat_placeholder() -> str:
    """
    Return the placeholder text for chat input.
    
    Returns:
        str: Placeholder text
    """
    return "Ciao, come posso aiutarti oggi?"
