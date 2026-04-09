import re

with open("heal_analyzer.py", "r", encoding="utf-8") as f:
    text = f.read()

properties_str = """    tissue_overlay: Optional[np.ndarray] = None

    @property
    def dl_prediction(self):
        return self.ai_predictions.dl.__dict__ if self.ai_predictions and self.ai_predictions.dl else None

    @property
    def resnet_prediction(self):
        return self.ai_predictions.resnet if self.ai_predictions else None

    @property
    def ensemble_classification(self):
        return self.ai_predictions.ensemble.get("classification") if self.ai_predictions and self.ai_predictions.ensemble else None

    @property
    def ensemble_agreement(self):
        return self.ai_predictions.ensemble.get("agreement") if self.ai_predictions and self.ai_predictions.ensemble else None

    @property
    def ensemble_infection(self):
        return self.ai_predictions.ensemble.get("infection") if self.ai_predictions and self.ai_predictions.ensemble else None

    @property
    def ensemble_severity(self):
        return self.ai_predictions.ensemble.get("severity") if self.ai_predictions and self.ai_predictions.ensemble else None

    @property
    def ensemble_models_loaded(self):
        return self.ai_predictions.ensemble.get("models_loaded") if self.ai_predictions and self.ai_predictions.ensemble else None
"""

text = text.replace("    tissue_overlay: Optional[np.ndarray] = None\n", properties_str)

with open("heal_analyzer.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Properties injected.")
