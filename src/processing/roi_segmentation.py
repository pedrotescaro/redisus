import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class ROISegmenter:
    """Segmentador de ROI e máscaras associadas para feridas."""

    @staticmethod
    def create_wound_roi_mask(image: np.ndarray, detections: list) -> np.ndarray:
        h, w = image.shape[:2]
        wound_mask = np.zeros((h, w), dtype=np.uint8)

        if not detections:
            wound_mask[:] = 255
            return wound_mask

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        for det in detections:
            x1, y1, x2, y2 = det.bbox if hasattr(det, 'bbox') else det.get('bbox', [0,0,w,h])
            margin_x = int((x2 - x1) * 0.05)
            margin_y = int((y2 - y1) * 0.05)
            rx1 = max(0, x1 - margin_x)
            ry1 = max(0, y1 - margin_y)
            rx2 = min(w, x2 + margin_x)
            ry2 = min(h, y2 + margin_y)

            roi_hsv = hsv[ry1:ry2, rx1:rx2]

            wound_colors = np.zeros(roi_hsv.shape[:2], dtype=np.uint8)
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(roi_hsv, np.array([0, 40, 40]), np.array([15, 255, 255])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(roi_hsv, np.array([155, 40, 40]), np.array([180, 255, 255])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(roi_hsv, np.array([12, 30, 100]), np.array([45, 255, 255])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(roi_hsv, np.array([0, 0, 0]), np.array([180, 255, 70])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(roi_hsv, np.array([0, 8, 160]), np.array([20, 80, 255])))
            wound_colors = cv2.bitwise_or(wound_colors, cv2.inRange(roi_hsv, np.array([150, 8, 160]), np.array([180, 80, 255])))

            bg_mask = np.zeros(roi_hsv.shape[:2], dtype=np.uint8)
            bg_mask = cv2.bitwise_or(bg_mask, cv2.inRange(roi_hsv, np.array([90, 30, 20]), np.array([130, 255, 255])))
            bg_mask = cv2.bitwise_or(bg_mask, cv2.inRange(roi_hsv, np.array([35, 30, 30]), np.array([85, 255, 255])))

            roi_mask = cv2.bitwise_and(wound_colors, cv2.bitwise_not(bg_mask))

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_OPEN, kernel, iterations=1)

            roi_filled = np.zeros_like(roi_mask)
            contours, _ = cv2.findContours(roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                min_contour_area = (rx2 - rx1) * (ry2 - ry1) * 0.02
                for cnt in contours:
                    if cv2.contourArea(cnt) >= min_contour_area:
                        cv2.drawContours(roi_filled, [cnt], -1, 255, cv2.FILLED)

            roi_area = np.sum(roi_filled > 0)
            bbox_area = (rx2 - rx1) * (ry2 - ry1)
            if roi_area < bbox_area * 0.10:
                wound_mask[y1:y2, x1:x2] = 255
            else:
                wound_mask[ry1:ry2, rx1:rx2] = cv2.bitwise_or(wound_mask[ry1:ry2, rx1:rx2], roi_filled)

        return wound_mask

    @staticmethod
    def exclude_surgical_background(image: np.ndarray, wound_mask: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        drape_mask = np.zeros(image.shape[:2], dtype=np.uint8)

        drape_mask = cv2.bitwise_or(drape_mask, cv2.inRange(hsv, np.array([90, 30, 20]), np.array([130, 255, 255])))
        drape_mask = cv2.bitwise_or(drape_mask, cv2.inRange(hsv, np.array([35, 30, 30]), np.array([85, 255, 255])))
        drape_mask = cv2.bitwise_or(drape_mask, cv2.inRange(hsv, np.array([0, 0, 40]), np.array([180, 25, 170])))

        drape_ratio = np.sum(drape_mask > 0) / max(drape_mask.size, 1)
        if drape_ratio < 0.05:
            return wound_mask

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        drape_mask = cv2.dilate(drape_mask, kernel, iterations=1)

        cleaned = cv2.bitwise_and(wound_mask, cv2.bitwise_not(drape_mask))

        if np.sum(cleaned > 0) < 0.02 * wound_mask.size:
            return wound_mask

        return cleaned

    @staticmethod
    def create_background_mask_spatial(image: np.ndarray, wound_mask: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]
        background_mask = np.zeros((h, w), dtype=np.uint8)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        very_dark = (gray < 20).astype(np.uint8) * 255
        dark_in_roi = cv2.bitwise_and(very_dark, wound_mask)

        dark_count = np.sum(dark_in_roi > 0)
        roi_count = max(np.sum(wound_mask > 0), 1)
        if dark_count < roi_count * 0.02:
            return background_mask

        gray_f = gray.astype(np.float32)
        local_mean = cv2.blur(gray_f, (5, 5))
        local_sqmean = cv2.blur(gray_f ** 2, (5, 5))
        local_var = local_sqmean - local_mean ** 2
        local_var = np.clip(local_var, 0, None)

        low_var = (local_var < 8.0).astype(np.uint8) * 255

        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        a_ch = lab[:, :, 1].astype(np.float32)
        b_ch = lab[:, :, 2].astype(np.float32)
        chroma_deviation = np.sqrt((a_ch - 128.0) ** 2 + (b_ch - 128.0) ** 2)

        achromatic = (chroma_deviation < 5.0).astype(np.uint8) * 255

        bg_candidate = cv2.bitwise_and(dark_in_roi, low_var)
        bg_candidate = cv2.bitwise_and(bg_candidate, achromatic)

        contours, _ = cv2.findContours(bg_candidate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        border_margin = 3
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > roi_count * 0.15:
                cv2.drawContours(background_mask, [cnt], -1, 255, cv2.FILLED)
                continue

            x, y, cw, ch = cv2.boundingRect(cnt)
            touches_border = (
                x <= border_margin or
                y <= border_margin or
                (x + cw) >= (w - border_margin) or
                (y + ch) >= (h - border_margin)
            )
            if touches_border and area > 50:
                cv2.drawContours(background_mask, [cnt], -1, 255, cv2.FILLED)
                continue

            cnt_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(cnt_mask, [cnt], -1, 255, cv2.FILLED)
            region_var = local_var[cnt_mask > 0]
            if len(region_var) > 10 and np.mean(region_var) < 2.0:
                cv2.drawContours(background_mask, [cnt], -1, 255, cv2.FILLED)

        if np.sum(background_mask > 0) > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            background_mask = cv2.dilate(background_mask, kernel, iterations=1)
            background_mask = cv2.bitwise_and(background_mask, wound_mask)

        return background_mask

    @staticmethod
    def create_zone_masks(wound_mask: np.ndarray, border_width_px: int = 15) -> tuple:
        h, w = wound_mask.shape[:2]
        wound_area = np.sum(wound_mask > 0)
        equiv_radius = np.sqrt(wound_area / np.pi) if wound_area > 0 else 0
        adaptive_width = int(np.clip(equiv_radius * 0.15, 3, border_width_px))

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * adaptive_width + 1, 2 * adaptive_width + 1))
        eroded = cv2.erode(wound_mask, kernel, iterations=1)

        core_zone = eroded
        peripheral_zone = cv2.bitwise_and(wound_mask, cv2.bitwise_not(core_zone))
        dilated = cv2.dilate(wound_mask, kernel, iterations=1)
        outer_ring = cv2.bitwise_and(dilated, cv2.bitwise_not(wound_mask))

        return peripheral_zone, core_zone, outer_ring
