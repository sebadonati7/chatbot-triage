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
import threading
import csv
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
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
# V5.0: Path log unificato - identico a frontend.py per garantire coerenza
# Cloud-ready: Usa env var per path log persistente, ma default identico a frontend
# Entrambi i file (frontend.py e backend.py) usano os.path.dirname(os.path.abspath(__file__))
# quindi puntano alla stessa directory root del progetto
LOG_DIR = os.environ.get("TRIAGE_LOGS_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(LOG_DIR, exist_ok=True)  # Crea directory se non esiste
LOG_FILE = os.path.join(LOG_DIR, "triage_logs.jsonl")
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

# === THREAD-SAFETY E CACHE ===
_WRITE_LOCK = threading.Lock()  # Lock globale per scrittura thread-safe JSONL
_FILE_CACHE = {}  # Cache per ottimizzazione mtime: {filepath: {'mtime': float, 'records': List, 'sessions': Dict}}

# Schema obbligatorio per validazione
# V6.0: Schema flessibile - supporta sia log "summary" (vecchi) che "interaction" (nuovi)
REQUIRED_FIELDS_SUMMARY = {
    'session_id': str,
    'timestamp_start': str,
    'timestamp_end': str,
}

REQUIRED_FIELDS_INTERACTION = {
    'session_id': str,
    'timestamp': str,
    'user_input': str,
    'bot_response': str,
}
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
        self.validation_errors = 0  # Nuovo: conta errori validazione schema
        
        # Cache key per questo filepath
        self._cache_key = str(Path(filepath).absolute())
        
        self._load_data()
        self._enrich_data()
    
    def _validate_record_schema(self, record: Dict, line_num: int = None) -> bool:
        """
        V6.0: Validazione flessibile - supporta sia log "summary" che "interaction".
        
        Args:
            record: Record da validare
            line_num: Numero riga (per logging)
        
        Returns:
            bool: True se valido, False se scartato
        """
        # === DETECTION: Summary vs Interaction ===
        is_interaction = 'timestamp' in record and 'user_input' in record and 'bot_response' in record
        is_summary = 'timestamp_start' in record and 'timestamp_end' in record
        
        if not is_interaction and not is_summary:
            self.validation_errors += 1
            log_msg = f"Record scartato (linea {line_num}): formato sconosciuto (né summary né interaction)"
            print(f"⚠️ {log_msg}")
            return False
        
        # === VALIDAZIONE INTERACTION (V6.0 - Real-time) ===
        if is_interaction:
            # Campi obbligatori per interaction
            for field, expected_type in REQUIRED_FIELDS_INTERACTION.items():
                if field not in record:
                    self.validation_errors += 1
                    log_msg = f"Record interaction scartato (linea {line_num}): campo '{field}' mancante"
                    print(f"⚠️ {log_msg}")
                    return False
                
                if not isinstance(record[field], expected_type):
                    self.validation_errors += 1
                    log_msg = f"Record interaction scartato (linea {line_num}): campo '{field}' tipo errato"
                    print(f"⚠️ {log_msg}")
                    return False
            
            # Validazione timestamp ISO 8601
            try:
                datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                self.validation_errors += 1
                log_msg = f"Record interaction scartato (linea {line_num}): timestamp formato non valido"
                print(f"⚠️ {log_msg}")
                return False
            
            # Interaction log valido (urgency_level opzionale, può essere in metadata)
            return True
        
        # === VALIDAZIONE SUMMARY (Legacy - Fine Sessione) ===
        if is_summary:
            # Campi obbligatori per summary
            for field, expected_type in REQUIRED_FIELDS_SUMMARY.items():
                if field not in record:
                    self.validation_errors += 1
                    log_msg = f"Record summary scartato (linea {line_num}): campo '{field}' mancante"
                    print(f"⚠️ {log_msg}")
                    return False
                
                if not isinstance(record[field], expected_type):
                    self.validation_errors += 1
                    log_msg = f"Record summary scartato (linea {line_num}): campo '{field}' tipo errato"
                    print(f"⚠️ {log_msg}")
                    return False
            
            # Verifica presenza urgency_level (obbligatorio per summary)
            urgency_found = False
            
            if 'outcome' in record and isinstance(record['outcome'], dict):
                if 'urgency_level' in record['outcome']:
                    urgency_found = True
            
            if not urgency_found and 'metadata' in record and isinstance(record['metadata'], dict):
                if 'urgency' in record['metadata'] or 'urgency_level' in record['metadata']:
                    urgency_found = True
            
            if not urgency_found and ('urgency' in record or 'urgency_level' in record):
                urgency_found = True
            
            if not urgency_found:
                self.validation_errors += 1
                log_msg = f"Record summary scartato (linea {line_num}): urgency_level non trovato"
                print(f"⚠️ {log_msg}")
                return False
            
            # Validazione formato timestamp (ISO 8601)
            for ts_field in ['timestamp_start', 'timestamp_end']:
                if ts_field in record:
                    ts_str = record[ts_field]
                    try:
                        datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        self.validation_errors += 1
                        log_msg = f"Record summary scartato (linea {line_num}): timestamp '{ts_field}' formato non valido"
                        print(f"⚠️ {log_msg}")
                        return False
            
            return True
        
        return False
    
    def _load_data(self):
        """
        Caricamento JSONL con gestione errori robusta, encoding resiliente,
        validazione schema e cache-busting basato su mtime.
        """
        filepath_obj = Path(self.filepath)
        
        if not filepath_obj.exists():
            st.warning(f"⚠️ File {self.filepath} non trovato. Nessun dato disponibile.")
            return
        
        if filepath_obj.stat().st_size == 0:
            st.warning(f"⚠️ File {self.filepath} vuoto. Inizia un triage per popolare i dati.")
            return
        
        # === CACHE-BUSTING: Verifica mtime ===
        current_mtime = filepath_obj.stat().st_mtime
        
        if self._cache_key in _FILE_CACHE:
            cached = _FILE_CACHE[self._cache_key]
            if cached['mtime'] == current_mtime:
                # Cache hit: usa dati cached
                self.records = cached['records'].copy()
                self.sessions = cached['sessions'].copy()
                return
        
        # Cache miss o file modificato: ricarica
        self.parse_errors = 0
        self.validation_errors = 0
        self.records = []
        self.sessions = {}
        
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
                            
                            # === VALIDAZIONE SCHEMA ===
                            if not self._validate_record_schema(record, line_num):
                                # Record scartato per validazione fallita
                                continue
                            
                            self.records.append(record)
                            
                        except json.JSONDecodeError as e:
                            self.parse_errors += 1
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
        
        # Aggiorna cache
        _FILE_CACHE[self._cache_key] = {
            'mtime': current_mtime,
            'records': self.records.copy(),
            'sessions': {}
        }
        
        if self.parse_errors > 0:
            st.info(f"ℹ️ {self.parse_errors} righe JSON corrotte saltate durante il caricamento.")
        
        if self.validation_errors > 0:
            st.warning(f"⚠️ {self.validation_errors} record scartati per validazione schema fallita (campi obbligatori mancanti).")
    
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
        """Arricchimento dati con calcoli temporali e NLP. Aggiorna anche cache."""
        for record in self.records:
            # === PARSING TEMPORALE ROBUSTO ===
            # Usa timestamp_end se disponibile, altrimenti timestamp_start
            timestamp_str = record.get('timestamp_end') or record.get('timestamp_start') or record.get('timestamp')
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
            
            # Estrazione Urgenza (priorità: outcome > metadata > root)
            urgency = None
            if 'outcome' in record and isinstance(record['outcome'], dict):
                urgency = record['outcome'].get('urgency_level') or record['outcome'].get('urgency')
            if urgency is None and 'metadata' in record and isinstance(record['metadata'], dict):
                urgency = record['metadata'].get('urgency_level') or record['metadata'].get('urgency')
            if urgency is None:
                urgency = record.get('urgency_level') or record.get('urgency', 3)
            
            record['urgenza'] = urgency if urgency is not None else 3
            record['area_clinica'] = record.get('area_clinica', 'Non Specificato')
            record['specializzazione'] = record.get('specializzazione', 'Generale')
            
            # === MAPPING COMUNE → DISTRETTO (Case-Insensitive & Trim-Safe) ===
            comune_raw = record.get('comune') or record.get('location') or record.get('LOCATION')
            if comune_raw:
                comune_normalized = str(comune_raw).lower().strip()
                try:
                    district_data = load_district_mapping()
                    if district_data:
                        mapping = district_data.get("comune_to_district_mapping", {})
                        distretto = mapping.get(comune_normalized, "UNKNOWN")
                        record['distretto'] = distretto
                except Exception:
                    record['distretto'] = "UNKNOWN"
            else:
                record['distretto'] = "UNKNOWN"
            
            # Organizzazione per Sessione
            session_id = record.get('session_id')
            if session_id:
                if session_id not in self.sessions:
                    self.sessions[session_id] = []
                self.sessions[session_id].append(record)
        
        # Aggiorna cache sessions
        if self._cache_key in _FILE_CACHE:
            _FILE_CACHE[self._cache_key]['sessions'] = self.sessions.copy()
    
    def filter(self, year: Optional[int] = None, month: Optional[int] = None, 
               week: Optional[int] = None, district: Optional[str] = None) -> 'TriageDataStore':
        """
        Filtraggio records con creazione nuovo datastore.
        """
        filtered = TriageDataStore.__new__(TriageDataStore)
        filtered.filepath = self.filepath
        filtered.parse_errors = 0
        filtered.validation_errors = 0  # Reset per filtered datastore
        filtered._cache_key = str(Path(filtered.filepath).absolute())
        filtered.records = self.records.copy()
        filtered.sessions = {}
        
        if year is not None:
            filtered.records = [r for r in filtered.records if r.get('year') == year]
        
        if month is not None:
            filtered.records = [r for r in filtered.records if r.get('month') == month]
        
        if week is not None:
            filtered.records = [r for r in filtered.records if r.get('week') == week]
        
        if district and district != "Tutti":
            # Case-insensitive district filtering (usa campo 'distretto' se disponibile)
            district_normalized = str(district).lower().strip()
            filtered.records = [
                r for r in filtered.records 
                if str(r.get('distretto', '')).lower().strip() == district_normalized
            ]
        
        # Ricostruisci sessions
        for record in filtered.records:
            sid = record.get('session_id')
            if sid:
                if sid not in filtered.sessions:
                    filtered.sessions[sid] = []
                filtered.sessions[sid].append(record)
        
        return filtered
    
    @staticmethod
    def append_record_thread_safe(filepath: str, record: Dict) -> bool:
        """
        Scrittura thread-safe di un record su file JSONL.
        Usa lock globale per prevenire corruzioni in ambienti multi-utente.
        
        Args:
            filepath: Path al file JSONL
            record: Record da scrivere (dict)
        
        Returns:
            bool: True se scritto con successo, False altrimenti
        """
        try:
            with _WRITE_LOCK:
                # Validazione record prima di scrivere
                temp_store = TriageDataStore.__new__(TriageDataStore)
                temp_store.validation_errors = 0
                
                if not temp_store._validate_record_schema(record):
                    return False
                
                # Scrittura atomica: append con flush
                with open(filepath, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(record, ensure_ascii=False) + '\n')
                    f.flush()
                    os.fsync(f.fileno())  # Force write to disk
                
                # Invalida cache per questo filepath
                cache_key = str(Path(filepath).absolute())
                if cache_key in _FILE_CACHE:
                    del _FILE_CACHE[cache_key]
                
                return True
                
        except Exception as e:
            return False
    
    def to_csv(self, include_enriched: bool = True) -> bytes:
        """
        Esporta dati in formato CSV pronto per download Streamlit.
        
        Args:
            include_enriched: Se True, include campi arricchiti (year, month, week, distretto, ecc.)
        
        Returns:
            bytes: CSV in memoria (pronto per st.download_button)
        """
        if not self.records:
            return b''
        
        output = io.StringIO()
        
        base_columns = [
            'session_id', 'timestamp_start', 'timestamp_end', 'total_duration_seconds',
            'urgency_level', 'disposition', 'facility_recommended', 'comune', 'distretto'
        ]
        
        enriched_columns = [
            'year', 'month', 'week', 'day_of_week', 'hour',
            'area_clinica', 'specializzazione', 'has_red_flag', 'red_flags_count'
        ]
        
        columns = base_columns + (enriched_columns if include_enriched else [])
        
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        
        for record in self.records:
            row = {}
            
            row['session_id'] = record.get('session_id', '')
            row['timestamp_start'] = record.get('timestamp_start', '')
            row['timestamp_end'] = record.get('timestamp_end', '')
            row['total_duration_seconds'] = record.get('total_duration_seconds', '')
            
            # Urgency (cerca in outcome/metadata/root)
            urgency = None
            if 'outcome' in record and isinstance(record['outcome'], dict):
                urgency = record['outcome'].get('urgency_level') or record['outcome'].get('urgency')
            if urgency is None and 'metadata' in record and isinstance(record['metadata'], dict):
                urgency = record['metadata'].get('urgency_level') or record['metadata'].get('urgency')
            row['urgency_level'] = urgency or record.get('urgenza', record.get('urgency', ''))
            
            if 'outcome' in record and isinstance(record['outcome'], dict):
                row['disposition'] = record['outcome'].get('disposition', '')
                row['facility_recommended'] = record['outcome'].get('facility_recommended', '')
            
            row['comune'] = record.get('comune') or record.get('location') or record.get('LOCATION', '')
            row['distretto'] = record.get('distretto', '')
            
            if include_enriched:
                row['year'] = record.get('year', '')
                row['month'] = record.get('month', '')
                row['week'] = record.get('week', '')
                row['day_of_week'] = record.get('day_of_week', '')
                row['hour'] = record.get('hour', '')
                row['area_clinica'] = record.get('area_clinica', '')
                row['specializzazione'] = record.get('specializzazione', '')
                row['has_red_flag'] = record.get('has_red_flag', False)
                row['red_flags_count'] = len(record.get('red_flags', []))
            
            writer.writerow(row)
        
        return output.getvalue().encode('utf-8-sig')  # UTF-8 BOM per Excel compatibility
    
    def to_excel(self, kpi_vol: Dict = None, kpi_clin: Dict = None, kpi_ctx: Dict = None) -> Optional[bytes]:
        """
        Esporta dati in formato Excel con fogli multipli (KPI + Dati Grezzi).
        Metodo della classe per coerenza architetturale.
        
        Args:
            kpi_vol: KPI volumetrici (opzionale)
            kpi_clin: KPI clinici (opzionale)
            kpi_ctx: KPI context-aware (opzionale)
        
        Returns:
            bytes: Excel in memoria (pronto per st.download_button) o None se xlsxwriter non disponibile
        """
        if not XLSX_AVAILABLE:
            return None
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        if kpi_vol or kpi_clin or kpi_ctx:
            ws_kpi = workbook.add_worksheet('KPI Aggregati')
            header_format = workbook.add_format({'bold': True, 'bg_color': '#4472C4', 'font_color': 'white'})
            number_format = workbook.add_format({'num_format': '0.00'})
            
            row = 0
            ws_kpi.write(row, 0, 'Categoria', header_format)
            ws_kpi.write(row, 1, 'Metrica', header_format)
            ws_kpi.write(row, 2, 'Valore', header_format)
            row += 1
            
            if kpi_vol:
                for key, val in kpi_vol.items():
                    if key != 'throughput_orario':
                        ws_kpi.write(row, 0, 'Volumetrico')
                        ws_kpi.write(row, 1, key)
                        ws_kpi.write(row, 2, val, number_format if isinstance(val, (int, float)) else None)
                        row += 1
            
            if kpi_clin:
                ws_kpi.write(row, 0, 'Clinico')
                ws_kpi.write(row, 1, 'prevalenza_red_flags')
                ws_kpi.write(row, 2, kpi_clin.get('prevalenza_red_flags', 0), number_format)
                row += 1
            
            if kpi_ctx:
                ws_kpi.write(row, 0, 'Context-Aware')
                ws_kpi.write(row, 1, 'tasso_deviazione_ps')
                ws_kpi.write(row, 2, kpi_ctx.get('tasso_deviazione_ps', 0), number_format)
        
        ws_raw = workbook.add_worksheet('Dati Grezzi')
        header_format = workbook.add_format({'bold': True, 'bg_color': '#4472C4', 'font_color': 'white'})
        
        headers = [
            'Timestamp End', 'Session ID', 'Urgency Level', 'Disposition', 
            'Facility', 'Comune', 'Distretto', 'Year', 'Month', 'Week',
            'Area Clinica', 'Specializzazione', 'Has Red Flag'
        ]
        
        for col, header in enumerate(headers):
            ws_raw.write(0, col, header, header_format)
        
        row = 1
        for record in self.records:
            ws_raw.write(row, 0, record.get('timestamp_end', ''))
            ws_raw.write(row, 1, record.get('session_id', ''))
            
            urgency = record.get('urgenza')
            if urgency is None and 'outcome' in record and isinstance(record['outcome'], dict):
                urgency = record['outcome'].get('urgency_level') or record['outcome'].get('urgency')
            ws_raw.write(row, 2, urgency or '')
            
            if 'outcome' in record and isinstance(record['outcome'], dict):
                ws_raw.write(row, 3, record['outcome'].get('disposition', ''))
                ws_raw.write(row, 4, record['outcome'].get('facility_recommended', ''))
            
            ws_raw.write(row, 5, record.get('comune') or record.get('location', ''))
            ws_raw.write(row, 6, record.get('distretto', ''))
            ws_raw.write(row, 7, record.get('year', ''))
            ws_raw.write(row, 8, record.get('month', ''))
            ws_raw.write(row, 9, record.get('week', ''))
            ws_raw.write(row, 10, record.get('area_clinica', ''))
            ws_raw.write(row, 11, record.get('specializzazione', ''))
            ws_raw.write(row, 12, record.get('has_red_flag', False))
            
            row += 1
        
        workbook.close()
        output.seek(0)
        return output.read()
    
    def reload_if_updated(self) -> bool:
        """
        Ricarica i dati solo se il file è stato modificato (cache-busting).
        Utile per aggiornare dashboard dopo nuovi triage.
        
        Returns:
            bool: True se ricaricato, False se cache valida
        """
        filepath_obj = Path(self.filepath)
        if not filepath_obj.exists():
            return False
        
        current_mtime = filepath_obj.stat().st_mtime
        
        if self._cache_key in _FILE_CACHE:
            cached = _FILE_CACHE[self._cache_key]
            if cached['mtime'] == current_mtime:
                return False  # Cache valida
        
        # File modificato: ricarica
        self._load_data()
        self._enrich_data()
        return True
    
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
    [DEPRECATED] Usa datastore.to_excel() invece.
    Mantenuta per retrocompatibilità.
    """
    return datastore.to_excel(kpi_vol, kpi_clin, kpi_ctx)

def _export_to_excel_legacy(datastore: TriageDataStore, kpi_vol: Dict, kpi_clin: Dict, kpi_ctx: Dict) -> Optional[bytes]:
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
    """Grafico throughput orario con protezione zero-data."""
    throughput = kpi_vol.get('throughput_orario', {})
    if not throughput or len(throughput) == 0:
        st.info("ℹ️ Nessun dato disponibile per throughput orario.")
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
    """Grafico urgenza con protezione zero-data."""
    stratificazione = kpi_clin.get('stratificazione_urgenza', {})
    if not stratificazione or len(stratificazione) == 0:
        st.info("ℹ️ Nessun dato disponibile per stratificazione urgenza.")
        return
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
    
    # V6.0: Inizializza file log se non esiste
    if not os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'w', encoding='utf-8') as f:
                pass  # Crea file vuoto
            st.info("💡 File log creato. Inizia una chat per popolare i dati.")
        except Exception as e:
            st.error(f"❌ Errore creazione file log: {e}")
    
    # Early return se nessun dato
    if not datastore.records:
        st.warning("⚠️ Nessun dato disponibile. Inizia una chat per popolare i log.")
        st.info("💡 Avvia il **Chatbot Triage** tramite `app.py` per generare dati di triage.")
        return
    
    # === SIDEBAR: FILTRI ===
    st.sidebar.header("📂 Filtri Temporali e Territoriali")
    
    # Filtro Anno (pre-popolato con anni disponibili + 2025/2026)
    years = datastore.get_unique_values('year')
    # Aggiungi anni standard se non presenti
    all_years = sorted(set(years + [2025, 2026]), reverse=True)
    sel_year = st.sidebar.selectbox("Anno", all_years) if all_years else None
    
    # Filtro Mese (pre-popolato 1-12, mostra "0" se nessun dato)
    month_names = {
        1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
        5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
        9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"
    }
    
    months_available = []
    if sel_year:
        filtered_by_year = datastore.filter(year=sel_year)
        months_available = filtered_by_year.get_unique_values('month')
    
    # Pre-popolare con tutti i mesi 1-12
    month_options = ['Tutti']
    for m in range(1, 13):
        month_label = f"{m:02d} - {month_names.get(m, 'Mese')}"
        if m in months_available:
            month_options.append(month_label)
        else:
            month_options.append(f"{month_label} (0 dati)")
    
    sel_month = st.sidebar.selectbox("Mese", month_options)
    sel_month = None if sel_month == 'Tutti' else int(sel_month.split(' - ')[0])
    
    # Filtro Settimana (pre-popolato 1-52, mostra "0" se nessun dato)
    weeks_available = []
    if sel_year:
        filtered_temp = datastore.filter(year=sel_year, month=sel_month)
        weeks_available = filtered_temp.get_unique_values('week')
    
    # Pre-popolare con tutte le settimane 1-52
    week_options = ['Tutte']
    for w in range(1, 53):
        week_label = f"Settimana {w:02d}"
        if w in weeks_available:
            week_options.append(week_label)
        else:
            week_options.append(f"{week_label} (0 dati)")
    
    sel_week = st.sidebar.selectbox("Settimana ISO", week_options)
    sel_week = None if sel_week == 'Tutte' else int(sel_week.split(' ')[1])
    
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
            
            excel_data = filtered_datastore.to_excel(kpi_vol, kpi_clin, kpi_ctx)
            
            # Export CSV
            csv_data = filtered_datastore.to_csv(include_enriched=True)
            if csv_data:
                st.sidebar.download_button(
                    label="📄 Scarica Report CSV",
                    data=csv_data,
                    file_name=f"Report_Triage_W{sel_week or 'ALL'}_{sel_year or 'ALL'}.csv",
                    mime="text/csv"
                )
            
            # Export Excel
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
    
    # === INJECT SIRAYA CSS ===
    try:
        from ui_components import inject_siraya_css
        inject_siraya_css()
    except ImportError:
        # Fallback CSS if ui_components not available
        st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        * { font-family: 'Inter', sans-serif !important; }
        .stApp { background-color: #f8fafc; }
        section[data-testid="stSidebar"] { background-color: #1e293b !important; }
        section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        </style>
        """, unsafe_allow_html=True)
    
    # === MAIN DASHBOARD ===
    st.title("🧬 SIRAYA Analytics | Dashboard Professionale")
    st.caption(f"📊 Dati: {len(filtered_datastore.records)} interazioni | {len(filtered_datastore.sessions)} sessioni")
    
    if not filtered_datastore.records:
        st.info("ℹ️ Nessun dato disponibile per i filtri selezionati.")
        return
    
    # === LIVE CRITICAL ALERTS ===
    st.markdown("### 🚨 Live Critical Alerts")
    
    # Get records from last hour
    from datetime import datetime, timedelta
    now = datetime.now()
    one_hour_ago = now - timedelta(hours=1)
    
    critical_records = []
    for record in datastore.records:
        try:
            ts_str = record.get('timestamp', '')
            # Parse ISO timestamp
            if ts_str:
                # Handle different timestamp formats
                if 'T' in ts_str:
                    ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                else:
                    ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                
                if ts >= one_hour_ago:
                    urgency_level = record.get('urgency_level', '').upper()
                    if urgency_level in ['ROSSO', 'ARANCIONE', 'RED', 'ORANGE']:
                        critical_records.append({
                            'timestamp': ts,
                            'session_id': record.get('session_id', 'N/D'),
                            'urgency': urgency_level,
                            'comune': record.get('comune', 'N/D'),
                            'chief_complaint': record.get('chief_complaint', 'N/D')[:100]
                        })
        except Exception:
            continue
    
    if critical_records:
        # Sort by timestamp (most recent first)
        critical_records.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Display in alert box
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); 
                    border-left: 4px solid #dc2626; 
                    border-radius: 12px; 
                    padding: 20px; 
                    margin-bottom: 20px;
                    box-shadow: 0 2px 8px rgba(220, 38, 38, 0.1);'>
            <h4 style='margin: 0 0 10px 0; color: #991b1b;'>
                ⚠️ {len(critical_records)} Casi Critici (Ultima Ora)
            </h4>
        </div>
        """, unsafe_allow_html=True)
        
        # Show details in expander
        with st.expander("📋 Dettagli Casi Critici", expanded=False):
            for i, rec in enumerate(critical_records[:10], 1):  # Max 10 most recent
                ts_str = rec['timestamp'].strftime('%H:%M:%S')
                urgency_emoji = "🔴" if rec['urgency'] in ['ROSSO', 'RED'] else "🟠"
                
                st.markdown(f"""
                **{urgency_emoji} Caso {i}** - {ts_str}  
                - **Sessione**: `{rec['session_id']}`  
                - **Comune**: {rec['comune']}  
                - **Sintomo**: {rec['chief_complaint']}...
                """)
                st.divider()
    else:
        st.success("✅ Nessun caso critico nell'ultima ora")
    
    st.markdown("---")
    
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
