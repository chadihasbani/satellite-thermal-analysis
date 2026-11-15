"""PDF engineering-report generation tests."""

from __future__ import annotations

import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from satellite_thermal import report_pdf as report_pdf_mod
from satellite_thermal.gui_support import (
    GuiRunRequest,
    all_curves,
    apply_spacecraft_configuration,
    default_gui_request,
    default_inspect_curve_name,
    resolve_inspect_curve,
    run_environment_comparison_mode,
    run_single_mode,
)
from satellite_thermal.report_pdf import (
    ORBITAL_IMAGE_UNAVAILABLE_NOTE,
    SIMULATOR_VERSION,
    build_engineering_report_pdf,
    default_report_meta,
    ensure_kaleido_browser_configured,
    export_orbital_snapshot_png,
    power_schedule_detail_rows,
)
from satellite_thermal.spacecraft_configurations import SpacecraftConfigurationId


def _short_request(**overrides):
    base = default_gui_request().__dict__
    base.update({"orbit_count": 1, "time_step_s": 30.0})
    base.update(overrides)
    return GuiRunRequest(**base)


def _pdf_text(pdf_bytes: bytes) -> str:
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
        report = build_engineering_report_pdf(
            study,
            viz_curve=study.primary,
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
        self.assertIn("Satellite Thermal Simulation", text)

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

    def test_power_schedule_rows_are_constant(self) -> None:
        rows = dict(power_schedule_detail_rows(_short_request(internal_heat_w=5.0)))
        self.assertEqual(rows["Internal heat schedule"], "constant")
        self.assertIn("5", rows["Internal heat dissipation"])


class ReportPdfOrbitalExportTests(unittest.TestCase):
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
        self.assertIn("Heat-flow", text)

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
    def test_write_sample_reports(self) -> None:
        out_dir = Path(__file__).resolve().parents[1] / "outputs"
        out_dir.mkdir(exist_ok=True)
        cases = [
            (
                "sample_single.pdf",
                run_single_mode(_short_request()),
                SpacecraftConfigurationId.LEGACY_SIMPLIFIED.value,
            ),
            (
                "sample_heat_sources.pdf",
                run_environment_comparison_mode(_short_request()),
                SpacecraftConfigurationId.CUSTOM.value,
            ),
        ]
        for filename, study, config_id in cases:
            curve = study.primary
            mid = len(curve.result.time_s) // 2
            pdf = _build_pdf_bytes(
                study,
                viz_curve=curve,
                sample_index=mid,
                meta=default_report_meta(config_id),
            )
            (out_dir / filename).write_bytes(pdf)
            self.assertTrue(pdf.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
