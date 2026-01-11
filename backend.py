"""
CHATBOT.ALPHA v2 - Analytics Dashboard
Analytics engine per visualizzazione KPI clinici e operativi.

Porta: 8502
Principi: Zero Pandas, Zero PX, Robustezza Assoluta
"""

import streamlit as st

# CONFIGURAZIONE PAGINA - DEVE ESSERE LA PRIMA ISTRUZIONE STREAMLIT
st.set_page_config(
    page_title="Health Navigator | Strategic Analytics",
    page_icon="🧬",
    layout="wide"
)

import json
import os
import re
import io
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import Dict, List, Any, Optional, Tuple
import plotly.graph_objects as go

# === GESTIONE DIPENDENZE OPZIONALI ===
# CRITICAL: Check fatto DOPO st.set_page_config per evitare crash
try:
    import xlsxwriter
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False
    # Warning mostrato in main() per non violare order rule

# === COSTANTI ===
LOG_FILE = "triage_logs.jsonl"
DISTRICTS_FILE = "distretti_sanitari_er.json"
def load_json_file(filepath: str) -> Dict:
    """Caricamento sicuro dei file JSON."""
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

# === MAPPATURE CLINICHE ===
RED_FLAGS_KEYWORDS = [
    "svenimento", "sangue", "confusione", "petto", "respiro",
    "paralisi", "convulsioni", "coscienza", "dolore torace",
    "emorragia", "trauma cranico", "infarto", "ictus"
]

SINTOMI_COMUNI = [
    "febbre", "tosse", "mal di testa", "nausea", "dolore addominale",
    "vertigini", "debolezza", "affanno", "palpitazioni", "diarrea",
    "vomito", "mal di gola", "dolore articolare", "eruzioni cutanee",
    "gonfiore", "bruciore", "prurito", "stanchezza"
]

SPECIALIZZAZIONI = [
    "Cardiologia", "Neurologia", "Ortopedia", "Gastroenterologia",
    "Pediatria", "Ginecologia", "Dermatologia", "Psichiatria",
    "Otorinolaringoiatria", "Oftalmologia", "Generale"
]
def cleanup_streamlit_cache():
    """Rimuove le cache fisiche che possono causare il 'Failed to fetch'"""
    cache_dirs = ['.streamlit/cache', '__pycache__']
    for d in cache_dirs:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
            except:
                pass

cleanup_streamlit_cache()
# --------------------------

# === CLASSE PRINCIPALE: TRIAGE DATA STORE ===
class TriageDataStore:
    """
    Storage e analisi dati triage con parsing robusto.
    """
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.records: List[Dict] = []
        self.sessions: Dict[str, List[Dict]] = {}
        self.parse_errors = 0
        
        self._load_data()
        self._enrich_data()
    
    def _load_data(self):
        """Caricamento JSONL con gestione errori robusta e encoding resiliente."""
        if not os.path.exists(self.filepath):
            st.warning(f"⚠️ File {self.filepath} non trovato. Nessun dato disponibile.")
            return
        
        if os.path.getsize(self.filepath) == 0:
            st.warning(f"⚠️ File {self.filepath} vuoto. Inizia un triage per popolare i dati.")
            return
        
        # CRITICAL: Prova encoding multipli per massima resilienza
        encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
        
        for encoding in encodings_to_try:
            try:
                with open(self.filepath, 'r', encoding=encoding, errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            record = json.loads(line)
                            self.records.append(record)
                        except json.JSONDecodeError as e:
                            self.parse_errors += 1
                            print(f"Warning: Riga {line_num} corrotta, skipping: {e}")
                            continue
                
                # Se siamo arrivati qui, l'encoding ha funzionato
                if encoding != 'utf-8':
                    print(f"Info: File caricato con encoding {encoding}")
                break
                
            except UnicodeDecodeError:
                # Prova con il prossimo encoding
                continue
            except Exception as e:
                if encoding == encodings_to_try[-1]:
                    # Ultimo tentativo fallito
                    st.error(f"❌ Errore lettura file con tutti gli encoding: {e}")
                    return
        
        if self.parse_errors > 0:
            st.info(f"ℹ️ {self.parse_errors} righe corrotte saltate durante il caricamento.")
    
    def _parse_timestamp_iso(self, timestamp_str: str) -> Optional[datetime]:
        """
        Parsing ISO robusto con correzione bug temporale.
        Supporta formati: ISO 8601, datetime standard.
        """
        if not timestamp_str:
            return None
        
        try:
            # Rimuovi 'Z' finale e converti in offset +00:00
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            
            # Parsing ISO 8601
            dt = datetime.fromisoformat(timestamp_str)
            
            # Fix timezone-aware to naive (usa orario locale)
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            
            return dt
        
        except ValueError:
            # Fallback: formati alternativi
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                try:
                    return datetime.strptime(timestamp_str, fmt)
                except ValueError:
                    continue
        
        except Exception as e:
            print(f"⚠️ Errore parsing timestamp '{timestamp_str}': {e}")
        
        return None
    
    def _enrich_data(self):
        """Arricchimento dati con calcoli temporali e NLP."""
        for record in self.records:
            # === PARSING TEMPORALE ROBUSTO ===
            timestamp_str = record.get('timestamp')
            dt = self._parse_timestamp_iso(timestamp_str)
            
            if dt:
                record['datetime'] = dt
                record['date'] = dt.date()
                record['year'] = dt.isocalendar()[0]
                record['month'] = dt.month
                record['week'] = dt.isocalendar()[1]  # Settimana ISO
                record['day_of_week'] = dt.weekday()  # 0=Lunedì, 6=Domenica
                record['hour'] = dt.hour
            else:
                # Fallback: timestamp corrente se mancante
                now = datetime.now()
                record['datetime'] = now
                record['date'] = now.date()
                record['year'] = now.year
                record['month'] = now.month
                record['week'] = now.isocalendar()[1]
                record['day_of_week'] = now.weekday()
                record['hour'] = now.hour
            
            # === NLP E CLASSIFICAZIONE ===
            user_input = str(record.get('user_input', '')).lower()
            bot_response = str(record.get('bot_response', '')).lower()
            combined_text = user_input + " " + bot_response
            
            # Red Flags Detection
            record['red_flags'] = [kw for kw in RED_FLAGS_KEYWORDS if kw in combined_text]
            record['has_red_flag'] = len(record['red_flags']) > 0
            
            # Sintomi Detection
            record['sintomi_rilevati'] = [s for s in SINTOMI_COMUNI if s in combined_text]
            
            # Estrazione Urgenza
            metadata = record.get('metadata', {})
            if isinstance(metadata, dict):
                record['urgenza'] = metadata.get('urgenza', metadata.get('urgency', 3))
                record['area_clinica'] = metadata.get('area', 'Non Specificato')
                record['specializzazione'] = metadata.get('specialization', 'Generale')
            else:
                record['urgenza'] = 3
                record['area_clinica'] = 'Non Specificato'
                record['specializzazione'] = 'Generale'
            
            # Organizzazione per Sessione
            session_id = record.get('session_id')
            if session_id:
                if session_id not in self.sessions:
                    self.sessions[session_id] = []
                self.sessions[session_id].append(record)
    
    def filter(self, year: Optional[int] = None, month: Optional[int] = None, 
               week: Optional[int] = None, district: Optional[str] = None) -> 'TriageDataStore':
        """
        Filtraggio records con creazione nuovo datastore.
        """
        filtered = TriageDataStore.__new__(TriageDataStore)
        filtered.filepath = self.filepath
        filtered.parse_errors = 0
        filtered.records = self.records.copy()
        filtered.sessions = {}
        
        if year is not None:
            filtered.records = [r for r in filtered.records if r.get('year') == year]
        
        if month is not None:
            filtered.records = [r for r in filtered.records if r.get('month') == month]
        
        if week is not None:
            filtered.records = [r for r in filtered.records if r.get('week') == week]
        
        if district and district != "Tutti":
            filtered.records = [r for r in filtered.records if r.get('comune', '').lower() == district.lower()]
        
        # Ricostruisci sessions
        for record in filtered.records:
            sid = record.get('session_id')
            if sid:
                if sid not in filtered.sessions:
                    filtered.sessions[sid] = []
                filtered.sessions[sid].append(record)
        
        return filtered
    
    def get_unique_values(self, field: str) -> List:
        """Estrae valori unici per un campo."""
        values = set()
        for record in self.records:
            val = record.get(field)
            if val is not None:
                values.add(val)
        return sorted(list(values))


# === FUNZIONI KPI ===
def calculate_kpi_volumetrici(datastore: TriageDataStore) -> Dict:
    """KPI Volumetrici: Sessioni, Throughput, Completion Rate."""
    kpi = {}
    
    # Sessioni Univoche
    kpi['sessioni_uniche'] = len(datastore.sessions)
    
    # Interazioni Totali
    kpi['interazioni_totali'] = len(datastore.records)
    
    # Throughput Orario (distribuzione)
    hours = [r.get('hour', 0) for r in datastore.records if r.get('hour') is not None]
    kpi['throughput_orario'] = Counter(hours)
    
    # Completion Rate (sessioni che raggiungono DISPOSITION)
    completed_sessions = 0
    for sid, records in datastore.sessions.items():
        # Controlla se c'è un record con step DISPOSITION o parole chiave finali
        for r in records:
            bot_resp = str(r.get('bot_response', '')).lower()
            if 'raccomand' in bot_resp or 'disposition' in bot_resp or 'pronto soccorso' in bot_resp:
                completed_sessions += 1
                break
    
    kpi['completion_rate'] = (completed_sessions / kpi['sessioni_uniche'] * 100) if kpi['sessioni_uniche'] > 0 else 0
    
    # Tempo Mediano Triage (calcolo approssimativo)
    session_durations = []
    for sid, records in datastore.sessions.items():
        if len(records) >= 2:
            timestamps = [r.get('datetime') for r in records if r.get('datetime')]
            if len(timestamps) >= 2:
                duration = (max(timestamps) - min(timestamps)).total_seconds() / 60  # minuti
                if duration < 120:  # Escludi sessioni "zombie" > 2h
                    session_durations.append(duration)
    
    if session_durations:
        session_durations.sort()
        median_idx = len(session_durations) // 2
        kpi['tempo_mediano_minuti'] = session_durations[median_idx]
    else:
        kpi['tempo_mediano_minuti'] = 0
    
    # Profondità Media (interazioni per sessione)
    kpi['profondita_media'] = kpi['interazioni_totali'] / kpi['sessioni_uniche'] if kpi['sessioni_uniche'] > 0 else 0
    
    return kpi


def calculate_kpi_clinici(datastore: TriageDataStore) -> Dict:
    """KPI Clinici: Sintomi, Urgenza, Red Flags."""
    kpi = {}
    
    # Spettro Sintomatologico Completo
    all_sintomi = []
    for r in datastore.records:
        all_sintomi.extend(r.get('sintomi_rilevati', []))
    kpi['spettro_sintomi'] = Counter(all_sintomi)
    
    # Stratificazione Urgenza
    urgenze = [r.get('urgenza', 3) for r in datastore.records]
    kpi['stratificazione_urgenza'] = Counter(urgenze)
    
    # Prevalenza Red Flags
    red_flags_count = sum(1 for r in datastore.records if r.get('has_red_flag', False))
    kpi['prevalenza_red_flags'] = (red_flags_count / len(datastore.records) * 100) if datastore.records else 0
    
    # Red Flags per Tipo
    all_red_flags = []
    for r in datastore.records:
        all_red_flags.extend(r.get('red_flags', []))
    kpi['red_flags_dettaglio'] = Counter(all_red_flags)
    
    return kpi


def calculate_kpi_context_aware(datastore: TriageDataStore) -> Dict:
    """KPI Context-Aware: Urgenza per Specializzazione, Deviazione PS."""
    kpi = {}
    
    # Urgenza Media per Specializzazione
    urgenza_per_spec = defaultdict(list)
    for r in datastore.records:
        spec = r.get('specializzazione', 'Generale')
        urgenza = r.get('urgenza', 3)
        urgenza_per_spec[spec].append(urgenza)
    
    kpi['urgenza_media_per_spec'] = {
        spec: sum(urgs) / len(urgs) if urgs else 0
        for spec, urgs in urgenza_per_spec.items()
    }
    
    # Tasso Deviazione PS per Area
    ps_keywords = ['pronto soccorso', 'ps', 'emergenza', '118']
    territorial_keywords = ['cau', 'guardia medica', 'medico di base', 'farmacia']
    
    deviazione_ps = 0
    deviazione_territoriale = 0
    
    for r in datastore.records:
        bot_resp = str(r.get('bot_response', '')).lower()
        if any(kw in bot_resp for kw in ps_keywords):
            deviazione_ps += 1
        elif any(kw in bot_resp for kw in territorial_keywords):
            deviazione_territoriale += 1
    
    total_recommendations = deviazione_ps + deviazione_territoriale
    kpi['tasso_deviazione_ps'] = (deviazione_ps / total_recommendations * 100) if total_recommendations > 0 else 0
    kpi['tasso_deviazione_territoriale'] = (deviazione_territoriale / total_recommendations * 100) if total_recommendations > 0 else 0
    
    return kpi


# === INTEGRAZIONE DISTRETTI ===
def load_district_mapping() -> Dict:
    """Carica mapping distretti sanitari."""
    if not os.path.exists(DISTRICTS_FILE):
        st.warning(f"⚠️ File {DISTRICTS_FILE} non trovato.")
        return {"health_districts": [], "comune_to_district_mapping": {}}
    
    try:
        with open(DISTRICTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"❌ Errore caricamento distretti: {e}")
        return {"health_districts": [], "comune_to_district_mapping": {}}


def map_comune_to_district(comune: str, district_data: Dict) -> str:
    """Mappa comune a distretto sanitario."""
    if not comune or not district_data:
        return "UNKNOWN"
    
    mapping = district_data.get("comune_to_district_mapping", {})
    return mapping.get(comune.lower().strip(), "UNKNOWN")


# === EXPORT EXCEL ===
def export_to_excel(datastore: TriageDataStore, kpi_vol: Dict, kpi_clin: Dict, kpi_ctx: Dict) -> Optional[bytes]:
    """
    Export professionale Excel con fogli separati.
    """
    if not XLSX_AVAILABLE:
        return None
    
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    
    # === FOGLIO 1: KPI AGGREGATI ===
    ws_kpi = workbook.add_worksheet('KPI Aggregati')
    
    # Formati
    header_format = workbook.add_format({'bold': True, 'bg_color': '#4472C4', 'font_color': 'white'})
    number_format = workbook.add_format({'num_format': '0.00'})
    
    row = 0
    ws_kpi.write(row, 0, 'Categoria', header_format)
    ws_kpi.write(row, 1, 'Metrica', header_format)
    ws_kpi.write(row, 2, 'Valore', header_format)
    row += 1
    
    # KPI Volumetrici
    for key, val in kpi_vol.items():
        if key not in ['throughput_orario']:
            ws_kpi.write(row, 0, 'Volumetrico')
            ws_kpi.write(row, 1, key)
            ws_kpi.write(row, 2, val, number_format)
            row += 1
    
    # KPI Clinici
    ws_kpi.write(row, 0, 'Clinico')
    ws_kpi.write(row, 1, 'prevalenza_red_flags')
    ws_kpi.write(row, 2, kpi_clin['prevalenza_red_flags'], number_format)
    row += 1
    
    # KPI Context-Aware
    ws_kpi.write(row, 0, 'Context-Aware')
    ws_kpi.write(row, 1, 'tasso_deviazione_ps')
    ws_kpi.write(row, 2, kpi_ctx['tasso_deviazione_ps'], number_format)
    row += 1
    
    # === FOGLIO 2: DATI GREZZI ===
    ws_raw = workbook.add_worksheet('Dati Grezzi')
    
    headers = ['Timestamp', 'Session ID', 'User Input', 'Bot Response', 'Urgenza', 'Area Clinica', 'Red Flags']
    for col, header in enumerate(headers):
        ws_raw.write(0, col, header, header_format)
    
    for row_idx, record in enumerate(datastore.records, 1):
        ws_raw.write(row_idx, 0, str(record.get('timestamp', '')))
        ws_raw.write(row_idx, 1, str(record.get('session_id', '')))
        ws_raw.write(row_idx, 2, str(record.get('user_input', ''))[:100])
        ws_raw.write(row_idx, 3, str(record.get('bot_response', ''))[:100])
        ws_raw.write(row_idx, 4, record.get('urgenza', 3))
        ws_raw.write(row_idx, 5, record.get('area_clinica', 'N/D'))
        ws_raw.write(row_idx, 6, ', '.join(record.get('red_flags', [])))
    
    workbook.close()
    output.seek(0)
    return output.getvalue()


# === VISUALIZZAZIONI PLOTLY (Aggiornate v2.1 - Gennaio 2026) ===

def render_throughput_chart(kpi_vol: Dict):
    """Grafico throughput orario."""
    throughput = kpi_vol.get('throughput_orario', {})
    if not throughput:
        st.info("Nessun dato disponibile per throughput orario.")
        return
    
    hours = sorted(throughput.keys())
    counts = [throughput[h] for h in hours]
    
    fig = go.Figure(data=[
        go.Bar(
            x=hours, 
            y=counts, 
            marker_color='#4A90E2',
            hovertemplate='<b>Ora %{x}:00</b><br>Accessi: %{y}<extra></extra>'
        )
    ])
    
    fig.update_layout(
        title="Throughput Orario (Distribuzione Accessi)",
        xaxis_title="Ora del Giorno",
        yaxis_title="N° Interazioni",
        height=400,
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family="Arial, sans-serif", size=12)
    )
    
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#e5e7eb')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#e5e7eb')
    
    st.plotly_chart(fig, use_container_width=True)


def render_urgenza_pie(kpi_clin: Dict):
    """Grafico a torta stratificazione urgenza."""
    stratificazione = kpi_clin.get('stratificazione_urgenza', {})
    if not stratificazione:
        st.info("Nessun dato disponibile per stratificazione urgenza.")
        return
    
    labels = [f"Codice {k}" for k in sorted(stratificazione.keys())]
    values = [stratificazione[k] for k in sorted(stratificazione.keys())]
    
    # Palette colori clinica standard ER
    colors = ['#00C853', '#FFEB3B', '#FF9800', '#FF5722', '#B71C1C']
    
    fig = go.Figure(data=[
        go.Pie(
            labels=labels, 
            values=values, 
            marker_colors=colors[:len(labels)],
            hovertemplate='<b>%{label}</b><br>Casi: %{value}<br>Percentuale: %{percent}<extra></extra>',
            textinfo='label+percent',
            textposition='auto'
        )
    ])
    
    fig.update_layout(
        title="Stratificazione Urgenza (Codici 1-5)",
        height=400,
        showlegend=True,
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family="Arial, sans-serif", size=12)
    )
    
    st.plotly_chart(fig, use_container_width=True)

def render_sintomi_table(kpi_clin: Dict):
    """Tabella spettro sintomi completo (NON troncato)."""
    spettro = kpi_clin.get('spettro_sintomi', {})
    if not spettro:
        st.info("Nessun sintomo rilevato nei dati.")
        return
    
    st.subheader("📋 Spettro Sintomatologico Completo")
    
    # Converti in lista ordinata
    sintomi_list = sorted(spettro.items(), key=lambda x: x[1], reverse=True)
    
    # Rendering tabella
    st.dataframe(
        {
            'Sintomo': [s[0].title() for s in sintomi_list],
            'Frequenza': [s[1] for s in sintomi_list]
        },
        use_container_width=True,  # <--- CORRETTO: Sostituito use_container_width=True
        height=400
    )
# === MAIN APPLICATION ===
def main():
    """Entry point principale con gestione errori robusta."""
    
    # CRITICAL: Mostra warning xlsxwriter QUI, non nel global scope
    if not XLSX_AVAILABLE:
        st.sidebar.warning("⚠️ xlsxwriter non disponibile. Export Excel disabilitato.\nInstalla con: `pip install xlsxwriter`")
    
    # Carica dati con gestione errori robusta
    try:
        datastore = TriageDataStore(LOG_FILE)
    except Exception as e:
        st.error(f"❌ Errore fatale durante caricamento dati: {e}")
        st.info("💡 Verifica che il file `triage_logs.jsonl` sia valido o rimuovilo per ripartire da zero.")
        return
    
    try:
        district_data = load_district_mapping()
    except Exception as e:
        st.warning(f"⚠️ Errore caricamento distretti: {e}")
        district_data = {"health_districts": [], "comune_to_district_mapping": {}}
    
    # Early return se nessun dato
    if not datastore.records:
        st.warning("⚠️ Nessun dato disponibile. Inizia una chat per popolare i log.")
        st.info("💡 Avvia `frontend.py` sulla porta 8501 per generare dati di triage.")
        return
    
    # === SIDEBAR: FILTRI ===
    st.sidebar.header("📂 Filtri Temporali e Territoriali")
    
    # Filtro Anno
    years = datastore.get_unique_values('year')
    sel_year = st.sidebar.selectbox("Anno", sorted(years, reverse=True)) if years else None
    
    # Filtro Mese
    months = []
    if sel_year:
        filtered_by_year = datastore.filter(year=sel_year)
        months = filtered_by_year.get_unique_values('month')
    
    sel_month = st.sidebar.selectbox("Mese", ['Tutti'] + sorted(months)) if months else 'Tutti'
    sel_month = None if sel_month == 'Tutti' else sel_month
    
    # Filtro Settimana
    weeks = []
    if sel_year:
        filtered_temp = datastore.filter(year=sel_year, month=sel_month)
        weeks = filtered_temp.get_unique_values('week')
    
    sel_week = st.sidebar.selectbox("Settimana ISO", ['Tutte'] + sorted(weeks)) if weeks else 'Tutte'
    sel_week = None if sel_week == 'Tutte' else sel_week
    
    # Filtro Distretto Sanitario (Integrato con distretti_sanitari_er.json)
    st.sidebar.divider()
    st.sidebar.subheader("🏥 Filtro Distretto Sanitario")
    
    # Estrai distretti disponibili dal mapping
    available_districts = []
    if district_data and 'health_districts' in district_data:
        for ausl_item in district_data['health_districts']:
            if 'districts' in ausl_item:
                for d in ausl_item['districts']:
                    if 'name' in d:
                        available_districts.append(d['name'])
    
    available_districts = sorted(list(set(available_districts)))

    # Filtro Comune (per compatibilità)
    comuni = datastore.get_unique_values('comune')
    sel_comune = st.sidebar.selectbox("Comune", ['Tutti'] + sorted([c for c in comuni if c])) if comuni else 'Tutti'
    sel_comune = None if sel_comune == 'Tutti' else sel_comune
    
    # Applica filtri
    filtered_datastore = datastore.filter(year=sel_year, month=sel_month, week=sel_week)
    
    # === EXPORT EXCEL ===
    st.sidebar.divider()
    st.sidebar.subheader("📥 Export Dati")
    
    if XLSX_AVAILABLE and filtered_datastore.records:
        try:
            kpi_vol = calculate_kpi_volumetrici(filtered_datastore)
            kpi_clin = calculate_kpi_clinici(filtered_datastore)
            kpi_ctx = calculate_kpi_context_aware(filtered_datastore)
            
            excel_data = export_to_excel(filtered_datastore, kpi_vol, kpi_clin, kpi_ctx)
            
            if excel_data:
                filename = f"Report_Triage_W{sel_week or 'ALL'}_{sel_year or 'ALL'}.xlsx"
                st.sidebar.download_button(
                    label="📊 Scarica Report Excel",
                    data=excel_data,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        except Exception as e:
            st.sidebar.error(f"❌ Errore export Excel: {e}")
    
    # === MAIN DASHBOARD ===
    st.title("🧬 SIRAYA Analytics | Dashboard Professionale")
    st.caption(f"📊 Dati: {len(filtered_datastore.records)} interazioni | {len(filtered_datastore.sessions)} sessioni")
    
    if not filtered_datastore.records:
        st.info("ℹ️ Nessun dato disponibile per i filtri selezionati.")
        return
    
    # === KPI SELECTOR (Multiselect) ===
    st.sidebar.divider()
    st.sidebar.subheader("📊 Personalizza KPI")
    
    available_kpis = {
        "Volumetrici": ["Sessioni Univoche", "Throughput Orario", "Completion Rate", "Tempo Mediano"],
        "Clinici": ["Stratificazione Urgenza", "Spettro Sintomi", "Red Flags"],
        "Context-Aware": ["Urgenza per Specializzazione", "Deviazione PS"]
    }
    
    selected_kpis = st.sidebar.multiselect(
        "Seleziona KPI da visualizzare",
        options=["Tutti"] + [f"{cat}: {kpi}" for cat, kpis in available_kpis.items() for kpi in kpis],
        default=["Tutti"],
        key="kpi_selector"
    )
    
    # Se "Tutti" è selezionato, mostra tutto
    show_all_kpis = "Tutti" in selected_kpis
    
    # === CALCOLO KPI CON PROTEZIONE ERRORI ===
    try:
        kpi_vol = calculate_kpi_volumetrici(filtered_datastore)
    except Exception as e:
        st.error(f"❌ Errore calcolo KPI volumetrici: {e}")
        kpi_vol = {'sessioni_uniche': 0, 'interazioni_totali': 0, 'completion_rate': 0, 
                   'tempo_mediano_minuti': 0, 'profondita_media': 0, 'throughput_orario': {}}
    
    try:
        kpi_clin = calculate_kpi_clinici(filtered_datastore)
    except Exception as e:
        st.error(f"❌ Errore calcolo KPI clinici: {e}")
        kpi_clin = {'spettro_sintomi': {}, 'stratificazione_urgenza': {}, 
                    'prevalenza_red_flags': 0, 'red_flags_dettaglio': {}}
    
    try:
        kpi_ctx = calculate_kpi_context_aware(filtered_datastore)
    except Exception as e:
        st.error(f"❌ Errore calcolo KPI context-aware: {e}")
        kpi_ctx = {'urgenza_media_per_spec': {}, 'tasso_deviazione_ps': 0, 
                   'tasso_deviazione_territoriale': 0}
    
    # === SEZIONE 1: KPI VOLUMETRICI ===
    st.header("📈 KPI Volumetrici")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Sessioni Uniche", f"{kpi_vol['sessioni_uniche']}")
    
    with col2:
        st.metric("Interazioni Totali", f"{kpi_vol['interazioni_totali']}")
    
    with col3:
        st.metric("Completion Rate", f"{kpi_vol['completion_rate']:.1f}%")
    
    with col4:
        st.metric("Tempo Mediano", f"{kpi_vol['tempo_mediano_minuti']:.1f} min")
    
    with col5:
        st.metric("Profondità Media", f"{kpi_vol['profondita_media']:.1f}")
    
    st.divider()
    
    # Throughput Orario (con gestione errori)
    try:
        render_throughput_chart(kpi_vol)
    except Exception as e:
        st.error(f"❌ Errore rendering throughput: {e}")
    
    # === SEZIONE 2: KPI CLINICI ===
    if show_all_kpis or any("Clinici" in kpi for kpi in selected_kpis):
        st.header("🏥 KPI Clinici ed Epidemiologici")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if show_all_kpis or "Clinici: Red Flags" in selected_kpis:
                st.metric("Prevalenza Red Flags", f"{kpi_clin.get('prevalenza_red_flags', 0):.1f}%")
                
                # Red Flags Dettaglio
                if kpi_clin.get('red_flags_dettaglio'):
                    st.subheader("🚨 Red Flags per Tipo")
                    rf_list = sorted(kpi_clin['red_flags_dettaglio'].items(), key=lambda x: x[1], reverse=True)
                    for rf, count in rf_list[:10]:
                        st.write(f"**{rf.title()}**: {count}")
        
        with col2:
            if show_all_kpis or "Clinici: Stratificazione Urgenza" in selected_kpis:
                try:
                    render_urgenza_pie(kpi_clin)
                except Exception as e:
                    st.error(f"❌ Errore rendering urgenza: {e}")
        
        st.divider()
        
        # Spettro Sintomi Completo (con gestione errori)
        if show_all_kpis or "Clinici: Spettro Sintomi" in selected_kpis:
            try:
                render_sintomi_table(kpi_clin)
            except Exception as e:
                st.error(f"❌ Errore rendering sintomi: {e}")
    
    # === SEZIONE 3: KPI CONTEXT-AWARE ===
    st.header("🎯 KPI Context-Aware")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Deviazione Pronto Soccorso", f"{kpi_ctx['tasso_deviazione_ps']:.1f}%")
        st.metric("Deviazione Territoriale", f"{kpi_ctx['tasso_deviazione_territoriale']:.1f}%")
    
    with col2:
        # Urgenza Media per Specializzazione
        st.subheader("⚕️ Urgenza Media per Specializzazione")
        urgenza_spec = kpi_ctx.get('urgenza_media_per_spec', {})
        if urgenza_spec:
            sorted_spec = sorted(urgenza_spec.items(), key=lambda x: x[1], reverse=True)
            for spec, urg in sorted_spec:
                st.write(f"**{spec}**: {urg:.2f}")
    
    # === FOOTER ===
    st.divider()
    st.caption("CHATBOT.ALPHA v2 | Analytics Engine | Powered by Streamlit + Plotly GO")


# === ENTRY POINT ===
if __name__ == "__main__":
    main()
