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
from unittest.mock import patch

from satellite_thermal import report_pdf as report_pdf_mod
from satellite_thermal.report_pdf import (
    ORBITAL_IMAGE_UNAVAILABLE_NOTE,
    ReportMeta,
    SIMULATOR_VERSION,
    build_engineering_report_pdf,
    default_report_meta,
    ensure_kaleido_browser_configured,
    export_orbital_snapshot_png,
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


def _build_pdf_bytes(*args, **kwargs) -> bytes:
    return build_engineering_report_pdf(*args, **kwargs).pdf_bytes


class ReportPdfTests(unittest.TestCase):
    def test_single_mode_pdf_has_header_and_version(self) -> None:
        study = run_single_mode(_short_request())
        curve = study.primary
        report = build_engineering_report_pdf(
            study,
            viz_curve=curve,
            sample_index=0,
            meta=default_report_meta(
                SpacecraftConfigurationId.LEGACY_SIMPLIFIED.value
            ),
        )
        pdf = report.pdf_bytes
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
        pdf = _build_pdf_bytes(
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
        pdf = _build_pdf_bytes(
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
        pdf = _build_pdf_bytes(
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
        pdf = _build_pdf_bytes(
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
            pdf = _build_pdf_bytes(
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
        pdf = _build_pdf_bytes(
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


class ReportPdfOrbitalExportTests(unittest.TestCase):
    """Orbital Plotly/Kaleido export success and graceful fallback."""

    def test_orbital_export_helper_success_when_renderer_works(self) -> None:
        study = run_single_mode(_short_request())
        from satellite_thermal.orbit_3d import build_orbit_3d_figure

        req = study.primary.request
        fig = build_orbit_3d_figure(
            result=study.primary.result,
            orbit=study.primary.orbit,
            sample_index=0,
            title=study.primary.name,
            attitude_mode=req.attitude_mode,
            body_length_m=req.body_length_m,
            body_width_m=req.body_width_m,
            body_height_m=req.body_height_m,
            thermal_model=req.thermal_model,
        )
        png, err = export_orbital_snapshot_png(fig, width=400, height=300)
        if png is None:
            self.skipTest(f"Orbital export unavailable in this environment: {err}")
        self.assertIsNone(err)
        self.assertTrue(png.startswith(b"\x89PNG"))

    def test_pdf_includes_orbital_image_when_export_succeeds(self) -> None:
        study = run_single_mode(_short_request())
        from io import BytesIO

        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (32, 24), color=(40, 90, 160)).save(buf, format="PNG")
        fake_png = buf.getvalue()
        with patch(
            "satellite_thermal.report_pdf.export_orbital_snapshot_png",
            return_value=(fake_png, None),
        ):
            report = build_engineering_report_pdf(
                study,
                viz_curve=study.primary,
                sample_index=0,
                meta=default_report_meta(),
            )
        self.assertTrue(report.orbital_snapshot_included)
        self.assertIsNone(report.orbital_snapshot_error)
        text = _pdf_text(report.pdf_bytes)
        self.assertNotIn(ORBITAL_IMAGE_UNAVAILABLE_NOTE, text)
        self.assertIn("Selected sample", text)
        self.assertIn("predicted spacecraft temperature", text.lower())

    def test_pdf_fallback_when_orbital_export_raises(self) -> None:
        study = run_single_mode(_short_request())
        with patch(
            "satellite_thermal.report_pdf.export_orbital_snapshot_png",
            return_value=(None, "ChromeNotFoundError: mock missing Chrome"),
        ):
            report = build_engineering_report_pdf(
                study,
                viz_curve=study.primary,
                sample_index=0,
                meta=default_report_meta(),
            )
        self.assertFalse(report.orbital_snapshot_included)
        self.assertIn("mock missing Chrome", report.orbital_snapshot_error or "")
        self.assertTrue(report.pdf_bytes.startswith(b"%PDF"))
        text = _pdf_text(report.pdf_bytes)
        self.assertIn(ORBITAL_IMAGE_UNAVAILABLE_NOTE, text)
        self.assertIn("Selected sample", text)
        self.assertIn("sunlit", text.lower())
        self.assertIn("Heat-flow", text)
        self.assertIn("Technical references", text)

    def test_export_helper_swallows_plotly_exception(self) -> None:
        class _Boom:
            def to_image(self, **_kwargs):
                raise RuntimeError("kaleido chrome missing")

        png, err = export_orbital_snapshot_png(_Boom())
        self.assertIsNone(png)
        self.assertIsNotNone(err)
        self.assertIn("kaleido chrome missing", err.lower())

    def test_ensure_kaleido_sets_browser_path_when_chromium_exists(self) -> None:
        report_pdf_mod._kaleido_browser_configured = False
        fake_chrome = Path(__file__).resolve()
        with patch.dict("os.environ", {}, clear=False):
            os_environ = __import__("os").environ
            os_environ.pop("BROWSER_PATH", None)
            os_environ.pop("CHROME_PATH", None)
            with patch(
                "satellite_thermal.report_pdf._discover_system_chrome_path",
                return_value=str(fake_chrome),
            ):
                configured = ensure_kaleido_browser_configured()
            self.assertEqual(configured, str(fake_chrome))
            self.assertEqual(os_environ.get("BROWSER_PATH"), str(fake_chrome))
        report_pdf_mod._kaleido_browser_configured = False

    def test_ensure_kaleido_missing_chrome_does_not_raise(self) -> None:
        report_pdf_mod._kaleido_browser_configured = False
        with patch.dict("os.environ", {}, clear=False):
            os_environ = __import__("os").environ
            os_environ.pop("BROWSER_PATH", None)
            os_environ.pop("CHROME_PATH", None)
            with patch(
                "satellite_thermal.report_pdf._discover_system_chrome_path",
                return_value=None,
            ):
                configured = ensure_kaleido_browser_configured()
            self.assertIsNone(configured)
        report_pdf_mod._kaleido_browser_configured = False


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
            pdf = _build_pdf_bytes(
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
