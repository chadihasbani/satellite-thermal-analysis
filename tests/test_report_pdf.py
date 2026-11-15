"""PDF engineering-report generation tests."""

from __future__ import annotations

import unittest
from io import BytesIO
from pathlib import Path

from satellite_thermal.gui_support import (
    GuiRunRequest,
    all_curves,
    apply_spacecraft_configuration,
    default_gui_request,
    default_inspect_curve_name,
    resolve_inspect_curve,
    run_baseline_comparison_mode,
    run_environment_comparison_mode,
    run_scenario_comparison_mode,
    run_single_mode,
)
from satellite_thermal.report_pdf import (
    ReportMeta,
    SIMULATOR_VERSION,
    build_engineering_report_pdf,
    default_report_meta,
    overall_baseline_delta_c,
    power_schedule_detail_rows,
)
from satellite_thermal.gui_support import temperature_metrics_c
from satellite_thermal.spacecraft_configurations import SpacecraftConfigurationId


def _short_request(**overrides):
    base = default_gui_request().__dict__
    base.update({"orbit_count": 1, "time_step_s": 30.0})
    base.update(overrides)
    return GuiRunRequest(**base)


def _pdf_text(pdf_bytes: bytes) -> str:
    """Extract plain text from a PDF for content assertions."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise unittest.SkipTest("pypdf is required for PDF text assertions") from exc

    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


class ReportPdfTests(unittest.TestCase):
    def test_single_mode_pdf_has_header_and_version(self) -> None:
        study = run_single_mode(_short_request())
        curve = study.primary
        pdf = build_engineering_report_pdf(
            study,
            viz_curve=curve,
            sample_index=0,
            meta=default_report_meta(
                SpacecraftConfigurationId.LEGACY_SIMPLIFIED.value
            ),
        )
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 8_000)
        text = _pdf_text(pdf)
        self.assertIn(SIMULATOR_VERSION, text)
        self.assertIn("Single Simulation", text)

    def test_environment_compare_pdf(self) -> None:
        study = run_environment_comparison_mode(_short_request())
        curves = all_curves(study)
        name = default_inspect_curve_name(study)
        curve = resolve_inspect_curve(curves, name, name)
        pdf = build_engineering_report_pdf(
            study,
            viz_curve=curve,
            sample_index=min(5, len(curve.result.time_s) - 1),
            meta=default_report_meta(),
        )
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn("Compare Heat Sources", _pdf_text(pdf))

    def test_scenario_compare_and_custom_spacecraft_pdf(self) -> None:
        request = _short_request(
            mass_kg=3.5,
            body_length_m=0.12,
            body_width_m=0.11,
            body_height_m=0.25,
            thermal_model="enhanced",
            attitude_mode="nadir_pointing",
        )
        study = run_scenario_comparison_mode(request)
        curves = all_curves(study)
        name = default_inspect_curve_name(study)
        curve = resolve_inspect_curve(curves, name, name)
        meta = ReportMeta(
            configuration_id=SpacecraftConfigurationId.CUSTOM.value,
            configuration_label="Custom Spacecraft",
            scenario_id="custom",
            scenario_label="Custom",
        )
        pdf = build_engineering_report_pdf(
            study,
            viz_curve=curve,
            sample_index=0,
            meta=meta,
        )
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn("Custom Spacecraft", _pdf_text(pdf))

    def test_baseline_compare_and_variable_power_pdf(self) -> None:
        request = _short_request(
            power_schedule_kind="periodic_high",
            periodic_period_s=600.0,
            periodic_high_duration_s=120.0,
            mass_kg=8.0,
        )
        study = run_baseline_comparison_mode(request)
        curves = all_curves(study)
        curve = curves[-1]
        pdf = build_engineering_report_pdf(
            study,
            viz_curve=curve,
            sample_index=0,
            meta=default_report_meta(),
        )
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn("Compare Configurations", _pdf_text(pdf))

    def test_cubesat_configuration_pdf(self) -> None:
        request = apply_spacecraft_configuration(
            _short_request(),
            SpacecraftConfigurationId.CUBESAT_3U,
        )
        study = run_single_mode(request)
        pdf = build_engineering_report_pdf(
            study,
            viz_curve=study.primary,
            sample_index=0,
            meta=default_report_meta(SpacecraftConfigurationId.CUBESAT_3U.value),
        )
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn("3U CubeSat", _pdf_text(pdf))

    def test_rejects_bad_sample_index(self) -> None:
        study = run_single_mode(_short_request())
        with self.assertRaises(IndexError):
            build_engineering_report_pdf(
                study,
                viz_curve=study.primary,
                sample_index=10_000_000,
                meta=default_report_meta(),
            )

    def test_baseline_delta_is_modified_minus_reference(self) -> None:
        request = _short_request(mass_kg=8.0)
        study = run_baseline_comparison_mode(request)
        curves = all_curves(study)
        expected = (
            temperature_metrics_c(study.primary.result)["final_c"]
            - temperature_metrics_c(study.companions[0].result)["final_c"]
        )
        self.assertAlmostEqual(overall_baseline_delta_c(study), expected, places=6)
        # Inspection case must not change the overall delta helper.
        for curve in curves:
            pdf = build_engineering_report_pdf(
                study,
                viz_curve=curve,
                sample_index=0,
                meta=default_report_meta(),
            )
            text = _pdf_text(pdf)
            self.assertIn("Modified − Reference", text)
            self.assertIn(f"{expected:+.2f} °C", text)

    def test_power_schedule_rows_cover_custom_intervals(self) -> None:
        request = _short_request(
            power_schedule_kind="custom_intervals",
            custom_intervals_text="0,120,10; 200,260,20",
            internal_heat_w=5.0,
        )
        rows = dict(power_schedule_detail_rows(request))
        self.assertEqual(rows["Internal power schedule"], "custom_intervals")
        self.assertIn("5", rows["Baseline power (outside intervals)"])
        self.assertTrue(any(key.startswith("Interval ") for key in rows))

    def test_scenario_compare_cover_lists_all_cases(self) -> None:
        study = run_scenario_comparison_mode(_short_request())
        curves = all_curves(study)
        name = default_inspect_curve_name(study)
        curve = resolve_inspect_curve(curves, name, name)
        pdf = build_engineering_report_pdf(
            study,
            viz_curve=curve,
            sample_index=0,
            meta=default_report_meta(scenario_id="custom"),
        )
        text = _pdf_text(pdf)
        self.assertIn("Cold screening", text)
        self.assertIn("Hot screening", text)
        self.assertIn("not a single", text)
        self.assertIn("Custom case", text)
        self.assertNotIn(
            "Single Simulation mode reports one case only",
            text,
        )


class ReportPdfSampleArtifacts(unittest.TestCase):
    """Write representative PDFs under outputs/ for manual visual review."""

    def test_write_sample_reports(self) -> None:
        out_dir = Path(__file__).resolve().parents[1] / "outputs"
        out_dir.mkdir(exist_ok=True)
        cases = [
            ("sample_single.pdf", run_single_mode(_short_request()), "legacy_simplified"),
            (
                "sample_heat_sources.pdf",
                run_environment_comparison_mode(_short_request()),
                "custom",
            ),
            (
                "sample_conditions.pdf",
                run_scenario_comparison_mode(
                    apply_spacecraft_configuration(
                        _short_request(thermal_model="enhanced"),
                        SpacecraftConfigurationId.CUBESAT_1U,
                    )
                ),
                "cubesat_1u",
            ),
            (
                "sample_custom_power.pdf",
                run_baseline_comparison_mode(
                    _short_request(
                        power_schedule_kind="custom_intervals",
                        custom_intervals_text="0,120,10; 200,260,20",
                        mass_kg=7.0,
                    )
                ),
                "custom",
            ),
        ]
        for filename, study, config_id in cases:
            curves = all_curves(study)
            name = default_inspect_curve_name(study)
            curve = resolve_inspect_curve(curves, name, name)
            mid = max(0, len(curve.result.time_s) // 4)
            pdf = build_engineering_report_pdf(
                study,
                viz_curve=curve,
                sample_index=mid,
                meta=default_report_meta(config_id),
            )
            path = out_dir / filename
            path.write_bytes(pdf)
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 5_000)


if __name__ == "__main__":
    unittest.main()
