import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from simulation import STRATEGIES, compare_all, generate_scenario

st.set_page_config(page_title="Blackout-Brain", page_icon="⚡", layout="wide")
st.title("⚡ Blackout-Brain")
st.caption("Decision-support dashboard for comparing power-restoration strategies after a disaster.")

# Schematic polygon coordinates: these are illustrative zones, NOT real geographic data.
CITY_ZONES = {
    "University": [(0.5, 6.2), (2.2, 6.6), (3.0, 5.7), (2.5, 4.6), (0.8, 4.8)],
    "North Area": [(3.0, 6.6), (4.8, 6.7), (5.5, 5.8), (4.8, 4.9), (3.4, 5.1), (2.7, 5.7)],
    "Airport": [(7.4, 6.2), (9.2, 6.6), (9.7, 5.2), (8.6, 4.7), (7.5, 5.1)],
    "East Area": [(6.0, 5.8), (7.4, 6.0), (7.5, 4.8), (6.7, 4.2), (5.7, 4.7)],
    "West Area": [(0.3, 4.3), (2.2, 4.5), (2.7, 3.4), (2.0, 2.6), (0.4, 2.9)],
    "Old Town": [(2.5, 4.4), (4.1, 4.7), (4.6, 3.7), (3.8, 2.9), (2.4, 3.3), (2.1, 3.8)],
    "City Center": [(4.2, 4.7), (5.8, 4.8), (6.2, 3.8), (5.2, 3.1), (4.1, 3.4), (3.9, 4.0)],
    "Factory Area": [(6.3, 4.4), (8.1, 4.6), (8.4, 3.4), (7.5, 2.8), (6.2, 3.2)],
    "Green Area": [(0.5, 2.6), (2.1, 2.5), (2.8, 1.6), (2.1, 0.7), (0.4, 1.0)],
    "Hospital Area": [(2.5, 2.8), (4.1, 3.0), (4.4, 1.7), (3.6, 0.9), (2.4, 1.3)],
    "River Area": [(4.5, 2.9), (6.1, 3.1), (6.5, 1.9), (5.7, 0.8), (4.3, 1.3)],
    "Harbor": [(6.4, 2.8), (8.1, 2.9), (9.0, 1.8), (8.3, 0.8), (6.7, 1.1)],
}

STATUS_COLORS = {
    "Awaiting repair": ("#ef4444", "rgba(239,68,68,0.30)"),
    "Crew dispatched": ("#f59e0b", "rgba(245,158,11,0.34)"),
    "Restored": ("#22c55e", "rgba(34,197,94,0.30)"),
}

with st.sidebar:
    st.header("Scenario")
    severity = st.slider("Disaster severity", 1, 5, 3)
    n_regions = st.slider("Number of regions", 4, 12, 8)
    seed = st.number_input("Random seed", min_value=0, max_value=9999, value=42)
    st.header("Resources")
    crews = st.slider("Repair crews", 1, 6, 2)
    travel = st.slider("Travel time per dispatch (h)", 0.0, 2.0, 0.5, 0.25)
    run = st.button("▶ Run simulation", type="primary", use_container_width=True)

settings = {
    "severity": severity,
    "n_regions": n_regions,
    "seed": int(seed),
    "crews": crews,
    "travel": travel,
}

if "simulation_data" not in st.session_state:
    st.session_state.simulation_data = None
if run or st.session_state.simulation_data is None:
    scenario = generate_scenario(n_regions, severity, crews, travel, int(seed))
    table, results = compare_all(scenario)
    st.session_state.simulation_data = {
        "scenario": scenario,
        "table": table,
        "results": results,
        "settings": settings.copy(),
    }

saved = st.session_state.simulation_data
scenario = saved["scenario"]
table = saved["table"]
results = saved["results"]
settings_changed = settings != saved["settings"]
if settings_changed:
    st.warning("Your settings have changed. The results below belong to the previous run. Click Run simulation to update them.")

# Summary cards
best_avg_row = table.loc[table["Avg Restoration Time (h)"].idxmin()]
least_energy_row = table.loc[table["Unserved Energy (MWh)"].idxmin()]
fastest_critical_row = table.loc[table["Critical Facilities Avg Restore (h)"].idxmin()]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Affected regions", len(scenario.regions))
c2.metric("Best average restore time", f"{best_avg_row['Avg Restoration Time (h)']} h", str(best_avg_row["Strategy"]))
c3.metric("Least unserved energy", f"{least_energy_row['Unserved Energy (MWh)']} MWh", str(least_energy_row["Strategy"]))
c4.metric("Fastest critical-facility restore", f"{fastest_critical_row['Critical Facilities Avg Restore (h)']} h", str(fastest_critical_row["Strategy"]))

left, right = st.columns([3.4, 1])
with left:
    st.subheader("City power status — schematic map")
    strategy_name = st.selectbox("Strategy shown on map and timeline", list(STRATEGIES.keys()), key="map_strategy")
    summary, details, log = results[strategy_name]
    max_time = max(float(details["Restored at (h)"].max()), 1.0)
    if st.session_state.get("timeline_time", 0.0) > max_time:
        st.session_state["timeline_time"] = max_time
    timeline_time = st.slider(
        "Simulation time (hours)", min_value=0.0, max_value=float(max_time),
        value=min(float(st.session_state.get("timeline_time", 0.0)), float(max_time)),
        step=0.25, key="timeline_time"
    )

    fig = go.Figure()
    details_by_region = {row["Region"]: row for _, row in details.iterrows()}
    active_regions = set(details_by_region.keys())

    # Draw the city zones, color-coded by their simulated state at the selected time.
    for region_name, points in CITY_ZONES.items():
        if region_name not in active_regions:
            color, fill = ("#64748b", "rgba(100,116,139,0.12)")
            status = "Not affected"
        else:
            row = details_by_region[region_name]
            if timeline_time >= float(row["Restored at (h)"]):
                status = "Restored"
            elif timeline_time >= float(row["Dispatch (h)"]):
                status = "Crew dispatched"
            else:
                status = "Awaiting repair"
            color, fill = STATUS_COLORS[status]

        xs = [p[0] for p in points] + [points[0][0]]
        ys = [p[1] for p in points] + [points[0][1]]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines", fill="toself",
            fillcolor=fill, line=dict(color=color, width=2),
            hovertemplate=f"<b>{region_name}</b><br>Status: {status}<extra></extra>",
            showlegend=False,
        ))
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        label = region_name.replace(" ", "<br>")
        fig.add_annotation(x=cx, y=cy, text=f"<b>{label}</b>", showarrow=False,
                           font=dict(size=10, color="#f8fafc"), bgcolor="rgba(15,23,42,0.72)",
                           bordercolor=color, borderwidth=1, borderpad=3)

    # Draw illustrative dispatch routes for crews that have left but have not restored power yet.
    center = (5.0, 3.8)
    for _, row in details.iterrows():
        if float(row["Dispatch (h)"]) <= timeline_time < float(row["Restored at (h)"]):
            region_name = row["Region"]
            pts = CITY_ZONES[region_name]
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            fig.add_trace(go.Scatter(
                x=[center[0], cx], y=[center[1], cy], mode="lines+markers",
                line=dict(color="#e2e8f0", width=2, dash="dash"),
                marker=dict(size=[5, 8], color="#e2e8f0"), showlegend=False,
                hovertemplate=f"Crew {int(row['Crew'])} route to {region_name}<extra></extra>"
            ))

    fig.add_annotation(x=5.0, y=3.8, text="⚡<br>Dispatch<br>Center", showarrow=False,
                       font=dict(size=10, color="#ffffff"), bgcolor="#1d4ed8", borderpad=5)
    fig.update_layout(
        height=530, margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0b1728",
        font=dict(color="#e2e8f0"),
        xaxis=dict(visible=False, range=[0, 10]), yaxis=dict(visible=False, range=[0.4, 7], scaleanchor="x"),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Schematic fictional city: region shapes and dispatch routes are illustrative, not real geographic locations.")

with right:
    st.subheader("Map legend")
    st.markdown("🟢 **Restored** — power is back\n\n🟠 **Crew dispatched** — repair in progress\n\n🔴 **Awaiting repair** — waiting for a crew\n\n⚪ **Not affected** — outside this scenario")
    st.divider()
    st.subheader("Scenario details")
    st.write(f"**Severity:** {saved['settings']['severity']}/5")
    st.write(f"**Repair crews:** {saved['settings']['crews']}")
    st.write(f"**Travel time:** {saved['settings']['travel']} h per dispatch")
    st.write(f"**Time shown:** {timeline_time:.2f} h")

st.subheader("Strategy comparison")
st.dataframe(table, use_container_width=True, hide_index=True)
chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    st.markdown("**Average restoration time (lower is better)**")
    st.bar_chart(table.set_index("Strategy")[["Avg Restoration Time (h)"]])
with chart_col2:
    st.markdown("**Unserved energy (lower is better)**")
    st.bar_chart(table.set_index("Strategy")[["Unserved Energy (MWh)"]])

st.subheader("Regions and restoration details")
st.dataframe(details.sort_values("Restored at (h)"), use_container_width=True, hide_index=True)

st.subheader("Event log")
filter_event = st.selectbox("Filter events", ["All", "DISPATCH", "RESTORED"], key="event_filter")
visible_log = log.copy()
visible_log = visible_log[visible_log["Time (h)"] <= timeline_time]
if filter_event != "All":
    visible_log = visible_log[visible_log["Event"] == filter_event]
st.dataframe(visible_log, use_container_width=True, hide_index=True)

csv = table.to_csv(index=False).encode("utf-8")
st.download_button("⬇ Download strategy comparison (CSV)", data=csv,
                   file_name="blackout_brain_comparison.csv", mime="text/csv")
