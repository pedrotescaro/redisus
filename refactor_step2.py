import re

with open("heal_analyzer.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Insert ModelPrediction and AIPredictions before ClinicalReport
dataclass_str = """
@dataclass
class ModelPrediction:
    class_name: str
    display_name: str
    confidence: float
    top3: List[Dict[str, float]] = field(default_factory=list)
    probabilities: Dict[str, float] = field(default_factory=dict)

@dataclass
class AIPredictions:
    dl: Optional[ModelPrediction] = None
    resnet: Optional[Dict] = None
    ensemble: Optional[Dict] = None

@dataclass
class ClinicalReport:
"""
text = text.replace("@dataclass\nclass ClinicalReport:", dataclass_str)

# 2. Update ClinicalReport fields
old_report_fields = """    # Deep Learning prediction (quando disponível)
    dl_prediction: Optional[Dict] = None

    # Classificação ResNet50 dois estágios (Normal/Ferida + Tipo)
    resnet_prediction: Optional[Dict] = None
    grad_cam_overlay: Optional[np.ndarray] = None

    # Escalas clínicas (PUSH, BWAT) - calculadas automaticamente
    push_score: Optional[Dict] = None
    bwat_score: Optional[Dict] = None

    # Análise de iluminação (quando disponível)
    lighting_analysis: Optional[Dict] = None
    image_corrections: Optional[Dict] = None
    
    # Detecção de parte do corpo (quando disponível)
    body_part: Optional[Dict] = None

    # Zonas espaciais da ferida (periferia, core, anel externo)
    wound_zones: Optional[Dict] = None

    # Ensemble Multi-Modelo (camada adicional de IA pré-treinada)
    ensemble_classification: Optional[Dict] = None
    ensemble_agreement: Optional[Dict] = None
    ensemble_infection: Optional[Dict] = None
    ensemble_severity: Optional[float] = None
    ensemble_models_loaded: Optional[Dict] = None"""

new_report_fields = """    # Classificação ResNet50 Grad-CAM (se disponível)
    grad_cam_overlay: Optional[np.ndarray] = None

    # Escalas clínicas (PUSH, BWAT)
    push_score: Optional[Dict] = None
    bwat_score: Optional[Dict] = None

    # Imagens processadas e análises adicionais
    lighting_analysis: Optional[Dict] = None
    image_corrections: Optional[Dict] = None
    body_part: Optional[Dict] = None
    wound_zones: Optional[Dict] = None

    # Agrupamento de predições de IA
    ai_predictions: Optional[AIPredictions] = None"""

text = text.replace(old_report_fields, new_report_fields)

# 3. Update _predict_dl signature and return
old_dl_def = """    def _predict_dl(self, image: np.ndarray) -> Optional[Dict]:"""
new_dl_def = """    def _predict_dl(self, image: np.ndarray) -> Optional[ModelPrediction]:"""
text = text.replace(old_dl_def, new_dl_def)

old_dl_return = """            return {
                "class_name": class_name,
                "display_name": display_name,
                "confidence": confidence,
                "top3": top3,
                "all_probs": {class_names[i]: float(avg_pred[i]) for i in range(len(class_names)) if i < len(avg_pred)},
            }"""
new_dl_return = """            probabilities = {class_names[i]: float(avg_pred[i]) for i in range(len(class_names)) if i < len(avg_pred)}
            return ModelPrediction(
                class_name=class_name,
                display_name=display_name,
                confidence=confidence,
                top3=top3,
                probabilities=probabilities,
            )"""
text = text.replace(old_dl_return, new_dl_return)

# 4. Add _safe_load wrapper
safe_load_str = """    def _safe_load(self, name: str, loader):
        try:
            result = loader()
            if result:
                logger.info(f"[HEAL+] {name} carregado com sucesso")
            return result, True
        except Exception as e:
            logger.exception(f"[HEAL+] Falha ao carregar {name}: {e}")
            return None, False

    def _load_resnet_classifier(self):"""
text = text.replace("    def _load_resnet_classifier(self):", safe_load_str)

# 5. Update _fill_ai_predictions to use ai_predictions
old_fill = """    def _fill_ai_predictions(self, report: ClinicalReport, image: np.ndarray, detections: list, wound_mask: np.ndarray):
        dl_result = self._predict_dl(image)
        if dl_result:
            report.dl_prediction = dl_result

        resnet_result = self._predict_resnet(image)
        if resnet_result:
            report.resnet_prediction = resnet_result
            if isinstance(resnet_result, dict) and resnet_result.get('grad_cam_overlay') is not None:
                report.grad_cam_overlay = resnet_result.pop('grad_cam_overlay')

        dl_probs = None
        if dl_result and "all_probs" in dl_result:
            dl_probs = dl_result["all_probs"]
            
        ensemble_result = self._predict_ensemble(
            image, detections, dl_probs=dl_probs, wound_mask=wound_mask,
        )
        if ensemble_result:
            ens = ensemble_result.get("ensemble", {})
            report.ensemble_classification = ens.get("classification")
            report.ensemble_agreement = ens.get("agreement")
            report.ensemble_infection = ensemble_result.get("infection")
            report.ensemble_severity = ensemble_result.get("severity")
            report.ensemble_models_loaded = ens.get("models_loaded")"""

new_fill = """    def _fill_ai_predictions(self, report: ClinicalReport, image: np.ndarray, detections: list, wound_mask: np.ndarray):
        ai_preds = AIPredictions()
        
        dl_result = self._predict_dl(image)
        if dl_result:
            ai_preds.dl = dl_result

        resnet_result = self._predict_resnet(image)
        if resnet_result:
            ai_preds.resnet = resnet_result
            if isinstance(resnet_result, dict) and resnet_result.get('grad_cam_overlay') is not None:
                report.grad_cam_overlay = resnet_result.pop('grad_cam_overlay')

        dl_probs = None
        if dl_result and hasattr(dl_result, 'probabilities'):
            dl_probs = dl_result.probabilities
            
        ensemble_result = self._predict_ensemble(
            image, detections, dl_probs=dl_probs, wound_mask=wound_mask,
        )
        if ensemble_result:
            ai_preds.ensemble = ensemble_result
            
        report.ai_predictions = ai_preds"""

text = text.replace(old_fill, new_fill)

with open("heal_analyzer.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Step 2 replacements done.")
