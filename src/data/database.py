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
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "birth_date": self.birth_date,
            "medical_record": self.medical_record,
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
            
            conn.commit()
            
        logger.info(f"Banco de dados inicializado: {self.db_path}")

    # === MODELO CLÍNICO E JOBS ===

    def create_wound_case(self, patient_id: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        case_id = payload.get("id") or str(uuid.uuid4())
        now = datetime.now().isoformat()
        case = {
            "id": case_id,
            "patient_id": patient_id,
            "title": payload.get("title"),
            "wound_type": payload.get("wound_type"),
            "location": payload.get("location"),
            "status": payload.get("status", "active"),
            "opened_at": payload.get("opened_at", now),
            "closed_at": payload.get("closed_at"),
            "metadata": payload.get("metadata", {}),
        }
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO wound_cases
                    (id, patient_id, title, wound_type, location, status, opened_at, closed_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        case["id"], case["patient_id"], case["title"], case["wound_type"],
                        case["location"], case["status"], case["opened_at"], case["closed_at"],
                        json.dumps(case["metadata"]),
                    ),
                )
                conn.commit()
            return case
        except Exception as e:
            logger.error(f"Erro ao criar caso clínico: {e}")
            return None

    def create_wound_evaluation(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        evaluation_id = payload.get("id") or str(uuid.uuid4())
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
        image_id = payload.get("id") or str(uuid.uuid4())
        now = datetime.now().isoformat()
        record = {
            "id": image_id,
            "evaluation_id": evaluation_id,
            "image_role": payload.get("image_role", "clinical"),
            "image_path": payload["image_path"],
            "content_type": payload.get("content_type", "image/jpeg"),
            "metadata": payload.get("metadata", {}),
            "created_at": now,
        }
        try:
            with self._get_connection() as conn:
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
                        "id": row["id"],
                        "evaluation_id": row["evaluation_id"],
                        "image_role": row["image_role"],
                        "image_path": row["image_path"],
                        "content_type": row["content_type"],
                        "metadata": json.loads(row["metadata"] or "{}"),
                        "created_at": row["created_at"],
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Erro ao listar imagens: {e}")
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
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO ai_results
                    (id, run_id, etiology, confidence, tissue_percentages, wound_area_cm2,
                     diagnosis_summary, recommendations, payload, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result_id, run_id, payload.get("etiology"), payload.get("confidence"),
                        json.dumps(payload.get("tissue_percentages", {})), payload.get("wound_area_cm2"),
                        payload.get("diagnosis_summary"), json.dumps(payload.get("recommendations", [])),
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
                return {
                    "id": row["id"],
                    "run_id": row["run_id"],
                    "etiology": row["etiology"],
                    "confidence": row["confidence"],
                    "tissue_percentages": json.loads(row["tissue_percentages"] or "{}"),
                    "wound_area_cm2": row["wound_area_cm2"],
                    "diagnosis_summary": row["diagnosis_summary"],
                    "recommendations": json.loads(row["recommendations"] or "[]"),
                    "payload": json.loads(row["payload"] or "{}"),
                    "created_at": row["created_at"],
                }
        except Exception as e:
            logger.error(f"Erro ao buscar resultado de IA: {e}")
            return None

    def create_structured_report(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        report_id = payload.get("id") or str(uuid.uuid4())
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
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO patients 
                    (id, name, birth_date, medical_record, notes, created_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    patient.id,
                    patient.name,
                    patient.birth_date,
                    patient.medical_record,
                    patient.notes,
                    patient.created_at,
                    json.dumps(patient.metadata)
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
