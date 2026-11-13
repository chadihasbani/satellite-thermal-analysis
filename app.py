"""Streamlit GUI for the satellite thermal simulator.

Presentation layer only. All physics come from the verified solvers in
`satellite_thermal`.
"""

from __future__ import annotations

import streamlit as st

from satellite_thermal.gui_support import (
    GuiRunRequest,
    all_curves,
    changed_parameter_rows,
    comparison_metrics_rows,
    default_gui_request,
    figure_to_png_bytes,
    make_comparison_temperature_figure,
    make_gui_temperature_figure,
    make_heat_flow_bar_figure,
    request_fingerprint,
    run_baseline_comparison_mode,
    run_environment_comparison_mode,
    run_single_mode,
    temperature_history_csv,
    temperature_metrics_c,
    validate_gui_request,
)
from satellite_thermal.heat_flows import heat_flow_at_index
from satellite_thermal.orbit import orbital_period_s
from satellite_thermal.orbit_3d import build_orbit_3d_figure

st.set_page_config(
    page_title="Satellite Thermal Analysis",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
.block-container {
    padding-top: 2.4rem;
    padding-bottom: 3.5rem;
    max-width: 1120px;
}
h1 {
    font-weight: 700 !important;
    letter-spacing: -0.035em !important;
    font-size: 2.55rem !important;
    line-height: 1.1 !important;
    color: #1D1D1F !important;
    margin-bottom: 0.55rem !important;
}
h3 {
    font-weight: 600 !important;
    letter-spacing: -0.02em !important;
    color: #1D1D1F !important;
    margin-top: 1.6rem !important;
}
h5 {
    font-weight: 600 !important;
    letter-spacing: -0.01em !important;
    color: #1D1D1F !important;
}
.sta-lede {
    font-size: 1.12rem;
    line-height: 1.55;
    color: #1D1D1F;
    max-width: 42rem;
    margin: 0 0 0.55rem 0;
}
.sta-body {
    font-size: 0.98rem;
    line-height: 1.55;
    color: #6E6E73;
    max-width: 44rem;
    margin: 0 0 0.65rem 0;
}
.sta-tech {
    font-size: 0.82rem;
    color: #86868B;
    margin: 0 0 1.6rem 0;
}
.sta-section-label {
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #86868B;
    margin: 0 0 0.35rem 0;
}
div[data-testid="stMetric"] {
    background: #F5F5F7;
    border: none;
    border-radius: 14px;
    padding: 0.7rem 0.9rem;
}
div[data-testid="stMetric"] label {
    color: #6E6E73 !important;
    font-size: 0.74rem !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 1.28rem !important;
    font-weight: 600 !important;
    color: #1D1D1F !important;
    letter-spacing: -0.02em;
}
.sta-state-panel {
    background: #F5F5F7;
    border-radius: 16px;
    padding: 1rem 1.1rem 0.85rem 1.1rem;
    height: 520px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
.sta-state-panel h5 {
    margin: 0 0 0.55rem 0 !important;
    font-size: 0.95rem !important;
}
.sta-state-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.55rem;
}
.sta-state-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 0.55rem 0.7rem;
}
.sta-state-card .lbl {
    font-size: 0.72rem;
    color: #6E6E73;
    margin-bottom: 0.15rem;
}
.sta-state-card .val {
    font-size: 1.15rem;
    font-weight: 600;
    color: #1D1D1F;
    letter-spacing: -0.02em;
}
.sta-state-note {
    font-size: 0.75rem;
    color: #86868B;
    margin-top: 0.65rem;
}
section[data-testid="stSidebar"] {
    background: #F5F5F7;
    border-right: 1px solid #E8E8ED;
}
section[data-testid="stSidebar"] > div:first-child {
    padding-top: 0.35rem !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"],
section[data-testid="stSidebar"] .block-container,
section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
    padding-top: 0.25rem !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarHeader"],
section[data-testid="stSidebar"] [data-testid="stLogoSpacer"] {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}
div[data-testid="stSidebarNav"] { display: none; }
.stButton > button[kind="primary"] {
    border-radius: 980px !important;
    font-weight: 600 !important;
    padding: 0.55rem 1.1rem !important;
}
.stButton > button {
    border-radius: 980px !important;
}
div[data-testid="stTabs"] button {
    font-weight: 500;
}
hr { border: none; border-top: 1px solid #E8E8ED; margin: 1.4rem 0; }
</style>
""",
    unsafe_allow_html=True,
)

TERM_HELP = {
    "alpha": "Fraction of sunlight (and albedo) absorbed. Solar-band property.",
    "epsilon": "Infrared emissivity. This model sets α_ir = ε (Kirchhoff).",
    "areas": "Effective lumped-node area — not a CAD surface.",
    "earth_ir": "Absorbed Earth infrared (planetshine). Can remain on in eclipse.",
    "albedo": "Sunlight reflected from Earth. Zero in eclipse here.",
    "time_step": "Smaller steps resolve eclipses more finely; larger steps run faster.",
    "olr": "Outgoing longwave radiation from Earth used for planetshine.",
    "internal": "Onboard dissipation (≥ 0 W in this interface).",
}

MODE_LABELS = {
    "single": "Single simulation",
    "baseline_compare": "Reference vs modified",
    "environment_compare": "Environmental heating comparison",
}


def _init_state() -> None:
    if "study" not in st.session_state:
        st.session_state.study = None
    if "study_fingerprint" not in st.session_state:
        st.session_state.study_fingerprint = None
    if "sample_index" not in st.session_state:
        st.session_state.sample_index = 0
    if "gui_mode" not in st.session_state:
        st.session_state.gui_mode = "single"
    defaults = default_gui_request()
    for field, value in defaults.__dict__.items():
        key = f"gui_{field}"
        if key not in st.session_state:
            st.session_state[key] = value


def _apply_defaults() -> None:
    defaults = default_gui_request()
    for field, value in defaults.__dict__.items():
        st.session_state[f"gui_{field}"] = value


def _mode_blurb(mode: str) -> str:
    return {
        "single": "One orbital temperature history from your inputs.",
        "baseline_compare": "Compare your case with the default reference (matched orbits and time step).",
        "environment_compare": "Stack heating: solar+internal → +Earth IR → +albedo.",
    }[mode]


def _request_from_state() -> GuiRunRequest:
    return GuiRunRequest(
        mass_kg=float(st.session_state.gui_mass_kg),
        specific_heat_j_per_kg_k=float(st.session_state.gui_specific_heat_j_per_kg_k),
        initial_temperature_c=float(st.session_state.gui_initial_temperature_c),
        absorptivity=float(st.session_state.gui_absorptivity),
        emissivity=float(st.session_state.gui_emissivity),
        projected_area_m2=float(st.session_state.gui_projected_area_m2),
        radiating_area_m2=float(st.session_state.gui_radiating_area_m2),
        earth_facing_area_m2=float(st.session_state.gui_earth_facing_area_m2),
        albedo_area_m2=float(st.session_state.gui_albedo_area_m2),
        internal_heat_w=float(st.session_state.gui_internal_heat_w),
        solar_flux_w_per_m2=float(st.session_state.gui_solar_flux_w_per_m2),
        earth_olr_w_per_m2=float(st.session_state.gui_earth_olr_w_per_m2),
        earth_bond_albedo=float(st.session_state.gui_earth_bond_albedo),
        altitude_km=float(st.session_state.gui_altitude_km),
        orbit_count=int(st.session_state.gui_orbit_count),
        time_step_s=float(st.session_state.gui_time_step_s),
        include_earth_infrared=bool(st.session_state.gui_include_earth_infrared),
        include_albedo=bool(st.session_state.gui_include_albedo),
    )


def _run_study(mode: str, request: GuiRunRequest):
    validate_gui_request(request)
    if mode == "single":
        return run_single_mode(request)
    if mode == "baseline_compare":
        return run_baseline_comparison_mode(request)
    return run_environment_comparison_mode(request)


_init_state()

# --- Header ---
st.title("Satellite Thermal Analysis")
st.markdown(
    '<p class="sta-lede">Explore how a satellite’s temperature changes as it travels around Earth.</p>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="sta-body">This interactive simulator models the heating and cooling of a '
    "simplified spacecraft in low Earth orbit, accounting for direct sunlight, "
    "Earth’s infrared radiation, reflected solar energy, internal heat generation, "
    "and radiative cooling.</p>",
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="sta-body">Adjust spacecraft properties, compare thermal scenarios, '
    "and explore the results through interactive temperature graphs and a "
    "synchronized 3D orbital visualization.</p>",
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="sta-tech">Built with Python · Interface: Streamlit · '
    "Scientific plots: Matplotlib · 3D visualization: Plotly</p>",
    unsafe_allow_html=True,
)

# --- Sidebar ---
with st.sidebar:
    st.markdown("### Configure")
    st.caption("Defaults are ready to run. Results update only when you run.")

    mode = st.radio(
        "Simulation mode",
        options=["single", "baseline_compare", "environment_compare"],
        format_func=lambda value: MODE_LABELS[value],
        key="gui_mode",
    )
    st.caption(_mode_blurb(mode))

    st.markdown("#### Orbit")
    st.number_input("Number of orbits", 1, 20, step=1, key="gui_orbit_count")
    st.number_input(
        "Time step (s)",
        min_value=0.1,
        max_value=60.0,
        step=1.0,
        key="gui_time_step_s",
        help=TERM_HELP["time_step"],
    )
    st.number_input(
        "Altitude (km)",
        min_value=200.0,
        max_value=2000.0,
        step=50.0,
        key="gui_altitude_km",
    )

    st.markdown("#### Spacecraft")
    st.number_input(
        "Initial temperature (°C)",
        min_value=-273.14,
        step=1.0,
        key="gui_initial_temperature_c",
        help="Must stay above absolute zero (−273.15 °C).",
    )
    st.number_input(
        "Internal heat (W)",
        min_value=0.0,
        step=1.0,
        key="gui_internal_heat_w",
        help=TERM_HELP["internal"],
    )
    st.slider(
        "Solar absorptivity α",
        min_value=0.0,
        max_value=1.0,
        step=0.01,
        key="gui_absorptivity",
        help=TERM_HELP["alpha"],
    )
    st.slider(
        "IR emissivity ε (= α_ir)",
        min_value=0.0,
        max_value=1.0,
        step=0.01,
        key="gui_emissivity",
        help=TERM_HELP["epsilon"],
    )

    st.markdown("#### Environment")
    env_disabled = mode == "environment_compare"
    st.checkbox(
        "Include Earth IR",
        key="gui_include_earth_infrared",
        help=TERM_HELP["earth_ir"],
        disabled=env_disabled,
    )
    st.checkbox(
        "Include albedo",
        key="gui_include_albedo",
        help=TERM_HELP["albedo"],
        disabled=env_disabled,
    )
    if env_disabled:
        st.caption("Heating flags follow the A / B / C comparison cases.")

    with st.expander("Advanced parameters"):
        st.number_input("Mass (kg)", min_value=0.1, step=0.5, key="gui_mass_kg")
        st.number_input(
            "Specific heat cp (J/(kg·K))",
            min_value=1.0,
            step=50.0,
            key="gui_specific_heat_j_per_kg_k",
        )
        st.number_input(
            "Projected solar area (m²)",
            min_value=1e-4,
            format="%.4f",
            key="gui_projected_area_m2",
            help=TERM_HELP["areas"],
        )
        st.number_input(
            "Radiating area (m²)",
            min_value=1e-4,
            format="%.4f",
            key="gui_radiating_area_m2",
            help=TERM_HELP["areas"],
        )
        st.number_input(
            "Earth-facing area (m²)",
            min_value=1e-4,
            format="%.4f",
            key="gui_earth_facing_area_m2",
            help=TERM_HELP["areas"],
        )
        st.number_input(
            "Albedo area (m²)",
            min_value=1e-4,
            format="%.4f",
            key="gui_albedo_area_m2",
            help=TERM_HELP["areas"],
        )
        st.number_input(
            "Solar flux S (W/m²)",
            min_value=0.0,
            step=1.0,
            key="gui_solar_flux_w_per_m2",
        )
        st.number_input(
            "Earth OLR E_olr (W/m²)",
            min_value=0.0,
            step=1.0,
            key="gui_earth_olr_w_per_m2",
            help=TERM_HELP["olr"],
        )
        st.slider(
            "Earth Bond albedo a",
            min_value=0.0,
            max_value=1.0,
            step=0.01,
            key="gui_earth_bond_albedo",
        )

    st.divider()
    run_clicked = st.button("Run Simulation", type="primary", use_container_width=True)
    # on_click runs before widgets are created on the next run, which avoids
    # StreamlitWidgetAlreadyInstantiatedError when resetting keyed inputs.
    st.button(
        "Reset to defaults",
        use_container_width=True,
        on_click=_apply_defaults,
    )
    if st.session_state.study is not None:
        st.caption("Displayed results update only after a successful run.")

request = _request_from_state()
if mode == "environment_compare":
    request = GuiRunRequest(
        **{
            **request.__dict__,
            "include_earth_infrared": True,
            "include_albedo": True,
        }
    )

if run_clicked:
    try:
        with st.spinner("Running simulation…"):
            study = _run_study(mode, request)
        st.session_state.study = study
        st.session_state.study_fingerprint = request_fingerprint(mode, request)
        st.session_state.sample_index = 0
        st.session_state.time_min = 0.0
        st.success("Simulation complete.")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Simulation failed: {exc}")

study = st.session_state.study
if study is None:
    st.info(
        "Choose a mode in the sidebar if you want, then click **Run Simulation**. "
        "Default parameters are already set."
    )
    with st.expander("What the heating terms mean"):
        st.markdown(
            """
| Term | Meaning |
| --- | --- |
| **Solar** | Direct sunlight absorbed (zero in eclipse) |
| **Earth IR** | Infrared from Earth absorbed by the spacecraft |
| **Albedo** | Sunlight reflected from Earth |
| **Internal** | Onboard dissipation |
| **Radiated** | Heat emitted to space (`ε σ A T⁴`) |
            """
        )
    st.stop()

inputs_changed = (
    st.session_state.study_fingerprint is not None
    and st.session_state.study_fingerprint != request_fingerprint(mode, request)
)
if inputs_changed:
    st.warning(
        "Inputs have changed. Run Simulation to update these results. "
        "Plots below are from the last completed run."
    )

curves = all_curves(study)
primary = study.primary
n_samples = len(primary.result.time_s)
primary_metrics = temperature_metrics_c(primary.result)
times_min = [t / 60.0 for t in primary.result.time_s]
period = orbital_period_s(primary.orbit)

# --- Key results ---
st.markdown(
    f'<p class="sta-section-label">Results · {MODE_LABELS.get(study.mode, study.mode)}</p>',
    unsafe_allow_html=True,
)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Final temperature", f"{primary_metrics['final_c']:.2f} °C")
m2.metric("Minimum", f"{primary_metrics['minimum_c']:.2f} °C")
m3.metric("Maximum", f"{primary_metrics['maximum_c']:.2f} °C")
m4.metric("Orbit period", f"{primary.result.period_s/60.0:.2f} min")

if study.mode == "baseline_compare" and study.companions:
    baseline_final = temperature_metrics_c(study.companions[0].result)["final_c"]
    delta = primary_metrics["final_c"] - baseline_final
    st.caption(f"Change vs reference final temperature: **{delta:+.3f} °C**")
elif study.mode == "environment_compare" and len(curves) == 3:
    finals = [temperature_metrics_c(curve.result)["final_c"] for curve in curves]
    st.caption(
        f"**A** solar+internal {finals[0]:.2f} °C · "
        f"**B** +Earth IR {finals[1]:.2f} °C ({finals[1]-finals[0]:+.2f} K) · "
        f"**C** +albedo {finals[2]:.2f} °C ({finals[2]-finals[1]:+.2f} K)"
    )

# --- Time scrubber ---
st.markdown('<p class="sta-section-label">Time</p>', unsafe_allow_html=True)
max_t = times_min[-1] if times_min else 0.0
step_t = (times_min[1] - times_min[0]) if len(times_min) > 1 else 0.1
if "time_min" not in st.session_state:
    st.session_state.time_min = float(times_min[0])
st.session_state.time_min = min(float(st.session_state.time_min), float(max_t))
selected_t = st.slider(
    "Simulation time (minutes)",
    min_value=0.0,
    max_value=float(max_t),
    step=float(step_t),
    key="time_min",
    label_visibility="collapsed",
)
sample_index = min(range(len(times_min)), key=lambda i: abs(times_min[i] - selected_t))
st.session_state.sample_index = sample_index
orbit_number_primary = primary.result.time_s[sample_index] / period + 1.0
status_now = "Eclipsed" if primary.result.in_eclipse[sample_index] else "Sunlit"
st.caption(
    f"{times_min[sample_index]:.2f} min · "
    f"orbit {orbit_number_primary:.2f} of {primary.request.orbit_count} · "
    f"{status_now}"
)

if len(curves) > 1:
    source_names = [curve.name for curve in curves]
    selected_name = st.selectbox(
        "Curve for 3D view and heat flow",
        options=source_names,
        index=source_names.index(primary.name),
    )
    viz_curve = next(curve for curve in curves if curve.name == selected_name)
else:
    viz_curve = primary

if len(viz_curve.result.time_s) == n_samples:
    viz_index = sample_index
else:
    target_t = primary.result.time_s[sample_index]
    viz_index = min(
        range(len(viz_curve.result.time_s)),
        key=lambda i: abs(viz_curve.result.time_s[i] - target_t),
    )

snap = heat_flow_at_index(
    result=viz_curve.result,
    index=viz_index,
    thermal=viz_curve.thermal,
    orbit=viz_curve.orbit,
    include_earth_infrared=viz_curve.request.include_earth_infrared,
    include_albedo=viz_curve.request.include_albedo,
    earth_infrared=viz_curve.earth_infrared,
    albedo=viz_curve.albedo,
)
viz_period = orbital_period_s(viz_curve.orbit)
orbit_number = snap.time_s / viz_period + 1.0

# --- Temperature history ---
st.markdown("### Temperature history")
st.caption("Temperature over time. Grey bands are eclipse periods. The red marker follows the time control.")
if study.mode == "single":
    temp_fig = make_gui_temperature_figure(
        primary.result,
        marker_index=sample_index,
        title="Orbital temperature",
    )
elif study.mode == "baseline_compare":
    temp_fig = make_comparison_temperature_figure(
        curves,
        marker_index=viz_index,
        marker_curve_name=viz_curve.name,
        title="Reference vs modified",
        shade_from=curves[0],
    )
    altitudes = {round(curve.orbit.altitude_m) for curve in curves}
    if len(altitudes) > 1:
        st.info(
            f"Eclipse shading follows **{curves[0].name}** only because "
            "the compared cases use different altitudes."
        )
else:
    temp_fig = make_comparison_temperature_figure(
        curves,
        marker_index=viz_index,
        marker_curve_name=viz_curve.name,
        title="Environmental heating comparison",
        shade_from=curves[0],
    )
st.pyplot(temp_fig, clear_figure=True, use_container_width=True)

# --- 3D + thermal state ---
st.markdown("### Orbit and thermal state")
st.caption(
    "Heat flows: positive values heat the spacecraft; radiated power cools it. "
    "Net = all heat inputs − radiated."
)
viz_left, viz_right = st.columns([1.3, 0.9], gap="medium")
with viz_left:
    fig3d = build_orbit_3d_figure(
        result=viz_curve.result,
        orbit=viz_curve.orbit,
        sample_index=viz_index,
        title=viz_curve.name,
    )
    st.plotly_chart(
        fig3d,
        use_container_width=True,
        config={
            "displayModeBar": True,
            "responsive": True,
            "scrollZoom": False,
        },
    )

with viz_right:
    status_text = "Eclipsed" if snap.in_eclipse else "Sunlit"
    st.markdown(
        f"""
<div class="sta-state-panel">
  <div>
    <h5>At selected time</h5>
    <div class="sta-state-grid">
      <div class="sta-state-card"><div class="lbl">Temperature</div><div class="val">{snap.temperature_c:.2f} °C</div></div>
      <div class="sta-state-card"><div class="lbl">Status</div><div class="val">{status_text}</div></div>
      <div class="sta-state-card"><div class="lbl">Time</div><div class="val">{snap.time_s/60.0:.2f} min</div></div>
      <div class="sta-state-card"><div class="lbl">Orbit</div><div class="val">{orbit_number:.2f}</div></div>
    </div>
  </div>
  <div>
    <h5>Heat flows</h5>
    <div class="sta-state-grid">
      <div class="sta-state-card"><div class="lbl">Solar</div><div class="val">{snap.q_solar_w:.2f} W</div></div>
      <div class="sta-state-card"><div class="lbl">Earth IR</div><div class="val">{snap.q_earth_ir_w:.2f} W</div></div>
      <div class="sta-state-card"><div class="lbl">Albedo</div><div class="val">{snap.q_albedo_w:.2f} W</div></div>
      <div class="sta-state-card"><div class="lbl">Internal</div><div class="val">{snap.q_internal_w:.2f} W</div></div>
      <div class="sta-state-card"><div class="lbl">Radiated</div><div class="val">{snap.q_radiated_w:.2f} W</div></div>
      <div class="sta-state-card"><div class="lbl">Net</div><div class="val">{snap.q_net_w:.2f} W</div></div>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

st.pyplot(make_heat_flow_bar_figure(snap), clear_figure=True, use_container_width=True)
st.caption(
    "3D view is illustrative — craft enlarged, not to scale. "
    "Position and eclipse come from the orbit model; attitude is not simulated."
)

# --- Details ---
st.markdown("### Details")
detail_tabs = st.tabs(["Analysis", "Assumptions", "Export"])

with detail_tabs[0]:
    st.dataframe(
        comparison_metrics_rows(curves),
        hide_index=True,
        use_container_width=True,
    )
    if study.mode == "environment_compare" and len(curves) == 3:
        finals = [temperature_metrics_c(curve.result)["final_c"] for curve in curves]
        st.caption(
            f"A {finals[0]:.2f} °C · "
            f"Earth IR effect {finals[1]-finals[0]:+.2f} K · "
            f"albedo effect {finals[2]-finals[1]:+.2f} K"
        )
    if study.mode == "baseline_compare" and study.companions:
        rows = changed_parameter_rows(study.companions[0].request, primary.request)
        if rows:
            st.markdown("##### Changed parameters")
            st.dataframe(rows, hide_index=True, use_container_width=True)
        else:
            st.caption("No parameter differences from the matched reference case.")
    elif study.mode == "environment_compare":
        st.markdown(
            """
| Case | Heating |
| --- | --- |
| **A** | Solar + internal |
| **B** | A + Earth IR |
| **C** | B + albedo |
            """
        )

with detail_tabs[1]:
    st.markdown(
        """
- Single lumped thermal node; areas are model inputs, not CAD.
- Emission uses `εσAT⁴` to a 0 K sink; Earth IR and albedo are separate loads.
- Eclipse uses a cylindrical Earth shadow (beta = 0).
- 3D spacecraft geometry is illustrative and enlarged.
- No detailed attitude dynamics and no flight-data validation.
- Sidebar edits do not erase results; a new solve runs only on **Run Simulation**.
        """
    )

with detail_tabs[2]:
    st.caption("Downloads use the last completed run at the selected time marker.")
    if study.mode == "single":
        export_temp = make_gui_temperature_figure(
            primary.result,
            marker_index=sample_index,
            title="Orbital temperature",
        )
    elif study.mode == "baseline_compare":
        export_temp = make_comparison_temperature_figure(
            curves,
            marker_index=viz_index,
            marker_curve_name=viz_curve.name,
            title="Reference vs modified",
            shade_from=curves[0],
        )
    else:
        export_temp = make_comparison_temperature_figure(
            curves,
            marker_index=viz_index,
            marker_curve_name=viz_curve.name,
            title="Environmental heating comparison",
            shade_from=curves[0],
        )
    export_heat = make_heat_flow_bar_figure(snap)
    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button(
            "Temperature CSV",
            data=temperature_history_csv(curves),
            file_name="temperature_history.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with d2:
        st.download_button(
            "Temperature PNG",
            data=figure_to_png_bytes(export_temp),
            file_name="temperature_history.png",
            mime="image/png",
            use_container_width=True,
        )
    with d3:
        st.download_button(
            "Heat-flow PNG",
            data=figure_to_png_bytes(export_heat),
            file_name="heat_flow.png",
            mime="image/png",
            use_container_width=True,
        )
