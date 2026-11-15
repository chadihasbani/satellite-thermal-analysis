"""Streamlit GUI for the satellite thermal simulator.

Presentation layer only. All physics come from the verified solvers in
`satellite_thermal`.
"""

from __future__ import annotations

import streamlit as st

from satellite_thermal.gui_support import (
    GuiRunRequest,
    SCENARIO_COMPARE_MODE,
    all_curves,
    apply_spacecraft_configuration,
    apply_thermal_scenario,
    changed_parameter_rows,
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
    run_baseline_comparison_mode,
    run_environment_comparison_mode,
    run_scenario_comparison_mode,
    run_single_mode,
    scenario_comparison_interpretation,
    scenario_comparison_summary_rows,
    temperature_history_csv,
    temperature_metrics_c,
    validate_gui_request,
)
from satellite_thermal.spacecraft_configurations import (
    SpacecraftConfigurationId,
    build_spacecraft_configuration,
    configuration_controls_locked,
    configuration_select_options,
    primary_configuration_select_options,
    sync_session_values_from_configuration,
)
from satellite_thermal.thermal_scenarios import (
    ThermalScenarioId,
    build_scenario_definition,
    preset_controls_locked,
    scenario_select_options,
    sync_session_values_from_scenario,
)
from satellite_thermal.heat_flows import heat_flow_at_index
from satellite_thermal.orbit import orbital_period_s
from satellite_thermal.orbit_3d import build_orbit_3d_figure
from satellite_thermal.report_pdf import (
    ReportMeta,
    SIMULATOR_VERSION,
    build_engineering_report_pdf,
)

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
    padding-top: 2.0rem;
    padding-bottom: 3.0rem;
    max-width: 1120px;
}
h1 {
    font-weight: 700 !important;
    letter-spacing: -0.035em !important;
    font-size: 2.2rem !important;
    line-height: 1.15 !important;
    color: #1D1D1F !important;
    margin-bottom: 0.4rem !important;
}
h3 {
    font-weight: 600 !important;
    letter-spacing: -0.02em !important;
    color: #1D1D1F !important;
    margin-top: 1.4rem !important;
}
.sta-lede {
    font-size: 1.05rem;
    line-height: 1.5;
    color: #1D1D1F;
    max-width: 40rem;
    margin: 0 0 0.35rem 0;
}
.sta-body {
    font-size: 0.95rem;
    line-height: 1.5;
    color: #6E6E73;
    max-width: 42rem;
    margin: 0 0 1.0rem 0;
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
    border-radius: 12px;
    padding: 0.65rem 0.85rem;
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
    border-radius: 14px;
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
    border-radius: 10px;
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
section[data-testid="stSidebar"] {
    background: #F5F5F7;
    border-right: 1px solid #E8E8ED;
}
section[data-testid="stSidebar"] > div:first-child {
    padding-top: 0.35rem !important;
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
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 0.55rem 1.1rem !important;
}
.stButton > button {
    border-radius: 10px !important;
}
hr { border: none; border-top: 1px solid #E8E8ED; margin: 1.2rem 0; }
</style>
""",
    unsafe_allow_html=True,
)

TERM_HELP = {
    "alpha": (
        "Solar absorptivity (α): fraction of incoming sunlight absorbed by a surface."
    ),
    "epsilon": (
        "Infrared emissivity (ε): how effectively a surface radiates heat. "
        "This model sets infrared absorptivity equal to ε."
    ),
    "areas": (
        "Effective areas used by the simplified model — not detailed CAD surfaces."
    ),
    "earth_ir": (
        "Earth infrared radiation: heat radiated by Earth toward the spacecraft."
    ),
    "albedo": "Albedo: sunlight reflected from Earth toward the spacecraft.",
    "time_step": (
        "Time step: how often the temperature is updated. Smaller steps resolve "
        "eclipses more finely."
    ),
    "olr": (
        "Earth infrared intensity (outgoing longwave radiation) used for "
        "planetshine heating."
    ),
    "internal": (
        "Internal heating: heat generated by the satellite’s own equipment (≥ 0 W)."
    ),
    "radiative": "Radiative cooling: heat the spacecraft loses by radiating to space.",
    "single_node": (
        "Single-node model: the whole spacecraft is represented by one temperature."
    ),
    "eclipse": (
        "Eclipse: when Earth blocks direct sunlight from reaching the spacecraft."
    ),
    "beta": (
        "Sun–orbit angle (β): angle between the Sun direction and the orbital plane. "
        "β = 0° gives the longest eclipse; large |β| can mean continuous sunlight."
    ),
    "thermal_model": (
        "Legacy uses fixed projected and radiating areas (Version 1.0 reference). "
        "Enhanced uses six bus faces with a chosen orientation for solar heating."
    ),
    "attitude": (
        "Orientation used for face-based solar heating (enhanced model). "
        "Engineering terms: fixed inertial, nadir-pointing (LVLH), or Sun-pointing. "
        "This is a prescribed geometry, not a closed-loop attitude controller."
    ),
    "power_schedule": (
        "Internal heating over time. Constant uses a fixed wattage. Other options "
        "are illustrative educational schedules, not a real power budget."
    ),
    "thermal_scenario": (
        "Environmental condition presets set sunlight strength, Earth reflection, "
        "Earth infrared intensity, Sun–orbit angle, and constant internal heating. "
        "Hot / Cold / Normal are educational screening cases, not universal "
        "spacecraft worst cases. Custom uses the values you enter."
    ),
    "spacecraft_configuration": (
        "Spacecraft presets set size, mass, heat capacity, surface properties, and "
        "calculation method. CubeSat sizes follow CDS Rev 14.1 envelopes; masses "
        "are illustrative. Visual solar wings are decoration only."
    ),
}

MODE_LABELS = {
    "single": "Single Simulation",
    "baseline_compare": "Compare Configurations",
    "environment_compare": "Compare Heat Sources",
    "scenario_compare": "Compare Conditions",
}

ATTITUDE_LABELS = {
    "fixed_inertial": "Fixed orientation",
    "nadir_pointing": "Earth-facing",
    "sun_pointing": "Sun-facing",
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
    if "gui_thermal_scenario" not in st.session_state:
        st.session_state.gui_thermal_scenario = ThermalScenarioId.CUSTOM.value
    if "_scenario_sync_id" not in st.session_state:
        st.session_state._scenario_sync_id = st.session_state.gui_thermal_scenario
    if "gui_spacecraft_configuration" not in st.session_state:
        st.session_state.gui_spacecraft_configuration = (
            SpacecraftConfigurationId.LEGACY_SIMPLIFIED.value
        )
    defaults = default_gui_request()
    for field, value in defaults.__dict__.items():
        key = f"gui_{field}"
        if key not in st.session_state:
            st.session_state[key] = value
    # Force one configuration sync on first load so locked preset fields match.
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
    st.session_state.gui_thermal_scenario = ThermalScenarioId.CUSTOM.value
    st.session_state._scenario_sync_id = ThermalScenarioId.CUSTOM.value
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


def _mode_blurb(mode: str) -> str:
    return {
        "single": "Simulate one satellite with the settings you choose.",
        "baseline_compare": (
            "Compare your settings with the repository reference defaults "
            "(same number of orbits and time step)."
        ),
        "environment_compare": (
            "Compare the same satellite with sunlight only, then add Earth "
            "infrared, then add reflected sunlight (albedo)."
        ),
        "scenario_compare": (
            "Compare cold, normal, and hot environmental screening cases on "
            "the same satellite."
        ),
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
        beta_deg=float(st.session_state.gui_beta_deg),
        orbit_count=int(st.session_state.gui_orbit_count),
        time_step_s=float(st.session_state.gui_time_step_s),
        include_earth_infrared=bool(st.session_state.gui_include_earth_infrared),
        include_albedo=bool(st.session_state.gui_include_albedo),
        thermal_model=str(st.session_state.gui_thermal_model),
        attitude_mode=str(st.session_state.gui_attitude_mode),
        body_length_m=float(st.session_state.gui_body_length_m),
        body_width_m=float(st.session_state.gui_body_width_m),
        body_height_m=float(st.session_state.gui_body_height_m),
        power_schedule_kind=str(st.session_state.gui_power_schedule_kind),
        standby_power_w=float(st.session_state.gui_standby_power_w),
        nominal_power_w=float(st.session_state.gui_nominal_power_w),
        high_power_w=float(st.session_state.gui_high_power_w),
        periodic_period_s=float(st.session_state.gui_periodic_period_s),
        periodic_high_duration_s=float(st.session_state.gui_periodic_high_duration_s),
        custom_intervals_text=str(st.session_state.gui_custom_intervals_text),
    )


def _run_study(mode: str, request: GuiRunRequest, scenario_id: str):
    del scenario_id
    if mode == SCENARIO_COMPARE_MODE:
        validate_gui_request(apply_thermal_scenario(request, ThermalScenarioId.NOMINAL))
        return run_scenario_comparison_mode(request)
    validate_gui_request(request)
    if mode == "single":
        return run_single_mode(request)
    if mode == "baseline_compare":
        return run_baseline_comparison_mode(request)
    return run_environment_comparison_mode(request)


def _sync_configuration(configuration_id: str) -> bool:
    """Apply preset field sync when the spacecraft selection changes."""
    config_locked = configuration_controls_locked(configuration_id)
    if configuration_id != st.session_state.get("_configuration_sync_id"):
        updates = sync_session_values_from_configuration(configuration_id)
        for key, value in updates.items():
            st.session_state[key] = value
        st.session_state._configuration_sync_id = configuration_id
    return config_locked


def _sync_scenario(mode: str, scenario_id: str) -> None:
    """Keep Hot/Cold/Normal locked fields aligned with altitude."""
    if mode != "scenario_compare" and scenario_id != ThermalScenarioId.CUSTOM.value:
        altitude_now = float(st.session_state.gui_altitude_km)
        needs_sync = (
            scenario_id != st.session_state.get("_scenario_sync_id")
            or altitude_now
            != float(st.session_state.get("_scenario_sync_altitude_km", -1.0))
        )
        if needs_sync:
            updates = sync_session_values_from_scenario(scenario_id, altitude_now)
            for key, value in updates.items():
                st.session_state[key] = value
            st.session_state._scenario_sync_id = scenario_id
            st.session_state._scenario_sync_altitude_km = altitude_now
    elif mode != "scenario_compare" and scenario_id == ThermalScenarioId.CUSTOM.value:
        st.session_state._scenario_sync_id = ThermalScenarioId.CUSTOM.value


_init_state()

# --- Header ---
st.title("Satellite Thermal Analysis")
st.markdown(
    '<p class="sta-lede">Explore how a satellite’s temperature changes as it orbits Earth.</p>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="sta-body">This simulator models heating from sunlight, Earth’s infrared '
    "radiation, reflected sunlight, and onboard equipment, alongside cooling through "
    "thermal radiation. Choose a spacecraft, set its orbit and orientation, compare "
    f"scenarios, and download an engineering PDF report. {TERM_HELP['single_node']}</p>",
    unsafe_allow_html=True,
)
st.markdown(
    f'<p class="sta-body" style="font-size:0.88rem;color:#86868B;">'
    f"Version {SIMULATOR_VERSION} · Built with Python, Streamlit, Matplotlib, and Plotly · "
    "Developed with AI-assisted tooling (Cursor) under human engineering review · "
    "Git-tracked open-source project</p>",
    unsafe_allow_html=True,
)

# --- Sidebar ---
with st.sidebar:
    # ----- Spacecraft -----
    st.markdown("### Spacecraft")
    primary_options = primary_configuration_select_options()
    all_options = configuration_select_options()
    all_labels = {item[0]: item[1] for item in all_options}
    primary_ids = [item[0] for item in primary_options]
    current_config = str(st.session_state.gui_spacecraft_configuration)
    # Keep the widget valid if Advanced selected the enhanced cube.
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
        st.caption("Version 1.0 educational reference (fixed-area heating model).")
    elif configuration_id == SpacecraftConfigurationId.ILLUSTRATIVE_CUBE.value:
        st.caption("Same size class as the reference, with face-based solar heating.")
    elif configuration_id != SpacecraftConfigurationId.CUSTOM.value:
        st.caption(build_spacecraft_configuration(configuration_id).summary)

    st.selectbox(
        "Spacecraft orientation",
        options=["fixed_inertial", "nadir_pointing", "sun_pointing"],
        format_func=lambda value: ATTITUDE_LABELS[value],
        key="gui_attitude_mode",
        help=TERM_HELP["attitude"],
        disabled=st.session_state.get("gui_thermal_model", "legacy") == "legacy",
    )
    if st.session_state.get("gui_thermal_model", "legacy") == "legacy":
        st.caption(
            "Orientation affects face-based (enhanced) heating. "
            "The Reference Satellite uses the legacy fixed-area model."
        )

    # ----- Orbit -----
    st.markdown("### Orbit")
    st.number_input(
        "Orbital altitude (km)",
        min_value=200.0,
        max_value=2000.0,
        step=50.0,
        key="gui_altitude_km",
        help="Height above Earth’s surface. Affects orbit period and eclipse length.",
    )
    # Scenario sync needs altitude before beta is shown as locked.
    # Scenario id is read early for locking; Advanced owns the selector widget.
    _early_scenario_id = str(
        st.session_state.get("gui_thermal_scenario", ThermalScenarioId.CUSTOM.value)
    )
    _early_mode = str(st.session_state.get("gui_mode", "single"))
    _sync_scenario(_early_mode, _early_scenario_id)
    preset_locked = preset_controls_locked(_early_scenario_id, mode=_early_mode)

    st.slider(
        "Sun–orbit angle (β)",
        min_value=-90.0,
        max_value=90.0,
        step=1.0,
        key="gui_beta_deg",
        help=TERM_HELP["beta"],
        disabled=preset_locked,
    )

    # ----- Simulation -----
    st.markdown("### Simulation")
    mode = st.selectbox(
        "Simulation mode",
        options=[
            "single",
            "baseline_compare",
            "environment_compare",
            "scenario_compare",
        ],
        format_func=lambda value: MODE_LABELS[value],
        key="gui_mode",
    )
    st.caption(_mode_blurb(mode))
    st.number_input(
        "Number of orbits",
        1,
        20,
        step=1,
        key="gui_orbit_count",
        help="How many full revolutions around Earth to simulate.",
    )

    run_clicked = st.button("Run Simulation", type="primary", use_container_width=True)
    st.button(
        "Reset to defaults",
        use_container_width=True,
        on_click=_apply_defaults,
    )

    # ----- Advanced -----
    with st.expander("Advanced Settings", expanded=False):
        st.caption("Detailed inputs for experienced users. Defaults are already set.")

        # Enhanced cube access (kept out of the primary four choices).
        if st.button(
            "Use Enhanced 0.1 m cube",
            use_container_width=True,
            help=(
                "Switch to the enhanced face-based model on a 0.1 m cube "
                "(same size class as the Reference Satellite)."
            ),
        ):
            st.session_state.gui_spacecraft_configuration = (
                SpacecraftConfigurationId.ILLUSTRATIVE_CUBE.value
            )
            updates = sync_session_values_from_configuration(
                SpacecraftConfigurationId.ILLUSTRATIVE_CUBE.value
            )
            for key, value in updates.items():
                st.session_state[key] = value
            st.session_state._configuration_sync_id = (
                SpacecraftConfigurationId.ILLUSTRATIVE_CUBE.value
            )
            st.rerun()

        st.markdown("##### Environmental conditions")
        scenario_options = scenario_select_options()
        scenario_ids = [item[0] for item in scenario_options]
        scenario_labels = {item[0]: item[1] for item in scenario_options}
        scenario_selector_disabled = mode == "scenario_compare"
        scenario_id = st.selectbox(
            "Condition preset",
            options=scenario_ids,
            format_func=lambda value: scenario_labels[value],
            key="gui_thermal_scenario",
            help=TERM_HELP["thermal_scenario"],
            disabled=scenario_selector_disabled,
        )
        if scenario_selector_disabled:
            st.caption(
                "Compare Conditions always runs Cold, Normal, and Hot together. "
                "This preset selector is unused in that mode."
            )
        # Re-sync after the scenario widget (and any altitude change) is known.
        _sync_scenario(mode, scenario_id)
        preset_locked = preset_controls_locked(scenario_id, mode=mode)
        if mode != "scenario_compare" and scenario_id != ThermalScenarioId.CUSTOM.value:
            definition = build_scenario_definition(
                scenario_id,
                altitude_km=float(st.session_state.gui_altitude_km),
            )
            st.caption(definition.summary)

        st.markdown("##### Calculation method")
        st.selectbox(
            "Thermal model",
            options=["legacy", "enhanced"],
            format_func=lambda value: (
                "Legacy (fixed areas, V1 reference)"
                if value == "legacy"
                else "Enhanced (face solar + orientation)"
            ),
            key="gui_thermal_model",
            help=TERM_HELP["thermal_model"],
            disabled=config_locked,
        )

        st.markdown("##### Mass and heat capacity")
        st.number_input(
            "Mass (kg)",
            min_value=0.1,
            step=0.5,
            key="gui_mass_kg",
            disabled=config_locked,
        )
        st.number_input(
            "Specific heat (J/(kg·K))",
            min_value=1.0,
            step=50.0,
            key="gui_specific_heat_j_per_kg_k",
            disabled=config_locked,
            help="Effective heat capacity of the whole satellite, not one material alone.",
        )
        st.number_input(
            "Initial temperature (°C)",
            min_value=-273.14,
            step=1.0,
            key="gui_initial_temperature_c",
            help="Starting temperature. Must stay above absolute zero (−273.15 °C).",
        )

        st.markdown("##### Dimensions")
        st.number_input(
            "Length (m)",
            min_value=1e-3,
            step=0.01,
            format="%.4f",
            key="gui_body_length_m",
            disabled=config_locked,
        )
        st.number_input(
            "Width (m)",
            min_value=1e-3,
            step=0.01,
            format="%.4f",
            key="gui_body_width_m",
            disabled=config_locked,
        )
        st.number_input(
            "Height (m)",
            min_value=1e-3,
            step=0.01,
            format="%.4f",
            key="gui_body_height_m",
            disabled=config_locked,
        )
        st.number_input(
            "Projected solar area (m²)",
            min_value=1e-4,
            format="%.5f",
            key="gui_projected_area_m2",
            help=TERM_HELP["areas"] + " Used in legacy mode only.",
            disabled=config_locked,
        )
        st.number_input(
            "Radiating area (m²)",
            min_value=1e-4,
            format="%.5f",
            key="gui_radiating_area_m2",
            help=TERM_HELP["areas"],
            disabled=config_locked,
        )
        st.number_input(
            "Earth-facing area (m²)",
            min_value=1e-4,
            format="%.5f",
            key="gui_earth_facing_area_m2",
            help=TERM_HELP["areas"],
            disabled=config_locked,
        )
        st.number_input(
            "Albedo area (m²)",
            min_value=1e-4,
            format="%.5f",
            key="gui_albedo_area_m2",
            help=TERM_HELP["areas"],
            disabled=config_locked,
        )

        st.markdown("##### Surface properties")
        st.slider(
            "Solar absorptivity α",
            min_value=0.0,
            max_value=1.0,
            step=0.01,
            key="gui_absorptivity",
            help=TERM_HELP["alpha"],
            disabled=config_locked,
        )
        st.slider(
            "Infrared emissivity ε",
            min_value=0.0,
            max_value=1.0,
            step=0.01,
            key="gui_emissivity",
            help=TERM_HELP["epsilon"],
            disabled=config_locked,
        )

        st.markdown("##### Environment")
        env_flag_locked = preset_locked or mode == "environment_compare"
        if mode != "environment_compare":
            st.checkbox(
                "Include Earth infrared",
                key="gui_include_earth_infrared",
                help=TERM_HELP["earth_ir"],
                disabled=env_flag_locked,
            )
            st.checkbox(
                "Include albedo (reflected sunlight)",
                key="gui_include_albedo",
                help=TERM_HELP["albedo"],
                disabled=env_flag_locked,
            )
        else:
            # Keep widgets registered so session state stays valid.
            st.checkbox(
                "Include Earth infrared",
                key="gui_include_earth_infrared",
                help=TERM_HELP["earth_ir"],
                disabled=True,
            )
            st.checkbox(
                "Include albedo (reflected sunlight)",
                key="gui_include_albedo",
                help=TERM_HELP["albedo"],
                disabled=True,
            )
            st.caption(
                "In Compare Heat Sources, these flags are set by each case "
                "(sunlight only → +Earth IR → +albedo)."
            )

        if mode != "scenario_compare":
            st.number_input(
                "Solar irradiance (W/m²)",
                min_value=0.0,
                step=1.0,
                key="gui_solar_flux_w_per_m2",
                disabled=preset_locked,
                help="Strength of sunlight at the spacecraft.",
            )
            st.number_input(
                "Earth infrared intensity (W/m²)",
                min_value=0.0,
                step=1.0,
                key="gui_earth_olr_w_per_m2",
                help=TERM_HELP["olr"],
                disabled=preset_locked,
            )
            st.slider(
                "Earth Bond albedo",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                key="gui_earth_bond_albedo",
                help=TERM_HELP["albedo"],
                disabled=preset_locked,
            )
        else:
            # Register widgets while Compare Conditions owns these values.
            st.number_input(
                "Solar irradiance (W/m²)",
                min_value=0.0,
                step=1.0,
                key="gui_solar_flux_w_per_m2",
                disabled=True,
            )
            st.number_input(
                "Earth infrared intensity (W/m²)",
                min_value=0.0,
                step=1.0,
                key="gui_earth_olr_w_per_m2",
                disabled=True,
            )
            st.slider(
                "Earth Bond albedo",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                key="gui_earth_bond_albedo",
                disabled=True,
            )
            st.caption(
                "Compare Conditions applies its own Cold / Normal / Hot "
                "environment values to each curve."
            )

        st.markdown("##### Internal heating")
        if mode != "scenario_compare":
            st.number_input(
                "Internal heat (W)",
                min_value=0.0,
                step=1.0,
                key="gui_internal_heat_w",
                help=TERM_HELP["internal"],
                disabled=preset_locked,
            )
            st.selectbox(
                "Heating schedule",
                options=[
                    "constant",
                    "eclipse_reduced",
                    "periodic_high",
                    "custom_intervals",
                ],
                format_func=lambda value: {
                    "constant": "Constant",
                    "eclipse_reduced": "Reduced in eclipse",
                    "periodic_high": "Periodic high-power pulses",
                    "custom_intervals": "Custom time intervals",
                }[value],
                key="gui_power_schedule_kind",
                help=TERM_HELP["power_schedule"],
                disabled=preset_locked,
            )
            schedule_kind = str(st.session_state.gui_power_schedule_kind)
            if schedule_kind != "constant":
                st.number_input(
                    "Standby power (W)",
                    min_value=0.0,
                    step=0.5,
                    key="gui_standby_power_w",
                )
                st.number_input(
                    "Nominal power (W)",
                    min_value=0.0,
                    step=0.5,
                    key="gui_nominal_power_w",
                )
                st.number_input(
                    "High power (W)",
                    min_value=0.0,
                    step=0.5,
                    key="gui_high_power_w",
                )
            else:
                # Keep schedule fields in session state without showing them.
                st.session_state.setdefault("gui_standby_power_w", default_gui_request().standby_power_w)
                st.session_state.setdefault("gui_nominal_power_w", default_gui_request().nominal_power_w)
                st.session_state.setdefault("gui_high_power_w", default_gui_request().high_power_w)

            if schedule_kind == "periodic_high":
                st.number_input(
                    "Pulse period (s)",
                    min_value=1.0,
                    step=60.0,
                    key="gui_periodic_period_s",
                )
                st.number_input(
                    "Pulse duration (s)",
                    min_value=0.0,
                    step=30.0,
                    key="gui_periodic_high_duration_s",
                )
            else:
                st.session_state.setdefault(
                    "gui_periodic_period_s", default_gui_request().periodic_period_s
                )
                st.session_state.setdefault(
                    "gui_periodic_high_duration_s",
                    default_gui_request().periodic_high_duration_s,
                )

            if schedule_kind == "custom_intervals":
                st.text_area(
                    "Custom intervals (start_s, end_s, power_w)",
                    key="gui_custom_intervals_text",
                    height=80,
                    help="Example: 0,120,10; 300,400,25. Outside intervals, Internal heat applies.",
                )
            else:
                st.session_state.setdefault("gui_custom_intervals_text", "")
        else:
            st.number_input(
                "Internal heat (W)",
                min_value=0.0,
                step=1.0,
                key="gui_internal_heat_w",
                disabled=True,
            )
            st.selectbox(
                "Heating schedule",
                options=[
                    "constant",
                    "eclipse_reduced",
                    "periodic_high",
                    "custom_intervals",
                ],
                format_func=lambda value: {
                    "constant": "Constant",
                    "eclipse_reduced": "Reduced in eclipse",
                    "periodic_high": "Periodic high-power pulses",
                    "custom_intervals": "Custom time intervals",
                }[value],
                key="gui_power_schedule_kind",
                disabled=True,
            )
            st.number_input(
                "Standby power (W)",
                min_value=0.0,
                step=0.5,
                key="gui_standby_power_w",
                disabled=True,
            )
            st.number_input(
                "Nominal power (W)",
                min_value=0.0,
                step=0.5,
                key="gui_nominal_power_w",
                disabled=True,
            )
            st.number_input(
                "High power (W)",
                min_value=0.0,
                step=0.5,
                key="gui_high_power_w",
                disabled=True,
            )
            st.number_input(
                "Pulse period (s)",
                min_value=1.0,
                step=60.0,
                key="gui_periodic_period_s",
                disabled=True,
            )
            st.number_input(
                "Pulse duration (s)",
                min_value=0.0,
                step=30.0,
                key="gui_periodic_high_duration_s",
                disabled=True,
            )
            st.text_area(
                "Custom intervals (start_s, end_s, power_w)",
                key="gui_custom_intervals_text",
                height=80,
                disabled=True,
            )
            st.caption(
                "Each screening case sets its own constant internal heating."
            )

        st.markdown("##### Numerics")
        st.number_input(
            "Time step (s)",
            min_value=0.1,
            max_value=60.0,
            step=1.0,
            key="gui_time_step_s",
            help=TERM_HELP["time_step"],
        )

# Active scenario after Advanced widgets exist.
active_configuration_id = str(
    st.session_state.get(
        "gui_spacecraft_configuration",
        SpacecraftConfigurationId.LEGACY_SIMPLIFIED.value,
    )
)
active_scenario_id = (
    ThermalScenarioId.CUSTOM.value
    if mode == "scenario_compare"
    else str(
        st.session_state.get("gui_thermal_scenario", ThermalScenarioId.CUSTOM.value)
    )
)

request = _request_from_state()
request = apply_spacecraft_configuration(request, active_configuration_id)
if mode != "scenario_compare":
    request = apply_thermal_scenario(request, active_scenario_id)
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
            study = _run_study(mode, request, active_scenario_id)
        st.session_state.study = study
        st.session_state.study_fingerprint = request_fingerprint(
            mode, request, active_scenario_id, active_configuration_id
        )
        config_labels = dict(configuration_select_options())
        scenario_labels = dict(scenario_select_options())
        st.session_state.study_report_meta = ReportMeta(
            configuration_id=active_configuration_id,
            configuration_label=config_labels.get(
                active_configuration_id, active_configuration_id
            ),
            scenario_id=active_scenario_id,
            scenario_label=scenario_labels.get(active_scenario_id, active_scenario_id),
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
    with st.expander("What the heating terms mean"):
        st.markdown(
            f"""
| Term | Meaning |
| --- | --- |
| **Direct solar heating** | Sunlight absorbed by the spacecraft (zero in eclipse). |
| **Earth infrared** | {TERM_HELP["earth_ir"]} |
| **Albedo** | {TERM_HELP["albedo"]} |
| **Internal heating** | {TERM_HELP["internal"]} |
| **Radiative cooling** | {TERM_HELP["radiative"]} |
| **Eclipse** | {TERM_HELP["eclipse"]} |
            """
        )
    st.stop()

inputs_changed = (
    st.session_state.study_fingerprint is not None
    and st.session_state.study_fingerprint
    != request_fingerprint(
        mode, request, active_scenario_id, active_configuration_id
    )
)
if inputs_changed:
    st.warning(
        "Settings have changed. Click **Run Simulation** to update these results."
    )

curves = all_curves(study)
primary = study.primary
primary_metrics = temperature_metrics_c(primary.result)

# --- Key results ---
st.markdown(
    f'<p class="sta-section-label">Results · {MODE_LABELS.get(study.mode, study.mode)}</p>',
    unsafe_allow_html=True,
)
m1, m2, m3 = st.columns(3)
m1.metric("Final temperature", f"{primary_metrics['final_c']:.2f} °C")
m2.metric("Minimum", f"{primary_metrics['minimum_c']:.2f} °C")
m3.metric("Maximum", f"{primary_metrics['maximum_c']:.2f} °C")

if study.mode == "baseline_compare" and study.companions:
    baseline_final = temperature_metrics_c(study.companions[0].result)["final_c"]
    delta_k = primary_metrics["final_c"] - baseline_final
    st.caption(
        f"Your result minus Reference: **{delta_k:+.2f} K** "
        f"(Reference {baseline_final:.2f} °C → Modified {primary_metrics['final_c']:.2f} °C)."
    )
elif study.mode == "environment_compare" and len(curves) == 3:
    with st.expander("Heat-source comparison summary", expanded=True):
        st.dataframe(
            environment_comparison_summary_rows(curves),
            hide_index=True,
            use_container_width=True,
        )
        st.caption(environment_comparison_interpretation(curves))
elif study.mode == SCENARIO_COMPARE_MODE and len(curves) == 3:
    with st.expander("Conditions comparison summary", expanded=True):
        st.dataframe(
            scenario_comparison_summary_rows(curves),
            hide_index=True,
            use_container_width=True,
        )
        st.caption(scenario_comparison_interpretation(curves))

if len(curves) > 1:
    source_names = [curve.name for curve in curves]
    default_name = default_inspect_curve_name(study)
    if st.session_state.get("inspect_case_name") not in source_names:
        st.session_state.inspect_case_name = default_name
    selected_name = st.selectbox(
        "Inspect case",
        options=source_names,
        key="inspect_case_name",
        help=(
            "All cases stay on the temperature graph. This chooses which result "
            "feeds the 3D view and heat-flow details."
        ),
    )
    viz_curve = resolve_inspect_curve(curves, selected_name, default_name)
else:
    viz_curve = primary
    st.session_state.inspect_case_name = viz_curve.name

# --- Temperature history ---
st.markdown("### Temperature over time")
n_viz_samples = len(viz_curve.result.time_s)
max_sample_index = max(0, n_viz_samples - 1)
st.session_state.sample_index = clamp_sample_index(
    n_viz_samples,
    int(st.session_state.get("sample_index", 0)),
)
sample_index = st.slider(
    "Time sample",
    min_value=0,
    max_value=max_sample_index,
    step=1,
    key="sample_index",
    help="Move through the simulated timeline. The red marker follows this sample.",
)
viz_index = sample_index
selected_time_s = viz_curve.result.time_s[viz_index]
selected_time_min = selected_time_s / 60.0
viz_period = orbital_period_s(viz_curve.orbit)
orbit_number_selected = selected_time_s / viz_period + 1.0
status_now = "Eclipsed" if viz_curve.result.in_eclipse[viz_index] else "Sunlit"
st.caption(
    f"{selected_time_min:.2f} min · orbit {orbit_number_selected:.2f} · "
    f"{status_now} · β = {viz_curve.request.beta_deg:.1f}°"
)

if study.mode == "single":
    temp_fig = make_gui_temperature_figure(
        primary.result,
        marker_index=viz_index,
        title="Orbital temperature",
        label=primary.name,
    )
elif study.mode == "baseline_compare":
    temp_fig = make_comparison_temperature_figure(
        curves,
        marker_index=viz_index,
        marker_curve_name=viz_curve.name,
        emphasize_name=viz_curve.name,
        title="Reference vs your settings",
        shade_from=curves[0],
    )
elif study.mode == SCENARIO_COMPARE_MODE:
    temp_fig = make_comparison_temperature_figure(
        curves,
        marker_index=viz_index,
        marker_curve_name=viz_curve.name,
        emphasize_name=viz_curve.name,
        title="Cold / Normal / Hot conditions",
        shade_from=curves[0],
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
st.pyplot(temp_fig, clear_figure=True, use_container_width=True)
st.caption("Grey bands mark eclipse (Earth blocking sunlight).")

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
    geometry=geometry_from_request(viz_curve.request),
    attitude_mode=viz_curve.request.attitude_mode,
    power_schedule=power_schedule_from_request(viz_curve.request),
)
orbit_number = snap.time_s / viz_period + 1.0

# --- 3D orbit ---
st.markdown("### Orbit visualization")
st.caption(
    "Earth stays tipped (~23°) while the satellite orbits. Drag to spin around "
    "the scene (Earth will not flip upside down). Wings and antennas are visual only."
)
viz_left, viz_right = st.columns([1.3, 0.9], gap="medium")
with viz_left:
    fig3d = build_orbit_3d_figure(
        result=viz_curve.result,
        orbit=viz_curve.orbit,
        sample_index=viz_index,
        title=viz_curve.name,
        attitude_mode=viz_curve.request.attitude_mode,
        body_length_m=viz_curve.request.body_length_m,
        body_width_m=viz_curve.request.body_width_m,
        body_height_m=viz_curve.request.body_height_m,
        thermal_model=viz_curve.request.thermal_model,
    )
    st.plotly_chart(
        fig3d,
        use_container_width=True,
        config={
            "displayModeBar": True,
            "responsive": True,
            "scrollZoom": True,
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
    <h5>Heating and cooling (W)</h5>
    <div class="sta-state-grid">
      <div class="sta-state-card"><div class="lbl">Sunlight</div><div class="val">{snap.q_solar_w:.2f} W</div></div>
      <div class="sta-state-card"><div class="lbl">Earth IR</div><div class="val">{snap.q_earth_ir_w:.2f} W</div></div>
      <div class="sta-state-card"><div class="lbl">Albedo</div><div class="val">{snap.q_albedo_w:.2f} W</div></div>
      <div class="sta-state-card"><div class="lbl">Internal</div><div class="val">{snap.q_internal_w:.2f} W</div></div>
      <div class="sta-state-card"><div class="lbl">Cooling</div><div class="val">{snap.q_radiated_w:.2f} W</div></div>
      <div class="sta-state-card"><div class="lbl">Net</div><div class="val">{snap.q_net_w:.2f} W</div></div>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

# --- Collapsed details ---
with st.expander("Heat-flow chart and analysis", expanded=False):
    st.pyplot(make_heat_flow_bar_figure(snap), clear_figure=True, use_container_width=True)
    st.caption(
        "Positive values heat the spacecraft; radiative cooling is shown as negative. "
        f"Inspecting **{viz_curve.name}**."
    )
    st.dataframe(
        comparison_metrics_rows(curves),
        hide_index=True,
        use_container_width=True,
    )
    if study.mode == "baseline_compare" and study.companions:
        rows = changed_parameter_rows(study.companions[0].request, primary.request)
        if rows:
            st.markdown("##### What changed vs reference")
            st.dataframe(rows, hide_index=True, use_container_width=True)
        else:
            st.info("Your settings match the reference, so the curves overlap.")
    elif study.mode == "environment_compare" and len(curves) == 3:
        st.markdown(
            """
| Case | Includes |
| --- | --- |
| **A – No Earth Heating** | Sunlight, internal heat, cooling to space |
| **B – With Earth Infrared** | A + Earth infrared |
| **C – With Earth Infrared and Albedo** | B + reflected sunlight |
            """
        )
    elif study.mode == SCENARIO_COMPARE_MODE and len(curves) == 3:
        st.markdown(
            """
| Scenario | Idea |
| --- | --- |
| **Cold** | Weaker sunlight, longer eclipse, lower internal heat |
| **Nominal** | Repository educational defaults |
| **Hot** | Stronger sunlight, little or no eclipse, higher internal heat |
            """
        )

with st.expander("Assumptions", expanded=False):
    st.markdown(
        f"""
- {TERM_HELP["single_node"]}
- Areas are model inputs, not CAD surfaces.
- {TERM_HELP["eclipse"]} {TERM_HELP["beta"]}
- {TERM_HELP["thermal_model"]}
- {TERM_HELP["attitude"]}
- {TERM_HELP["power_schedule"]}
- {TERM_HELP["thermal_scenario"]}
- 3D craft is enlarged for visibility; wing panels are visual-only.
- Results check numerical consistency — not flight-data validation.
- See `docs/MODEL.md` for equations and assumptions.
        """
    )

with st.expander("Export", expanded=False):
    st.caption(
        "Downloads use the last completed run. The PDF and images follow the "
        "selected time marker on that completed run."
    )
    if study.mode == "single":
        export_temp = make_gui_temperature_figure(
            primary.result,
            marker_index=viz_index,
            title="Orbital temperature",
        )
    elif study.mode == "baseline_compare":
        export_temp = make_comparison_temperature_figure(
            curves,
            marker_index=viz_index,
            marker_curve_name=viz_curve.name,
            emphasize_name=viz_curve.name,
            title="Reference vs your settings",
            shade_from=curves[0],
        )
    elif study.mode == SCENARIO_COMPARE_MODE:
        export_temp = make_comparison_temperature_figure(
            curves,
            marker_index=viz_index,
            marker_curve_name=viz_curve.name,
            emphasize_name=viz_curve.name,
            title="Cold / Normal / Hot conditions",
            shade_from=curves[0],
        )
    else:
        export_temp = make_comparison_temperature_figure(
            curves,
            marker_index=viz_index,
            marker_curve_name=viz_curve.name,
            emphasize_name=viz_curve.name,
            title="Heat-source comparison",
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

    st.markdown("##### Engineering report")
    if inputs_changed:
        st.warning(
            "Settings have changed since this run. Click **Run Simulation** "
            "before preparing a PDF so the report matches the plots above."
        )
    report_meta = st.session_state.get("study_report_meta")
    if report_meta is None:
        report_meta = ReportMeta(
            configuration_id=active_configuration_id,
            configuration_label=dict(configuration_select_options()).get(
                active_configuration_id, active_configuration_id
            ),
            scenario_id=active_scenario_id,
            scenario_label=dict(scenario_select_options()).get(
                active_scenario_id, active_scenario_id
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
        help=(
            "Builds a multi-page PDF for the completed simulation at the "
            "selected time marker. Then use the download button below."
        ),
    )
    if prepare_pdf and not inputs_changed:
        try:
            with st.spinner("Building engineering PDF…"):
                st.session_state.pdf_report_bytes = build_engineering_report_pdf(
                    study,
                    viz_curve=viz_curve,
                    sample_index=viz_index,
                    meta=report_meta,
                )
            st.session_state.pdf_report_key = pdf_cache_key
            st.success("PDF ready — use the download button below.")
        except Exception as exc:  # noqa: BLE001
            st.session_state.pdf_report_bytes = None
            st.session_state.pdf_report_key = None
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
