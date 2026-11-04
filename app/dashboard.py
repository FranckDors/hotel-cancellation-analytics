from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Booking Cancellation and Agent Analytics", layout="wide")
DATA = Path(__file__).parent / "exports"
LEAD_ORDER = ["0-7 days", "8-30 days", "31-90 days", "91-180 days", "181+ days"]

@st.cache_data
def load(name):
    return pd.read_csv(DATA / name)

by_year = load("overview_by_year.csv")
drivers = load("driver_rates.csv")
agents = load("agent_summary.csv")
segments = load("agent_segments.csv")
seg_profile = load("segment_profile.csv")
dq = load("dq_results.csv")
metrics = load("model_metrics.csv")
thresholds = load("threshold_table.csv")

page = st.sidebar.radio("Page", ["Overview and drivers", "Agent lookup",
                                 "Segments", "Model and data quality"])
st.sidebar.caption("Personal project. Public hotel booking dataset "
                   "(Antonio, de Almeida and Nunes, 2019).")

# ---------------------------------------------------------------- page 1
if page == "Overview and drivers":
    st.title("Hotel booking cancellations: overview and drivers")
    total = int(by_year["bookings"].sum())
    overall = (by_year["bookings"] * by_year["cancel_pct"]).sum() / total
    c1, c2, c3 = st.columns(3)
    c1.metric("Bookings analysed", f"{total:,}")
    c2.metric("Overall cancellation rate", f"{overall:.1f}%")
    c3.metric("Arrival years", f"{int(by_year['arrival_year'].min())}-{int(by_year['arrival_year'].max())}")

    driver = st.selectbox("Driver", sorted(drivers["driver"].unique()))
    d = drivers[drivers["driver"] == driver]
    orders = {"category": LEAD_ORDER} if driver == "lead_time_bucket" else {}

    left, right = st.columns(2)
    with left:
        st.subheader("All years")
        fig = px.bar(d[d["year"] == "All"], x="category", y="cancel_pct",
                     text="cancel_pct", category_orders=orders,
                     labels={"cancel_pct": "Cancellation rate (%)", "category": ""})
        fig.add_hline(y=overall, line_dash="dash", annotation_text="overall")
        st.plotly_chart(fig)
    with right:
        st.subheader("By arrival year (is the pattern stable?)")
        fig = px.bar(d[d["year"] != "All"], x="category", y="cancel_pct", color="year",
                     barmode="group", category_orders=orders,
                     labels={"cancel_pct": "Cancellation rate (%)", "category": ""})
        st.plotly_chart(fig)

    if driver == "deposit_type":
        st.warning("Non Refund bookings cancel at about 99% in every year, which looks like a "
                   "recording quirk in the data. I report it but do not base recommendations on it.")

# ---------------------------------------------------------------- page 2
elif page == "Agent lookup":
    st.title("Agent lookup")
    ag = agents.sort_values("bookings", ascending=False).copy()
    agent_id = st.selectbox("Agent ID (largest first)", ag["agent_id"].tolist())
    row = ag[ag["agent_id"] == agent_id].iloc[0]
    overall_rate = 100 * row["overall_cancel_rate"]
    rate = 100 * row["cancel_rate"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bookings", f"{int(row['bookings']):,}")
    c2.metric("Cancel rate", f"{rate:.1f}%", f"{rate - overall_rate:+.1f} pts vs overall",
              delta_color="inverse")
    c3.metric("Share of all cancellations", f"{100 * row['share_of_all_cancellations']:.2f}%")
    c4.metric("Rank by bookings", int(row["rank_by_bookings"]))

    seg = segments[segments["agent_id"] == agent_id]
    if len(seg):
        st.success(f"Segment: {seg.iloc[0]['segment']}")
    else:
        st.info("This agent has fewer than 100 bookings, so it was not assigned a segment.")
    if bool(row["is_high_cancel_agent"]):
        st.error("Flagged as a high-cancel agent (100+ bookings and a rate 10+ points above overall).")

    ag["cancel_pct"] = 100 * ag["cancel_rate"]
    ag["selected"] = ag["agent_id"] == agent_id
    fig = px.scatter(ag, x="bookings", y="cancel_pct", color="selected", log_x=True,
                     hover_name="agent_id",
                     labels={"cancel_pct": "Cancellation rate (%)", "bookings": "Bookings (log scale)"})
    fig.add_hline(y=overall_rate, line_dash="dash", annotation_text="overall")
    st.plotly_chart(fig)

    st.subheader("Top 15 agents by number of cancellations")
    top = ag.sort_values("cancellations", ascending=False).head(15)
    top = top.assign(cancel_pct=top["cancel_pct"].round(1))
    st.dataframe(top[["agent_id", "bookings", "cancellations", "cancel_pct",
                      "is_high_cancel_agent"]], hide_index=True)

# ---------------------------------------------------------------- page 3
elif page == "Segments":
    st.title("Agent segments")
    st.caption("84 agents with 100+ bookings, grouped by behavior with K-means "
               "(silhouette 0.24, stability ARI 1.00). Treat as a practical grouping, "
               "not distinct natural clusters.")
    cols = ["segment", "agents", "pct_of_agent_bookings", "pct_of_cancellations",
            "cancel_pct", "cancel_pct_excl_non_refund", "pct_non_refund",
            "avg_lead_time", "avg_adr"]
    st.dataframe(seg_profile[cols], hide_index=True)

    comp = seg_profile.melt(id_vars="segment",
                            value_vars=["cancel_pct", "cancel_pct_excl_non_refund"],
                            var_name="measure", value_name="rate")
    comp["measure"] = comp["measure"].map({"cancel_pct": "All bookings",
                                           "cancel_pct_excl_non_refund": "Excluding Non Refund"})
    fig = px.bar(comp, x="segment", y="rate", color="measure", barmode="group", text="rate",
                 labels={"rate": "Cancellation rate (%)", "segment": ""})
    st.plotly_chart(fig)
    st.info("The group specialists' 66% falls to 32% once Non Refund bookings are excluded, "
            "so the Non Refund effect, not group business itself, drives the high rate.")

    img = DATA / "agent_segments_pca.png"
    if img.exists():
        st.image(str(img), caption="2D view of the segments (ten features squeezed into two)")

    st.subheader("Recommended actions")
    for _, r in seg_profile.iterrows():
        st.markdown(f"**{r['segment']}**: {r['recommended_action']}")

# ---------------------------------------------------------------- page 4
else:
    st.title("Prediction model and data quality")
    st.subheader("Model comparison (tested on 2017 arrivals)")
    st.dataframe(metrics, hide_index=True)
    st.caption("The row marked LEAKY only shows what leakage looks like and is not used.")

    st.subheader("Threshold trade-off (final model)")
    th = thresholds.melt(id_vars="threshold", value_vars=["precision", "recall"],
                         var_name="metric", value_name="value")
    fig = px.line(th, x="threshold", y="value", color="metric", markers=True)
    st.plotly_chart(fig)
    st.dataframe(thresholds, hide_index=True)

    st.subheader("Data quality checks")
    st.dataframe(dq, hide_index=True)