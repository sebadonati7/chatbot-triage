"""
SIRAYA Health Navigator - Session Storage & Supabase Integration
V4.0: Zero-File Policy - Full migration to Supabase
"""

import os
import json
import time
import streamlit as st
from typing import Any, Dict, List, Optional
from datetime import datetime

# ============================================================================
# SUPABASE INTEGRATION (V4.0 - Zero-File Policy)
# ============================================================================

@st.cache_resource
def init_supabase():
    """
    Inizializza connessione Supabase con connection pooling.
    Usa st.cache_resource per garantire una singola istanza per sessione.
    
    Returns:
        Supabase client o None se fallisce
    """
    try:
        from supabase import create_client, Client
        
        # Leggi credenziali da st.secrets
        url = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL"))
        key = st.secrets.get("SUPABASE_KEY", os.environ.get("SUPABASE_KEY"))
        
        if not url or not key:
            # Silent warning - non usare st.warning qui (causa errori in import)
            print("⚠️ Credenziali Supabase non trovate. Logging disabilitato.")
            return None
        
        client: Client = create_client(url, key)
        print("✅ Connessione Supabase attiva")
        return client
        
    except ImportError:
        print("❌ Libreria supabase non installata. Esegui: pip install supabase")
        return None
    except Exception as e:
        print(f"❌ Errore connessione Supabase: {e}")
        return None


class SupabaseLogger:
    """
    Logger centralizzato per interazioni chatbot su Supabase.
    Zero-File Policy: Tutti i log vengono scritti nel database.
    """
    
    def __init__(self):
        self.client = init_supabase()
        self.table_name = "triage_logs"
    
    def log_interaction(
        self,
        session_id: str,
        user_input: str,
        bot_response: str,
        metadata: Dict[str, Any],
        duration_ms: int = 0
    ) -> bool:
        """
        Salva interazione chatbot su Supabase con schema SQL completo.
        
        Args:
            session_id: ID univoco sessione
            user_input: Messaggio utente
            bot_response: Risposta bot
            metadata: Metadati aggiuntivi (triage_step, urgency_code, etc.)
            duration_ms: Durata risposta AI in millisecondi
        
        Returns:
            bool: True se salvato con successo
        """
        if not self.client:
            # Fail silently - non crashare mai la chat
            return False
        
        try:
            # Estrazione sicura con defaults schema-compliant
            payload = {
                # Core fields
                "session_id": session_id,
                "created_at": datetime.utcnow().isoformat(),
                "user_input": user_input,
                "bot_response": bot_response,
                
                # Clinical KPI
                "detected_intent": metadata.get('intent', metadata.get('detected_intent', 'triage')),
                "triage_code": metadata.get('triage_code') or metadata.get('codice_urgenza') or metadata.get('urgency_code', 'N/D'),
                "medical_specialty": metadata.get('medical_specialty') or metadata.get('specialization', 'Generale'),
                "suggested_facility_type": metadata.get('suggested_facility_type') or metadata.get('destinazione', 'N/D'),
                "reasoning": metadata.get('reasoning', ''),
                "estimated_wait_time": metadata.get('wait_time', metadata.get('estimated_wait_time', '')),
                
                # Technical KPI
                "processing_time_ms": duration_ms,
                "model_version": metadata.get('model', metadata.get('model_version', 'v2.0')),
                "tokens_used": metadata.get('tokens', metadata.get('tokens_used', 0)),
                "client_ip": metadata.get('client_ip', ''),
                
                # Metadata dump (full JSON)
                "metadata": json.dumps(metadata, ensure_ascii=False)
            }
            
            # Insert con gestione errori
            response = self.client.table(self.table_name).insert(payload).execute()
            
            # Verifica successo
            if response.data:
                return True
            else:
                # Silent warning - non usare st.warning qui per evitare problemi di contesto
                print(f"⚠️ Log non salvato: {response}")
                return False
                
        except Exception as e:
            # Fail silently - logging non deve mai bloccare la chat
            print(f"⚠️ Errore logging Supabase: {e}")
            return False
    
    def get_recent_logs(self, limit: int = 50, session_id: Optional[str] = None) -> List[Dict]:
        """
        Recupera log recenti da Supabase.
        
        Args:
            limit: Numero massimo di record
            session_id: Filtra per session_id specifico (opzionale)
        
        Returns:
            Lista di record log
        """
        if not self.client:
            return []
        
        try:
            query = self.client.table(self.table_name).select("*")
            
            if session_id:
                query = query.eq("session_id", session_id)
            
            response = query.order("created_at", desc=True).limit(limit).execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            # Silent error - non usare st.error qui (causa problemi in import)
            print(f"❌ Errore recupero log: {e}")
            return []
    
    def get_all_logs_for_analytics(self) -> List[Dict]:
        """
        Recupera TUTTI i log per analytics dashboard.
        Usa paginazione per dataset grandi.
        
        Returns:
            Lista completa di record log
        """
        if not self.client:
            print("🔍 DEBUG: No Supabase client available")
            return []
        
        try:
            all_records = []
            page_size = 1000
            offset = 0
            
            while True:
                response = (
                    self.client.table(self.table_name)
                    .select("*")
                    .order("created_at", desc=False)
                    .range(offset, offset + page_size - 1)
                    .execute()
                )
                
                # DEBUG: Print response details
                print(f"🔍 DEBUG: Supabase query response status: {response}")
                print(f"🔍 DEBUG: Response.data type: {type(response.data)}")
                print(f"🔍 DEBUG: Response.data length: {len(response.data) if response.data else 0}")
                
                if not response.data:
                    print(f"🔍 DEBUG: No data in response (offset={offset})")
                    break
                
                all_records.extend(response.data)
                print(f"🔍 DEBUG: Accumulated {len(all_records)} records so far")
                
                # Se riceviamo meno di page_size record, abbiamo finito
                if len(response.data) < page_size:
                    print(f"🔍 DEBUG: Last page received ({len(response.data)} < {page_size}), stopping")
                    break
                
                offset += page_size
            
            print(f"🔍 DEBUG: Total records retrieved: {len(all_records)}")
            return all_records
            
        except Exception as e:
            # Print full error trace for debugging
            import traceback
            print(f"❌ Errore recupero log completi: {e}")
            print(f"🔍 DEBUG: Full traceback:\n{traceback.format_exc()}")
            return []


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

_logger_singleton: Optional[SupabaseLogger] = None

def get_logger() -> SupabaseLogger:
    """
    Singleton per SupabaseLogger.
    
    Returns:
        SupabaseLogger instance
    """
    global _logger_singleton
    if _logger_singleton is None:
        _logger_singleton = SupabaseLogger()
    return _logger_singleton


# ============================================================================
# LEGACY FILE-BASED STORAGE (Deprecated - manteniamo per compatibilità)
# ============================================================================

SESSIONS_DIR = os.environ.get("SESSION_STORAGE_DIR", "sessions")

class FileSessionStorage:
    """
    DEPRECATED: Storage basato su file JSON nella cartella `sessions/`.
    Manteniamo per compatibilità legacy, ma si consiglia Supabase.
    """
    def __init__(self, base_dir: str = SESSIONS_DIR):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, session_id: str) -> str:
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_.")
        return os.path.join(self.base_dir, f"{safe_id}.json")

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        p = self._path(session_id)
        if not os.path.exists(p):
            return None
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        p = self._path(session_id)
        try:
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, p)
            return True
        except Exception:
            return False

    def delete_session(self, session_id: str) -> bool:
        p = self._path(session_id)
        try:
            if os.path.exists(p):
                os.remove(p)
                return True
            return False
        except Exception:
            return False

    def list_active_sessions(self) -> List[Dict[str, Any]]:
        results = []
        for fn in os.listdir(self.base_dir):
            if fn.endswith(".json"):
                p = os.path.join(self.base_dir, fn)
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    results.append({
                        "session_id": fn[:-5],
                        "last_modified": time.ctime(os.path.getmtime(p)),
                        "snapshot": data
                    })
                except Exception:
                    continue
        return results

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        now = time.time()
        cutoff = now - max_age_hours * 3600
        deleted = 0
        for fn in os.listdir(self.base_dir):
            if fn.endswith(".json"):
                p = os.path.join(self.base_dir, fn)
                try:
                    if os.path.getmtime(p) < cutoff:
                        os.remove(p)
                        deleted += 1
                except Exception:
                    continue
        return deleted


_storage_singleton: Optional[FileSessionStorage] = None

def get_storage() -> FileSessionStorage:
    """DEPRECATED: Usa get_logger() per Supabase invece."""
    global _storage_singleton
    if _storage_singleton is None:
        _storage_singleton = FileSessionStorage()
    return _storage_singleton


def sync_session_to_storage(session_id: str, session_state: Any) -> bool:
    """DEPRECATED: Compatibilità legacy."""
    storage = get_storage()
    data = {}
    for key, value in session_state.items():
        if not key.startswith('_') and key != 'rerun':
            try:
                json.dumps(value, default=str)
                data[key] = value
            except (TypeError, ValueError):
                continue
    return storage.save_session(session_id, data)


def load_session_from_storage(session_id: str) -> Optional[Dict[str, Any]]:
    """DEPRECATED: Compatibilità legacy."""
    storage = get_storage()
    return storage.load_session(session_id)
