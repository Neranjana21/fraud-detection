import networkx as nx
import pandas as pd

def compute_risk(df):

    G = nx.DiGraph()

    # Build graph
    for _, row in df.iterrows():
        G.add_edge(row["sender"], row["receiver"])

    total_nodes = len(G.nodes())

    results = []

    # Compute normalized degree centrality
    centrality = nx.degree_centrality(G)

    for node in G.nodes():

        if node.startswith("A"):

            in_deg = G.in_degree(node)
            out_deg = G.out_degree(node)

            centrality_score = centrality[node]

            # Dampening for small graphs
            if total_nodes < 10:
                centrality_score *= 0.4

            # Normalize centrality risk (0–1)
            structural_risk = min(1.0, centrality_score)

            # Basic behavior signal
            behavior_risk = min(1.0, (in_deg + out_deg) / 10)

            # Final weighted hybrid score
            risk_score = (
                structural_risk * 0.6 +
                behavior_risk * 0.4
            )

            results.append({
                "account": node,
                "incoming": in_deg,
                "outgoing": out_deg,
                "centrality": round(centrality_score, 3),
                "risk_score": round(risk_score, 3)
            })

    risk_df = pd.DataFrame(results)

    # Batch-level risk = average of top 3 risky accounts
    if not risk_df.empty:
        batch_risk_score = risk_df.sort_values(
            by="risk_score",
            ascending=False
        )["risk_score"].head(3).mean()
    else:
        batch_risk_score = 0

    # Adjusted safer thresholds
    if batch_risk_score > 0.65:
        risk_level = "HIGH"
    elif batch_risk_score > 0.40:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "batch_risk_score": round(batch_risk_score, 3),
        "batch_risk_level": risk_level,
        "accounts": risk_df.to_dict(orient="records")
    }

