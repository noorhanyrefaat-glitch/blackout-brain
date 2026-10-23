import streamlit as st
from simulation import STRATEGIES, compare_all, generate_scenario

st.set_page_config(
    page_title="Blackout-Brain",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ Blackout-Brain")
st.caption(
    "Decision-support dashboard: comparing power-restoration "
    "strategies after a disaster."
)

# ---------------- Sidebar: simulation settings ----------------
with st.sidebar:
    st.header("Scenario")

    severity = st.slider("Disaster severity", 1, 5, 3)
    n_regions = st.slider("Number of regions", 4, 12, 8)
    seed = st.number_input("Random seed", 0, 9999, 42)

    st.header("Resources")

    crews = st.slider("Repair crews", 1, 6, 2)
    travel = st.slider(
        "Travel time per dispatch (h)",
        0.0,
        2.0,
        0.5,
        0.25,
    )

    run = st.button(
        "▶ Run simulation",
        type="primary",
        use_container_width=True,
    )

# Save the settings currently selected by the user.
current_settings = {
    "severity": severity,
    "n_regions": n_regions,
    "seed": int(seed),
    "crews": crews,
    "travel": travel,
}

# ---------------- Run ONLY when the button is clicked ----------------
if run:
    with st.spinner("Running the simulation..."):
        scenario = generate_scenario(
            n_regions,
            severity,
            crews,
            travel,
            int(seed),
        )

        table, results = compare_all(scenario)

        # Keep the last completed run across Streamlit reruns.
        st.session_state["simulation_scenario"] = scenario
        st.session_state["simulation_table"] = table
        st.session_state["simulation_results"] = results
        st.session_state["simulation_settings"] = current_settings.copy()

    st.success("Simulation completed successfully!")

# ---------------- First visit: no results yet ----------------
if "simulation_table" not in st.session_state:
    st.info(
        "Choose the scenario settings in the sidebar, "
        "then click Run simulation to generate your first results."
    )
    st.stop()

# Load the LAST completed simulation.
scenario = st.session_state["simulation_scenario"]
table = st.session_state["simulation_table"]
results = st.session_state["simulation_results"]
saved_settings = st.session_state["simulation_settings"]

# Warn if settings changed after the last run.
if current_settings != saved_settings:
    st.warning(
        "Your settings have changed. The results below belong to "
        "the previous run. Click Run simulation to update them."
    )

# ---------------- KPI cards ----------------
best_unserved = table.loc[
    table["Unserved Energy (MWh)"].idxmin()
]
best_avg = table.loc[
    table["Avg Restoration Time (h)"].idxmin()
]
best_crit = table.loc[
    table["Critical Facilities Avg Restore (h)"].idxmin()
]

c1, c2, c3, c4 = st.columns(4)

c1.metric("Damaged regions", len(scenario.regions))

c2.metric(
    "Best avg restore time",
    f"{best_avg['Avg Restoration Time (h)']} h",
    best_avg["Strategy"],
    delta_color="off",
)

c3.metric(
    "Least unserved energy",
    f"{best_unserved['Unserved Energy (MWh)']:,} MWh",
    best_unserved["Strategy"],
    delta_color="off",
)

c4.metric(
    "Fastest critical restore",
    f"{best_crit['Critical Facilities Avg Restore (h)']} h",
    best_crit["Strategy"],
    delta_color="off",
)

# ---------------- Charts ----------------
left, right = st.columns(2)

with left:
    st.subheader("Average restoration time (h)")
    st.bar_chart(
        table.set_index("Strategy")["Avg Restoration Time (h)"]
    )

with right:
    st.subheader("Unserved energy (MWh)")
    st.bar_chart(
        table.set_index("Strategy")["Unserved Energy (MWh)"]
    )

# ---------------- Results table + CSV ----------------
st.subheader("Strategy comparison")

st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
)

st.download_button(
    "⬇ Download comparison (CSV)",
    table.to_csv(index=False).encode("utf-8"),
    "blackout_brain_comparison.csv",
    "text/csv",
)

# ---------------- Event log ----------------
st.subheader("Event log")

chosen = st.selectbox(
    "Inspect strategy",
    list(STRATEGIES),
)

_, details, log = results[chosen]

kind = st.multiselect(
    "Event types",
    ["DISPATCH", "RESTORED"],
    default=["DISPATCH", "RESTORED"],
)

st.dataframe(
    log[log["Event"].isin(kind)],
    use_container_width=True,
    hide_index=True,
)

with st.expander("Per-region details"):
    st.dataframe(
        details,
        use_container_width=True,
        hide_index=True,
    )

st.caption(
    "Prototype: synthetic data and simplified assumptions. "
    "Map view and inter-region cascade are planned future work."
)
