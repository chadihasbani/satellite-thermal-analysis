# Engineering PDF report

The Streamlit Export panel can prepare a multi-page PDF for the **most recently
completed simulation**.

## How to generate

1. Run a simulation.
2. Optionally move the time-sample slider to the orbital instant you want.
3. Open **Export**.
4. Click **Prepare Engineering Report (PDF)**.
5. Click **Download Engineering Report (PDF)**.

If sidebar settings change after a run, prepare/download is disabled until you
run again — the report must not mix new inputs with old results. All tables use
the **frozen** completed-run configuration.

## Contents

1. Cover page (mode, spacecraft, version, date; multi-case runs list each case)
2. Executive summary (final / min / max predicted spacecraft temperature)
3. Spacecraft configuration table
4. Orbital and environmental conditions
5. Internal equipment heating schedule (full reproducibility detail)
6. Temperature analysis + history figure
7. 3D orbital snapshot (Plotly static export via Kaleido)
8. Heat-flow breakdown at the selected sample
9. Mode-specific comparison section (omitted for Single Simulation)
10. Numerical method summary
11. Assumptions and limitations
12. Technical references

### Internal power documentation

| Schedule | Report includes |
| --- | --- |
| Constant | Actual constant power (W) |
| Eclipse-reduced | Sunlit power and eclipse power |
| Periodic | Baseline power, high power, period, high-power duration |
| Custom | Baseline power plus every interval start, end, and power |

### Comparison meaning

For Reference versus Modified studies, overall temperature differences are
always **Modified − Reference**. The selected inspection case only affects the
selected-time snapshot and instantaneous heat-flow panel — not the overall
comparison sign convention.

## Implementation

- Module: `satellite_thermal/report_pdf.py`
- PDF library: ReportLab
- 3D snapshot: Plotly `to_image` (Kaleido; may require Chrome/Chromium)
- Temperature / heat-flow figures: Matplotlib helpers in the package

Reports are generated in memory for download; they are not stored on the server.
Sample PDFs written during local checks land under `outputs/` (gitignored).

## Dependencies and hosting notes

- `requirements.txt` lists `reportlab`, `kaleido`, and `pypdf` (tests).
- Root `packages.txt` installs Debian `chromium` on Streamlit Community Cloud
  so Kaleido can render the optional 3D orbital snapshot without per-user
  Chrome downloads.
- The PDF builder sets `BROWSER_PATH` once when a system Chromium/Chrome
  executable is found (typical Cloud path: `/usr/bin/chromium`).
- GitHub Actions installs requirements and downloads Chrome via
  `asyncio.run(kaleido.get_chrome())` (hard failure if that step fails).
- If orbital-image export still fails, the PDF is still generated with a
  disclosed note that the 3D snapshot could not be included; temperature,
  heat-flow, configuration, and reference sections remain intact.
