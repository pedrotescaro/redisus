"""
HEAL/REDISUS - Monitoramento de Sinais Vitais e Alertas Preditivos
Captura, análise e alertas baseados em sinais vitais e dados de vestíveis.

Implementa:
- Registro e armazenamento de sinais vitais
- Integração com dispositivos vestíveis (BLE, APIs)
- Alertas preditivos baseados em tendências
- Detecção de deterioração clínica precoce
- Suporte ao monitoramento domiciliar (Programa Melhor em Casa)
"""
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Tuple

from loguru import logger


class VitalSignType(Enum):
    """Tipos de sinais vitais"""
    HEART_RATE = "frequencia_cardiaca"
    BLOOD_PRESSURE_SYS = "pressao_sistolica"
    BLOOD_PRESSURE_DIA = "pressao_diastolica"
    TEMPERATURE = "temperatura"
    OXYGEN_SATURATION = "saturacao_o2"
    RESPIRATORY_RATE = "frequencia_respiratoria"
    BLOOD_GLUCOSE = "glicemia"
    PAIN_LEVEL = "nivel_dor"
    WEIGHT = "peso"


class DeviceType(Enum):
    """Tipos de dispositivo de monitoramento"""
    MANUAL = "manual"
    SMARTWATCH = "smartwatch"
    BLUETOOTH_BP = "esfigmo_bluetooth"
    PULSE_OXIMETER = "oximetro"
    GLUCOSE_METER = "glicosimetro"
    SMART_SCALE = "balanca"
    TEMPERATURE_SENSOR = "sensor_temperatura"
    AMBIENT_SENSOR = "sensor_ambiental"


@dataclass
class VitalSignReading:
    """Leitura individual de sinal vital"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    patient_id: str = ""
    type: VitalSignType = VitalSignType.HEART_RATE
    value: float = 0.0
    unit: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    device: DeviceType = DeviceType.MANUAL
    device_id: str = ""
    quality: str = "good"  # good, acceptable, poor
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "type": self.type.value,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp,
            "device": self.device.value,
            "quality": self.quality,
        }


@dataclass
class VitalSignAlert:
    """Alerta de sinal vital fora do normal"""
    type: str
    severity: str  # info, warning, critical
    vital_sign: VitalSignType
    value: float
    threshold: float
    message: str
    patient_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    action_required: str = ""


# Limites normais de sinais vitais (adultos)
VITAL_SIGN_RANGES = {
    VitalSignType.HEART_RATE: {
        "unit": "bpm",
        "low_critical": 40, "low_warning": 50,
        "high_warning": 100, "high_critical": 130,
        "normal_range": "60-100 bpm",
    },
    VitalSignType.BLOOD_PRESSURE_SYS: {
        "unit": "mmHg",
        "low_critical": 70, "low_warning": 90,
        "high_warning": 140, "high_critical": 180,
        "normal_range": "90-140 mmHg",
    },
    VitalSignType.BLOOD_PRESSURE_DIA: {
        "unit": "mmHg",
        "low_critical": 40, "low_warning": 60,
        "high_warning": 90, "high_critical": 120,
        "normal_range": "60-90 mmHg",
    },
    VitalSignType.TEMPERATURE: {
        "unit": "°C",
        "low_critical": 35.0, "low_warning": 36.0,
        "high_warning": 37.8, "high_critical": 39.0,
        "normal_range": "36.0-37.8 °C",
    },
    VitalSignType.OXYGEN_SATURATION: {
        "unit": "%",
        "low_critical": 88, "low_warning": 92,
        "high_warning": 101, "high_critical": 101,
        "normal_range": "92-100%",
    },
    VitalSignType.RESPIRATORY_RATE: {
        "unit": "irpm",
        "low_critical": 8, "low_warning": 12,
        "high_warning": 20, "high_critical": 30,
        "normal_range": "12-20 irpm",
    },
    VitalSignType.BLOOD_GLUCOSE: {
        "unit": "mg/dL",
        "low_critical": 54, "low_warning": 70,
        "high_warning": 180, "high_critical": 300,
        "normal_range": "70-180 mg/dL",
    },
}


class VitalSignsMonitor:
    """
    Monitor de sinais vitais do paciente.
    Coleta, analisa e gera alertas baseados em leituras de sinais vitais.
    """

    def __init__(self, history_size: int = 1000):
        self.readings: Dict[str, Deque[VitalSignReading]] = {}
        self.alerts: List[VitalSignAlert] = []
        self.history_size = history_size
        logger.info("VitalSignsMonitor inicializado")

    def record_reading(
        self,
        patient_id: str,
        vital_type: VitalSignType,
        value: float,
        device: DeviceType = DeviceType.MANUAL,
        device_id: str = "",
        notes: str = "",
    ) -> Tuple[VitalSignReading, List[VitalSignAlert]]:
        """
        Registra leitura de sinal vital e verifica alertas.

        Returns:
            Tupla (leitura, alertas gerados)
        """
        ranges = VITAL_SIGN_RANGES.get(vital_type, {})
        reading = VitalSignReading(
            patient_id=patient_id,
            type=vital_type,
            value=value,
            unit=ranges.get("unit", ""),
            device=device,
            device_id=device_id,
            notes=notes,
        )

        # Armazenar
        if patient_id not in self.readings:
            self.readings[patient_id] = deque(maxlen=self.history_size)
        self.readings[patient_id].append(reading)

        # Verificar alertas
        new_alerts = self._check_alerts(patient_id, reading, ranges)
        self.alerts.extend(new_alerts)

        if new_alerts:
            for a in new_alerts:
                logger.warning(f"ALERTA VITAL: {a.message}")

        return reading, new_alerts

    def _check_alerts(
        self,
        patient_id: str,
        reading: VitalSignReading,
        ranges: Dict,
    ) -> List[VitalSignAlert]:
        """Verifica se leitura está fora dos limites"""
        alerts = []

        if not ranges:
            return alerts

        val = reading.value

        # Crítico baixo
        if val < ranges.get("low_critical", float("-inf")):
            alerts.append(VitalSignAlert(
                type="low_critical",
                severity="critical",
                vital_sign=reading.type,
                value=val,
                threshold=ranges["low_critical"],
                message=(
                    f"CRÍTICO: {reading.type.value} = {val} {reading.unit} "
                    f"(limite crítico baixo: {ranges['low_critical']})"
                ),
                patient_id=patient_id,
                action_required="Avaliação médica IMEDIATA necessária",
            ))
        elif val < ranges.get("low_warning", float("-inf")):
            alerts.append(VitalSignAlert(
                type="low_warning",
                severity="warning",
                vital_sign=reading.type,
                value=val,
                threshold=ranges["low_warning"],
                message=(
                    f"ATENÇÃO: {reading.type.value} = {val} {reading.unit} "
                    f"(abaixo do normal: {ranges['normal_range']})"
                ),
                patient_id=patient_id,
                action_required="Monitorar e avaliar em até 4 horas",
            ))

        # Crítico alto
        if val > ranges.get("high_critical", float("inf")):
            alerts.append(VitalSignAlert(
                type="high_critical",
                severity="critical",
                vital_sign=reading.type,
                value=val,
                threshold=ranges["high_critical"],
                message=(
                    f"CRÍTICO: {reading.type.value} = {val} {reading.unit} "
                    f"(limite crítico alto: {ranges['high_critical']})"
                ),
                patient_id=patient_id,
                action_required="Avaliação médica IMEDIATA necessária",
            ))
        elif val > ranges.get("high_warning", float("inf")):
            alerts.append(VitalSignAlert(
                type="high_warning",
                severity="warning",
                vital_sign=reading.type,
                value=val,
                threshold=ranges["high_warning"],
                message=(
                    f"ATENÇÃO: {reading.type.value} = {val} {reading.unit} "
                    f"(acima do normal: {ranges['normal_range']})"
                ),
                patient_id=patient_id,
                action_required="Monitorar e avaliar em até 4 horas",
            ))

        # Alertas de tendência (deterioração)
        trend_alert = self._check_trend(patient_id, reading)
        if trend_alert:
            alerts.append(trend_alert)

        return alerts

    def _check_trend(self, patient_id: str, reading: VitalSignReading) -> Optional[VitalSignAlert]:
        """Detecta tendência de deterioração (3 leituras consecutivas piorando)"""
        history = [
            r for r in self.readings.get(patient_id, [])
            if r.type == reading.type
        ]

        if len(history) < 3:
            return None

        last3 = list(history)[-3:]
        values = [r.value for r in last3]

        # Tendência de subida contínua (para tipo que sobe = ruim)
        rising = all(values[i] < values[i + 1] for i in range(len(values) - 1))
        falling = all(values[i] > values[i + 1] for i in range(len(values) - 1))

        ranges = VITAL_SIGN_RANGES.get(reading.type, {})

        if rising and reading.value > ranges.get("high_warning", float("inf")) * 0.9:
            return VitalSignAlert(
                type="trend_rising",
                severity="warning",
                vital_sign=reading.type,
                value=reading.value,
                threshold=0,
                message=(
                    f"TENDÊNCIA: {reading.type.value} subindo continuamente "
                    f"({values[0]} → {values[1]} → {values[2]}) — monitorar"
                ),
                patient_id=patient_id,
                action_required="Aumentar frequência de monitoramento",
            )

        if falling and reading.value < ranges.get("low_warning", float("-inf")) * 1.1:
            return VitalSignAlert(
                type="trend_falling",
                severity="warning",
                vital_sign=reading.type,
                value=reading.value,
                threshold=0,
                message=(
                    f"TENDÊNCIA: {reading.type.value} caindo continuamente "
                    f"({values[0]} → {values[1]} → {values[2]}) — monitorar"
                ),
                patient_id=patient_id,
                action_required="Aumentar frequência de monitoramento",
            )

        return None

    def get_patient_vitals(
        self,
        patient_id: str,
        vital_type: Optional[VitalSignType] = None,
        hours: int = 24,
    ) -> List[Dict]:
        """Obtém histórico de sinais vitais do paciente"""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        readings = self.readings.get(patient_id, [])

        results = []
        for r in readings:
            if r.timestamp < cutoff:
                continue
            if vital_type and r.type != vital_type:
                continue
            results.append(r.to_dict())

        return results

    def get_latest_vitals(self, patient_id: str) -> Dict[str, Dict]:
        """Obtém últimas leituras de cada tipo de sinal vital"""
        latest = {}
        for r in reversed(list(self.readings.get(patient_id, []))):
            key = r.type.value
            if key not in latest:
                latest[key] = r.to_dict()
                ranges = VITAL_SIGN_RANGES.get(r.type, {})
                latest[key]["normal_range"] = ranges.get("normal_range", "")
                latest[key]["status"] = self._classify_reading(r, ranges)

            if len(latest) == len(VitalSignType):
                break

        return latest

    def _classify_reading(self, reading: VitalSignReading, ranges: Dict) -> str:
        """Classifica se leitura está normal, atenção ou crítica"""
        if not ranges:
            return "unknown"

        v = reading.value
        if v < ranges.get("low_critical", float("-inf")) or v > ranges.get("high_critical", float("inf")):
            return "critical"
        if v < ranges.get("low_warning", float("-inf")) or v > ranges.get("high_warning", float("inf")):
            return "warning"
        return "normal"

    def generate_vitals_report(self, patient_id: str, days: int = 7) -> Dict:
        """Gera relatório de sinais vitais do paciente"""
        readings = self.readings.get(patient_id, [])
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        recent = [r for r in readings if r.timestamp >= cutoff]

        # Agrupar por tipo
        by_type: Dict[str, List[float]] = {}
        for r in recent:
            key = r.type.value
            if key not in by_type:
                by_type[key] = []
            by_type[key].append(r.value)

        # Estatísticas
        stats = {}
        for vtype, values in by_type.items():
            stats[vtype] = {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "mean": sum(values) / len(values),
                "latest": values[-1],
            }

        # Alertas do período
        period_alerts = [
            {
                "severity": a.severity,
                "vital_sign": a.vital_sign.value,
                "value": a.value,
                "message": a.message,
                "timestamp": a.timestamp,
            }
            for a in self.alerts
            if a.patient_id == patient_id and a.timestamp >= cutoff
        ]

        return {
            "patient_id": patient_id,
            "period_days": days,
            "total_readings": len(recent),
            "statistics": stats,
            "alerts_count": len(period_alerts),
            "alerts": period_alerts,
            "latest_vitals": self.get_latest_vitals(patient_id),
            "generated_at": datetime.now().isoformat(),
        }


class WearableIntegration:
    """
    Integração com dispositivos vestíveis e sensores.
    Suporta múltiplos protocolos e dispositivos.
    """

    # Dispositivos suportados
    SUPPORTED_DEVICES = {
        "generic_ble_hr": {
            "name": "Monitor cardíaco BLE genérico",
            "type": DeviceType.SMARTWATCH,
            "vitals": [VitalSignType.HEART_RATE],
            "protocol": "BLE",
        },
        "generic_ble_bp": {
            "name": "Esfigmomanômetro BLE",
            "type": DeviceType.BLUETOOTH_BP,
            "vitals": [VitalSignType.BLOOD_PRESSURE_SYS, VitalSignType.BLOOD_PRESSURE_DIA, VitalSignType.HEART_RATE],
            "protocol": "BLE",
        },
        "generic_pulse_ox": {
            "name": "Oxímetro de pulso BLE",
            "type": DeviceType.PULSE_OXIMETER,
            "vitals": [VitalSignType.OXYGEN_SATURATION, VitalSignType.HEART_RATE],
            "protocol": "BLE",
        },
        "generic_glucose": {
            "name": "Glicosímetro BLE",
            "type": DeviceType.GLUCOSE_METER,
            "vitals": [VitalSignType.BLOOD_GLUCOSE],
            "protocol": "BLE",
        },
        "generic_scale": {
            "name": "Balança inteligente",
            "type": DeviceType.SMART_SCALE,
            "vitals": [VitalSignType.WEIGHT],
            "protocol": "BLE",
        },
        "ambient_sensor": {
            "name": "Sensor ambiental (temperatura/umidade)",
            "type": DeviceType.AMBIENT_SENSOR,
            "vitals": [],
            "protocol": "MQTT",
        },
    }

    def __init__(self, vital_monitor: VitalSignsMonitor):
        self.monitor = vital_monitor
        self.paired_devices: Dict[str, List[str]] = {}  # patient_id → [device_ids]
        logger.info("WearableIntegration inicializado")

    def list_supported_devices(self) -> List[Dict]:
        """Lista dispositivos suportados"""
        return [
            {"id": did, **info}
            for did, info in self.SUPPORTED_DEVICES.items()
        ]

    def pair_device(self, patient_id: str, device_id: str, device_type: str) -> bool:
        """Emparelha dispositivo com paciente"""
        if patient_id not in self.paired_devices:
            self.paired_devices[patient_id] = []
        self.paired_devices[patient_id].append(device_id)
        logger.info(f"Dispositivo {device_id} ({device_type}) pareado com paciente {patient_id}")
        return True

    def process_device_data(
        self,
        patient_id: str,
        device_id: str,
        data: Dict[str, float],
    ) -> List[VitalSignAlert]:
        """
        Processa dados recebidos de um dispositivo.

        Args:
            patient_id: ID do paciente
            device_id: ID do dispositivo
            data: Dict com tipo_sinal → valor

        Returns:
            Lista de alertas gerados
        """
        all_alerts = []

        type_mapping = {
            "heart_rate": VitalSignType.HEART_RATE,
            "systolic": VitalSignType.BLOOD_PRESSURE_SYS,
            "diastolic": VitalSignType.BLOOD_PRESSURE_DIA,
            "temperature": VitalSignType.TEMPERATURE,
            "spo2": VitalSignType.OXYGEN_SATURATION,
            "respiratory_rate": VitalSignType.RESPIRATORY_RATE,
            "glucose": VitalSignType.BLOOD_GLUCOSE,
            "weight": VitalSignType.WEIGHT,
        }

        for key, value in data.items():
            vital_type = type_mapping.get(key)
            if vital_type:
                _, alerts = self.monitor.record_reading(
                    patient_id=patient_id,
                    vital_type=vital_type,
                    value=value,
                    device=DeviceType.SMARTWATCH,
                    device_id=device_id,
                )
                all_alerts.extend(alerts)

        return all_alerts

    def get_patient_devices(self, patient_id: str) -> List[str]:
        """Lista dispositivos pareados com paciente"""
        return self.paired_devices.get(patient_id, [])
