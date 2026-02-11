"""
REDISUS - Sistema de Diagnóstico de Feridas
Módulo de Banco de Dados

Gerencia persistência de dados de análises, pacientes e histórico.
Usa SQLite para armazenamento local.
"""
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
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
            
            # Índices
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analyses_patient 
                ON analyses(patient_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analyses_timestamp 
                ON analyses(timestamp)
            """)
            
            conn.commit()
            
        logger.info(f"Banco de dados inicializado: {self.db_path}")
    
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
