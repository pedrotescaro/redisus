import re

with open("heal_analyzer.py", "r", encoding="utf-8") as f:
    text = f.read()

analyze_block_pattern = re.compile(
    r'(    def analyze\(self, image: np\.ndarray\) -> ClinicalReport:.*?        report\.processing_time_ms = \(time\.perf_counter\(\) - t0\) \* 1000\n        return report\n)',
    re.DOTALL
)

new_analyze_methods = """    def _prepare_input(self, image: np.ndarray, report: ClinicalReport) -> np.ndarray:
        h, w = image.shape[:2]
        if max(h, w) > 1024:
            scale = 1024 / max(h, w)
            image = cv2.resize(image, (int(w * scale), int(h * scale)))

        if self.image_enhancer is not None:
            try:
                lighting = self.image_enhancer.analyze_lighting(image)
                report.lighting_analysis = lighting.to_dict()
                if lighting.corrections_needed:
                    image, corrections = self.image_enhancer.auto_correct(image, lighting)
                    report.image_corrections = corrections
            except Exception as e:
                logger.exception(f"[HEAL+] Erro análise de iluminação: {e}")

        if self.body_detector is not None:
            try:
                body_part = self.body_detector.detect(image)
                report.body_part = body_part.to_dict()
            except Exception as e:
                logger.exception(f"[HEAL+] Erro detecção parte do corpo: {e}")

        return image

    def _detect_wound_region(self, image: np.ndarray):
        detections = self.detector.detect(image)

        wound_mask = self._create_wound_roi_mask(image, detections)
        wound_mask = self._exclude_surgical_background(image, wound_mask)

        background_mask = self._create_background_mask_spatial(image, wound_mask)
        wound_mask_clean = cv2.bitwise_and(wound_mask, cv2.bitwise_not(background_mask))

        if np.sum(wound_mask > 0) > 0:
            cleaned_ratio = np.sum(wound_mask_clean > 0) / np.sum(wound_mask > 0)
            if cleaned_ratio > 0.05:
                wound_mask = wound_mask_clean

        return detections, wound_mask

    def _fill_ai_predictions(self, report: ClinicalReport, image: np.ndarray, detections: list, wound_mask: np.ndarray):
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
            report.ensemble_models_loaded = ens.get("models_loaded")

    def analyze(self, image: np.ndarray) -> ClinicalReport:
        \"\"\"Pipeline completo de análise clínica.\"\"\"
        t0 = time.perf_counter()
        report = ClinicalReport(is_valid_wound=True)
        report.original = image.copy()

        try:
            image = self._prepare_input(image, report)

            if not self._validate_wound_image(image):
                report.is_valid_wound = False
                report.rejection_reason = (
                    "Input Inválido — A imagem fornecida não apresenta características "
                    "compatíveis com ferida cutânea humana."
                )
                return report

            detections, wound_mask = self._detect_wound_region(image)
            report.wound_area_px = int(np.sum(wound_mask > 0))

            peripheral_zone, core_zone, outer_ring = self._create_zone_masks(wound_mask)
            report.wound_zones = {
                "peripheral_area_px": int(np.sum(peripheral_zone > 0)),
                "core_area_px": int(np.sum(core_zone > 0)),
                "outer_ring_area_px": int(np.sum(outer_ring > 0)),
                "border_width_adaptive": True,
            }

            det_overlay = image.copy()
            for det in detections:
                x1, y1, x2, y2 = det.bbox
                cv2.rectangle(det_overlay, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(det_overlay,
                            f"Ferida {det.confidence:.0%}",
                            (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
            report.detection_overlay = det_overlay

            tissue_pcts, seg_map, tissue_overlay = self._segment_clinical_v3(
                image, wound_mask, peripheral_zone, core_zone, outer_ring
            )
            report.segmentation_map = seg_map
            report.tissue_overlay = tissue_overlay

            for key in ["necrosis", "slough", "granulation", "epithelialization"]:
                pct = tissue_pcts.get(key, 0.0)
                info = CLINICAL_TISSUES[key]
                report.tissues.append(TissueClassification(
                    name=info["name"], name_en=info["name_en"], percentage=pct,
                    color_bgr=info["color_bgr"], color_hex=info["color_hex"],
                    description=info["description"], clinical_action=info["clinical_action"],
                ))

            dominant = max(report.tissues, key=lambda t: t.percentage)
            report.primary_tissue = dominant.name
            report.primary_justification = self._build_justification(dominant, tissue_pcts)

            report.border_analysis = self._analyze_borders(image, wound_mask)
            report.health_score = self._compute_health_score(tissue_pcts)

            if HAS_CLINICAL_SCALES:
                try:
                    border_dict = None
                    if report.border_analysis:
                        border_dict = {
                            "maceration": report.border_analysis.maceration,
                            "inflammation": report.border_analysis.inflammation,
                            "regular_borders": report.border_analysis.regular_borders,
                        }
                    
                    push = ScaleCalculator.calculate_push_from_analysis(
                        tissue_percentages=tissue_pcts, wound_area_px=report.wound_area_px
                    )
                    report.push_score = push.to_dict()
                    
                    bwat = ScaleCalculator.calculate_bwat_from_analysis(
                        tissue_percentages=tissue_pcts, wound_area_px=report.wound_area_px,
                        border_analysis=border_dict
                    )
                    report.bwat_score = bwat.to_dict()
                except Exception as e:
                    logger.exception(f"[HEAL+] Erro ao calcular escalas clínicas: {e}")

            self._fill_ai_predictions(report, image, detections, wound_mask)

            return report

        except Exception as e:
            logger.exception(f"[HEAL+] Erro no pipeline principal: {e}")
            report.is_valid_wound = False
            report.rejection_reason = "Erro interno durante a análise."
            return report

        finally:
            report.processing_time_ms = (time.perf_counter() - t0) * 1000
"""

if not analyze_block_pattern.search(text):
    print("Could not find the analyze() block!")
else:
    text = analyze_block_pattern.sub(new_analyze_methods, text)
    with open("heal_analyzer.py", "w", encoding="utf-8") as f:
        f.write(text)
    print("Analyze block successfully replaced.")
