"""PDF engineering-report generator for completed GUI simulations.

Builds an in-memory PDF from a ``CompletedGuiStudy`` and the user-selected
inspection sample. Does not re-solve the thermal equations.
"""

from __future__ import annotations

import logging
import math
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from satellite_thermal.gui_support import (
    ENV_CASE_NAMES,
    CompletedGuiStudy,
    GuiRunRequest,
    NamedResult,
    all_curves,
    comparison_metrics_rows,
    environment_comparison_interpretation,
    environment_comparison_summary_rows,
    figure_to_png_bytes,
    geometry_from_request,
    make_comparison_temperature_figure,
    make_gui_temperature_figure,
    make_heat_flow_bar_figure,
    power_schedule_from_request,
    temperature_metrics_c,
)
from satellite_thermal.heat_flows import heat_flow_at_index
from satellite_thermal.orbit import (
    analytical_eclipse_duration_s,
    critical_beta_rad,
    orbital_period_s,
    orbital_radius_m,
)
from satellite_thermal.orbit_3d import build_orbit_3d_figure
from satellite_thermal.spacecraft_configurations import (
    SpacecraftConfigurationId,
    configuration_select_options,
    derived_face_areas_m2,
    parse_spacecraft_configuration_id,
)
from satellite_thermal.spacecraft_geometry import RectangularBusGeometry

SIMULATOR_VERSION = "2.0.0"
SIMULATOR_NAME = "Satellite Thermal Analysis Simulator"

MODE_TITLES = {
    "single": "Satellite Thermal Simulation",
    "environment_compare": "Compare Heat Sources",
}

ORBITAL_IMAGE_UNAVAILABLE_NOTE = (
    "The 3D orbital snapshot could not be included because the image "
    "renderer was unavailable."
)

# Typical Debian / Streamlit Community Cloud paths from packages.txt `chromium`.
_SYSTEM_CHROME_CANDIDATES = (
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/lib/chromium/chromium",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/google-chrome",
)

_logger = logging.getLogger(__name__)
_kaleido_browser_configured = False


@dataclass(frozen=True)
class ReportMeta:
    """Labels captured when the study was solved (not live sidebar state)."""

    configuration_id: str
    configuration_label: str


@dataclass(frozen=True)
class EngineeringReportPdf:
    """PDF bytes plus optional orbital-image export status."""

    pdf_bytes: bytes
    orbital_snapshot_included: bool
    orbital_snapshot_error: str | None = None


def default_report_meta(
    configuration_id: str = SpacecraftConfigurationId.CUSTOM.value,
) -> ReportMeta:
    """Build report metadata from configuration identifiers."""
    config_labels = dict(configuration_select_options())
    return ReportMeta(
        configuration_id=parse_spacecraft_configuration_id(configuration_id).value,
        configuration_label=config_labels.get(configuration_id, configuration_id),
    )


def power_schedule_detail_rows(request: GuiRunRequest) -> list[tuple[str, str]]:
    """Reproducible internal-power parameters from a frozen request."""
    return [
        ("Internal power schedule", "constant"),
        ("Constant internal power", f"{request.internal_heat_w:.3g} W"),
    ]


def _mode_cover_rows(
    study: CompletedGuiStudy,
    meta: ReportMeta,
    viz_curve: NamedResult,
) -> list[tuple[str, str]]:
    """Cover-page rows that describe the whole study, not only the inspect case."""
    rows = [
        ("Simulator version", SIMULATOR_VERSION),
        ("Simulation mode", MODE_TITLES.get(study.mode, study.mode)),
        ("Spacecraft configuration", meta.configuration_label),
    ]
    if study.mode == "single":
        rows.append(("Reported case", viz_curve.name))
    elif study.mode == "environment_compare":
        rows.append(("Compared cases", " → ".join(ENV_CASE_NAMES)))
        rows.append(("Inspection snapshot case", viz_curve.name))
    else:
        rows.append(("Inspection snapshot case", viz_curve.name))
    return rows


def _discover_system_chrome_path() -> str | None:
    """Return a usable Chromium/Chrome executable path if one is installed."""
    env_path = os.environ.get("BROWSER_PATH") or os.environ.get("CHROME_PATH")
    if env_path and Path(env_path).is_file():
        return env_path
    for candidate in _SYSTEM_CHROME_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    for name in ("chromium", "chromium-browser", "google-chrome-stable", "google-chrome"):
        found = shutil.which(name)
        if found and Path(found).is_file():
            return found
    return None


def ensure_kaleido_browser_configured() -> str | None:
    """Point Kaleido at a system browser once (no per-PDF Chrome download).

    Prefer the Streamlit Community Cloud / apt Chromium installed via
    ``packages.txt``. Returns the configured executable path, or ``None`` if
    no system browser was found (Kaleido may still succeed via its own cache).
    """
    global _kaleido_browser_configured
    if _kaleido_browser_configured:
        existing = os.environ.get("BROWSER_PATH")
        return existing if existing and Path(existing).is_file() else None

    path = _discover_system_chrome_path()
    if path:
        os.environ["BROWSER_PATH"] = path
        _logger.info("Kaleido BROWSER_PATH set to system browser: %s", path)
    else:
        _logger.info(
            "No system Chromium/Chrome found for Kaleido; relying on Kaleido defaults."
        )
    _kaleido_browser_configured = True
    return path


def _plotly_figure_to_png_bytes(figure, *, width: int = 900, height: int = 700) -> bytes:
    """Export a Plotly figure to PNG bytes (requires kaleido + browser)."""
    ensure_kaleido_browser_configured()
    try:
        return figure.to_image(format="png", width=width, height=height, scale=2)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Could not export the 3D orbital snapshot to an image. "
            "Install the kaleido package (see requirements.txt) and ensure a "
            "compatible Chrome/Chromium is available for Kaleido "
            "(Streamlit Community Cloud: packages.txt entry `chromium`). "
            f"Details: {exc}"
        ) from exc


def export_orbital_snapshot_png(
    figure, *, width: int = 900, height: int = 700
) -> tuple[bytes | None, str | None]:
    """Try Plotly/Kaleido orbital export; return (png_bytes, error_message)."""
    try:
        return _plotly_figure_to_png_bytes(figure, width=width, height=height), None
    except Exception as exc:  # noqa: BLE001
        _logger.exception("Orbital snapshot image export failed")
        return None, str(exc)


def _temperature_figure_png(study: CompletedGuiStudy, viz_curve: NamedResult, sample_index: int) -> bytes:
    curves = all_curves(study)
    if study.mode == "single":
        fig = make_gui_temperature_figure(
            study.primary.result,
            marker_index=sample_index,
            title="Predicted spacecraft temperature",
            label=study.primary.name,
        )
    else:
        fig = make_comparison_temperature_figure(
            curves,
            marker_index=sample_index,
            marker_curve_name=viz_curve.name,
            emphasize_name=viz_curve.name,
            title="Heat-source comparison",
            shade_from=curves[0],
        )
    return figure_to_png_bytes(fig)


def build_engineering_report_pdf(
    study: CompletedGuiStudy,
    *,
    viz_curve: NamedResult,
    sample_index: int,
    meta: ReportMeta,
) -> EngineeringReportPdf:
    """Generate a multi-page engineering PDF for one completed study.

    Uses only the completed study curves and the selected inspection sample.
    Does not read live Streamlit sidebar widgets.

    Orbital-image export failures are non-fatal: the PDF is still produced with
    a disclosed missing-visualization note. Other failures still raise.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        KeepTogether,
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    curves = all_curves(study)
    if viz_curve.name not in {curve.name for curve in curves}:
        raise ValueError(
            f"Inspection case {viz_curve.name!r} is not part of the completed study."
        )
    n_samples = len(viz_curve.result.time_s)
    if sample_index < 0 or sample_index >= n_samples:
        raise IndexError(
            f"sample_index {sample_index} out of range for {n_samples} stored samples."
        )

    request = viz_curve.request
    snap = heat_flow_at_index(
        result=viz_curve.result,
        index=sample_index,
        thermal=viz_curve.thermal,
        orbit=viz_curve.orbit,
        include_earth_infrared=request.include_earth_infrared,
        include_albedo=request.include_albedo,
        earth_infrared=viz_curve.earth_infrared,
        albedo=viz_curve.albedo,
        thermal_model=request.thermal_model,
        geometry=geometry_from_request(request),
        attitude_mode=request.attitude_mode,
        power_schedule=power_schedule_from_request(request),
    )
    inspect_metrics = temperature_metrics_c(viz_curve.result)
    config_request = study.primary.request
    period_s = orbital_period_s(viz_curve.orbit)
    radius_m = orbital_radius_m(viz_curve.orbit)
    beta_c_deg = math.degrees(critical_beta_rad(viz_curve.orbit))
    eclipse_duration_s = analytical_eclipse_duration_s(viz_curve.orbit)
    total_duration_s = config_request.orbit_count * period_s

    temp_png = _temperature_figure_png(study, viz_curve, sample_index)
    heat_png = figure_to_png_bytes(make_heat_flow_bar_figure(snap))
    fig3d = build_orbit_3d_figure(
        result=viz_curve.result,
        orbit=viz_curve.orbit,
        sample_index=sample_index,
        title=viz_curve.name,
        attitude_mode=request.attitude_mode,
        body_length_m=request.body_length_m,
        body_width_m=request.body_width_m,
        body_height_m=request.body_height_m,
        thermal_model=request.thermal_model,
    )
    orbit_png, orbit_export_error = export_orbital_snapshot_png(fig3d)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"{SIMULATOR_NAME} — Engineering Report",
        author=SIMULATOR_NAME,
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            fontSize=20,
            leading=24,
            alignment=TA_CENTER,
            spaceAfter=6,
            textColor=colors.HexColor("#1D1D1F"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSub",
            parent=styles["Normal"],
            fontSize=12,
            leading=16,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#3A3A3C"),
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading1"],
            fontSize=13,
            leading=16,
            spaceBefore=10,
            spaceAfter=5,
            textColor=colors.HexColor("#1D1D1F"),
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyJust",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=12.5,
            alignment=TA_JUSTIFY,
            spaceAfter=5,
            textColor=colors.HexColor("#1D1D1F"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="Caption",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#6E6E73"),
            spaceBefore=2,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCell",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
        )
    )

    mode_title = MODE_TITLES.get(study.mode, study.mode)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story: list = []

    def p(text: str, style: str = "BodyJust") -> Paragraph:
        return Paragraph(text, styles[style])

    def section(title: str) -> Paragraph:
        return Paragraph(title, styles["Section"])

    def kv_table(rows: list[tuple[str, str]], col_widths=None) -> Table:
        data = [
            [Paragraph(str(a), styles["TableCell"]), Paragraph(str(b), styles["TableCell"])]
            for a, b in rows
        ]
        table = Table(data, colWidths=col_widths or [72 * mm, 98 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F5F5F7")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D2D2D7")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ]
            )
        )
        return table

    def multi_table(headers: list[str], rows: list[list[str]]) -> Table:
        data = [[Paragraph(h, styles["TableCell"]) for h in headers]]
        for row in rows:
            data.append([Paragraph(str(cell), styles["TableCell"]) for cell in row])
        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D1D1F")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D2D2D7")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F5F5F7")],
                    ),
                ]
            )
        )
        return table

    def image_flow(png: bytes, width_mm: float = 160.0, height_mm: float | None = None) -> Image:
        if height_mm is None:
            img = Image(BytesIO(png), width=width_mm * mm, height=width_mm * mm * 0.55)
        else:
            img = Image(BytesIO(png), width=width_mm * mm, height=height_mm * mm)
        img.hAlign = "CENTER"
        return img

    def block(*flowables) -> KeepTogether:
        return KeepTogether(list(flowables))

    # --- Cover ---
    story.append(Spacer(1, 18 * mm))
    story.append(Paragraph(SIMULATOR_NAME, styles["CoverTitle"]))
    story.append(Paragraph("Spacecraft Thermal Analysis Report", styles["CoverSub"]))
    story.append(Spacer(1, 4 * mm))
    cover_rows = _mode_cover_rows(study, meta, viz_curve)
    cover_rows.insert(1, ("Report generated", generated))
    story.append(kv_table(cover_rows))
    story.append(Spacer(1, 5 * mm))
    story.append(
        p(
            "This report summarises a single-node thermal simulation of a spacecraft "
            "in circular low Earth orbit. Heating terms include direct sunlight, "
            "Earth infrared radiation, reflected sunlight (albedo), and onboard "
            "equipment dissipation. Cooling is modelled as thermal radiation to deep "
            "space. Results are predicted model outputs for education and engineering "
            "exploration — not flight-qualified temperature predictions."
        )
    )
    story.append(PageBreak())

    # --- Executive summary ---
    summary_bits: list = [section("1. Executive summary")]
    if study.mode == "environment_compare" and len(curves) == 3:
        summary_bits.append(
            p(
                f"A <b>{mode_title}</b> was completed for "
                f"<b>{meta.configuration_label}</b> "
                f"({config_request.thermal_model} thermal model) at "
                f"{config_request.altitude_km:.0f} km. "
                "The table below is the selected inspection snapshot; overall "
                "case-to-case results appear in the comparison section."
            )
        )
        summary_bits.append(p(environment_comparison_interpretation(curves)))
        summary_bits.append(
            kv_table(
                [
                    (
                        "Inspection case",
                        viz_curve.name,
                    ),
                    ("Predicted final (inspect case)", f"{inspect_metrics['final_c']:.2f} °C"),
                    ("Predicted minimum (inspect case)", f"{inspect_metrics['minimum_c']:.2f} °C"),
                    ("Predicted maximum (inspect case)", f"{inspect_metrics['maximum_c']:.2f} °C"),
                    (
                        "At selected sample",
                        (
                            f"{snap.temperature_c:.2f} °C · "
                            f"{'eclipsed' if snap.in_eclipse else 'sunlit'} · "
                            f"t = {snap.time_s / 60.0:.2f} min"
                        ),
                    ),
                ]
            )
        )
    else:
        summary_bits.append(
            p(
                f"A <b>{mode_title}</b> was completed for "
                f"<b>{meta.configuration_label}</b> "
                f"({request.thermal_model} thermal model) at "
                f"{request.altitude_km:.0f} km altitude with Sun–orbit angle "
                f"β = {request.beta_deg:.1f}°. "
                f"{request.orbit_count} orbit(s) were integrated with a "
                f"{request.time_step_s:.1f} s nominal time step."
            )
        )
        summary_bits.append(
            kv_table(
                [
                    ("Predicted final temperature", f"{inspect_metrics['final_c']:.2f} °C"),
                    ("Predicted minimum", f"{inspect_metrics['minimum_c']:.2f} °C"),
                    ("Predicted maximum", f"{inspect_metrics['maximum_c']:.2f} °C"),
                    ("Initial temperature", f"{inspect_metrics['initial_c']:.2f} °C"),
                    (
                        "At selected sample",
                        (
                            f"{snap.temperature_c:.2f} °C · "
                            f"{'eclipsed' if snap.in_eclipse else 'sunlit'} · "
                            f"t = {snap.time_s / 60.0:.2f} min"
                        ),
                    ),
                ]
            )
        )
        summary_bits.append(
            p(
                "The temperature history reflects the balance between absorbed "
                "environmental and internal equipment heating and radiative cooling "
                "as the spacecraft moves through sunlight and orbital eclipse."
            )
        )
    summary_bits.append(
        p(
            "<b>Key limitations:</b> single-node thermal model; idealized geometry; "
            "cylindrical eclipse shadow; prescribed spacecraft orientation (not "
            "closed-loop control); illustrative CubeSat properties where noted; "
            "no flight-data correlation."
        )
    )
    story.append(block(*summary_bits))

    # --- Spacecraft ---
    geom = RectangularBusGeometry(
        length_m=config_request.body_length_m,
        width_m=config_request.body_width_m,
        height_m=config_request.body_height_m,
        absorptivity=config_request.absorptivity,
        emissivity=config_request.emissivity,
    ).validated()
    faces = derived_face_areas_m2(
        config_request.body_length_m,
        config_request.body_width_m,
        config_request.body_height_m,
    )
    capacitance = config_request.mass_kg * config_request.specific_heat_j_per_kg_k
    story.append(
        block(
            section("2. Spacecraft configuration"),
            kv_table(
                [
                    ("Spacecraft type", meta.configuration_label),
                    (
                        "Body L × W × H",
                        (
                            f"{config_request.body_length_m:.4g} × "
                            f"{config_request.body_width_m:.4g} × "
                            f"{config_request.body_height_m:.4g} m"
                        ),
                    ),
                    (
                        "Mass",
                        f"{config_request.mass_kg:.3g} kg "
                        "(illustrative unless labelled otherwise)",
                    ),
                    (
                        "Effective specific heat",
                        f"{config_request.specific_heat_j_per_kg_k:.0f} J/(kg·K)",
                    ),
                    ("Thermal capacitance m·cp", f"{capacitance:.1f} J/K"),
                    (
                        "Face areas ±X / ±Y / ±Z",
                        (
                            f"{faces['+x']:.5f} / {faces['+y']:.5f} / "
                            f"{faces['+z']:.5f} m²"
                        ),
                    ),
                    (
                        "Total exterior area",
                        f"{geom.total_exterior_area_m2():.5f} m²",
                    ),
                    (
                        "Radiating area (model input)",
                        f"{config_request.radiating_area_m2:.5f} m²",
                    ),
                    (
                        "Projected solar area (legacy input)",
                        f"{config_request.projected_area_m2:.5f} m²",
                    ),
                    (
                        "Earth-facing / albedo areas",
                        (
                            f"{config_request.earth_facing_area_m2:.5f} / "
                            f"{config_request.albedo_area_m2:.5f} m²"
                        ),
                    ),
                    ("Solar absorptivity α", f"{config_request.absorptivity:.3f}"),
                    ("Infrared emissivity ε", f"{config_request.emissivity:.3f}"),
                    ("Thermal model", config_request.thermal_model),
                    (
                        "Spacecraft orientation",
                        "Fixed orientation (inertial)",
                    ),
                ]
            ),
            p(
                "CubeSat envelopes follow CDS Rev 14.1 mechanical limits where noted; "
                "masses, coatings, and effective heat capacity used here are educational "
                "illustrative assumptions unless a custom spacecraft is fully user-defined. "
                "Visual solar wings in the 3D view are not thermal surfaces.",
                "Caption",
            ),
        )
    )

    # --- Orbit + power (from inspected/frozen request; scenario cases noted) ---
    orbit_rows = [
        ("Altitude", f"{request.altitude_km:.1f} km"),
        ("Orbital radius", f"{radius_m / 1000.0:.3f} km"),
        ("Orbital period", f"{period_s / 60.0:.2f} min ({period_s:.1f} s)"),
        ("Sun–orbit angle β", f"{request.beta_deg:.2f}°"),
        ("Critical β (cylindrical model)", f"{beta_c_deg:.2f}°"),
        (
            "Analytical eclipse duration / orbit",
            (
                f"{eclipse_duration_s / 60.0:.2f} min"
                if eclipse_duration_s > 0.0
                else "None (continuous sunlight under this model)"
            ),
        ),
        ("Number of orbits", str(request.orbit_count)),
        ("Total simulation duration", f"{total_duration_s / 60.0:.2f} min"),
        ("Nominal time step", f"{request.time_step_s:.2f} s"),
        ("Solar irradiance S", f"{request.solar_flux_w_per_m2:.1f} W/m²"),
        ("Earth infrared radiation intensity", f"{request.earth_olr_w_per_m2:.2f} W/m²"),
        ("Earth Bond albedo", f"{request.earth_bond_albedo:.3f}"),
        ("Include Earth infrared", "Yes" if request.include_earth_infrared else "No"),
        ("Include reflected sunlight (albedo)", "Yes" if request.include_albedo else "No"),
    ]
    story.append(
        block(
            section("3. Orbital and environmental conditions"),
            kv_table(orbit_rows),
            p(
                "Orbital eclipse uses an ideal cylindrical Earth shadow. Direct solar "
                "and albedo heating are zero in eclipse in this model. β is the angle "
                "between the Sun direction and the orbital plane.",
                "Caption",
            ),
        )
    )
    story.append(
        block(
            section("4. Internal equipment heating"),
            kv_table(power_schedule_detail_rows(request)),
            p(
                "These power values are taken from the frozen completed-simulation "
                "inputs for the inspection case above, so the run can be reproduced "
                "from this report alone.",
                "Caption",
            ),
        )
    )

    # --- Temperature ---
    story.append(section("5. Temperature analysis"))
    story.append(image_flow(temp_png, width_mm=165, height_mm=72))
    story.append(
        p(
            "Figure: Predicted spacecraft temperature versus time. Grey bands mark "
            "orbital eclipse. The red marker is the selected inspection sample.",
            "Caption",
        )
    )
    story.append(
        block(
            kv_table(
                [
                    ("Initial", f"{inspect_metrics['initial_c']:.2f} °C"),
                    ("Minimum", f"{inspect_metrics['minimum_c']:.2f} °C"),
                    ("Maximum", f"{inspect_metrics['maximum_c']:.2f} °C"),
                    ("Final", f"{inspect_metrics['final_c']:.2f} °C"),
                    (
                        "Range (max − min)",
                        f"{inspect_metrics['maximum_c'] - inspect_metrics['minimum_c']:.2f} °C",
                    ),
                ]
            ),
            p(
                "Overall behaviour follows the energy balance between absorbed heat and "
                "radiative rejection. Temperature typically falls in orbital eclipse "
                "(no direct sunlight or albedo) and recovers in sunlight, modulated by "
                "thermal capacitance and internal equipment heating."
            ),
        )
    )

    # --- 3D snapshot (optional image; selected-time facts always included) ---
    story.append(section("6. 3D orbital snapshot"))
    orbit_number = snap.time_s / period_s + 1.0
    snapshot_facts = (
        f"Selected sample: t = {snap.time_s / 60.0:.2f} min "
        f"(orbit {orbit_number:.2f}), "
        f"predicted spacecraft temperature = {snap.temperature_c:.2f} °C, "
        f"{'orbital eclipse' if snap.in_eclipse else 'sunlit'}, "
        f"β = {request.beta_deg:.1f}°, "
        "spacecraft orientation = fixed inertial."
    )
    if orbit_png is not None:
        story.append(image_flow(orbit_png, width_mm=150, height_mm=108))
        story.append(
            p(
                "Figure: Orbital visualization at the selected sample. "
                + snapshot_facts
                + " The craft is enlarged for readability; the view is illustrative "
                "and not to scale. Earth tip (~23°) is visual only.",
                "Caption",
            )
        )
    else:
        story.append(p(f"<b>{ORBITAL_IMAGE_UNAVAILABLE_NOTE}</b>"))
        story.append(p(snapshot_facts))
        if orbit_export_error:
            story.append(
                p(
                    f"Technical detail (for troubleshooting): {orbit_export_error}",
                    "Caption",
                )
            )

    # --- Heat flow ---
    story.append(
        block(
            section("7. Heat-flow analysis"),
            p(
                f"Instantaneous heat flows for <b>{viz_curve.name}</b> at the selected "
                f"sample (t = {snap.time_s / 60.0:.2f} min)."
            ),
            kv_table(
                [
                    ("Direct solar heating", f"{snap.q_solar_w:.2f} W"),
                    ("Earth infrared heating", f"{snap.q_earth_ir_w:.2f} W"),
                    ("Albedo (reflected sunlight)", f"{snap.q_albedo_w:.2f} W"),
                    (
                        "Internal equipment heating",
                        f"{snap.q_internal_w:.2f} W ({snap.internal_power_state})",
                    ),
                    ("Radiative heat rejection", f"{snap.q_radiated_w:.2f} W"),
                    ("Net thermal power", f"{snap.q_net_w:.2f} W"),
                ]
            ),
        )
    )
    story.append(image_flow(heat_png, width_mm=160, height_mm=62))
    story.append(
        p(
            "Figure: Heat-flow breakdown at the selected time. Positive values heat "
            "the spacecraft; radiative cooling is shown as a negative contribution "
            "on the chart.",
            "Caption",
        )
    )

    # --- Comparisons (omit for single) ---
    section_num = 8
    if study.mode != "single":
        story.append(section(f"{section_num}. Simulation comparisons"))
        section_num += 1
        metric_rows = comparison_metrics_rows(curves)
        story.append(
            multi_table(
                [
                    "Case",
                    "Initial (°C)",
                    "Min (°C)",
                    "Max (°C)",
                    "Final (°C)",
                    "Period (min)",
                ],
                [
                    [
                        row["Case"],
                        f"{row['Initial (°C)']:.2f}",
                        f"{row['Minimum (°C)']:.2f}",
                        f"{row['Maximum (°C)']:.2f}",
                        f"{row['Final (°C)']:.2f}",
                        f"{row['Period (min)']:.3f}",
                    ]
                    for row in metric_rows
                ],
            )
        )
        story.append(Spacer(1, 3 * mm))
        if study.mode == "environment_compare" and len(curves) == 3:
            story.append(p(environment_comparison_interpretation(curves)))
            summary = environment_comparison_summary_rows(curves)
            story.append(
                multi_table(
                    ["Case", "Environmental heating", "Final (°C)", "Change"],
                    [
                        [
                            r["Case"],
                            r["Environmental heating"],
                            f"{r['Final temperature (°C)']:.2f}",
                            r["Temperature change"],
                        ]
                        for r in summary
                    ],
                )
            )
            story.append(
                p(
                    "All three cases share the same spacecraft and orbit. Only the "
                    "Earth infrared and albedo inclusion flags differ "
                    f"({ENV_CASE_NAMES[0]} → {ENV_CASE_NAMES[1]} → {ENV_CASE_NAMES[2]})."
                )
            )

    # --- Numerical method ---
    story.append(
        block(
            section(f"{section_num}. Numerical method"),
            p(
                "The governing lumped energy balance is "
                "<b>m · cp · dT/dt = Q_solar + Q_earth_ir + Q_albedo + Q_internal − Q_radiated</b>. "
                "Time integration uses explicit Euler with a constant internal-power "
                "load. Orbital eclipse is evaluated with a cylindrical Earth-shadow test at each "
                "sample. Full equations and assumptions are documented in docs/MODEL.md."
            ),
        )
    )
    section_num += 1

    # --- Limitations ---
    lim_flow = [section(f"{section_num}. Model assumptions and limitations")]
    for item in (
        "The spacecraft is represented by one isothermal thermal node (single-node thermal model).",
        "Geometry is an idealized rectangular bus or effective-area model — not CAD flight hardware.",
        "Earth infrared radiation and albedo use simplified effective-area loads.",
        "Radiative rejection uses a simplified deep-space (0 K) sink.",
        "Orbital eclipse uses an ideal cylindrical shadow (no penumbra or refraction).",
        "Spacecraft orientations are prescribed geometries, not closed-loop attitude control.",
        "Visual-only 3D components (wings, dish, thrusters) do not participate thermally.",
        "Generic CubeSat configurations are illustrative educational envelopes.",
        "Results have not been correlated with flight temperature measurements.",
        "Outputs are not flight-qualified thermal predictions and are not NASA/ESA certified.",
    ):
        lim_flow.append(Paragraph(f"• {item}", styles["BodyJust"]))
    story.append(block(*lim_flow))
    section_num += 1

    # --- References ---
    story.append(
        block(
            section(f"{section_num}. Technical references"),
            p(
                "Primary engineering sources used by this project include NASA Preferred "
                "Practice GD-AP-2301 / PD-ED-1201 style environmental screening guidance, "
                "the Cal Poly CubeSat Design Specification (CDS) Rev 14.1 for mechanical "
                "envelopes, and public spacecraft thermal-control educational material "
                "(for example TFAWS / NTRS lecture notes on on-orbit thermal environments). "
                "See docs/REFERENCES.md and docs/SOURCE_TRACEABILITY.md for the full "
                "source register, access notes, and claim boundaries. This report does "
                "not claim endorsement or validation by NASA, ESA, or any spacecraft manufacturer."
            ),
            Spacer(1, 4 * mm),
            p(
                f"End of report · {SIMULATOR_NAME} v{SIMULATOR_VERSION} · {generated}",
                "Caption",
            ),
        )
    )

    def _on_page(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#8E8E93"))
        canvas.drawString(
            18 * mm,
            10 * mm,
            f"{SIMULATOR_NAME} v{SIMULATOR_VERSION}",
        )
        canvas.drawRightString(
            A4[0] - 18 * mm,
            10 * mm,
            f"Page {doc_.page}",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return EngineeringReportPdf(
        pdf_bytes=buffer.getvalue(),
        orbital_snapshot_included=orbit_png is not None,
        orbital_snapshot_error=orbit_export_error,
    )
