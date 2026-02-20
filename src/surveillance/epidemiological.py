"""
HEAL/REDISUS - Vigilância Epidemiológica Digital
Monitoramento, georreferenciamento e detecção de surtos.

Implementa:
- Georreferenciamento de casos (latitude/longitude, bairro, município)
- Mapeamento de incidência/prevalência por região
- Detecção automatizada de surtos (clustering espaço-temporal)
- Geração de mapas de calor epidemiológicos
- Integração com secretarias municipais/estaduais de saúde
- Vigilância de doenças negligenciadas (ex: esporotricose)
- Alertas de saúde pública
"""
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


@dataclass
class GeoCase:
    """Caso georreferenciado para vigilância"""
    case_id: str
    patient_id: str
    condition: str  # tipo de condição/doença
    latitude: float
    longitude: float
    city: str = ""
    state: str = ""
    neighborhood: str = ""
    municipality_code: str = ""  # Código IBGE
    date_reported: str = field(default_factory=lambda: datetime.now().isoformat()[:10])
    date_onset: str = ""
    severity: str = "moderado"
    confirmed: bool = False
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "case_id": self.case_id,
            "patient_id": self.patient_id,
            "condition": self.condition,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "city": self.city,
            "state": self.state,
            "neighborhood": self.neighborhood,
            "municipality_code": self.municipality_code,
            "date_reported": self.date_reported,
            "date_onset": self.date_onset,
            "severity": self.severity,
            "confirmed": self.confirmed,
            "metadata": self.metadata,
        }


@dataclass
class OutbreakAlert:
    """Alerta de surto epidemiológico"""
    alert_id: str
    condition: str
    region: str
    severity: str  # baixo, moderado, alto, critico
    case_count: int
    expected_count: float
    ratio: float  # observado/esperado
    period: str
    message: str
    coordinates: List[Tuple[float, float]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    acknowledged: bool = False


@dataclass
class EpiIndicator:
    """Indicador epidemiológico"""
    name: str
    value: float
    unit: str
    region: str
    period: str
    condition: str
    type: str  # incidencia, prevalencia, mortalidade, letalidade


class GeoSurveillance:
    """
    Sistema de georreferenciamento e vigilância digital.
    Monitora distribuição geográfica de casos e detecta surtos.
    """

    def __init__(self):
        self.cases: List[GeoCase] = []
        self.alerts: List[OutbreakAlert] = []
        self._baseline_rates: Dict[str, float] = {}
        logger.info("GeoSurveillance inicializado")

    def register_case(self, case: GeoCase) -> str:
        """Registra um novo caso georreferenciado"""
        self.cases.append(case)
        logger.info(
            f"Caso registrado: {case.condition} em "
            f"{case.city}/{case.state} ({case.latitude:.4f}, {case.longitude:.4f})"
        )
        # Verificar alertas após novo caso
        self._check_outbreak_thresholds(case.condition, case.city)
        return case.case_id

    def register_case_from_analysis(
        self,
        patient_id: str,
        wound_data: Dict,
        location: Dict,
    ) -> str:
        """
        Registra caso a partir de uma análise HEAL.

        Args:
            patient_id: ID do paciente
            wound_data: Dados da análise (etiology, risk_level, etc.)
            location: Dict com latitude, longitude, city, state, etc.
        """
        import uuid
        case = GeoCase(
            case_id=str(uuid.uuid4()),
            patient_id=patient_id,
            condition=wound_data.get("etiology", "wound_unspecified"),
            latitude=location.get("latitude", 0.0),
            longitude=location.get("longitude", 0.0),
            city=location.get("city", ""),
            state=location.get("state", ""),
            neighborhood=location.get("neighborhood", ""),
            municipality_code=location.get("ibge_code", ""),
            severity=wound_data.get("risk_level", "moderado"),
            confirmed=wound_data.get("confidence", 0) > 0.7,
            metadata={
                "etiology": wound_data.get("etiology", ""),
                "area_cm2": wound_data.get("area_cm2", 0),
                "health_score": wound_data.get("health_score", 0),
                "risk_score": wound_data.get("risk_score", 0),
            },
        )
        return self.register_case(case)

    def get_cases_by_region(
        self,
        city: Optional[str] = None,
        state: Optional[str] = None,
        condition: Optional[str] = None,
        period_days: int = 30,
    ) -> List[GeoCase]:
        """Filtra casos por região, condição e período"""
        cutoff = (datetime.now() - timedelta(days=period_days)).isoformat()[:10]
        results = []
        for c in self.cases:
            if city and c.city.lower() != city.lower():
                continue
            if state and c.state.lower() != state.lower():
                continue
            if condition and c.condition != condition:
                continue
            if c.date_reported < cutoff:
                continue
            results.append(c)
        return results

    def get_cases_in_radius(
        self,
        center_lat: float,
        center_lon: float,
        radius_km: float,
        condition: Optional[str] = None,
    ) -> List[GeoCase]:
        """Busca casos dentro de um raio geográfico"""
        results = []
        for c in self.cases:
            dist = self._haversine(center_lat, center_lon, c.latitude, c.longitude)
            if dist <= radius_km:
                if condition is None or c.condition == condition:
                    results.append(c)
        return results

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcula distância entre dois pontos em km (fórmula de Haversine)"""
        R = 6371.0  # Raio da Terra em km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    # -------------------------------------------------------------------------
    # Detecção de surtos
    # -------------------------------------------------------------------------
    def set_baseline_rate(self, condition: str, region: str, rate_per_month: float):
        """Define taxa baseline esperada para uma condição/região"""
        key = f"{condition}:{region}"
        self._baseline_rates[key] = rate_per_month

    def _check_outbreak_thresholds(self, condition: str, city: str):
        """Verifica se há indicativo de surto"""
        key = f"{condition}:{city}"
        baseline = self._baseline_rates.get(key, 5.0)  # Default: 5 casos/mês

        # Contar casos recentes (últimos 30 dias)
        recent = self.get_cases_by_region(city=city, condition=condition, period_days=30)
        count = len(recent)

        if count > 0 and baseline > 0:
            ratio = count / baseline
            if ratio >= 2.0:  # Dobro do esperado
                severity = "critico" if ratio >= 4.0 else "alto" if ratio >= 3.0 else "moderado"
                import uuid
                alert = OutbreakAlert(
                    alert_id=str(uuid.uuid4()),
                    condition=condition,
                    region=city,
                    severity=severity,
                    case_count=count,
                    expected_count=baseline,
                    ratio=ratio,
                    period="últimos 30 dias",
                    message=(
                        f"ALERTA DE SURTO: {count} casos de {condition} em {city} "
                        f"({ratio:.1f}x acima do esperado) nos últimos 30 dias"
                    ),
                    coordinates=[(c.latitude, c.longitude) for c in recent],
                )
                self.alerts.append(alert)
                logger.warning(alert.message)

    def detect_clusters(
        self,
        condition: Optional[str] = None,
        radius_km: float = 5.0,
        min_cases: int = 3,
        period_days: int = 30,
    ) -> List[Dict]:
        """
        Detecta clusters espaciais de casos.
        Algoritmo simples de density-based clustering.

        Args:
            condition: Filtrar por condição (None = todas)
            radius_km: Raio para considerar proximidade
            min_cases: Mínimo de casos para formar cluster
            period_days: Período de análise em dias

        Returns:
            Lista de clusters detectados
        """
        cases = self.get_cases_by_region(condition=condition, period_days=period_days)
        if len(cases) < min_cases:
            return []

        clusters = []
        visited = set()

        for i, case in enumerate(cases):
            if i in visited:
                continue

            # Buscar vizinhos
            neighbors = []
            for j, other in enumerate(cases):
                if j == i:
                    continue
                dist = self._haversine(
                    case.latitude, case.longitude,
                    other.latitude, other.longitude,
                )
                if dist <= radius_km:
                    neighbors.append(j)

            if len(neighbors) + 1 >= min_cases:
                cluster_cases = [case] + [cases[j] for j in neighbors]
                visited.add(i)
                visited.update(neighbors)

                # Centro do cluster
                avg_lat = sum(c.latitude for c in cluster_cases) / len(cluster_cases)
                avg_lon = sum(c.longitude for c in cluster_cases) / len(cluster_cases)

                clusters.append({
                    "center": (avg_lat, avg_lon),
                    "cases_count": len(cluster_cases),
                    "radius_km": radius_km,
                    "conditions": list(set(c.condition for c in cluster_cases)),
                    "cities": list(set(c.city for c in cluster_cases)),
                    "severities": {
                        s: sum(1 for c in cluster_cases if c.severity == s)
                        for s in ("baixo", "moderado", "alto", "critico")
                    },
                    "period": f"últimos {period_days} dias",
                })

        logger.info(f"Detectados {len(clusters)} clusters de casos")
        return clusters

    # -------------------------------------------------------------------------
    # Indicadores epidemiológicos
    # -------------------------------------------------------------------------
    def calculate_epidemiological_indicators(
        self,
        region: str,
        population: int,
        period_days: int = 30,
    ) -> List[EpiIndicator]:
        """
        Calcula indicadores epidemiológicos para uma região.

        Args:
            region: Nome da região/cidade
            population: População da região
            period_days: Período de análise

        Returns:
            Lista de indicadores epidemiológicos
        """
        cases = self.get_cases_by_region(city=region, period_days=period_days)
        period = f"últimos {period_days} dias"
        indicators = []

        if population <= 0:
            return indicators

        # Agrupar por condição
        condition_counts: Dict[str, int] = defaultdict(int)
        for c in cases:
            condition_counts[c.condition] += 1

        # Incidência por condição (por 100.000 hab)
        for cond, count in condition_counts.items():
            rate = (count / population) * 100_000
            indicators.append(EpiIndicator(
                name=f"Incidência de {cond}",
                value=round(rate, 2),
                unit="por 100.000 hab",
                region=region,
                period=period,
                condition=cond,
                type="incidencia",
            ))

        # Incidência total
        total_rate = (len(cases) / population) * 100_000
        indicators.append(EpiIndicator(
            name="Incidência total de feridas",
            value=round(total_rate, 2),
            unit="por 100.000 hab",
            region=region,
            period=period,
            condition="todas",
            type="incidencia",
        ))

        # Distribuição por gravidade
        for severity in ("baixo", "moderado", "alto", "critico"):
            count = sum(1 for c in cases if c.severity == severity)
            if count > 0:
                indicators.append(EpiIndicator(
                    name=f"Casos {severity}",
                    value=count,
                    unit="casos",
                    region=region,
                    period=period,
                    condition="todas",
                    type="prevalencia",
                ))

        return indicators

    # -------------------------------------------------------------------------
    # Geração de heatmap (dados para visualização)
    # -------------------------------------------------------------------------
    def generate_heatmap_data(
        self,
        condition: Optional[str] = None,
        period_days: int = 30,
        grid_size: float = 0.01,  # ~1km
    ) -> Dict:
        """
        Gera dados para mapa de calor epidemiológico.

        Returns:
            Dict com grid de intensidade para visualização
        """
        cases = self.get_cases_by_region(condition=condition, period_days=period_days)
        if not cases:
            return {"points": [], "bounds": None}

        points = []
        for c in cases:
            weight = {"baixo": 1, "moderado": 2, "alto": 3, "critico": 4}.get(c.severity, 1)
            points.append({
                "lat": c.latitude,
                "lng": c.longitude,
                "weight": weight,
                "condition": c.condition,
            })

        # Calcular limites
        lats = [p["lat"] for p in points]
        lngs = [p["lng"] for p in points]

        return {
            "points": points,
            "bounds": {
                "north": max(lats),
                "south": min(lats),
                "east": max(lngs),
                "west": min(lngs),
            },
            "total_cases": len(points),
            "period_days": period_days,
            "condition_filter": condition,
        }

    # -------------------------------------------------------------------------
    # Relatórios
    # -------------------------------------------------------------------------
    def generate_surveillance_report(
        self,
        region: str,
        population: int = 0,
        period_days: int = 30,
    ) -> Dict:
        """Gera relatório completo de vigilância para uma região"""
        cases = self.get_cases_by_region(city=region, period_days=period_days)
        clusters = self.detect_clusters(radius_km=5.0, min_cases=3, period_days=period_days)
        active_alerts = [a for a in self.alerts if a.region == region and not a.acknowledged]

        indicators = []
        if population > 0:
            indicators = self.calculate_epidemiological_indicators(region, population, period_days)

        return {
            "region": region,
            "report_date": datetime.now().isoformat(),
            "period": f"últimos {period_days} dias",
            "total_cases": len(cases),
            "cases_by_condition": dict(defaultdict(
                int, **{c.condition: 0 for c in cases}
            )),
            "cases_by_severity": {
                s: sum(1 for c in cases if c.severity == s)
                for s in ("baixo", "moderado", "alto", "critico")
            },
            "clusters_detected": len(clusters),
            "clusters": clusters,
            "active_alerts": [
                {"severity": a.severity, "message": a.message}
                for a in active_alerts
            ],
            "indicators": [
                {"name": i.name, "value": i.value, "unit": i.unit, "type": i.type}
                for i in indicators
            ],
            "heatmap_data": self.generate_heatmap_data(period_days=period_days),
            "generated_by": "HEAL/REDISUS — Vigilância Digital",
        }

    def export_to_geojson(
        self,
        condition: Optional[str] = None,
        period_days: int = 30,
    ) -> Dict:
        """
        Exporta casos em formato GeoJSON para visualização em mapas.
        """
        cases = self.get_cases_by_region(condition=condition, period_days=period_days)

        features = []
        for c in cases:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [c.longitude, c.latitude],
                },
                "properties": {
                    "case_id": c.case_id,
                    "condition": c.condition,
                    "severity": c.severity,
                    "city": c.city,
                    "state": c.state,
                    "date_reported": c.date_reported,
                    "confirmed": c.confirmed,
                },
            })

        return {
            "type": "FeatureCollection",
            "features": features,
            "properties": {
                "total_cases": len(features),
                "generated_by": "HEAL/REDISUS",
                "generated_at": datetime.now().isoformat(),
            },
        }
