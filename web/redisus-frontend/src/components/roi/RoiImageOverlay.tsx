import type { Roi } from '../../lib/types';
import { normalizeRois, roiPointsToPath, roiPointsToSvgPoints } from '../../lib/roi';

interface RoiImageOverlayProps {
  rois?: Roi[];
  className?: string;
  showPoints?: boolean;
}

export function RoiImageOverlay({ rois = [], className = '', showPoints = true }: RoiImageOverlayProps) {
  const normalized = normalizeRois(rois);
  if (!normalized.length) return null;

  return (
    <svg
      className={`pointer-events-none absolute inset-0 h-full w-full ${className}`}
      viewBox="0 0 1000 1000"
      preserveAspectRatio="none"
      aria-hidden
    >
      {normalized.map(roi => {
        const points = roiPointsToSvgPoints(roi.points);
        const path = roiPointsToPath(roi.points);

        return (
          <g key={roi.id}>
            {roi.type !== 'freehand' && roi.points.length >= 3 ? (
              <polygon points={points} fill={`${roi.color}22`} stroke={roi.color} strokeWidth="7" />
            ) : null}
            {roi.type === 'freehand' ? (
              <path d={path} fill="none" stroke={roi.color} strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
            ) : (
              <polyline points={points} fill="none" stroke={roi.color} strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
            )}
            {showPoints && roi.type !== 'freehand'
              ? roi.points.map((point, index) => (
                  <circle
                    key={`${roi.id}-${index}`}
                    cx={point.x * 1000}
                    cy={point.y * 1000}
                    r="10"
                    fill="#fff"
                    stroke={roi.color}
                    strokeWidth="5"
                  />
                ))
              : null}
          </g>
        );
      })}
    </svg>
  );
}
