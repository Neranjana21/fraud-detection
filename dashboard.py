import streamlit as st
import requests
import json
import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pyvis.network import Network

API_URL = "http://127.0.0.1:8000/analyze"
API_KEY = "supersecret123"

st.set_page_config(page_title="Fraud Risk Control Center", layout="wide")

# =========================================================
# ZERO WHITE SPACE DARK THEME
# =========================================================
st.markdown("""
<style>

header {visibility: hidden;}
footer {visibility: hidden;}

section.main > div {
    padding-top: 0rem !important;
}

.block-container {
    padding-top: 0rem !important;
    padding-bottom: 1rem !important;
}

html, body, .stApp {
    background-color: #0b1220 !important;
    color: #e6edf3 !important;
}

h1, h2, h3, h4 {
    color: #ffffff !important;
}

p, span, div, label {
    color: #e6edf3 !important;
}

[data-testid="stMetricValue"] {
    font-size: 30px !important;
    font-weight: 700 !important;
    color: #ffffff !important;
}

[data-testid="stMetricLabel"] {
    color: #9ca3af !important;
}

button[kind="primary"] {
    background-color: #1d4ed8 !important;
    color: white !important;
    font-weight: 600 !important;
    border-radius: 6px !important;
}

[data-testid="stAlert"] {
    background-color: #111827 !important;
    border: 1px solid #1f2937 !important;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# HEADER
# =========================================================
st.markdown("""
<div style="text-align:center;">
    <h1 style="font-weight:800; margin-bottom:5px;">
        🏦 Fraud Risk Control Center
    </h1>
    <div style="color:#9ca3af; font-size:16px;">
        Hybrid Graph + GNN Fraud Monitoring System
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# =========================================================
# SESSION HISTORY
# =========================================================
if "history" not in st.session_state:
    st.session_state.history = []

# =========================================================
# INPUT
# =========================================================
json_input = st.text_area(
    "Transaction Batch",
    height=110,
    value="""{
  "transactions": [
    {"sender": "A001", "receiver": "A002", "amount": 5000, "time": "2026-01-08T17:10:00"}
  ]
}"""
)

analyze = st.button("Run Risk Analysis", type="primary")

# =========================================================
# MAIN ANALYSIS
# =========================================================
if analyze:

    try:
        payload = json.loads(json_input)
    except:
        st.error("Invalid JSON format.")
        st.stop()

    headers = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers)
    except Exception as e:
        st.error(f"Backend connection failed: {e}")
        st.stop()

    # Show status code for debugging
    if response.status_code != 200:
        st.error(f"Backend Error {response.status_code}: {response.text}")
        st.stop()

    try:
        result = response.json()
    except:
        st.error("Invalid JSON returned from backend.")
        st.stop()

    if not result:
        st.error("Empty response from backend.")
        st.stop()

    # Extract safely
    risk_score = result.get("batch_risk_score", 0)
    risk_level = result.get("batch_risk_level", "LOW")
    confidence = round(risk_score * 100, 1)

    # DEBUG (you can remove later)
    st.write("DEBUG → Batch Score:", risk_score)
    st.write("DEBUG → Risk Level:", risk_level)

    prev_score = st.session_state.history[-1] if st.session_state.history else None
    st.session_state.history.append(risk_score)

    # =====================================================
    # EXECUTIVE SUMMARY
    # =====================================================
    col1, col2, col3 = st.columns(3)

    col1.metric("Risk Level", risk_level)
    col2.metric(
        "Batch Risk Score",
        risk_score,
        delta=round(risk_score - prev_score, 3) if prev_score else None
    )
    col3.metric("Model Confidence", f"{confidence}%")

    st.markdown("---")

    # =====================================================
    # GAUGE + BATCH COMPARISON
    # =====================================================
    colA, colB = st.columns(2)

    with colA:
        st.subheader("Risk Gauge")

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=risk_score,
            gauge={
                'axis': {'range': [0, 1]},
                'bar': {'color': "#ef4444"},
                'steps': [
                    {'range': [0, 0.35], 'color': "#065f46"},
                    {'range': [0.35, 0.55], 'color': "#92400e"},
                    {'range': [0.55, 1], 'color': "#7f1d1d"},
                ],
            }
        ))

        fig.update_layout(
            template="plotly_dark",
            height=300,
            paper_bgcolor="#0b1220",
            plot_bgcolor="#0b1220",
            font=dict(color="#ffffff")
        )

        st.plotly_chart(fig, use_container_width=True)

    with colB:
        st.subheader("Batch Risk Comparison")

        if len(st.session_state.history) > 1:

            df = pd.DataFrame({
                "Batch": range(1, len(st.session_state.history)+1),
                "Risk Score": st.session_state.history
            })

            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=df["Batch"],
                y=df["Risk Score"],
                mode="lines+markers",
                line=dict(width=3),
                marker=dict(size=8)
            ))

            fig2.add_hline(y=0.55, line_dash="dot", line_color="red")

            fig2.update_layout(
                template="plotly_dark",
                height=300,
                paper_bgcolor="#0b1220",
                plot_bgcolor="#0b1220",
                font=dict(color="#ffffff")
            )

            st.plotly_chart(fig2, use_container_width=True)

        else:
            st.info("Run multiple batches to see comparison.")

    st.markdown("---")

    # =====================================================
    # ACCOUNT RISK DISTRIBUTION
    # =====================================================
    st.subheader("Account Risk Distribution")

    if result["accounts"]:
        df_acc = pd.DataFrame(result["accounts"])

        fig_bar = px.bar(
            df_acc,
            x="account",
            y="risk_score",
            color="risk_score",
            color_continuous_scale="Reds",
            template="plotly_dark",
            height=300
        )

        fig_bar.update_layout(
            paper_bgcolor="#0b1220",
            plot_bgcolor="#0b1220",
            font=dict(color="#ffffff")
        )

        st.plotly_chart(fig_bar, use_container_width=True)

    else:
        st.info("No flagged accounts.")

    st.markdown("---")

    # =====================================================
    # EXPLAINABLE CONTRIBUTION GRAPH (NEW)
    # =====================================================
    st.subheader("Explainable Risk Breakdown")

    if result["accounts"]:

        for acc in result["accounts"]:

            breakdown = {
                "Feature": [
                    "Model Confidence",
                    "Network Centrality",
                    "Hybrid Risk Signal"
                ],
                "Contribution": [
                    acc.get("confidence", 0),
                    acc.get("centrality", 0),
                    acc["risk_score"]
                ]
            }

            df_break = pd.DataFrame(breakdown)

            fig_exp = px.bar(
                df_break,
                x="Contribution",
                y="Feature",
                orientation="h",
                template="plotly_dark",
                height=250,
                title=f"Account {acc['account']}"
            )

            fig_exp.update_layout(
                paper_bgcolor="#0b1220",
                plot_bgcolor="#0b1220",
                font=dict(color="#ffffff")
            )

            st.plotly_chart(fig_exp, use_container_width=True)

    else:
        st.info("No explainable risk signals available.")

    st.markdown("---")

       # =====================================================
    # ACCOUNT EXPLANATIONS (FEATURE LIST FORMAT)
    # =====================================================
    st.subheader("Flagged Account Explanations")

    if result["accounts"]:

        for acc in result["accounts"]:

            with st.container():

                st.markdown(f"### Account: {acc['account']}")

                col1, col2, col3 = st.columns(3)

                col1.metric("Risk Score", acc["risk_score"])
                col2.metric("Model Confidence", acc.get("confidence", "N/A"))
                col3.metric("Centrality Score", acc.get("centrality", "N/A"))

                st.markdown("**Detected Features:**")

                drivers = acc.get("top_drivers", [])

                if drivers:
                    for d in drivers:
                        st.markdown(f"- {d}")
                else:
                    st.markdown("_No specific drivers detected_")

                st.markdown("---")

    else:
        st.success("No high-risk accounts detected.")

    # =====================================================
    # NETWORK GRAPH
    # =====================================================
    st.subheader("Transaction Network")

    G = nx.DiGraph()
    for tx in result["transactions"]:
        G.add_edge(tx["sender"], tx["receiver"])

    net = Network(
        height="450px",
        width="100%",
        directed=True,
        bgcolor="#0b1220",
        font_color="white"
    )

    risky = {a["account"] for a in result["accounts"]}

    for node in G.nodes():
        net.add_node(
            node,
            size=30 if node in risky else 20,
            color="#ef4444" if node in risky else "#3b82f6"
        )

    for u, v in G.edges():
        net.add_edge(u, v, arrows="to")

    net.save_graph("graph.html")

    with open("graph.html", "r", encoding="utf-8") as f:
        st.components.v1.html(f.read(), height=460)
