"""Streamlit GUI for the satellite thermal simulator.

Presentation layer only. All physics come from the verified solvers in
`satellite_thermal`.
"""

from __future__ import annotations

import streamlit as st

from satellite_thermal.gui_support import (
    GuiRunRequest,
    all_curves,
    apply_spacecraft_configuration,
    clamp_sample_index,
    comparison_metrics_rows,
    default_gui_request,
    default_inspect_curve_name,
    environment_comparison_interpretation,
    environment_comparison_summary_rows,
    figure_to_png_bytes,
    geometry_from_request,
    make_comparison_temperature_figure,
    make_gui_temperature_figure,
    make_heat_flow_bar_figure,
    power_schedule_from_request,
    request_fingerprint,
    resolve_inspect_curve,
    run_environment_comparison_mode,
    run_single_mode,
    temperature_history_csv,
    temperature_metrics_c,
)
from satellite_thermal.spacecraft_configurations import (
    SpacecraftConfigurationId,
    build_spacecraft_configuration,
    configuration_controls_locked,
    configuration_select_options,
    primary_configuration_select_options,
    sync_session_values_from_configuration,
)
from satellite_thermal.heat_flows import heat_flow_at_index
from satellite_thermal.orbit import orbital_period_s
from satellite_thermal.orbit_3d import build_orbit_3d_figure
from satellite_thermal.report_pdf import (
    ReportMeta,
    SIMULATOR_VERSION,
    build_engineering_report_pdf,
    ensure_kaleido_browser_configured,
)
from satellite_thermal.attitude import AttitudeMode

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
    padding-top: 1.75rem;
    padding-bottom: 3.0rem;
    max-width: 1120px;
}
h1 {
    font-weight: 700 !important;
    letter-spacing: -0.035em !important;
    font-size: 2.15rem !important;
    line-height: 1.15 !important;
    color: #1D1D1F !important;
    margin-bottom: 0.35rem !important;
}
h3 {
    font-weight: 600 !important;
    letter-spacing: -0.02em !important;
    color: #1D1D1F !important;
    margin-top: 1.25rem !important;
}
.sta-lede {
    font-size: 1.05rem;
    line-height: 1.5;
    color: #1D1D1F;
    margin: 0 0 0.35rem 0;
}
.sta-body {
    font-size: 0.95rem;
    line-height: 1.55;
    color: #6E6E73;
    margin: 0 0 0.85rem 0;
}
.sta-section-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: #86868B;
    margin: 0.4rem 0 0.45rem 0;
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
    height: 560px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
.sta-state-panel h5 {
    margin: 0 0 0.55rem 0 !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: #1D1D1F !important;
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
    font-size: 1.05rem;
    font-weight: 600;
    color: #1D1D1F;
    letter-spacing: -0.02em;
}
.sta-heat-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 0.45rem;
    margin-top: 0.55rem;
}
.sta-heat-card {
    background: #FFFFFF;
    border-radius: 10px;
    padding: 0.45rem 0.55rem;
}
.sta-heat-card .lbl { font-size: 0.68rem; color: #6E6E73; }
.sta-heat-card .val { font-size: 0.92rem; font-weight: 600; color: #1D1D1F; }
div[data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: #1D1D1F !important;
    border: none !important;
}
</style>
""",
    unsafe_allow_html=True,
)

MODE_LABELS = {
    "single": "Satellite Thermal Simulation",
    "environment_compare": "Compare Heat Sources",
}

TERM_HELP = {
    "spacecraft_configuration": (
        "Preset spacecraft. Reference Satellite uses the Version 1 fixed-area "
        "legacy model. 1U/3U CubeSats use CDS Rev 14.1 envelope sizes with "
        "face-based (enhanced) solar heating. Custom lets you edit all fields."
    ),
    "altitude": (
        "Orbital altitude above Earth’s surface (km). Higher orbits have longer "
        "periods and usually shorter eclipses. Used for circular-orbit timing "
        "and the cylindrical eclipse model."
    ),
    "beta": (
        "Sun–orbit angle β (°): angle between the Sun direction and the orbital "
        "plane. β = 0° gives the longest eclipse; large |β| can mean continuous "
        "sunlight under this model."
    ),
    "mode": (
        "Satellite Thermal Simulation runs one case. Compare Heat Sources runs "
        "the same spacecraft three times: sunlight only, then +Earth infrared, "
        "then +Earth infrared and albedo."
    ),
    "internal": (
        "Constant onboard equipment dissipation (W). Adds continuous heating in "
        "the energy balance. This simplified model does not vary power with "
        "eclipse or duty cycle."
    ),
    "mass": "Spacecraft mass (kg). With specific heat, sets thermal capacitance m·cp.",
    "cp": (
        "Effective specific heat capacity (J/(kg·K)). Educational lumped value, "
        "not a material datasheet for every component."
    ),
    "t0": "Initial uniform spacecraft temperature (°C) at the start of the run.",
    "alpha": (
        "Solar absorptivity α (0–1). Fraction of incident sunlight absorbed. "
        "Higher α increases solar heating."
    ),
    "epsilon": (
        "Infrared emissivity ε (0–1). Controls radiative cooling. Infrared "
        "absorptivity for Earth IR uses Kirchhoff’s law (α_IR = ε)."
    ),
    "areas": (
        "Effective areas (m²) used by the legacy heating path and for Earth IR / "
        "albedo loads in both models. Enhanced solar heating uses face geometry "
        "instead of projected solar area."
    ),
    "dims": "Bus length, width, and height (m) for enhanced face-based solar heating and the 3D view.",
    "thermal_model": (
        "Legacy: fixed projected and radiating areas (Version 1 reference). "
        "Enhanced: six bus faces with fixed inertial orientation for solar heating."
    ),
    "solar": "Solar irradiance S at the spacecraft (W/m²). Typical LEO value ≈ 1361.",
    "olr": "Earth outgoing longwave radiation intensity (W/m²) for Earth infrared heating.",
    "albedo": "Earth Bond albedo (0–1). Fraction of sunlight reflected by Earth.",
    "time_step": (
        "Nominal integrator time step (s). Smaller steps resolve eclipse edges more "
        "finely but create more samples."
    ),
    "single_node": (
        "Single-node model: the whole spacecraft is one uniform temperature. "
        "Component-level gradients are not resolved."
    ),
}


def _init_state() -> None:
    if "study" not in st.session_state:
        st.session_state.study = None
    if "study_fingerprint" not in st.session_state:
        st.session_state.study_fingerprint = None
    if "study_report_meta" not in st.session_state:
        st.session_state.study_report_meta = None
    if "sample_index" not in st.session_state:
        st.session_state.sample_index = 0
    if "gui_mode" not in st.session_state:
        st.session_state.gui_mode = "single"
    if "inspect_case_name" not in st.session_state:
        st.session_state.inspect_case_name = None
    if "gui_spacecraft_configuration" not in st.session_state:
        st.session_state.gui_spacecraft_configuration = (
            SpacecraftConfigurationId.LEGACY_SIMPLIFIED.value
        )
    defaults = default_gui_request()
    for field, value in defaults.__dict__.items():
        key = f"gui_{field}"
        if key not in st.session_state:
            st.session_state[key] = value
    st.session_state.gui_attitude_mode = AttitudeMode.FIXED_INERTIAL.value
    if "_configuration_sync_id" not in st.session_state:
        updates = sync_session_values_from_configuration(
            st.session_state.gui_spacecraft_configuration
        )
        for key, value in updates.items():
            st.session_state[key] = value
        st.session_state._configuration_sync_id = (
            st.session_state.gui_spacecraft_configuration
        )


def _apply_defaults() -> None:
    defaults = default_gui_request()
    for field, value in defaults.__dict__.items():
        st.session_state[f"gui_{field}"] = value
    st.session_state.gui_spacecraft_configuration = (
        SpacecraftConfigurationId.LEGACY_SIMPLIFIED.value
    )
    updates = sync_session_values_from_configuration(
        SpacecraftConfigurationId.LEGACY_SIMPLIFIED.value
    )
    for key, value in updates.items():
        st.session_state[key] = value
    st.session_state._configuration_sync_id = (
        SpacecraftConfigurationId.LEGACY_SIMPLIFIED.value
    )
    st.session_state.gui_mode = "single"
    st.session_state.gui_attitude_mode = AttitudeMode.FIXED_INERTIAL.value


def _apply_enhanced_cube() -> None:
    """Switch to the illustrative enhanced cube via button callback."""
    cube_id = SpacecraftConfigurationId.ILLUSTRATIVE_CUBE.value
    st.session_state.gui_spacecraft_configuration = cube_id
    updates = sync_session_values_from_configuration(cube_id)
    for key, value in updates.items():
        st.session_state[key] = value
    st.session_state._configuration_sync_id = cube_id
    st.session_state.gui_attitude_mode = AttitudeMode.FIXED_INERTIAL.value


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
        beta_deg=float(st.session_state.gui_beta_deg),
        orbit_count=int(st.session_state.gui_orbit_count),
        time_step_s=float(st.session_state.gui_time_step_s),
        include_earth_infrared=bool(st.session_state.gui_include_earth_infrared),
        include_albedo=bool(st.session_state.gui_include_albedo),
        thermal_model=str(st.session_state.gui_thermal_model),
        attitude_mode=AttitudeMode.FIXED_INERTIAL.value,
        body_length_m=float(st.session_state.gui_body_length_m),
        body_width_m=float(st.session_state.gui_body_width_m),
        body_height_m=float(st.session_state.gui_body_height_m),
    )


def _run_study(mode: str, request: GuiRunRequest):
    if mode == "environment_compare":
        return run_environment_comparison_mode(request)
    return run_single_mode(request)


def _sync_configuration(configuration_id: str) -> bool:
    config_locked = configuration_controls_locked(configuration_id)
    if configuration_id != st.session_state.get("_configuration_sync_id"):
        updates = sync_session_values_from_configuration(configuration_id)
        for key, value in updates.items():
            st.session_state[key] = value
        st.session_state._configuration_sync_id = configuration_id
        st.session_state.gui_attitude_mode = AttitudeMode.FIXED_INERTIAL.value
    return config_locked


_init_state()

# --- Header ---
st.title("Satellite Thermal Analysis")
st.markdown(
    '<p class="sta-lede">Predict spacecraft temperature through sunlight and eclipse '
    "in low Earth orbit.</p>",
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="sta-body">This educational single-node model balances heating from the '
    "Sun, Earth infrared, reflected sunlight, and onboard equipment against radiative "
    "cooling to space. Configure the spacecraft and orbit, compare heat sources, and "
    f"download an engineering PDF report. {TERM_HELP['single_node']}</p>",
    unsafe_allow_html=True,
)
st.markdown(
    f'<p class="sta-body" style="font-size:0.88rem;color:#86868B;">'
    f"Version {SIMULATOR_VERSION} · Python · Streamlit · Matplotlib · Plotly · "
    "Open-source · Reviewed engineering model</p>",
    unsafe_allow_html=True,
)

# --- Sidebar ---
with st.sidebar:
    st.markdown("### Spacecraft")
    primary_options = primary_configuration_select_options()
    all_options = configuration_select_options()
    all_labels = {item[0]: item[1] for item in all_options}
    primary_ids = [item[0] for item in primary_options]
    current_config = str(st.session_state.gui_spacecraft_configuration)
    spacecraft_options = list(primary_ids)
    if current_config not in spacecraft_options:
        spacecraft_options.append(current_config)

    configuration_id = st.selectbox(
        "Spacecraft configuration",
        options=spacecraft_options,
        format_func=lambda value: all_labels.get(value, value),
        key="gui_spacecraft_configuration",
        help=TERM_HELP["spacecraft_configuration"],
    )
    config_locked = _sync_configuration(configuration_id)
    if configuration_id == SpacecraftConfigurationId.LEGACY_SIMPLIFIED.value:
        st.caption("Version 1 educational reference (fixed-area legacy model).")
    elif configuration_id == SpacecraftConfigurationId.ILLUSTRATIVE_CUBE.value:
        st.caption("Same size class as the reference, with face-based solar heating.")
    elif configuration_id != SpacecraftConfigurationId.CUSTOM.value:
        st.caption(build_spacecraft_configuration(configuration_id).summary)

    st.markdown("### Orbit")
    st.number_input(
        "Orbital altitude (km)",
        min_value=200.0,
        max_value=2000.0,
        step=50.0,
        key="gui_altitude_km",
        help=TERM_HELP["altitude"],
    )
    st.slider(
        "Sun–orbit angle (β)",
        min_value=-90.0,
        max_value=90.0,
        step=1.0,
        key="gui_beta_deg",
        help=TERM_HELP["beta"],
    )

    st.markdown("### Simulation")
    mode = st.selectbox(
        "Analysis mode",
        options=["single", "environment_compare"],
        format_func=lambda value: MODE_LABELS[value],
        key="gui_mode",
        help=TERM_HELP["mode"],
    )
    if mode == "single":
        st.caption("One spacecraft and orbit — temperature, heat flows, and 3D view.")
    else:
        st.caption(
            "Same spacecraft three times: sunlight only → +Earth IR → +Earth IR & albedo."
        )
    st.number_input(
        "Number of orbits",
        1,
        20,
        step=1,
        key="gui_orbit_count",
        help="How many full revolutions around Earth to simulate.",
    )
    st.number_input(
        "Internal power (W)",
        min_value=0.0,
        max_value=500.0,
        step=0.5,
        key="gui_internal_heat_w",
        help=TERM_HELP["internal"],
    )

    run_clicked = st.button("Run Simulation", type="primary", use_container_width=True)
    st.button("Reset to defaults", use_container_width=True, on_click=_apply_defaults)

    with st.expander("Advanced settings", expanded=False):
        st.caption("Secondary inputs. Presets lock geometry and optics until you choose Custom.")
        st.button(
            "Use Enhanced 0.1 m cube",
            use_container_width=True,
            on_click=_apply_enhanced_cube,
            help=(
                "Switch to the enhanced face-based model on a 0.1 m cube "
                "(same size class as the Reference Satellite)."
            ),
        )
        st.selectbox(
            "Thermal model",
            options=["legacy", "enhanced"],
            format_func=lambda value: (
                "Legacy (fixed areas, V1 reference)"
                if value == "legacy"
                else "Enhanced (face-based solar)"
            ),
            key="gui_thermal_model",
            help=TERM_HELP["thermal_model"],
            disabled=config_locked,
        )
        c1, c2 = st.columns(2)
        with c1:
            st.number_input(
                "Mass (kg)",
                min_value=0.01,
                step=0.1,
                key="gui_mass_kg",
                help=TERM_HELP["mass"],
                disabled=config_locked,
            )
            st.number_input(
                "Initial temperature (°C)",
                step=1.0,
                key="gui_initial_temperature_c",
                help=TERM_HELP["t0"],
            )
        with c2:
            st.number_input(
                "Specific heat (J/(kg·K))",
                min_value=1.0,
                step=10.0,
                key="gui_specific_heat_j_per_kg_k",
                help=TERM_HELP["cp"],
                disabled=config_locked,
            )
            st.number_input(
                "Time step (s)",
                min_value=0.5,
                max_value=60.0,
                step=1.0,
                key="gui_time_step_s",
                help=TERM_HELP["time_step"],
            )

        st.markdown("##### Dimensions")
        d1, d2, d3 = st.columns(3)
        with d1:
            st.number_input(
                "Length (m)",
                min_value=0.01,
                step=0.01,
                format="%.4f",
                key="gui_body_length_m",
                help=TERM_HELP["dims"],
                disabled=config_locked,
            )
        with d2:
            st.number_input(
                "Width (m)",
                min_value=0.01,
                step=0.01,
                format="%.4f",
                key="gui_body_width_m",
                help=TERM_HELP["dims"],
                disabled=config_locked,
            )
        with d3:
            st.number_input(
                "Height (m)",
                min_value=0.01,
                step=0.01,
                format="%.4f",
                key="gui_body_height_m",
                help=TERM_HELP["dims"],
                disabled=config_locked,
            )

        st.markdown("##### Optical properties")
        o1, o2 = st.columns(2)
        with o1:
            st.number_input(
                "Solar absorptivity α",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                key="gui_absorptivity",
                help=TERM_HELP["alpha"],
                disabled=config_locked,
            )
        with o2:
            st.number_input(
                "Infrared emissivity ε",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                key="gui_emissivity",
                help=TERM_HELP["epsilon"],
                disabled=config_locked,
            )

        st.markdown("##### Effective areas")
        a1, a2 = st.columns(2)
        with a1:
            st.number_input(
                "Projected solar area (m²)",
                min_value=1e-6,
                format="%.5f",
                key="gui_projected_area_m2",
                help=TERM_HELP["areas"],
                disabled=config_locked,
            )
            st.number_input(
                "Earth-facing area (m²)",
                min_value=1e-6,
                format="%.5f",
                key="gui_earth_facing_area_m2",
                help=TERM_HELP["areas"],
                disabled=config_locked,
            )
        with a2:
            st.number_input(
                "Radiating area (m²)",
                min_value=1e-6,
                format="%.5f",
                key="gui_radiating_area_m2",
                help=TERM_HELP["areas"],
                disabled=config_locked,
            )
            st.number_input(
                "Albedo area (m²)",
                min_value=1e-6,
                format="%.5f",
                key="gui_albedo_area_m2",
                help=TERM_HELP["areas"],
                disabled=config_locked,
            )

        st.markdown("##### Environment")
        if mode == "environment_compare":
            st.caption(
                "Compare Heat Sources controls Earth IR and albedo per case. "
                "Solar irradiance and OLR below still apply."
            )
            st.session_state.gui_include_earth_infrared = True
            st.session_state.gui_include_albedo = True
        else:
            st.checkbox(
                "Include Earth infrared",
                key="gui_include_earth_infrared",
                help=TERM_HELP["olr"],
            )
            st.checkbox(
                "Include Earth-reflected sunlight (albedo)",
                key="gui_include_albedo",
                help=TERM_HELP["albedo"],
            )
        st.number_input(
            "Solar irradiance S (W/m²)",
            min_value=0.0,
            step=1.0,
            key="gui_solar_flux_w_per_m2",
            help=TERM_HELP["solar"],
        )
        st.number_input(
            "Earth OLR (W/m²)",
            min_value=0.0,
            step=1.0,
            key="gui_earth_olr_w_per_m2",
            help=TERM_HELP["olr"],
        )
        st.number_input(
            "Earth Bond albedo",
            min_value=0.0,
            max_value=1.0,
            step=0.01,
            key="gui_earth_bond_albedo",
            help=TERM_HELP["albedo"],
        )

active_configuration_id = str(
    st.session_state.get(
        "gui_spacecraft_configuration",
        SpacecraftConfigurationId.LEGACY_SIMPLIFIED.value,
    )
)
request = apply_spacecraft_configuration(
    _request_from_state(), active_configuration_id
)
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
        with st.spinner("Running thermal simulation…"):
            study = _run_study(mode, request)
        st.session_state.study = study
        st.session_state.study_fingerprint = request_fingerprint(
            mode, request, active_configuration_id
        )
        config_labels = dict(configuration_select_options())
        st.session_state.study_report_meta = ReportMeta(
            configuration_id=active_configuration_id,
            configuration_label=config_labels.get(
                active_configuration_id, active_configuration_id
            ),
        )
        st.session_state.sample_index = 0
        st.session_state.inspect_case_name = default_inspect_curve_name(study)
        st.success("Simulation complete.")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Simulation failed: {exc}")

study = st.session_state.study
if study is None:
    st.info(
        "Set the spacecraft and orbit in the sidebar, then click **Run Simulation**. "
        "Defaults are ready to use."
    )
    st.stop()

inputs_changed = (
    st.session_state.study_fingerprint is not None
    and st.session_state.study_fingerprint
    != request_fingerprint(mode, request, active_configuration_id)
)
if inputs_changed:
    st.warning(
        "Settings have changed. Click **Run Simulation** to update these results."
    )

curves = all_curves(study)
primary = study.primary
primary_metrics = temperature_metrics_c(primary.result)

st.markdown(
    f'<p class="sta-section-label">Results · {MODE_LABELS.get(study.mode, study.mode)}</p>',
    unsafe_allow_html=True,
)
m1, m2, m3 = st.columns(3)
m1.metric("Final temperature", f"{primary_metrics['final_c']:.2f} °C")
m2.metric("Minimum", f"{primary_metrics['minimum_c']:.2f} °C")
m3.metric("Maximum", f"{primary_metrics['maximum_c']:.2f} °C")

if study.mode == "environment_compare":
    st.caption(environment_comparison_interpretation(curves))
    st.dataframe(
        environment_comparison_summary_rows(curves),
        use_container_width=True,
        hide_index=True,
    )

# --- Temperature ---
st.markdown("### Temperature over time")
source_names = [curve.name for curve in curves]
default_name = default_inspect_curve_name(study)
if st.session_state.get("inspect_case_name") not in source_names:
    st.session_state.inspect_case_name = default_name
if study.mode == "environment_compare":
    inspect_name = st.selectbox(
        "Inspection case",
        options=source_names,
        index=source_names.index(st.session_state.inspect_case_name),
        help="Case used for the time slider, heat-flow panel, 3D view, and PDF snapshot.",
    )
    st.session_state.inspect_case_name = inspect_name
else:
    inspect_name = default_name

viz_curve = resolve_inspect_curve(curves, inspect_name, default_name)
n_samples = len(viz_curve.result.time_s)
st.session_state.sample_index = clamp_sample_index(
    n_samples, int(st.session_state.get("sample_index", 0))
)
viz_index = st.slider(
    "Time sample",
    min_value=0,
    max_value=max(0, n_samples - 1),
    key="sample_index",
    help="Inspect temperature, heat flow, eclipse state, and orbital position together.",
)
period_s = orbital_period_s(viz_curve.orbit)
t_s = viz_curve.result.time_s[viz_index]
temp_c = (
    viz_curve.result.temperature_k[viz_index] - 273.15
)
eclipsed = bool(viz_curve.result.in_eclipse[viz_index])
st.caption(
    f"{t_s / 60.0:.2f} min · orbit {t_s / period_s + 1.0:.2f} · "
    f"{'Eclipse' if eclipsed else 'Sunlit'} · β = {viz_curve.request.beta_deg:.1f}°"
)

if study.mode == "single":
    temp_fig = make_gui_temperature_figure(
        study.primary.result,
        marker_index=viz_index,
        title="Predicted spacecraft temperature",
        label=study.primary.name,
    )
else:
    temp_fig = make_comparison_temperature_figure(
        curves,
        marker_index=viz_index,
        marker_curve_name=viz_curve.name,
        emphasize_name=viz_curve.name,
        title="Heat-source comparison",
        shade_from=curves[0],
    )
st.pyplot(temp_fig, use_container_width=True)
st.caption("Grey bands mark eclipse (Earth blocking sunlight).")

# --- Orbit + state ---
st.markdown("### Orbit visualization")
st.caption(
    "Earth stays tipped (~23°) while the satellite orbits. Drag to spin the scene. "
    "Wings and antennas are visual only."
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
    thermal_model=viz_curve.request.thermal_model,
    geometry=(
        None
        if viz_curve.request.thermal_model == "legacy"
        else geometry_from_request(viz_curve.request)
    ),
    attitude_mode=AttitudeMode.FIXED_INERTIAL.value,
    power_schedule=power_schedule_from_request(viz_curve.request),
)

left, right = st.columns([1.55, 1.0], gap="large")
with left:
    fig3d = build_orbit_3d_figure(
        result=viz_curve.result,
        orbit=viz_curve.orbit,
        sample_index=viz_index,
        title=viz_curve.name,
        attitude_mode=AttitudeMode.FIXED_INERTIAL.value,
        body_length_m=viz_curve.request.body_length_m,
        body_width_m=viz_curve.request.body_width_m,
        body_height_m=viz_curve.request.body_height_m,
        thermal_model=viz_curve.request.thermal_model,
    )
    fig3d.update_layout(height=560)
    st.plotly_chart(fig3d, use_container_width=True)
with right:
    st.markdown(
        f"""
<div class="sta-state-panel">
  <div>
    <h5>At selected time</h5>
    <div class="sta-state-grid">
      <div class="sta-state-card"><div class="lbl">Temperature</div>
        <div class="val">{temp_c:.2f} °C</div></div>
      <div class="sta-state-card"><div class="lbl">Status</div>
        <div class="val">{'Eclipse' if eclipsed else 'Sunlit'}</div></div>
      <div class="sta-state-card"><div class="lbl">Time</div>
        <div class="val">{t_s / 60.0:.2f} min</div></div>
      <div class="sta-state-card"><div class="lbl">Orbit</div>
        <div class="val">{t_s / period_s + 1.0:.2f}</div></div>
    </div>
    <div style="margin-top:0.85rem;font-size:0.78rem;font-weight:600;color:#6E6E73;">
      Heating and cooling (W)
    </div>
    <div class="sta-heat-grid">
      <div class="sta-heat-card"><div class="lbl">Sunlight</div>
        <div class="val">{snap.q_solar_w:.2f}</div></div>
      <div class="sta-heat-card"><div class="lbl">Earth IR</div>
        <div class="val">{snap.q_earth_ir_w:.2f}</div></div>
      <div class="sta-heat-card"><div class="lbl">Albedo</div>
        <div class="val">{snap.q_albedo_w:.2f}</div></div>
      <div class="sta-heat-card"><div class="lbl">Internal</div>
        <div class="val">{snap.q_internal_w:.2f}</div></div>
      <div class="sta-heat-card"><div class="lbl">Cooling</div>
        <div class="val">{snap.q_radiated_w:.2f}</div></div>
      <div class="sta-heat-card"><div class="lbl">Net</div>
        <div class="val">{snap.q_net_w:.2f}</div></div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

# --- Heat flow chart ---
st.markdown("### Heat-flow analysis")
st.caption(
    "Instantaneous heat flows at the selected time sample for the inspection case."
)
st.pyplot(make_heat_flow_bar_figure(snap), use_container_width=True)
if study.mode == "environment_compare":
    st.dataframe(
        comparison_metrics_rows(curves),
        use_container_width=True,
        hide_index=True,
    )

with st.expander("Assumptions and limitations", expanded=False):
    st.markdown(
        f"""
- {TERM_HELP['single_node']}
- Circular LEO with a cylindrical Earth-shadow eclipse model.
- Direct solar and albedo heating are zero in eclipse.
- Earth IR and albedo use effective areas (not full view-factor geometry).
- Enhanced solar heating uses fixed inertial face orientation only.
- Constant internal power only — not a flight power budget.
- Educational model: not flight-qualified thermal analysis.
        """
    )

# --- Export ---
st.markdown("### Export")
st.caption(
    "Downloads use the last completed run. The PDF and images follow the selected "
    "time marker on that completed run."
)
csv_bytes = temperature_history_csv(curves).encode("utf-8")
c1, c2, c3 = st.columns(3)
with c1:
    st.download_button(
        "Temperature CSV",
        data=csv_bytes,
        file_name="satellite_thermal_temperature.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=inputs_changed,
    )
with c2:
    st.download_button(
        "Temperature PNG",
        data=figure_to_png_bytes(temp_fig),
        file_name="satellite_thermal_temperature.png",
        mime="image/png",
        use_container_width=True,
        disabled=inputs_changed,
    )
with c3:
    st.download_button(
        "Heat-flow PNG",
        data=figure_to_png_bytes(make_heat_flow_bar_figure(snap)),
        file_name="satellite_thermal_heat_flow.png",
        mime="image/png",
        use_container_width=True,
        disabled=inputs_changed,
    )

st.markdown("##### Engineering report")
report_meta = st.session_state.get("study_report_meta")
if report_meta is None or inputs_changed:
    report_meta = ReportMeta(
        configuration_id=active_configuration_id,
        configuration_label=dict(configuration_select_options()).get(
            active_configuration_id, active_configuration_id
        ),
    )
pdf_cache_key = (
    st.session_state.study_fingerprint,
    viz_curve.name,
    int(viz_index),
)
prepare_pdf = st.button(
    "Prepare Engineering Report (PDF)",
    use_container_width=True,
    disabled=inputs_changed,
    help="Builds a multi-page PDF for the completed simulation at the selected time.",
)
if prepare_pdf and not inputs_changed:
    try:
        with st.spinner("Building engineering PDF…"):
            ensure_kaleido_browser_configured()
            report = build_engineering_report_pdf(
                study,
                viz_curve=viz_curve,
                sample_index=viz_index,
                meta=report_meta,
            )
        st.session_state.pdf_report_bytes = report.pdf_bytes
        st.session_state.pdf_report_key = pdf_cache_key
        st.session_state.pdf_orbital_included = report.orbital_snapshot_included
        st.success("PDF ready — use the download button below.")
        if not report.orbital_snapshot_included:
            st.warning(
                "The engineering report was generated without the optional "
                "3D orbital image because the image renderer was unavailable. "
                "Temperature history, heat-flow results, and all other sections "
                "are still included."
            )
    except Exception as exc:  # noqa: BLE001
        st.session_state.pdf_report_bytes = None
        st.session_state.pdf_report_key = None
        st.session_state.pdf_orbital_included = None
        st.error(f"PDF report could not be generated: {exc}")

pdf_ready = (
    st.session_state.get("pdf_report_bytes")
    and st.session_state.get("pdf_report_key") == pdf_cache_key
    and not inputs_changed
)
if pdf_ready:
    st.download_button(
        "Download Engineering Report (PDF)",
        data=st.session_state.pdf_report_bytes,
        file_name="satellite_thermal_engineering_report.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
elif not inputs_changed:
    st.caption(
        "Click **Prepare Engineering Report (PDF)** after choosing the "
        "time sample you want in the orbital snapshot."
    )
