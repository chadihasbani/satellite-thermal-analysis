"""Streamlit GUI for the satellite thermal simulator.

This app only collects inputs and calls the existing verified solvers.
It does not duplicate the heat-transfer mathematics.
"""

from __future__ import annotations

import streamlit as st

from satellite_thermal.gui_support import (
    GuiRunRequest,
    build_model_inputs,
    default_gui_request,
    make_gui_temperature_figure,
    run_gui_simulation,
    temperature_metrics_c,
)
from satellite_thermal.orbit import orbital_period_s


st.set_page_config(
    page_title="Satellite Thermal Analysis",
    layout="wide",
)

st.title("Satellite Thermal Analysis")
st.caption(
    "Single-node teaching simulator. Uses the verified Python solvers. "
    "Not a prediction for real ICEYE or other flight satellites."
)

defaults = default_gui_request()

with st.sidebar:
    st.header("Simulation controls")
    orbit_count = st.number_input("Number of orbits", min_value=1, max_value=20, value=defaults.orbit_count, step=1)
    time_step_s = st.number_input(
        "Time step (s)",
        min_value=0.1,
        max_value=60.0,
        value=float(defaults.time_step_s),
        step=1.0,
        help="Default 5 s is faster for interactive use. Use 1 s to match CLI studies.",
    )
    altitude_km = st.number_input(
        "Orbital altitude (km)",
        min_value=200.0,
        max_value=2000.0,
        value=float(defaults.altitude_km),
        step=50.0,
    )
    include_earth_infrared = st.checkbox("Include Earth infrared", value=defaults.include_earth_infrared)
    include_albedo = st.checkbox("Include Earth albedo", value=defaults.include_albedo)

    st.header("Thermal properties")
    mass_kg = st.number_input("Mass (kg)", min_value=0.1, value=float(defaults.mass_kg), step=0.5)
    specific_heat = st.number_input(
        "Specific heat cp (J/(kg·K))",
        min_value=1.0,
        value=float(defaults.specific_heat_j_per_kg_k),
        step=50.0,
    )
    initial_c = st.number_input(
        "Initial temperature (°C)",
        value=float(defaults.initial_temperature_c),
        step=1.0,
    )
    absorptivity = st.slider("Solar absorptivity α", 0.0, 1.0, float(defaults.absorptivity), 0.01)
    emissivity = st.slider(
        "IR emissivity ε (= α_ir by Kirchhoff)",
        0.0,
        1.0,
        float(defaults.emissivity),
        0.01,
    )
    internal_heat_w = st.number_input(
        "Internal heat (W)",
        value=float(defaults.internal_heat_w),
        step=1.0,
    )

    st.header("Areas and environment")
    projected_area = st.number_input(
        "Projected solar area (m²)",
        min_value=1e-4,
        value=float(defaults.projected_area_m2),
        format="%.4f",
    )
    radiating_area = st.number_input(
        "Radiating area (m²)",
        min_value=1e-4,
        value=float(defaults.radiating_area_m2),
        format="%.4f",
    )
    earth_facing_area = st.number_input(
        "Earth-facing area (m²)",
        min_value=1e-4,
        value=float(defaults.earth_facing_area_m2),
        format="%.4f",
    )
    albedo_area = st.number_input(
        "Albedo area (m²)",
        min_value=1e-4,
        value=float(defaults.albedo_area_m2),
        format="%.4f",
    )
    solar_flux = st.number_input(
        "Solar flux S (W/m²)",
        min_value=0.0,
        value=float(defaults.solar_flux_w_per_m2),
        step=1.0,
    )
    earth_olr = st.number_input(
        "Earth OLR E_olr (W/m²)",
        min_value=0.0,
        value=float(defaults.earth_olr_w_per_m2),
        step=1.0,
    )
    bond_albedo = st.slider(
        "Earth Bond albedo a",
        0.0,
        1.0,
        float(defaults.earth_bond_albedo),
        0.01,
    )

    run_clicked = st.button("Run simulation", type="primary")

request = GuiRunRequest(
    mass_kg=float(mass_kg),
    specific_heat_j_per_kg_k=float(specific_heat),
    initial_temperature_c=float(initial_c),
    absorptivity=float(absorptivity),
    emissivity=float(emissivity),
    projected_area_m2=float(projected_area),
    radiating_area_m2=float(radiating_area),
    earth_facing_area_m2=float(earth_facing_area),
    albedo_area_m2=float(albedo_area),
    internal_heat_w=float(internal_heat_w),
    solar_flux_w_per_m2=float(solar_flux),
    earth_olr_w_per_m2=float(earth_olr),
    earth_bond_albedo=float(bond_albedo),
    altitude_km=float(altitude_km),
    orbit_count=int(orbit_count),
    time_step_s=float(time_step_s),
    include_earth_infrared=bool(include_earth_infrared),
    include_albedo=bool(include_albedo),
)

st.subheader("Model notes")
st.write(
    f"Infrared absorptivity is set equal to emissivity (Kirchhoff): "
    f"α_ir = ε = **{emissivity:.2f}**. "
    "Albedo uses solar absorptivity α. Earth IR can remain on in eclipse; albedo is zero in eclipse."
)

if run_clicked:
    try:
        with st.spinner("Running verified orbital thermal solver..."):
            result = run_gui_simulation(request)
            _, orbit, _, _ = build_model_inputs(request)
            metrics = temperature_metrics_c(result)
            figure = make_gui_temperature_figure(result)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Initial", f"{metrics['initial_c']:.2f} °C")
        col2.metric("Minimum", f"{metrics['minimum_c']:.2f} °C")
        col3.metric("Maximum", f"{metrics['maximum_c']:.2f} °C")
        col4.metric("Final", f"{metrics['final_c']:.2f} °C")

        st.pyplot(figure, clear_figure=True)

        st.subheader("Orbit summary")
        st.write(
            {
                "Altitude (km)": request.altitude_km,
                "Period (min)": result.period_s / 60.0,
                "Eclipse per orbit (min)": result.eclipse_duration_s / 60.0,
                "Sunlight per orbit (min)": result.sunlight_duration_s / 60.0,
                "Earth IR enabled": request.include_earth_infrared,
                "Q_earth_ir (W)": result.earth_infrared_heat_w,
                "Albedo enabled": request.include_albedo,
                "Samples": len(result.time_s),
                "Closed-form period check (min)": orbital_period_s(orbit) / 60.0,
            }
        )
    except Exception as exc:  # noqa: BLE001 - show validation errors in the UI
        st.error(f"Simulation failed: {exc}")
else:
    st.info("Set inputs in the sidebar, then click **Run simulation**.")
