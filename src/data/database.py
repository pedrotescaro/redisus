"""
REDISUS - Sistema de Diagnóstico de Feridas
Módulo de Banco de Dados

Gerencia persistência de dados de análises, pacientes e histórico.
Usa SQLite para armazenamento local.
"""
import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from contextlib import contextmanager
from loguru import logger


@dataclass
class PatientRecord:
    """Registro de paciente"""
    id: str
    name: str
    birth_date: Optional[str] = None
    medical_record: Optional[str] = None
    unit_id: Optional[str] = None
    team_id: Optional[str] = None
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "birth_date": self.birth_date,
            "medical_record": self.medical_record,
            "unit_id": self.unit_id,
            "team_id": self.team_id,
            "notes": self.notes,
            "created_at": self.created_at,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "PatientRecord":
        return cls(**data)


@dataclass
class AnalysisRecord:
    """Registro de análise de ferida"""
    id: str
    patient_id: str
    timestamp: str
    image_path: str
    etiology: str
    confidence: float
    tissue_percentages: Dict[str, float]
    wound_area_cm2: Optional[float] = None
    health_score: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    notes: str = ""
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "timestamp": self.timestamp,
            "image_path": self.image_path,
            "etiology": self.etiology,
            "confidence": self.confidence,
            "tissue_percentages": self.tissue_percentages,
            "wound_area_cm2": self.wound_area_cm2,
            "health_score": self.health_score,
            "recommendations": self.recommendations,
            "notes": self.notes,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "AnalysisRecord":
        return cls(**data)


class Database:
    """
    Gerenciador de banco de dados SQLite.
    
    Armazena:
    - Registros de pacientes
    - Análises de feridas
    - Histórico de evolução
    - Configurações
    
    Uso:
        db = Database("data/redisus.db")
        
        # Salvar análise
        record = AnalysisRecord(...)
        db.save_analysis(record)
        
        # Buscar histórico
        history = db.get_patient_analyses("patient_001")
    """
    
    def __init__(self, db_path: str = "data/redisus.db"):
        """
        Args:
            db_path: Caminho para o arquivo do banco de dados
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
        
    def _init_database(self):
        """Inicializa o banco de dados com as tabelas necessárias"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabela de pacientes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS patients (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    birth_date TEXT,
                    medical_record TEXT,
                    unit_id TEXT,
                    team_id TEXT,
                    notes TEXT,
                    created_at TEXT,
                    metadata TEXT
                )
            """)
            
            # Tabela de análises
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    patient_id TEXT,
                    timestamp TEXT,
                    image_path TEXT,
                    etiology TEXT,
                    confidence REAL,
                    tissue_percentages TEXT,
                    wound_area_cm2 REAL,
                    health_score REAL,
                    recommendations TEXT,
                    notes TEXT,
                    metadata TEXT,
                    FOREIGN KEY (patient_id) REFERENCES patients(id)
                )
            """)
            
            # Tabela de configurações
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Tabela de casos clínicos de ferida
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wound_cases (
                    id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    title TEXT,
                    wound_type TEXT,
                    location TEXT,
                    unit_id TEXT,
                    team_id TEXT,
                    assigned_to_uid TEXT,
                    assigned_to_name TEXT,
                    assigned_to_role TEXT,
                    claimed_by_uid TEXT,
                    claimed_by_name TEXT,
                    claimed_by_role TEXT,
                    claimed_at TEXT,
                    handoff_to_uid TEXT,
                    handoff_to_name TEXT,
                    handoff_to_role TEXT,
                    handoff_at TEXT,
                    status TEXT,
                    opened_at TEXT,
                    closed_at TEXT,
                    metadata TEXT,
                    FOREIGN KEY (patient_id) REFERENCES patients(id)
                )
            """)

            # Tabela de avaliações estruturadas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wound_evaluations (
                    id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    case_id TEXT,
                    evaluation_date TEXT NOT NULL,
                    professional_name TEXT,
                    wound_type TEXT,
                    wound_location TEXT,
                    clinical_description TEXT,
                    push_score REAL,
                    braden_score REAL,
                    bwat_score REAL,
                    pain_score REAL,
                    wound_area_cm2 REAL,
                    depth_mm REAL,
                    tissue_composition TEXT,
                    timers_payload TEXT,
                    metadata TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (patient_id) REFERENCES patients(id),
                    FOREIGN KEY (case_id) REFERENCES wound_cases(id)
                )
            """)

            # Tabela de imagens por avaliação
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wound_images (
                    id TEXT PRIMARY KEY,
                    evaluation_id TEXT NOT NULL,
                    image_role TEXT,
                    image_path TEXT NOT NULL,
                    content_type TEXT,
                    metadata TEXT,
                    created_at TEXT,
                    FOREIGN KEY (evaluation_id) REFERENCES wound_evaluations(id)
                )
            """)

            # Tabela de execução de IA (pipeline em 2 estágios)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_inference_runs (
                    id TEXT PRIMARY KEY,
                    evaluation_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    use_fallback INTEGER DEFAULT 0,
                    stage1_latency_ms INTEGER,
                    stage2_latency_ms INTEGER,
                    failure_reason TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (evaluation_id) REFERENCES wound_evaluations(id)
                )
            """)

            # Resultado consolidado da IA por job
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_results (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    etiology TEXT,
                    confidence REAL,
                    tissue_percentages TEXT,
                    wound_area_cm2 REAL,
                    diagnosis_summary TEXT,
                    recommendations TEXT,
                    payload TEXT,
                    created_at TEXT,
                    FOREIGN KEY (run_id) REFERENCES ai_inference_runs(id)
                )
            """)

            # Laudos estruturados e arquivos gerados
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS structured_reports (
                    id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    case_id TEXT,
                    evaluation_id TEXT,
                    report_type TEXT,
                    report_json TEXT,
                    pdf_path TEXT,
                    docx_path TEXT,
                    generated_by TEXT,
                    created_at TEXT,
                    FOREIGN KEY (patient_id) REFERENCES patients(id),
                    FOREIGN KEY (case_id) REFERENCES wound_cases(id),
                    FOREIGN KEY (evaluation_id) REFERENCES wound_evaluations(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS care_plans (
                    id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    unit_id TEXT,
                    team_id TEXT,
                    version INTEGER NOT NULL DEFAULT 1,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    risk_level TEXT,
                    goals TEXT,
                    frequency TEXT,
                    tasks TEXT,
                    alerts TEXT,
                    source_evaluation_id TEXT,
                    source_result_id TEXT,
                    review_due_date TEXT,
                    created_by TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    metadata TEXT,
                    FOREIGN KEY (patient_id) REFERENCES patients(id),
                    FOREIGN KEY (case_id) REFERENCES wound_cases(id),
                    FOREIGN KEY (source_evaluation_id) REFERENCES wound_evaluations(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS follow_ups (
                    id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    unit_id TEXT,
                    team_id TEXT,
                    care_plan_id TEXT,
                    evaluation_id TEXT,
                    scheduled_for TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT,
                    assigned_role TEXT,
                    assigned_to_uid TEXT,
                    assigned_to_name TEXT,
                    assigned_to_role TEXT,
                    created_by TEXT,
                    notes TEXT,
                    created_at TEXT,
                    completed_at TEXT,
                    metadata TEXT,
                    FOREIGN KEY (patient_id) REFERENCES patients(id),
                    FOREIGN KEY (case_id) REFERENCES wound_cases(id),
                    FOREIGN KEY (care_plan_id) REFERENCES care_plans(id),
                    FOREIGN KEY (evaluation_id) REFERENCES wound_evaluations(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clinical_alerts (
                    id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    unit_id TEXT,
                    team_id TEXT,
                    care_plan_id TEXT,
                    follow_up_id TEXT,
                    alert_type TEXT,
                    severity TEXT,
                    status TEXT,
                    title TEXT,
                    message TEXT,
                    assigned_to_uid TEXT,
                    assigned_to_name TEXT,
                    assigned_to_role TEXT,
                    claimed_by_uid TEXT,
                    claimed_by_name TEXT,
                    claimed_by_role TEXT,
                    claimed_at TEXT,
                    handoff_to_uid TEXT,
                    handoff_to_name TEXT,
                    handoff_to_role TEXT,
                    handoff_at TEXT,
                    due_at TEXT,
                    created_at TEXT,
                    resolved_at TEXT,
                    metadata TEXT,
                    FOREIGN KEY (patient_id) REFERENCES patients(id),
                    FOREIGN KEY (case_id) REFERENCES wound_cases(id),
                    FOREIGN KEY (care_plan_id) REFERENCES care_plans(id),
                    FOREIGN KEY (follow_up_id) REFERENCES follow_ups(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clinical_audit_log (
                    id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor_uid TEXT,
                    actor_name TEXT,
                    actor_role TEXT,
                    before_json TEXT,
                    after_json TEXT,
                    metadata TEXT,
                    created_at TEXT,
                    FOREIGN KEY (patient_id) REFERENCES patients(id),
                    FOREIGN KEY (case_id) REFERENCES wound_cases(id)
                )
            """)
            
            self._ensure_columns(conn, "patients", {"unit_id": "TEXT", "team_id": "TEXT"})
            self._ensure_columns(
                conn,
                "wound_cases",
                {
                    "unit_id": "TEXT",
                    "team_id": "TEXT",
                    "assigned_to_uid": "TEXT",
                    "assigned_to_name": "TEXT",
                    "assigned_to_role": "TEXT",
                    "claimed_by_uid": "TEXT",
                    "claimed_by_name": "TEXT",
                    "claimed_by_role": "TEXT",
                    "claimed_at": "TEXT",
                    "handoff_to_uid": "TEXT",
                    "handoff_to_name": "TEXT",
                    "handoff_to_role": "TEXT",
                    "handoff_at": "TEXT",
                },
            )
            self._ensure_columns(conn, "care_plans", {"unit_id": "TEXT", "team_id": "TEXT"})
            self._ensure_columns(
                conn,
                "follow_ups",
                {
                    "unit_id": "TEXT",
                    "team_id": "TEXT",
                    "assigned_to_uid": "TEXT",
                    "assigned_to_name": "TEXT",
                    "assigned_to_role": "TEXT",
                },
            )
            self._ensure_columns(
                conn,
                "clinical_alerts",
                {
                    "unit_id": "TEXT",
                    "team_id": "TEXT",
                    "assigned_to_uid": "TEXT",
                    "assigned_to_name": "TEXT",
                    "assigned_to_role": "TEXT",
                    "claimed_by_uid": "TEXT",
                    "claimed_by_name": "TEXT",
                    "claimed_by_role": "TEXT",
                    "claimed_at": "TEXT",
                    "handoff_to_uid": "TEXT",
                    "handoff_to_name": "TEXT",
                    "handoff_to_role": "TEXT",
                    "handoff_at": "TEXT",
                },
            )

            # Índices
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analyses_patient 
                ON analyses(patient_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analyses_timestamp 
                ON analyses(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_wound_cases_patient
                ON wound_cases(patient_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_patients_unit_team
                ON patients(unit_id, team_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_wound_cases_scope
                ON wound_cases(unit_id, team_id, status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_wound_cases_assigned
                ON wound_cases(assigned_to_uid, claimed_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_wound_evaluations_patient_date
                ON wound_evaluations(patient_id, evaluation_date DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_wound_evaluations_case
                ON wound_evaluations(case_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_wound_images_evaluation
                ON wound_images(evaluation_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ai_runs_evaluation
                ON ai_inference_runs(evaluation_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ai_runs_status
                ON ai_inference_runs(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_structured_reports_patient
                ON structured_reports(patient_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_care_plans_case_status
                ON care_plans(case_id, status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_follow_ups_case_status
                ON follow_ups(case_id, status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_follow_ups_scope
                ON follow_ups(unit_id, team_id, status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_clinical_alerts_case_status
                ON clinical_alerts(case_id, status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_clinical_alerts_scope
                ON clinical_alerts(unit_id, team_id, status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_clinical_alerts_assigned
                ON clinical_alerts(assigned_to_uid, claimed_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_clinical_audit_case_created
                ON clinical_audit_log(case_id, created_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_clinical_audit_entity
                ON clinical_audit_log(entity_type, entity_id)
            """)

            self._ensure_columns(conn, "patients", {"unit_id": "TEXT", "team_id": "TEXT"})
            self._ensure_columns(
                conn,
                "wound_cases",
                {
                    "unit_id": "TEXT",
                    "team_id": "TEXT",
                    "assigned_to_uid": "TEXT",
                    "assigned_to_name": "TEXT",
                    "assigned_to_role": "TEXT",
                    "claimed_by_uid": "TEXT",
                    "claimed_by_name": "TEXT",
                    "claimed_by_role": "TEXT",
                    "claimed_at": "TEXT",
                    "handoff_to_uid": "TEXT",
                    "handoff_to_name": "TEXT",
                    "handoff_to_role": "TEXT",
                    "handoff_at": "TEXT",
                },
            )
            self._ensure_columns(conn, "care_plans", {"unit_id": "TEXT", "team_id": "TEXT"})
            self._ensure_columns(
                conn,
                "follow_ups",
                {
                    "unit_id": "TEXT",
                    "team_id": "TEXT",
                    "assigned_to_uid": "TEXT",
                    "assigned_to_name": "TEXT",
                    "assigned_to_role": "TEXT",
                },
            )
            self._ensure_columns(
                conn,
                "clinical_alerts",
                {
                    "unit_id": "TEXT",
                    "team_id": "TEXT",
                    "assigned_to_uid": "TEXT",
                    "assigned_to_name": "TEXT",
                    "assigned_to_role": "TEXT",
                    "claimed_by_uid": "TEXT",
                    "claimed_by_name": "TEXT",
                    "claimed_by_role": "TEXT",
                    "claimed_at": "TEXT",
                    "handoff_to_uid": "TEXT",
                    "handoff_to_name": "TEXT",
                    "handoff_to_role": "TEXT",
                    "handoff_at": "TEXT",
                },
            )
            self._backfill_formal_scope_columns(conn)
            
            conn.commit()
            
        logger.info(f"Banco de dados inicializado: {self.db_path}")

    def _ensure_columns(self, conn: sqlite3.Connection, table: str, columns: Dict[str, str]) -> None:
        existing = {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for column, definition in columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _metadata_dict(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return dict(raw)
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _backfill_formal_scope_columns(self, conn: sqlite3.Connection) -> None:
        patient_rows = conn.execute("SELECT id, unit_id, team_id, metadata FROM patients").fetchall()
        for row in patient_rows:
            metadata = self._metadata_dict(row["metadata"])
            unit_id = row["unit_id"] or metadata.get("unit_id") or metadata.get("unit")
            team_id = row["team_id"] or metadata.get("team_id") or metadata.get("team")
            if unit_id != row["unit_id"] or team_id != row["team_id"]:
                conn.execute(
                    "UPDATE patients SET unit_id = ?, team_id = ? WHERE id = ?",
                    (unit_id, team_id, row["id"]),
                )

        case_rows = conn.execute(
            """
            SELECT wc.id, wc.unit_id, wc.team_id, wc.metadata, p.unit_id AS patient_unit_id, p.team_id AS patient_team_id
            FROM wound_cases wc
            LEFT JOIN patients p ON p.id = wc.patient_id
            """
        ).fetchall()
        for row in case_rows:
            metadata = self._metadata_dict(row["metadata"])
            unit_id = row["unit_id"] or metadata.get("unit_id") or metadata.get("unit") or row["patient_unit_id"]
            team_id = row["team_id"] or metadata.get("team_id") or metadata.get("team") or row["patient_team_id"]
            if unit_id != row["unit_id"] or team_id != row["team_id"]:
                conn.execute(
                    "UPDATE wound_cases SET unit_id = ?, team_id = ? WHERE id = ?",
                    (unit_id, team_id, row["id"]),
                )

        for table in ("care_plans", "follow_ups", "clinical_alerts"):
            rows = conn.execute(
                f"""
                SELECT item.id, item.case_id, item.unit_id, item.team_id, item.metadata,
                       wc.unit_id AS case_unit_id, wc.team_id AS case_team_id
                FROM {table} item
                LEFT JOIN wound_cases wc ON wc.id = item.case_id
                """
            ).fetchall()
            for row in rows:
                metadata = self._metadata_dict(row["metadata"])
                unit_id = row["unit_id"] or metadata.get("unit_id") or metadata.get("unit") or row["case_unit_id"]
                team_id = row["team_id"] or metadata.get("team_id") or metadata.get("team") or row["case_team_id"]
                if unit_id != row["unit_id"] or team_id != row["team_id"]:
                    conn.execute(
                        f"UPDATE {table} SET unit_id = ?, team_id = ? WHERE id = ?",
                        (unit_id, team_id, row["id"]),
                    )

    # === MODELO CLÍNICO E JOBS ===

    def _patient_scope(self, patient_id: str) -> Tuple[Optional[str], Optional[str]]:
        patient = self.get_patient(patient_id)
        if not patient:
            return None, None
        metadata = dict(patient.metadata or {})
        return (
            patient.unit_id or metadata.get("unit_id") or metadata.get("unit"),
            patient.team_id or metadata.get("team_id") or metadata.get("team"),
        )

    def _case_scope(self, case_id: str) -> Tuple[Optional[str], Optional[str]]:
        wound_case = self.get_wound_case(case_id)
        if not wound_case:
            return None, None
        metadata = dict(wound_case.get("metadata") or {})
        return (
            wound_case.get("unit_id") or metadata.get("unit_id") or metadata.get("unit"),
            wound_case.get("team_id") or metadata.get("team_id") or metadata.get("team"),
        )

    def create_wound_case(self, patient_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        case_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        patient_unit_id, patient_team_id = self._patient_scope(patient_id)
        metadata = dict(payload.get("metadata", {}) or {})
        case = {
            "id": case_id,
            "patient_id": patient_id,
            "title": payload.get("title"),
            "wound_type": payload.get("wound_type"),
            "location": payload.get("location"),
            "unit_id": payload.get("unit_id") or metadata.get("unit_id") or metadata.get("unit") or patient_unit_id,
            "team_id": payload.get("team_id") or metadata.get("team_id") or metadata.get("team") or patient_team_id,
            "assigned_to_uid": payload.get("assigned_to_uid"),
            "assigned_to_name": payload.get("assigned_to_name"),
            "assigned_to_role": payload.get("assigned_to_role"),
            "claimed_by_uid": payload.get("claimed_by_uid"),
            "claimed_by_name": payload.get("claimed_by_name"),
            "claimed_by_role": payload.get("claimed_by_role"),
            "claimed_at": payload.get("claimed_at"),
            "handoff_to_uid": payload.get("handoff_to_uid"),
            "handoff_to_name": payload.get("handoff_to_name"),
            "handoff_to_role": payload.get("handoff_to_role"),
            "handoff_at": payload.get("handoff_at"),
            "status": payload.get("status", "active"),
            "opened_at": payload.get("opened_at", now),
            "closed_at": payload.get("closed_at"),
            "metadata": metadata,
        }
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO wound_cases
                    (id, patient_id, title, wound_type, location, unit_id, team_id, assigned_to_uid, assigned_to_name,
                     assigned_to_role, claimed_by_uid, claimed_by_name, claimed_by_role, claimed_at, handoff_to_uid,
                     handoff_to_name, handoff_to_role, handoff_at, status, opened_at, closed_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        case["id"], case["patient_id"], case["title"], case["wound_type"], case["location"],
                        case["unit_id"], case["team_id"], case["assigned_to_uid"], case["assigned_to_name"],
                        case["assigned_to_role"], case["claimed_by_uid"], case["claimed_by_name"],
                        case["claimed_by_role"], case["claimed_at"], case["handoff_to_uid"],
                        case["handoff_to_name"], case["handoff_to_role"], case["handoff_at"],
                        case["status"], case["opened_at"], case["closed_at"],
                        json.dumps(case["metadata"]),
                    ),
                )
                conn.commit()
            return case
        except Exception as e:
            logger.error(f"Erro ao criar caso clínico: {e}")
            return None

    def get_wound_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM wound_cases WHERE id = ?", (case_id,)).fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "patient_id": row["patient_id"],
                    "title": row["title"],
                    "wound_type": row["wound_type"],
                    "location": row["location"],
                    "unit_id": row["unit_id"],
                    "team_id": row["team_id"],
                    "assigned_to_uid": row["assigned_to_uid"],
                    "assigned_to_name": row["assigned_to_name"],
                    "assigned_to_role": row["assigned_to_role"],
                    "claimed_by_uid": row["claimed_by_uid"],
                    "claimed_by_name": row["claimed_by_name"],
                    "claimed_by_role": row["claimed_by_role"],
                    "claimed_at": row["claimed_at"],
                    "handoff_to_uid": row["handoff_to_uid"],
                    "handoff_to_name": row["handoff_to_name"],
                    "handoff_to_role": row["handoff_to_role"],
                    "handoff_at": row["handoff_at"],
                    "status": row["status"],
                    "opened_at": row["opened_at"],
                    "closed_at": row["closed_at"],
                    "metadata": json.loads(row["metadata"] or "{}"),
                }
        except Exception as e:
            logger.error(f"Erro ao buscar caso clÃ­nico: {e}")
            return None

    def list_wound_cases(self, patient_id: str) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM wound_cases
                    WHERE patient_id = ?
                    ORDER BY opened_at DESC, id DESC
                    """,
                    (patient_id,),
                ).fetchall()
                return [
                    {
                        "id": row["id"],
                        "patient_id": row["patient_id"],
                        "title": row["title"],
                        "wound_type": row["wound_type"],
                        "location": row["location"],
                        "unit_id": row["unit_id"],
                        "team_id": row["team_id"],
                        "assigned_to_uid": row["assigned_to_uid"],
                        "assigned_to_name": row["assigned_to_name"],
                        "assigned_to_role": row["assigned_to_role"],
                        "claimed_by_uid": row["claimed_by_uid"],
                        "claimed_by_name": row["claimed_by_name"],
                        "claimed_by_role": row["claimed_by_role"],
                        "claimed_at": row["claimed_at"],
                        "handoff_to_uid": row["handoff_to_uid"],
                        "handoff_to_name": row["handoff_to_name"],
                        "handoff_to_role": row["handoff_to_role"],
                        "handoff_at": row["handoff_at"],
                        "status": row["status"],
                        "opened_at": row["opened_at"],
                        "closed_at": row["closed_at"],
                        "metadata": json.loads(row["metadata"] or "{}"),
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Erro ao listar casos clÃ­nicos: {e}")
            return []

    def update_wound_case(self, case_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        current = self.get_wound_case(case_id)
        if not current:
            return None

        merged_metadata = dict(current.get("metadata") or {})
        if isinstance(updates.get("metadata"), dict):
            merged_metadata.update(updates["metadata"])

        record = {
            **current,
            **{key: value for key, value in updates.items() if key != "metadata"},
            "metadata": merged_metadata,
        }
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE wound_cases
                    SET title = ?, wound_type = ?, location = ?, unit_id = ?, team_id = ?, assigned_to_uid = ?,
                        assigned_to_name = ?, assigned_to_role = ?, claimed_by_uid = ?, claimed_by_name = ?,
                        claimed_by_role = ?, claimed_at = ?, handoff_to_uid = ?, handoff_to_name = ?,
                        handoff_to_role = ?, handoff_at = ?, status = ?, opened_at = ?, closed_at = ?, metadata = ?
                    WHERE id = ?
                    """,
                    (
                        record.get("title"),
                        record.get("wound_type"),
                        record.get("location"),
                        record.get("unit_id"),
                        record.get("team_id"),
                        record.get("assigned_to_uid"),
                        record.get("assigned_to_name"),
                        record.get("assigned_to_role"),
                        record.get("claimed_by_uid"),
                        record.get("claimed_by_name"),
                        record.get("claimed_by_role"),
                        record.get("claimed_at"),
                        record.get("handoff_to_uid"),
                        record.get("handoff_to_name"),
                        record.get("handoff_to_role"),
                        record.get("handoff_at"),
                        record.get("status"),
                        record.get("opened_at"),
                        record.get("closed_at"),
                        json.dumps(record.get("metadata", {})),
                        case_id,
                    ),
                )
                conn.commit()
            return self.get_wound_case(case_id)
        except Exception as e:
            logger.error(f"Erro ao atualizar caso clÃ­nico: {e}")
            return None

    def create_wound_evaluation(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        evaluation_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        record = {
            "id": evaluation_id,
            "patient_id": payload["patient_id"],
            "case_id": payload.get("case_id"),
            "evaluation_date": payload.get("evaluation_date", now[:10]),
            "professional_name": payload.get("professional_name"),
            "wound_type": payload.get("wound_type"),
            "wound_location": payload.get("wound_location"),
            "clinical_description": payload.get("clinical_description"),
            "push_score": payload.get("push_score"),
            "braden_score": payload.get("braden_score"),
            "bwat_score": payload.get("bwat_score"),
            "pain_score": payload.get("pain_score"),
            "wound_area_cm2": payload.get("wound_area_cm2"),
            "depth_mm": payload.get("depth_mm"),
            "tissue_composition": payload.get("tissue_composition", {}),
            "timers_payload": payload.get("timers_payload", {}),
            "metadata": payload.get("metadata", {}),
            "created_at": now,
            "updated_at": now,
        }
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO wound_evaluations
                    (id, patient_id, case_id, evaluation_date, professional_name, wound_type, wound_location,
                     clinical_description, push_score, braden_score, bwat_score, pain_score, wound_area_cm2,
                     depth_mm, tissue_composition, timers_payload, metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"], record["patient_id"], record["case_id"], record["evaluation_date"],
                        record["professional_name"], record["wound_type"], record["wound_location"],
                        record["clinical_description"], record["push_score"], record["braden_score"],
                        record["bwat_score"], record["pain_score"], record["wound_area_cm2"], record["depth_mm"],
                        json.dumps(record["tissue_composition"]), json.dumps(record["timers_payload"]),
                        json.dumps(record["metadata"]), record["created_at"], record["updated_at"],
                    ),
                )
                conn.commit()
            return record
        except Exception as e:
            logger.error(f"Erro ao criar avaliação clínica: {e}")
            return None

    def get_wound_evaluation(self, evaluation_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM wound_evaluations WHERE id = ?", (evaluation_id,))
                row = cursor.fetchone()
                return self._row_to_evaluation(row) if row else None
        except Exception as e:
            logger.error(f"Erro ao buscar avaliação: {e}")
            return None

    def list_patient_evaluations(self, patient_id: str, case_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if case_id:
                    cursor.execute(
                        """
                        SELECT * FROM wound_evaluations
                        WHERE patient_id = ? AND case_id = ?
                        ORDER BY evaluation_date DESC, created_at DESC
                        """,
                        (patient_id, case_id),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT * FROM wound_evaluations
                        WHERE patient_id = ?
                        ORDER BY evaluation_date DESC, created_at DESC
                        """,
                        (patient_id,),
                    )
                return [self._row_to_evaluation(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erro ao listar avaliações: {e}")
            return []

    def add_wound_image(self, evaluation_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        image_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        try:
            with self._get_connection() as conn:
                image_count_row = conn.execute(
                    "SELECT COUNT(*) AS total FROM wound_images WHERE evaluation_id = ?",
                    (evaluation_id,),
                ).fetchone()
                next_version = int((image_count_row["total"] if image_count_row else 0) or 0) + 1
                metadata = dict(payload.get("metadata", {}))
                metadata.setdefault("version", next_version)
                metadata.setdefault("review_status", payload.get("review_status", "nao_revisada"))
                metadata.setdefault("captured_at", payload.get("captured_at", now))
                metadata.setdefault("patient_id", payload.get("patient_id"))
                metadata.setdefault("case_id", payload.get("case_id"))
                record = {
                    "id": image_id,
                    "evaluation_id": evaluation_id,
                    "image_role": payload.get("image_role", "clinical"),
                    "image_path": payload["image_path"],
                    "content_type": payload.get("content_type", "image/jpeg"),
                    "metadata": metadata,
                    "created_at": now,
                    "version": next_version,
                    "review_status": metadata.get("review_status"),
                    "captured_at": metadata.get("captured_at"),
                    "patient_id": metadata.get("patient_id"),
                    "case_id": metadata.get("case_id"),
                }
                conn.execute(
                    """
                    INSERT INTO wound_images
                    (id, evaluation_id, image_role, image_path, content_type, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"], record["evaluation_id"], record["image_role"], record["image_path"],
                        record["content_type"], json.dumps(record["metadata"]), record["created_at"],
                    ),
                )
                conn.commit()
            return record
        except Exception as e:
            logger.error(f"Erro ao salvar imagem da avaliação: {e}")
            return None

    def list_evaluation_images(self, evaluation_id: str) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM wound_images WHERE evaluation_id = ? ORDER BY created_at ASC",
                    (evaluation_id,),
                ).fetchall()
                return [
                    {
                        **{
                            "id": row["id"],
                            "evaluation_id": row["evaluation_id"],
                            "image_role": row["image_role"],
                            "image_path": row["image_path"],
                            "content_type": row["content_type"],
                            "metadata": json.loads(row["metadata"] or "{}"),
                            "created_at": row["created_at"],
                        },
                        "version": int(json.loads(row["metadata"] or "{}").get("version", 1) or 1),
                        "review_status": json.loads(row["metadata"] or "{}").get("review_status", "nao_revisada"),
                        "captured_at": json.loads(row["metadata"] or "{}").get("captured_at"),
                        "patient_id": json.loads(row["metadata"] or "{}").get("patient_id"),
                        "case_id": json.loads(row["metadata"] or "{}").get("case_id"),
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Erro ao listar imagens: {e}")
            return []

    def get_wound_image(self, image_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM wound_images WHERE id = ?", (image_id,)).fetchone()
                if not row:
                    return None
                metadata = json.loads(row["metadata"] or "{}")
                evaluation = self.get_wound_evaluation(row["evaluation_id"])
                return {
                    "id": row["id"],
                    "evaluation_id": row["evaluation_id"],
                    "image_role": row["image_role"],
                    "image_path": row["image_path"],
                    "content_type": row["content_type"],
                    "metadata": metadata,
                    "created_at": row["created_at"],
                    "version": int(metadata.get("version", 1) or 1),
                    "review_status": metadata.get("review_status", "nao_revisada"),
                    "captured_at": metadata.get("captured_at"),
                    "patient_id": metadata.get("patient_id") or (evaluation or {}).get("patient_id"),
                    "case_id": metadata.get("case_id") or (evaluation or {}).get("case_id"),
                }
        except Exception as e:
            logger.error(f"Erro ao buscar imagem: {e}")
            return None

    def list_ai_runs_for_evaluation(self, evaluation_id: str) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM ai_inference_runs
                    WHERE evaluation_id = ?
                    ORDER BY created_at DESC, id DESC
                    """,
                    (evaluation_id,),
                ).fetchall()
                return [
                    {
                        "id": row["id"],
                        "evaluation_id": row["evaluation_id"],
                        "status": row["status"],
                        "use_fallback": bool(row["use_fallback"]),
                        "stage1_latency_ms": row["stage1_latency_ms"],
                        "stage2_latency_ms": row["stage2_latency_ms"],
                        "failure_reason": row["failure_reason"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Erro ao listar jobs de IA: {e}")
            return []

    def create_ai_run(self, evaluation_id: str, use_fallback: bool = False) -> Optional[Dict[str, Any]]:
        run_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        record = {
            "id": run_id,
            "evaluation_id": evaluation_id,
            "status": "queued",
            "use_fallback": int(use_fallback),
            "stage1_latency_ms": None,
            "stage2_latency_ms": None,
            "failure_reason": None,
            "created_at": now,
            "updated_at": now,
        }
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO ai_inference_runs
                    (id, evaluation_id, status, use_fallback, stage1_latency_ms, stage2_latency_ms,
                     failure_reason, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"], record["evaluation_id"], record["status"], record["use_fallback"],
                        record["stage1_latency_ms"], record["stage2_latency_ms"], record["failure_reason"],
                        record["created_at"], record["updated_at"],
                    ),
                )
                conn.commit()
            return record
        except Exception as e:
            logger.error(f"Erro ao criar job de IA: {e}")
            return None

    def update_ai_run(self, run_id: str, updates: Dict[str, Any]) -> bool:
        allowed = {"status", "use_fallback", "stage1_latency_ms", "stage2_latency_ms", "failure_reason"}
        set_pairs: List[Tuple[str, Any]] = []
        for key, value in updates.items():
            if key in allowed:
                set_pairs.append((key, value))
        set_pairs.append(("updated_at", datetime.now().isoformat()))
        if not set_pairs:
            return False
        set_clause = ", ".join(f"{k} = ?" for k, _ in set_pairs)
        values = [v for _, v in set_pairs] + [run_id]
        try:
            with self._get_connection() as conn:
                conn.execute(f"UPDATE ai_inference_runs SET {set_clause} WHERE id = ?", values)
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar job de IA: {e}")
            return False

    def get_ai_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM ai_inference_runs WHERE id = ?", (run_id,)).fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "evaluation_id": row["evaluation_id"],
                    "status": row["status"],
                    "use_fallback": bool(row["use_fallback"]),
                    "stage1_latency_ms": row["stage1_latency_ms"],
                    "stage2_latency_ms": row["stage2_latency_ms"],
                    "failure_reason": row["failure_reason"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
        except Exception as e:
            logger.error(f"Erro ao buscar job de IA: {e}")
            return None

    def save_ai_result(self, run_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        result_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        try:
            inference = payload.get("inference", {}) if isinstance(payload.get("inference"), dict) else {}
            interpretation = payload.get("interpretation", {}) if isinstance(payload.get("interpretation"), dict) else {}
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO ai_results
                    (id, run_id, etiology, confidence, tissue_percentages, wound_area_cm2,
                     diagnosis_summary, recommendations, payload, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result_id,
                        run_id,
                        inference.get("etiology") or payload.get("etiology"),
                        inference.get("confidence") or payload.get("confidence"),
                        json.dumps(inference.get("tissue_percentages") or payload.get("tissue_percentages", {})),
                        inference.get("wound_area_cm2") or payload.get("wound_area_cm2"),
                        interpretation.get("summary") or payload.get("diagnosis_summary"),
                        json.dumps(interpretation.get("recommendations") or payload.get("recommendations", [])),
                        json.dumps(payload), created_at,
                    ),
                )
                conn.commit()
            return {
                "id": result_id,
                "run_id": run_id,
                "created_at": created_at,
                **payload,
            }
        except Exception as e:
            logger.error(f"Erro ao salvar resultado de IA: {e}")
            return None

    def get_ai_result_by_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM ai_results WHERE run_id = ? ORDER BY created_at DESC LIMIT 1",
                    (run_id,),
                ).fetchone()
                if not row:
                    return None
                payload = json.loads(row["payload"] or "{}")
                inference = payload.get("inference", {}) if isinstance(payload.get("inference"), dict) else {}
                interpretation = payload.get("interpretation", {}) if isinstance(payload.get("interpretation"), dict) else {}
                return {
                    "id": row["id"],
                    "run_id": row["run_id"],
                    "etiology": row["etiology"] or inference.get("etiology"),
                    "confidence": row["confidence"] if row["confidence"] is not None else inference.get("confidence"),
                    "tissue_percentages": json.loads(row["tissue_percentages"] or "{}") or inference.get("tissue_percentages", {}),
                    "wound_area_cm2": row["wound_area_cm2"] if row["wound_area_cm2"] is not None else inference.get("wound_area_cm2"),
                    "diagnosis_summary": row["diagnosis_summary"] or interpretation.get("summary"),
                    "recommendations": json.loads(row["recommendations"] or "[]") or interpretation.get("recommendations", []),
                    "contract_version": payload.get("contract_version"),
                    "model_version": payload.get("model_version"),
                    "patient_id": payload.get("patient_id"),
                    "case_id": payload.get("case_id"),
                    "evaluation_id": payload.get("evaluation_id"),
                    "fallback_used": inference.get("fallback_used", False),
                    "risk_level": interpretation.get("risk_level"),
                    "priority": interpretation.get("priority"),
                    "follow_up_days": interpretation.get("follow_up_days"),
                    "inference": inference,
                    "interpretation": interpretation,
                    "payload": payload,
                    "created_at": row["created_at"],
                }
        except Exception as e:
            logger.error(f"Erro ao buscar resultado de IA: {e}")
            return None

    def get_latest_ai_result_for_evaluation(self, evaluation_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT r.run_id
                    FROM ai_results r
                    INNER JOIN ai_inference_runs runs ON runs.id = r.run_id
                    WHERE runs.evaluation_id = ?
                    ORDER BY r.created_at DESC, r.id DESC
                    LIMIT 1
                    """,
                    (evaluation_id,),
                ).fetchone()
                if not row:
                    return None
                return self.get_ai_result_by_run(row["run_id"])
        except Exception as e:
            logger.error(f"Erro ao buscar resultado mais recente da avaliaÃ§Ã£o: {e}")
            return None

    def create_structured_report(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        report_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO structured_reports
                    (id, patient_id, case_id, evaluation_id, report_type, report_json, pdf_path, docx_path, generated_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_id, payload["patient_id"], payload.get("case_id"), payload.get("evaluation_id"),
                        payload.get("report_type", "evolution"), json.dumps(payload.get("report_json", {})),
                        payload.get("pdf_path"), payload.get("docx_path"), payload.get("generated_by"), created_at,
                    ),
                )
                conn.commit()
            return {"id": report_id, "created_at": created_at, **payload}
        except Exception as e:
            logger.error(f"Erro ao salvar laudo estruturado: {e}")
            return None

    def get_structured_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM structured_reports WHERE id = ?", (report_id,)).fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "patient_id": row["patient_id"],
                    "case_id": row["case_id"],
                    "evaluation_id": row["evaluation_id"],
                    "report_type": row["report_type"],
                    "report_json": json.loads(row["report_json"] or "{}"),
                    "pdf_path": row["pdf_path"],
                    "docx_path": row["docx_path"],
                    "generated_by": row["generated_by"],
                    "created_at": row["created_at"],
                }
        except Exception as e:
            logger.error(f"Erro ao buscar relatório: {e}")
            return None

    def create_care_plan(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        plan_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        unit_id, team_id = self._case_scope(payload["case_id"])
        try:
            with self._get_connection() as conn:
                version_row = conn.execute(
                    "SELECT COALESCE(MAX(version), 0) AS max_version FROM care_plans WHERE case_id = ?",
                    (payload["case_id"],),
                ).fetchone()
                version = int((version_row["max_version"] if version_row else 0) or 0) + 1
                if payload.get("status", "active") == "active":
                    conn.execute(
                        """
                        UPDATE care_plans
                        SET status = 'superseded', updated_at = ?
                        WHERE case_id = ? AND status = 'active'
                        """,
                        (now, payload["case_id"]),
                    )

                record = {
                    "id": plan_id,
                    "patient_id": payload["patient_id"],
                    "case_id": payload["case_id"],
                    "unit_id": payload.get("unit_id") or unit_id,
                    "team_id": payload.get("team_id") or team_id,
                    "version": version,
                    "title": payload.get("title", "Care plan"),
                    "status": payload.get("status", "draft"),
                    "risk_level": payload.get("risk_level", "moderado"),
                    "goals": payload.get("goals", []),
                    "frequency": payload.get("frequency"),
                    "tasks": payload.get("tasks", []),
                    "alerts": payload.get("alerts", []),
                    "source_evaluation_id": payload.get("source_evaluation_id"),
                    "source_result_id": payload.get("source_result_id"),
                    "review_due_date": payload.get("review_due_date"),
                    "created_by": payload.get("created_by"),
                    "created_at": now,
                    "updated_at": now,
                    "metadata": payload.get("metadata", {}),
                }
                conn.execute(
                    """
                    INSERT INTO care_plans
                    (id, patient_id, case_id, unit_id, team_id, version, title, status, risk_level, goals, frequency, tasks, alerts,
                     source_evaluation_id, source_result_id, review_due_date, created_by, created_at, updated_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"],
                        record["patient_id"],
                        record["case_id"],
                        record["unit_id"],
                        record["team_id"],
                        record["version"],
                        record["title"],
                        record["status"],
                        record["risk_level"],
                        json.dumps(record["goals"]),
                        record["frequency"],
                        json.dumps(record["tasks"]),
                        json.dumps(record["alerts"]),
                        record["source_evaluation_id"],
                        record["source_result_id"],
                        record["review_due_date"],
                        record["created_by"],
                        record["created_at"],
                        record["updated_at"],
                        json.dumps(record["metadata"]),
                    ),
                )
                conn.commit()
                return record
        except Exception as e:
            logger.error(f"Erro ao criar plano de cuidado: {e}")
            return None

    def list_case_care_plans(self, case_id: str) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM care_plans
                    WHERE case_id = ?
                    ORDER BY version DESC, created_at DESC
                    """,
                    (case_id,),
                ).fetchall()
                return [
                    {
                        "id": row["id"],
                        "patient_id": row["patient_id"],
                        "case_id": row["case_id"],
                        "unit_id": row["unit_id"],
                        "team_id": row["team_id"],
                        "version": row["version"],
                        "title": row["title"],
                        "status": row["status"],
                        "risk_level": row["risk_level"],
                        "goals": json.loads(row["goals"] or "[]"),
                        "frequency": row["frequency"],
                        "tasks": json.loads(row["tasks"] or "[]"),
                        "alerts": json.loads(row["alerts"] or "[]"),
                        "source_evaluation_id": row["source_evaluation_id"],
                        "source_result_id": row["source_result_id"],
                        "review_due_date": row["review_due_date"],
                        "created_by": row["created_by"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "metadata": json.loads(row["metadata"] or "{}"),
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Erro ao listar planos de cuidado: {e}")
            return []

    def get_active_care_plan_for_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        plans = self.list_case_care_plans(case_id)
        for plan in plans:
            if plan["status"] == "active":
                return plan
        return plans[0] if plans else None

    def get_care_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM care_plans WHERE id = ?", (plan_id,)).fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "patient_id": row["patient_id"],
                    "case_id": row["case_id"],
                    "unit_id": row["unit_id"],
                    "team_id": row["team_id"],
                    "version": row["version"],
                    "title": row["title"],
                    "status": row["status"],
                    "risk_level": row["risk_level"],
                    "goals": json.loads(row["goals"] or "[]"),
                    "frequency": row["frequency"],
                    "tasks": json.loads(row["tasks"] or "[]"),
                    "alerts": json.loads(row["alerts"] or "[]"),
                    "source_evaluation_id": row["source_evaluation_id"],
                    "source_result_id": row["source_result_id"],
                    "review_due_date": row["review_due_date"],
                    "created_by": row["created_by"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "metadata": json.loads(row["metadata"] or "{}"),
                }
        except Exception as e:
            logger.error(f"Erro ao buscar plano de cuidado: {e}")
            return None

    def update_care_plan(self, plan_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        current = self.get_care_plan(plan_id)
        if not current:
            return None

        now = datetime.now().isoformat()
        merged_metadata = dict(current.get("metadata") or {})
        if isinstance(updates.get("metadata"), dict):
            merged_metadata.update(updates["metadata"])

        record = {
            **current,
            **{key: value for key, value in updates.items() if key != "metadata"},
            "metadata": merged_metadata,
            "updated_at": now,
        }

        try:
            with self._get_connection() as conn:
                if record.get("status") == "active":
                    conn.execute(
                        """
                        UPDATE care_plans
                        SET status = 'superseded', updated_at = ?
                        WHERE case_id = ? AND status = 'active' AND id <> ?
                        """,
                        (now, record["case_id"], plan_id),
                    )
                conn.execute(
                    """
                    UPDATE care_plans
                    SET unit_id = ?, team_id = ?, title = ?, status = ?, risk_level = ?, goals = ?, frequency = ?, tasks = ?, alerts = ?,
                        review_due_date = ?, updated_at = ?, metadata = ?
                    WHERE id = ?
                    """,
                    (
                        record.get("unit_id"),
                        record.get("team_id"),
                        record["title"],
                        record["status"],
                        record["risk_level"],
                        json.dumps(record.get("goals", [])),
                        record.get("frequency"),
                        json.dumps(record.get("tasks", [])),
                        json.dumps(record.get("alerts", [])),
                        record.get("review_due_date"),
                        record["updated_at"],
                        json.dumps(record.get("metadata", {})),
                        plan_id,
                    ),
                )
                conn.commit()
            return self.get_care_plan(plan_id)
        except Exception as e:
            logger.error(f"Erro ao atualizar plano de cuidado: {e}")
            return None

    def create_follow_up(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        follow_up_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        unit_id, team_id = self._case_scope(payload["case_id"])
        record = {
            "id": follow_up_id,
            "patient_id": payload["patient_id"],
            "case_id": payload["case_id"],
            "unit_id": payload.get("unit_id") or unit_id,
            "team_id": payload.get("team_id") or team_id,
            "care_plan_id": payload.get("care_plan_id"),
            "evaluation_id": payload.get("evaluation_id"),
            "scheduled_for": payload["scheduled_for"],
            "status": payload.get("status", "scheduled"),
            "reason": payload.get("reason"),
            "assigned_role": payload.get("assigned_role"),
            "assigned_to_uid": payload.get("assigned_to_uid"),
            "assigned_to_name": payload.get("assigned_to_name"),
            "assigned_to_role": payload.get("assigned_to_role"),
            "created_by": payload.get("created_by"),
            "notes": payload.get("notes"),
            "created_at": now,
            "completed_at": payload.get("completed_at"),
            "metadata": payload.get("metadata", {}),
        }
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO follow_ups
                    (id, patient_id, case_id, unit_id, team_id, care_plan_id, evaluation_id, scheduled_for, status, reason, assigned_role,
                     assigned_to_uid, assigned_to_name, assigned_to_role, created_by, notes, created_at, completed_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"],
                        record["patient_id"],
                        record["case_id"],
                        record["unit_id"],
                        record["team_id"],
                        record["care_plan_id"],
                        record["evaluation_id"],
                        record["scheduled_for"],
                        record["status"],
                        record["reason"],
                        record["assigned_role"],
                        record["assigned_to_uid"],
                        record["assigned_to_name"],
                        record["assigned_to_role"],
                        record["created_by"],
                        record["notes"],
                        record["created_at"],
                        record["completed_at"],
                        json.dumps(record["metadata"]),
                    ),
                )
                conn.commit()
            return record
        except Exception as e:
            logger.error(f"Erro ao criar follow-up clÃ­nico: {e}")
            return None

    def list_case_follow_ups(self, case_id: str) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM follow_ups
                    WHERE case_id = ?
                    ORDER BY scheduled_for ASC, created_at ASC
                    """,
                    (case_id,),
                ).fetchall()
                return [
                    {
                        "id": row["id"],
                        "patient_id": row["patient_id"],
                        "case_id": row["case_id"],
                        "unit_id": row["unit_id"],
                        "team_id": row["team_id"],
                        "care_plan_id": row["care_plan_id"],
                        "evaluation_id": row["evaluation_id"],
                        "scheduled_for": row["scheduled_for"],
                        "status": row["status"],
                        "reason": row["reason"],
                        "assigned_role": row["assigned_role"],
                        "assigned_to_uid": row["assigned_to_uid"],
                        "assigned_to_name": row["assigned_to_name"],
                        "assigned_to_role": row["assigned_to_role"],
                        "created_by": row["created_by"],
                        "notes": row["notes"],
                        "created_at": row["created_at"],
                        "completed_at": row["completed_at"],
                        "metadata": json.loads(row["metadata"] or "{}"),
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Erro ao listar follow-ups: {e}")
            return []

    def get_follow_up(self, follow_up_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM follow_ups WHERE id = ?", (follow_up_id,)).fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "patient_id": row["patient_id"],
                    "case_id": row["case_id"],
                    "unit_id": row["unit_id"],
                    "team_id": row["team_id"],
                    "care_plan_id": row["care_plan_id"],
                    "evaluation_id": row["evaluation_id"],
                    "scheduled_for": row["scheduled_for"],
                    "status": row["status"],
                    "reason": row["reason"],
                    "assigned_role": row["assigned_role"],
                    "assigned_to_uid": row["assigned_to_uid"],
                    "assigned_to_name": row["assigned_to_name"],
                    "assigned_to_role": row["assigned_to_role"],
                    "created_by": row["created_by"],
                    "notes": row["notes"],
                    "created_at": row["created_at"],
                    "completed_at": row["completed_at"],
                    "metadata": json.loads(row["metadata"] or "{}"),
                }
        except Exception as e:
            logger.error(f"Erro ao buscar follow-up: {e}")
            return None

    def update_follow_up(self, follow_up_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        current = self.get_follow_up(follow_up_id)
        if not current:
            return None

        merged_metadata = dict(current.get("metadata") or {})
        if isinstance(updates.get("metadata"), dict):
            merged_metadata.update(updates["metadata"])

        record = {
            **current,
            **{key: value for key, value in updates.items() if key != "metadata"},
            "metadata": merged_metadata,
        }
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE follow_ups
                    SET unit_id = ?, team_id = ?, scheduled_for = ?, status = ?, reason = ?, assigned_role = ?,
                        assigned_to_uid = ?, assigned_to_name = ?, assigned_to_role = ?, notes = ?, completed_at = ?, metadata = ?
                    WHERE id = ?
                    """,
                    (
                        record.get("unit_id"),
                        record.get("team_id"),
                        record["scheduled_for"],
                        record["status"],
                        record.get("reason"),
                        record.get("assigned_role"),
                        record.get("assigned_to_uid"),
                        record.get("assigned_to_name"),
                        record.get("assigned_to_role"),
                        record.get("notes"),
                        record.get("completed_at"),
                        json.dumps(record.get("metadata", {})),
                        follow_up_id,
                    ),
                )
                conn.commit()
            return self.get_follow_up(follow_up_id)
        except Exception as e:
            logger.error(f"Erro ao atualizar follow-up: {e}")
            return None

    def create_clinical_alert(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        alert_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        unit_id, team_id = self._case_scope(payload["case_id"])
        record = {
            "id": alert_id,
            "patient_id": payload["patient_id"],
            "case_id": payload["case_id"],
            "unit_id": payload.get("unit_id") or unit_id,
            "team_id": payload.get("team_id") or team_id,
            "care_plan_id": payload.get("care_plan_id"),
            "follow_up_id": payload.get("follow_up_id"),
            "alert_type": payload.get("alert_type", "clinical"),
            "severity": payload.get("severity", "moderado"),
            "status": payload.get("status", "open"),
            "title": payload.get("title", "Clinical alert"),
            "message": payload.get("message", ""),
            "assigned_to_uid": payload.get("assigned_to_uid"),
            "assigned_to_name": payload.get("assigned_to_name"),
            "assigned_to_role": payload.get("assigned_to_role"),
            "claimed_by_uid": payload.get("claimed_by_uid"),
            "claimed_by_name": payload.get("claimed_by_name"),
            "claimed_by_role": payload.get("claimed_by_role"),
            "claimed_at": payload.get("claimed_at"),
            "handoff_to_uid": payload.get("handoff_to_uid"),
            "handoff_to_name": payload.get("handoff_to_name"),
            "handoff_to_role": payload.get("handoff_to_role"),
            "handoff_at": payload.get("handoff_at"),
            "due_at": payload.get("due_at"),
            "created_at": now,
            "resolved_at": payload.get("resolved_at"),
            "metadata": payload.get("metadata", {}),
        }
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO clinical_alerts
                    (id, patient_id, case_id, unit_id, team_id, care_plan_id, follow_up_id, alert_type, severity, status,
                     title, message, assigned_to_uid, assigned_to_name, assigned_to_role, claimed_by_uid, claimed_by_name,
                     claimed_by_role, claimed_at, handoff_to_uid, handoff_to_name, handoff_to_role, handoff_at, due_at,
                     created_at, resolved_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"],
                        record["patient_id"],
                        record["case_id"],
                        record["unit_id"],
                        record["team_id"],
                        record["care_plan_id"],
                        record["follow_up_id"],
                        record["alert_type"],
                        record["severity"],
                        record["status"],
                        record["title"],
                        record["message"],
                        record["assigned_to_uid"],
                        record["assigned_to_name"],
                        record["assigned_to_role"],
                        record["claimed_by_uid"],
                        record["claimed_by_name"],
                        record["claimed_by_role"],
                        record["claimed_at"],
                        record["handoff_to_uid"],
                        record["handoff_to_name"],
                        record["handoff_to_role"],
                        record["handoff_at"],
                        record["due_at"],
                        record["created_at"],
                        record["resolved_at"],
                        json.dumps(record["metadata"]),
                    ),
                )
                conn.commit()
            return record
        except Exception as e:
            logger.error(f"Erro ao criar alerta clÃ­nico: {e}")
            return None

    def list_case_alerts(self, case_id: str, active_only: bool = False) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                if active_only:
                    rows = conn.execute(
                        """
                        SELECT * FROM clinical_alerts
                        WHERE case_id = ? AND status IN ('open', 'acknowledged')
                        ORDER BY created_at DESC, id DESC
                        """,
                        (case_id,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT * FROM clinical_alerts
                        WHERE case_id = ?
                        ORDER BY created_at DESC, id DESC
                        """,
                        (case_id,),
                    ).fetchall()
                return [
                    {
                        "id": row["id"],
                        "patient_id": row["patient_id"],
                        "case_id": row["case_id"],
                        "unit_id": row["unit_id"],
                        "team_id": row["team_id"],
                        "care_plan_id": row["care_plan_id"],
                        "follow_up_id": row["follow_up_id"],
                        "alert_type": row["alert_type"],
                        "severity": row["severity"],
                        "status": row["status"],
                        "title": row["title"],
                        "message": row["message"],
                        "assigned_to_uid": row["assigned_to_uid"],
                        "assigned_to_name": row["assigned_to_name"],
                        "assigned_to_role": row["assigned_to_role"],
                        "claimed_by_uid": row["claimed_by_uid"],
                        "claimed_by_name": row["claimed_by_name"],
                        "claimed_by_role": row["claimed_by_role"],
                        "claimed_at": row["claimed_at"],
                        "handoff_to_uid": row["handoff_to_uid"],
                        "handoff_to_name": row["handoff_to_name"],
                        "handoff_to_role": row["handoff_to_role"],
                        "handoff_at": row["handoff_at"],
                        "due_at": row["due_at"],
                        "created_at": row["created_at"],
                        "resolved_at": row["resolved_at"],
                        "metadata": json.loads(row["metadata"] or "{}"),
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Erro ao listar alertas clÃ­nicos: {e}")
            return []

    def get_clinical_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM clinical_alerts WHERE id = ?", (alert_id,)).fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "patient_id": row["patient_id"],
                    "case_id": row["case_id"],
                    "unit_id": row["unit_id"],
                    "team_id": row["team_id"],
                    "care_plan_id": row["care_plan_id"],
                    "follow_up_id": row["follow_up_id"],
                    "alert_type": row["alert_type"],
                    "severity": row["severity"],
                    "status": row["status"],
                    "title": row["title"],
                    "message": row["message"],
                    "assigned_to_uid": row["assigned_to_uid"],
                    "assigned_to_name": row["assigned_to_name"],
                    "assigned_to_role": row["assigned_to_role"],
                    "claimed_by_uid": row["claimed_by_uid"],
                    "claimed_by_name": row["claimed_by_name"],
                    "claimed_by_role": row["claimed_by_role"],
                    "claimed_at": row["claimed_at"],
                    "handoff_to_uid": row["handoff_to_uid"],
                    "handoff_to_name": row["handoff_to_name"],
                    "handoff_to_role": row["handoff_to_role"],
                    "handoff_at": row["handoff_at"],
                    "due_at": row["due_at"],
                    "created_at": row["created_at"],
                    "resolved_at": row["resolved_at"],
                    "metadata": json.loads(row["metadata"] or "{}"),
                }
        except Exception as e:
            logger.error(f"Erro ao buscar alerta clÃ­nico: {e}")
            return None

    def update_clinical_alert(self, alert_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        current = self.get_clinical_alert(alert_id)
        if not current:
            return None

        merged_metadata = dict(current.get("metadata") or {})
        if isinstance(updates.get("metadata"), dict):
            merged_metadata.update(updates["metadata"])

        record = {
            **current,
            **{key: value for key, value in updates.items() if key != "metadata"},
            "metadata": merged_metadata,
        }
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE clinical_alerts
                    SET unit_id = ?, team_id = ?, severity = ?, status = ?, title = ?, message = ?, assigned_to_uid = ?,
                        assigned_to_name = ?, assigned_to_role = ?, claimed_by_uid = ?, claimed_by_name = ?,
                        claimed_by_role = ?, claimed_at = ?, handoff_to_uid = ?, handoff_to_name = ?, handoff_to_role = ?,
                        handoff_at = ?, due_at = ?, resolved_at = ?, metadata = ?
                    WHERE id = ?
                    """,
                    (
                        record.get("unit_id"),
                        record.get("team_id"),
                        record.get("severity"),
                        record.get("status"),
                        record.get("title"),
                        record.get("message"),
                        record.get("assigned_to_uid"),
                        record.get("assigned_to_name"),
                        record.get("assigned_to_role"),
                        record.get("claimed_by_uid"),
                        record.get("claimed_by_name"),
                        record.get("claimed_by_role"),
                        record.get("claimed_at"),
                        record.get("handoff_to_uid"),
                        record.get("handoff_to_name"),
                        record.get("handoff_to_role"),
                        record.get("handoff_at"),
                        record.get("due_at"),
                        record.get("resolved_at"),
                        json.dumps(record.get("metadata", {})),
                        alert_id,
                    ),
                )
                conn.commit()
            return self.get_clinical_alert(alert_id)
        except Exception as e:
            logger.error(f"Erro ao atualizar alerta clÃ­nico: {e}")
            return None

    def create_audit_event(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_id = str(uuid.uuid4())
        record = {
            "id": event_id,
            "patient_id": payload["patient_id"],
            "case_id": payload["case_id"],
            "entity_type": payload["entity_type"],
            "entity_id": payload["entity_id"],
            "action": payload["action"],
            "actor_uid": payload.get("actor_uid"),
            "actor_name": payload.get("actor_name"),
            "actor_role": payload.get("actor_role"),
            "before_json": payload.get("before_json"),
            "after_json": payload.get("after_json"),
            "metadata": payload.get("metadata", {}),
            "created_at": payload.get("created_at") or datetime.now().isoformat(),
        }
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO clinical_audit_log
                    (id, patient_id, case_id, entity_type, entity_id, action, actor_uid, actor_name, actor_role,
                     before_json, after_json, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["id"],
                        record["patient_id"],
                        record["case_id"],
                        record["entity_type"],
                        record["entity_id"],
                        record["action"],
                        record.get("actor_uid"),
                        record.get("actor_name"),
                        record.get("actor_role"),
                        json.dumps(record.get("before_json")) if record.get("before_json") is not None else None,
                        json.dumps(record.get("after_json")) if record.get("after_json") is not None else None,
                        json.dumps(record.get("metadata", {})),
                        record["created_at"],
                    ),
                )
                conn.commit()
            return record
        except Exception as e:
            logger.error(f"Erro ao registrar auditoria clÃ­nica: {e}")
            return None

    def list_case_audit_events(self, case_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(int(limit or 100), 500))
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM clinical_audit_log
                    WHERE case_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (case_id, safe_limit),
                ).fetchall()
                return [
                    {
                        "id": row["id"],
                        "patient_id": row["patient_id"],
                        "case_id": row["case_id"],
                        "entity_type": row["entity_type"],
                        "entity_id": row["entity_id"],
                        "action": row["action"],
                        "actor_uid": row["actor_uid"],
                        "actor_name": row["actor_name"],
                        "actor_role": row["actor_role"],
                        "before_json": json.loads(row["before_json"]) if row["before_json"] else None,
                        "after_json": json.loads(row["after_json"]) if row["after_json"] else None,
                        "metadata": json.loads(row["metadata"] or "{}"),
                        "created_at": row["created_at"],
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Erro ao listar auditoria clÃ­nica: {e}")
            return []

    def get_case_timeline(self, case_id: str) -> Optional[Dict[str, Any]]:
        case = self.get_wound_case(case_id)
        if not case:
            return None
        patient = self.get_patient(case["patient_id"])
        if not patient:
            return None

        evaluations = list(reversed(self.list_patient_evaluations(case["patient_id"], case_id=case_id)))
        enriched_evaluations: List[Dict[str, Any]] = []
        for evaluation in evaluations:
            images = self.list_evaluation_images(evaluation["id"])
            ai_result = self.get_latest_ai_result_for_evaluation(evaluation["id"])
            enriched_evaluations.append(
                {
                    **evaluation,
                    "lesion_id": case_id,
                    "images": images,
                    "inference_result": ai_result,
                }
            )

        return {
            "patient": patient,
            "lesion": case,
            "evaluations": enriched_evaluations,
            "care_plans": list(reversed(self.list_case_care_plans(case_id))),
            "follow_ups": self.list_case_follow_ups(case_id),
            "alerts": self.list_case_alerts(case_id),
            "audit_log": list(reversed(self.list_case_audit_events(case_id, limit=200))),
        }

    def _row_to_evaluation(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "patient_id": row["patient_id"],
            "case_id": row["case_id"],
            "evaluation_date": row["evaluation_date"],
            "professional_name": row["professional_name"],
            "wound_type": row["wound_type"],
            "wound_location": row["wound_location"],
            "clinical_description": row["clinical_description"],
            "push_score": row["push_score"],
            "braden_score": row["braden_score"],
            "bwat_score": row["bwat_score"],
            "pain_score": row["pain_score"],
            "wound_area_cm2": row["wound_area_cm2"],
            "depth_mm": row["depth_mm"],
            "tissue_composition": json.loads(row["tissue_composition"] or "{}"),
            "timers_payload": json.loads(row["timers_payload"] or "{}"),
            "metadata": json.loads(row["metadata"] or "{}"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
    
    @contextmanager
    def _get_connection(self):
        """Context manager para conexão com o banco"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    # === PACIENTES ===
    
    def save_patient(self, patient: PatientRecord) -> bool:
        """Salva ou atualiza registro de paciente"""
        try:
            metadata = dict(patient.metadata or {})
            unit_id = patient.unit_id or metadata.get("unit_id") or metadata.get("unit")
            team_id = patient.team_id or metadata.get("team_id") or metadata.get("team")
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO patients 
                    (id, name, birth_date, medical_record, unit_id, team_id, notes, created_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    patient.id,
                    patient.name,
                    patient.birth_date,
                    patient.medical_record,
                    unit_id,
                    team_id,
                    patient.notes,
                    patient.created_at,
                    json.dumps(metadata)
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Erro ao salvar paciente: {e}")
            return False
    
    def get_patient(self, patient_id: str) -> Optional[PatientRecord]:
        """Busca paciente por ID"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
                row = cursor.fetchone()
                
                if row:
                    return PatientRecord(
                        id=row["id"],
                        name=row["name"],
                        birth_date=row["birth_date"],
                        medical_record=row["medical_record"],
                        unit_id=row["unit_id"],
                        team_id=row["team_id"],
                        notes=row["notes"],
                        created_at=row["created_at"],
                        metadata=json.loads(row["metadata"] or "{}")
                    )
                return None
        except Exception as e:
            logger.error(f"Erro ao buscar paciente: {e}")
            return None
    
    def list_patients(self, limit: int = 100) -> List[PatientRecord]:
        """Lista todos os pacientes"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM patients ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
                rows = cursor.fetchall()
                
                return [
                    PatientRecord(
                        id=row["id"],
                        name=row["name"],
                        birth_date=row["birth_date"],
                        medical_record=row["medical_record"],
                        unit_id=row["unit_id"],
                        team_id=row["team_id"],
                        notes=row["notes"],
                        created_at=row["created_at"],
                        metadata=json.loads(row["metadata"] or "{}")
                    )
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Erro ao listar pacientes: {e}")
            return []
    
    def delete_patient(self, patient_id: str) -> bool:
        """Remove paciente e suas análises"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM analyses WHERE patient_id = ?", (patient_id,))
                cursor.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Erro ao deletar paciente: {e}")
            return False
    
    # === ANÁLISES ===
    
    def save_analysis(self, analysis: AnalysisRecord) -> bool:
        """Salva registro de análise"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO analyses 
                    (id, patient_id, timestamp, image_path, etiology, confidence,
                     tissue_percentages, wound_area_cm2, health_score, recommendations,
                     notes, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    analysis.id,
                    analysis.patient_id,
                    analysis.timestamp,
                    analysis.image_path,
                    analysis.etiology,
                    analysis.confidence,
                    json.dumps(analysis.tissue_percentages),
                    analysis.wound_area_cm2,
                    analysis.health_score,
                    json.dumps(analysis.recommendations),
                    analysis.notes,
                    json.dumps(analysis.metadata)
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Erro ao salvar análise: {e}")
            return False
    
    def get_analysis(self, analysis_id: str) -> Optional[AnalysisRecord]:
        """Busca análise por ID"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,))
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_analysis(row)
                return None
        except Exception as e:
            logger.error(f"Erro ao buscar análise: {e}")
            return None
    
    def get_patient_analyses(
        self,
        patient_id: str,
        limit: int = 50
    ) -> List[AnalysisRecord]:
        """Busca análises de um paciente"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM analyses 
                    WHERE patient_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (patient_id, limit))
                rows = cursor.fetchall()
                
                return [self._row_to_analysis(row) for row in rows]
        except Exception as e:
            logger.error(f"Erro ao buscar análises do paciente: {e}")
            return []
    
    def get_recent_analyses(self, limit: int = 20) -> List[AnalysisRecord]:
        """Busca análises recentes"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM analyses 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                
                return [self._row_to_analysis(row) for row in rows]
        except Exception as e:
            logger.error(f"Erro ao buscar análises recentes: {e}")
            return []
    
    def _row_to_analysis(self, row: sqlite3.Row) -> AnalysisRecord:
        """Converte row SQLite para AnalysisRecord"""
        return AnalysisRecord(
            id=row["id"],
            patient_id=row["patient_id"],
            timestamp=row["timestamp"],
            image_path=row["image_path"],
            etiology=row["etiology"],
            confidence=row["confidence"],
            tissue_percentages=json.loads(row["tissue_percentages"] or "{}"),
            wound_area_cm2=row["wound_area_cm2"],
            health_score=row["health_score"],
            recommendations=json.loads(row["recommendations"] or "[]"),
            notes=row["notes"],
            metadata=json.loads(row["metadata"] or "{}")
        )
    
    def delete_analysis(self, analysis_id: str) -> bool:
        """Remove análise"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Erro ao deletar análise: {e}")
            return False
    
    # === CONFIGURAÇÕES ===
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Obtém valor de configuração"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                
                if row:
                    return json.loads(row["value"])
                return default
        except Exception as e:
            logger.error(f"Erro ao obter configuração: {e}")
            return default
    
    def set_setting(self, key: str, value: Any) -> bool:
        """Define valor de configuração"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO settings (key, value)
                    VALUES (?, ?)
                """, (key, json.dumps(value)))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Erro ao definir configuração: {e}")
            return False
    
    # === ESTATÍSTICAS ===
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas do banco de dados"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Total de pacientes
                cursor.execute("SELECT COUNT(*) FROM patients")
                total_patients = cursor.fetchone()[0]
                
                # Total de análises
                cursor.execute("SELECT COUNT(*) FROM analyses")
                total_analyses = cursor.fetchone()[0]
                
                # Etiologias mais comuns
                cursor.execute("""
                    SELECT etiology, COUNT(*) as count 
                    FROM analyses 
                    GROUP BY etiology 
                    ORDER BY count DESC 
                    LIMIT 5
                """)
                top_etiologies = {row["etiology"]: row["count"] for row in cursor.fetchall()}
                
                # Média de health score
                cursor.execute("SELECT AVG(health_score) FROM analyses")
                avg_health_score = cursor.fetchone()[0] or 0
                
                return {
                    "total_patients": total_patients,
                    "total_analyses": total_analyses,
                    "top_etiologies": top_etiologies,
                    "avg_health_score": round(avg_health_score, 1)
                }
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {}
    
    def export_to_json(self, output_path: str) -> bool:
        """Exporta banco de dados para JSON"""
        try:
            data = {
                "patients": [p.to_dict() for p in self.list_patients(1000)],
                "analyses": [a.to_dict() for a in self.get_recent_analyses(1000)],
                "statistics": self.get_statistics(),
                "exported_at": datetime.now().isoformat()
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Dados exportados para: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Erro ao exportar dados: {e}")
            return False
