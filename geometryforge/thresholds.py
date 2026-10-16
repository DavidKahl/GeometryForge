"""Acceptance thresholds for typed checks, calibration and gated review.

Defaults are starting values taken from an unverified engineering report on
agentic hard-surface modeling. Projects own their limits: override them in
parameters.json under ``gf_thresholds.<class>`` or per check.
"""
from copy import deepcopy
import math

DEFAULTS = {
    'seam': {'master_deviation_mm': 0.25, 'step_mm': 0.5, 'gap_min_mm': 2.0, 'gap_max_mm': 4.0,
             'normal_angle_deg': 2.5, 'curvature_ratio': 0.08, 'probe_mm': 15.0, 'exterior_band_mm': 1.0,
             'exterior_normal_deg': 10.0, 'min_pairs': 3, 'flat_curvature_per_mm': 5e-4},
    'recess': {'rim_step_mm': 0.05, 'protrusion_mm': 0.05, 'draft_min_deg': 3.0, 'fillet_min_mm': 5.0,
               'rim_weight': 0.999, 'exterior_normal_deg': 10.0},
    'mating': {'axis_deg': 0.1, 'centroid_mm': 0.05, 'skin_crossings_max': 0},
    'global': {'silhouette_iou_min': 0.90, 'delta_iou_min': 0.0, 'open_edges_max': 0,
               'uncovered_area_mm2_max': 0.0, 'cover_tolerance_mm': 3.0},
    'calibration': {'max_rms_px': 2.0},
    'references': {'view_disagreement_pct': 3.0},
    'review': {'min_views': 21},
}


def resolve(parameters, kind, overrides=None):
    """Defaults < parameters.json gf_thresholds[kind] < per-check overrides."""
    if kind not in DEFAULTS:
        raise ValueError(f'Unknown threshold class: {kind}')
    result = deepcopy(DEFAULTS[kind])
    project = (parameters or {}).get('gf_thresholds', {})
    if not isinstance(project, dict):
        raise ValueError('gf_thresholds must be an object of threshold classes')
    for layer in (project.get(kind, {}), overrides or {}):
        if not isinstance(layer, dict):
            raise ValueError(f'{kind} thresholds must be an object')
        for key, value in layer.items():
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f'Threshold {kind}.{key} must be a finite number')
            result[key] = value
    return result
