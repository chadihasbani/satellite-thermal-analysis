"""Spacecraft configuration presets (Checkpoint 5).

CubeSat mechanical envelopes and **maximum masses** follow the Cal Poly
CubeSat Design Specification (CDS) Rev 14.1 (February 2022):

- 1U envelope: 100.0 × 100.0 × 113.5 mm; typical max mass 2.00 kg
- 3U envelope: 100.0 × 100.0 × 340.5 mm; typical max mass 6.00 kg

Source PDF (NASA-hosted copy of Cal Poly CDS Rev 14.1):
https://www.nasa.gov/wp-content/uploads/2018/01/cubesatdesignspecificationrev14_12022-02-09.pdf
(Table 1 mass notes; Appendix B / §2.2 mechanical envelope.)

Those values are **specification envelope / mass limits**, not the mass or
thermal properties of any particular flight spacecraft. Effective specific
heat, coatings, and the actual mass used in this educational model are
**illustrative lumped assumptions** unless otherwise labelled.

The rectangular L×W×H bus is an **idealized radiating geometry** for the
six-face thermal calculation — not an exact map of exposed flight-hardware
surfaces (rails, gaps, antennas, MLI details, or deployables).

Visual solar wings in the 3D view remain decorative and are **not** thermal
surfaces (no solar absorption, emission, or capacitance contribution).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from satellite_thermal.orbital_simulation import THERMAL_MODEL_ENHANCED, THERMAL_MODEL_LEGACY
from satellite_thermal.spacecraft_geometry import RectangularBusGeometry
from satellite_thermal.validation import require_positive


class SpacecraftConfigurationId(str, Enum):
    """GUI / API identifiers for spacecraft configuration presets."""

    LEGACY_SIMPLIFIED = "legacy_simplified"
    ILLUSTRATIVE_CUBE = "illustrative_cube"
    CUBESAT_1U = "cubesat_1u"
    CUBESAT_3U = "cubesat_3u"
    CUSTOM = "custom"


# CDS Rev 14.1 envelope dimensions (metres) and typical maximum masses (kg).
CDS_REV = "14.1"
CDS_1U_LENGTH_M = 0.100
CDS_1U_WIDTH_M = 0.100
CDS_1U_HEIGHT_M = 0.1135
CDS_1U_MAX_MASS_KG = 2.00

CDS_3U_LENGTH_M = 0.100
CDS_3U_WIDTH_M = 0.100
CDS_3U_HEIGHT_M = 0.3405
CDS_3U_MAX_MASS_KG = 6.00

# Illustrative educational defaults (not CDS-mandated spacecraft properties).
ILLUSTRATIVE_CP_J_PER_KG_K = 900.0
ILLUSTRATIVE_ALPHA = 0.60
ILLUSTRATIVE_EPSILON = 0.80
ILLUSTRATIVE_CUBE_MASS_KG = 5.0
# Chosen below the CDS max-mass notes; not a published flight mass.
ILLUSTRATIVE_1U_MASS_KG = 1.50
ILLUSTRATIVE_3U_MASS_KG = 4.00


def parse_spacecraft_configuration_id(
    value: str | SpacecraftConfigurationId,
) -> SpacecraftConfigurationId:
    """Parse a spacecraft configuration identifier."""
    if isinstance(value, SpacecraftConfigurationId):
        return value
    normalized = str(value).strip().lower()
    try:
        return SpacecraftConfigurationId(normalized)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in SpacecraftConfigurationId)
        raise ValueError(
            f"spacecraft configuration must be one of: {allowed}. Got {value!r}."
        ) from exc


def derived_face_areas_m2(
    length_m: float,
    width_m: float,
    height_m: float,
) -> dict[str, float]:
    """Six exterior face areas from rectangular dimensions (no double-count)."""
    length = require_positive("length_m", length_m)
    width = require_positive("width_m", width_m)
    height = require_positive("height_m", height_m)
    a_x = width * height
    a_y = length * height
    a_z = length * width
    return {
        "+x": a_x,
        "-x": a_x,
        "+y": a_y,
        "-y": a_y,
        "+z": a_z,
        "-z": a_z,
    }


def total_exterior_area_m2(length_m: float, width_m: float, height_m: float) -> float:
    """Sum of the six exterior face areas."""
    areas = derived_face_areas_m2(length_m, width_m, height_m)
    return sum(areas.values())


@dataclass(frozen=True)
class SpacecraftConfigurationDefinition:
    """Resolved spacecraft configuration for GUI display and request overlays."""

    configuration_id: SpacecraftConfigurationId
    display_name: str
    summary: str
    body_length_m: float
    body_width_m: float
    body_height_m: float
    mass_kg: float
    specific_heat_j_per_kg_k: float
    absorptivity: float
    emissivity: float
    thermal_model: str
    projected_area_m2: float
    radiating_area_m2: float
    earth_facing_area_m2: float
    albedo_area_m2: float
    cds_max_mass_kg: float | None
    dimension_note: str
    mass_note: str
    thermal_note: str
    optics_note: str

    @property
    def thermal_capacitance_j_per_k(self) -> float:
        return self.mass_kg * self.specific_heat_j_per_kg_k

    def geometry(self) -> RectangularBusGeometry:
        return RectangularBusGeometry(
            length_m=self.body_length_m,
            width_m=self.body_width_m,
            height_m=self.body_height_m,
            absorptivity=self.absorptivity,
            emissivity=self.emissivity,
        ).validated()

    def face_areas_m2(self) -> dict[str, float]:
        return derived_face_areas_m2(
            self.body_length_m, self.body_width_m, self.body_height_m
        )

    def parameter_rows(self) -> list[dict[str, object]]:
        areas = self.face_areas_m2()
        rows: list[dict[str, object]] = [
            {
                "Category": "Geometry",
                "Parameter": "Body L × W × H",
                "Value": (
                    f"{self.body_length_m:.4g} × {self.body_width_m:.4g} × "
                    f"{self.body_height_m:.4g}"
                ),
                "Units": "m",
                "Notes": self.dimension_note,
            },
            {
                "Category": "Geometry",
                "Parameter": "Total exterior area",
                "Value": round(self.radiating_area_m2, 6),
                "Units": "m²",
                "Notes": "Derived: 2(wh + lh + lw); six faces, no double-count.",
            },
            {
                "Category": "Geometry",
                "Parameter": "Face areas ±X / ±Y / ±Z",
                "Value": (
                    f"{areas['+x']:.5f} / {areas['+y']:.5f} / {areas['+z']:.5f}"
                ),
                "Units": "m²",
                "Notes": "A±x=w·h, A±y=l·h, A±z=l·w.",
            },
            {
                "Category": "Thermal mass",
                "Parameter": "Mass",
                "Value": self.mass_kg,
                "Units": "kg",
                "Notes": self.mass_note,
            },
            {
                "Category": "Thermal mass",
                "Parameter": "Effective specific heat",
                "Value": self.specific_heat_j_per_kg_k,
                "Units": "J/(kg·K)",
                "Notes": self.thermal_note,
            },
            {
                "Category": "Thermal mass",
                "Parameter": "Lumped capacitance m·cp",
                "Value": round(self.thermal_capacitance_j_per_k, 3),
                "Units": "J/K",
                "Notes": "Derived: m × cp.",
            },
            {
                "Category": "Optics",
                "Parameter": "α / ε (uniform bus)",
                "Value": f"{self.absorptivity:.2f} / {self.emissivity:.2f}",
                "Units": "—",
                "Notes": self.optics_note,
            },
            {
                "Category": "Model",
                "Parameter": "Thermal model",
                "Value": self.thermal_model,
                "Units": "—",
                "Notes": (
                    "Legacy uses fixed effective areas; enhanced uses six-face "
                    "solar + face-sum radiation."
                ),
            },
        ]
        if self.cds_max_mass_kg is not None:
            rows.insert(
                4,
                {
                    "Category": "Thermal mass",
                    "Parameter": "CDS typical max mass (limit)",
                    "Value": self.cds_max_mass_kg,
                    "Units": "kg",
                    "Notes": f"CDS Rev {CDS_REV} Table 1 typical maximum — not this model mass.",
                },
            )
        return rows


def build_spacecraft_configuration(
    configuration_id: str | SpacecraftConfigurationId,
) -> SpacecraftConfigurationDefinition:
    """Build a fully resolved non-custom spacecraft configuration."""
    kind = parse_spacecraft_configuration_id(configuration_id)
    if kind is SpacecraftConfigurationId.CUSTOM:
        raise ValueError("Custom spacecraft configuration has no fixed table.")

    if kind is SpacecraftConfigurationId.LEGACY_SIMPLIFIED:
        return SpacecraftConfigurationDefinition(
            configuration_id=kind,
            display_name="Legacy simplified (V1 areas)",
            summary=(
                "Version 1.0 fixed projected/radiating areas with the educational "
                "0.1 m-class body used only for 3D proportions."
            ),
            body_length_m=0.1,
            body_width_m=0.1,
            body_height_m=0.1,
            mass_kg=ILLUSTRATIVE_CUBE_MASS_KG,
            specific_heat_j_per_kg_k=ILLUSTRATIVE_CP_J_PER_KG_K,
            absorptivity=ILLUSTRATIVE_ALPHA,
            emissivity=ILLUSTRATIVE_EPSILON,
            thermal_model=THERMAL_MODEL_LEGACY,
            projected_area_m2=0.01,
            radiating_area_m2=0.06,
            earth_facing_area_m2=0.01,
            albedo_area_m2=0.01,
            cds_max_mass_kg=None,
            dimension_note="Illustrative 0.1 m cube proportions for visualization.",
            mass_note="Repo V1 educational mass (illustrative).",
            thermal_note="Repo V1 educational lumped cp (illustrative; not a material cp).",
            optics_note="Repo V1 educational coating-like α/ε (illustrative).",
        )

    if kind is SpacecraftConfigurationId.ILLUSTRATIVE_CUBE:
        geom = RectangularBusGeometry(
            length_m=0.1,
            width_m=0.1,
            height_m=0.1,
            absorptivity=ILLUSTRATIVE_ALPHA,
            emissivity=ILLUSTRATIVE_EPSILON,
        ).validated()
        total = geom.total_exterior_area_m2()
        face_z = geom.face_area_m2("+z")
        return SpacecraftConfigurationDefinition(
            configuration_id=kind,
            display_name="Illustrative 0.1 m cube",
            summary=(
                "Enhanced rectangular bus equal to a 0.1 m cube. Total exterior "
                "area matches the V1 0.06 m² radiating default."
            ),
            body_length_m=0.1,
            body_width_m=0.1,
            body_height_m=0.1,
            mass_kg=ILLUSTRATIVE_CUBE_MASS_KG,
            specific_heat_j_per_kg_k=ILLUSTRATIVE_CP_J_PER_KG_K,
            absorptivity=ILLUSTRATIVE_ALPHA,
            emissivity=ILLUSTRATIVE_EPSILON,
            thermal_model=THERMAL_MODEL_ENHANCED,
            projected_area_m2=face_z,
            radiating_area_m2=total,
            earth_facing_area_m2=face_z,
            albedo_area_m2=face_z,
            cds_max_mass_kg=None,
            dimension_note="Illustrative educational cube (not a CDS envelope).",
            mass_note="Illustrative educational mass (not a published spacecraft).",
            thermal_note="Illustrative lumped effective cp for the whole satellite.",
            optics_note="Illustrative uniform bus coating-like α/ε.",
        )

    if kind is SpacecraftConfigurationId.CUBESAT_1U:
        geom = RectangularBusGeometry(
            length_m=CDS_1U_LENGTH_M,
            width_m=CDS_1U_WIDTH_M,
            height_m=CDS_1U_HEIGHT_M,
            absorptivity=ILLUSTRATIVE_ALPHA,
            emissivity=ILLUSTRATIVE_EPSILON,
        ).validated()
        total = geom.total_exterior_area_m2()
        face_z = geom.face_area_m2("+z")
        return SpacecraftConfigurationDefinition(
            configuration_id=kind,
            display_name="Generic 1U CubeSat-inspired",
            summary=(
                f"CDS Rev {CDS_REV} 1U mechanical envelope with illustrative "
                "mass/thermal properties. Not an operational satellite."
            ),
            body_length_m=CDS_1U_LENGTH_M,
            body_width_m=CDS_1U_WIDTH_M,
            body_height_m=CDS_1U_HEIGHT_M,
            mass_kg=ILLUSTRATIVE_1U_MASS_KG,
            specific_heat_j_per_kg_k=ILLUSTRATIVE_CP_J_PER_KG_K,
            absorptivity=ILLUSTRATIVE_ALPHA,
            emissivity=ILLUSTRATIVE_EPSILON,
            thermal_model=THERMAL_MODEL_ENHANCED,
            projected_area_m2=face_z,
            radiating_area_m2=total,
            earth_facing_area_m2=face_z,
            albedo_area_m2=face_z,
            cds_max_mass_kg=CDS_1U_MAX_MASS_KG,
            dimension_note=(
                f"CDS Rev {CDS_REV} 1U envelope 100×100×113.5 mm (rails/Z)."
            ),
            mass_note=(
                f"Illustrative {ILLUSTRATIVE_1U_MASS_KG:g} kg "
                f"(below CDS typical max {CDS_1U_MAX_MASS_KG:g} kg)."
            ),
            thermal_note="Illustrative lumped effective cp (not CDS; not Al-only).",
            optics_note="Illustrative uniform α/ε (not a published coating).",
        )

    # 3U
    geom = RectangularBusGeometry(
        length_m=CDS_3U_LENGTH_M,
        width_m=CDS_3U_WIDTH_M,
        height_m=CDS_3U_HEIGHT_M,
        absorptivity=ILLUSTRATIVE_ALPHA,
        emissivity=ILLUSTRATIVE_EPSILON,
    ).validated()
    total = geom.total_exterior_area_m2()
    face_z = geom.face_area_m2("+z")
    return SpacecraftConfigurationDefinition(
        configuration_id=kind,
        display_name="Generic 3U CubeSat-inspired",
        summary=(
            f"CDS Rev {CDS_REV} 3U mechanical envelope with illustrative "
            "mass/thermal properties. Not an operational satellite."
        ),
        body_length_m=CDS_3U_LENGTH_M,
        body_width_m=CDS_3U_WIDTH_M,
        body_height_m=CDS_3U_HEIGHT_M,
        mass_kg=ILLUSTRATIVE_3U_MASS_KG,
        specific_heat_j_per_kg_k=ILLUSTRATIVE_CP_J_PER_KG_K,
        absorptivity=ILLUSTRATIVE_ALPHA,
        emissivity=ILLUSTRATIVE_EPSILON,
        thermal_model=THERMAL_MODEL_ENHANCED,
        projected_area_m2=face_z,
        radiating_area_m2=total,
        earth_facing_area_m2=face_z,
        albedo_area_m2=face_z,
        cds_max_mass_kg=CDS_3U_MAX_MASS_KG,
        dimension_note=(
            f"CDS Rev {CDS_REV} 3U envelope 100×100×340.5 mm (rails/Z)."
        ),
        mass_note=(
            f"Illustrative {ILLUSTRATIVE_3U_MASS_KG:g} kg "
            f"(below CDS typical max {CDS_3U_MAX_MASS_KG:g} kg)."
        ),
        thermal_note="Illustrative lumped effective cp (not CDS; not Al-only).",
        optics_note="Illustrative uniform α/ε (not a published coating).",
    )


def configuration_overlay_fields(
    definition: SpacecraftConfigurationDefinition,
) -> dict[str, object]:
    """GuiRunRequest fields owned by a non-custom spacecraft preset."""
    return {
        "body_length_m": definition.body_length_m,
        "body_width_m": definition.body_width_m,
        "body_height_m": definition.body_height_m,
        "mass_kg": definition.mass_kg,
        "specific_heat_j_per_kg_k": definition.specific_heat_j_per_kg_k,
        "absorptivity": definition.absorptivity,
        "emissivity": definition.emissivity,
        "thermal_model": definition.thermal_model,
        "projected_area_m2": definition.projected_area_m2,
        "radiating_area_m2": definition.radiating_area_m2,
        "earth_facing_area_m2": definition.earth_facing_area_m2,
        "albedo_area_m2": definition.albedo_area_m2,
    }


def configuration_controlled_field_names() -> tuple[str, ...]:
    """Bare request field names locked by non-custom spacecraft presets."""
    sample = build_spacecraft_configuration(SpacecraftConfigurationId.ILLUSTRATIVE_CUBE)
    return tuple(configuration_overlay_fields(sample).keys())


def configuration_select_options() -> list[tuple[str, str]]:
    """(id, label) pairs for the GUI selector."""
    return [
        (
            SpacecraftConfigurationId.LEGACY_SIMPLIFIED.value,
            "Legacy simplified (V1 fixed areas)",
        ),
        (
            SpacecraftConfigurationId.ILLUSTRATIVE_CUBE.value,
            "Illustrative 0.1 m cube (enhanced)",
        ),
        (
            SpacecraftConfigurationId.CUBESAT_1U.value,
            "Generic 1U CubeSat-inspired (CDS Rev 14.1 envelope)",
        ),
        (
            SpacecraftConfigurationId.CUBESAT_3U.value,
            "Generic 3U CubeSat-inspired (CDS Rev 14.1 envelope)",
        ),
        (
            SpacecraftConfigurationId.CUSTOM.value,
            "Custom rectangular spacecraft",
        ),
    ]


def sync_session_values_from_configuration(
    configuration_id: str | SpacecraftConfigurationId,
) -> dict[str, object]:
    """Session-state updates for sidebar widgets when a preset is chosen."""
    kind = parse_spacecraft_configuration_id(configuration_id)
    if kind is SpacecraftConfigurationId.CUSTOM:
        return {}
    definition = build_spacecraft_configuration(kind)
    return {
        f"gui_{name}": value
        for name, value in configuration_overlay_fields(definition).items()
    }


def configuration_controls_locked(
    configuration_id: str | SpacecraftConfigurationId,
) -> bool:
    """True when spacecraft-preset-owned widgets must not be user-editable."""
    return (
        parse_spacecraft_configuration_id(configuration_id)
        is not SpacecraftConfigurationId.CUSTOM
    )


def mismatched_configuration_field_names(
    field_values: dict[str, object],
    configuration_id: str | SpacecraftConfigurationId,
    *,
    rel_tol: float = 0.0,
    abs_tol: float = 1e-12,
) -> tuple[str, ...]:
    """Return overlay fields that disagree with the active non-custom preset."""
    kind = parse_spacecraft_configuration_id(configuration_id)
    if kind is SpacecraftConfigurationId.CUSTOM:
        return ()
    expected = configuration_overlay_fields(build_spacecraft_configuration(kind))
    mismatches: list[str] = []
    for name, expected_value in expected.items():
        if name not in field_values:
            mismatches.append(name)
            continue
        actual = field_values[name]
        if isinstance(expected_value, bool) or isinstance(expected_value, str):
            if actual != expected_value:
                mismatches.append(name)
            continue
        if isinstance(expected_value, (int, float)):
            try:
                actual_number = float(actual)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                mismatches.append(name)
                continue
            if not math.isclose(
                actual_number,
                float(expected_value),
                rel_tol=rel_tol,
                abs_tol=abs_tol,
            ):
                mismatches.append(name)
            continue
        if actual != expected_value:
            mismatches.append(name)
    return tuple(mismatches)
