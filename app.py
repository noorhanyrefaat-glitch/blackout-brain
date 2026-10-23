import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from simulation import STRATEGIES, compare_all, generate_scenario

st.set_page_config(
    page_title="Blackout-Brain",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ Blackout-Brain")
st.caption(
    "AI-inspired decision support for power restoration after a disaster. "
    "Educational simulation using synthetic data."
)

# Fixed positions for a schematic city map (not real geographic coordinates).
CITY_POSITIONS = {
    "Downtown": (0, 0),
    "North Hills": (0, 2),
    "Riverside": (2, 0),
    "Industrial Zone": (3, -1),
    "Old Town": (-2, 0),
    "Airport District": (4, 2),
    "University Quarter": (-2, 2),
    "Harbor": (4, -1),
    "East Suburbs": (2, 2),
    "West Suburbs": (-4, 1),
    "Medical District": (-1, -2),
    "Green Valley": (-4, -1),
}

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Scenario")
    severity = st.slider("Disaster severity", 1, 5, 3)
    n_regions = st.slider("Number of regions", 4, 12, 8)
    seed = st.number_input("Random seed", 0, 9999, 42)

    st.header("Resources")
    crews = st.slider("Repair crews", 1, 6, 2)
    travel = st.slider(
        "Travel time per dispatch (h)",
        0.0, 2.0, 0.5, 0.25,
    )

    run = st.button(
        "▶ Run simulation",
        type="primary",
        use_container_width=True,
    )

current_settings = {
    "severity": severity,
    "n_regions": n_regions,
    "seed": int(seed),
    "crews": crews,
    "travel": travel,
}

# ---------------- Run and save simulation ----------------
if run:
    with st.spinner("Simulating power restoration..."):
        scenario = generate_scenario(
            n_regions, severity, crews, travel, int(seed)
        )
        table, results = compare_all(scenario)

        st.session_state["simulation_scenario"] = scenario
        st.session_state["simulation_table"] = table
        st.session_state["simulation_results"] = results
        st.session_state["simulation_settings"] = current_settings.copy()
        st.session_state["timeline_time"] = 0.0

    st.success("Simulation completed successfully!")

if "simulation_table" not in st.session_state:
    st.info("Choose the settings and click Run simulation to begin.")
    st.stop()

scenario = st.session_state["simulation_scenario"]
table = st.session_state["simulation_table"]
results = st.session_state["simulation_results"]
saved_settings = st.session_state["simulation_settings"]

if current_settings != saved_settings:
    st.warning(
        "Your settings have changed. The results below belong to "
        "the previous run. Click Run simulation to update them."
    )

# ---------------- KPIs ----------------
best_unserved = table.loc[table["Unserved Energy (MWh)"].idxmin()]
best_avg = table.loc[table["Avg Restoration Time (h)"].idxmin()]
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

# ---------------- Strategy comparison ----------------
st.header("Strategy comparison")
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

st.dataframe(table, use_container_width=True, hide_index=True)

st.download_button(
    "⬇ Download comparison (CSV)",
    table.to_csv(index=False).encode("utf-8"),
    "blackout_brain_comparison.csv",
    "text/csv",
)

# ---------------- Select a strategy ----------------
st.header("🗺️ Live Disaster Simulation")

chosen = st.selectbox(
    "Choose a strategy to visualize",
    list(STRATEGIES),
)

_, details, log = results[chosen]

# Total simulated duration for this strategy.
max_time = max(
    float(details["Restored at (h)"].max()), 0.01
)

# Interactive time control: scrubbing this slider updates the map.
timeline_time = st.slider(
    "Simulation time (hours)",
    min_value=0.0,
    max_value=max_time,
    step=0.25,
    key="timeline_time",
)

st.caption(
    f"Showing {chosen} at hour {timeline_time:.2f} "
    f"of {max_time:.2f} simulated hours."
)

# ---------------- Build current map state ----------------
map_rows = []

for _, row in details.iterrows():
    name = row["Region"]
    x, y = CITY_POSITIONS[name]
    dispatch = float(row["Dispatch (h)"])
    restored = float(row["Restored at (h)"])

    if timeline_time >= restored:
        status = "Restored"
    elif timeline_time >= dispatch:
        status = "Crew dispatched"
    else:
        status = "Awaiting repair"

    map_rows.append({
        "Region": name,
        "x": x,
        "y": y,
        "Status": status,
        "Crew": int(row["Crew"]),
        "Load (MW)": row["Load (MW)"],
        "Hospitals": row["Hospitals"],
        "Dispatch (h)": dispatch,
        "Restored at (h)": restored,
    })

map_df = pd.DataFrame(map_rows)

colors = {
    "Awaiting repair": "#E74C3C",
    "Crew dispatched": "#F39C12",
    "Restored": "#2ECC71",
}

# Schematic route: order in which this strategy dispatches crews.
route_df = map_df.sort_values(
    ["Dispatch (h)", "Crew"]
).reset_index(drop=True)

fig_map = go.Figure()

# Draw a dashed line showing dispatch order, not a real road network.
if len(route_df) > 1:
    fig_map.add_trace(go.Scatter(
        x=route_df["x"],
        y=route_df["y"],
        mode="lines",
        line=dict(color="#8293A6", width=2, dash="dash"),
        hoverinfo="skip",
        name="Dispatch order",
    ))

for status, color in colors.items():
    subset = map_df[map_df["Status"] == status]
    if subset.empty:
        continue

    fig_map.add_trace(go.Scatter(
        x=subset["x"],
        y=subset["y"],
        mode="markers+text",
        text=subset["Region"],
        textposition="top center",
        name=status,
        marker=dict(
            size=24,
            color=color,
            line=dict(color="white", width=1),
        ),
        customdata=subset[
            ["Crew", "Load (MW)", "Hospitals",
             "Dispatch (h)", "Restored at (h)"]
        ],
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Status: " + status + "<br>"
            "Crew: %{customdata[0]}<br>"
            "Load: %{customdata[1]} MW<br>"
            "Critical facilities: %{customdata[2]}<br>"
            "Dispatch: %{customdata[3]:.2f} h<br>"
            "Restored: %{customdata[4]:.2f} h"
            "<extra></extra>"
        ),
    ))

fig_map.update_layout(
    title="City power status (schematic map)",
    height=550,
    template="plotly_dark",
    xaxis=dict(visible=False, range=[-5.5, 5.5]),
    yaxis=dict(visible=False, range=[-3.5, 3.5], scaleanchor="x"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(l=10, r=10, t=70, b=10),
)

st.plotly_chart(fig_map, use_container_width=True)

st.caption(
    "Map positions are illustrative, not geographic. "
    "Dashed lines show dispatch order, not actual roads or GPS routes."
)

# ---------------- Timeline and event playback ----------------
st.subheader("⏱️ Event timeline")

timeline_log = log.sort_values(
    ["Time (h)", "Event", "Crew"]
).copy()

timeline_log["Status at selected time"] = timeline_log[
    "Time (h)"
].apply(
    lambda t: "Occurred" if float(t) <= timeline_time else "Upcoming"
)

past_events = timeline_log[
    timeline_log["Time (h)"] <= timeline_time
]

future_events = timeline_log[
    timeline_log["Time (h)"] > timeline_time
]

a, b = st.columns(2)
a.metric("Events occurred", len(past_events))
b.metric("Events remaining", len(future_events))

st.markdown("**Events up to the selected time**")
st.dataframe(
    past_events,
    use_container_width=True,
    hide_index=True,
)

with st.expander("Show upcoming events"):
    st.dataframe(
        future_events,
        use_container_width=True,
        hide_index=True,
    )

st.markdown("**Per-region repair details**")
st.dataframe(
    details,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Prototype using synthetic data and simplified assumptions. "
    "This is an educational decision-support simulation, "
    "not a real electrical-grid control system."
)
