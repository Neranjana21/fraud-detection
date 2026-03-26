from fastapi import FastAPI, HTTPException, Header, Depends, Request
from pydantic import BaseModel
from typing import List
from datetime import datetime
import networkx as nx
import hashlib
import json
import torch
import numpy as np

from torch_geometric.data import Data
from sklearn.preprocessing import StandardScaler
from gnn_model import GraphSAGE

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi.responses import JSONResponse


# =========================================================
# App Setup
# =========================================================
app = FastAPI()

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests"}
    )

API_KEY = "supersecret123"

def require_api_key(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


# =========================================================
# Load GNN Model
# =========================================================
model = GraphSAGE(in_channels=6)
model.load_state_dict(torch.load("gnn_model.pth", map_location=torch.device("cpu")))
model.eval()


# =========================================================
# Request Models
# =========================================================
class Transaction(BaseModel):
    sender: str
    receiver: str
    amount: float
    time: datetime

class Batch(BaseModel):
    transactions: List[Transaction]


@app.get("/health")
def health():
    return {"status": "ok"}


# =========================================================
# ANALYZE ENDPOINT
# =========================================================
@app.post("/analyze", dependencies=[Depends(require_api_key)])
@limiter.limit("50/minute")   # Increased for testing
def analyze(request: Request, batch: Batch):

    txs = batch.transactions

    # Duplicate Protection
    batch_hash = hashlib.sha256(
        json.dumps(batch.dict(), sort_keys=True, default=str).encode()
    ).hexdigest()

    if not hasattr(app.state, "seen"):
        app.state.seen = set()

    if batch_hash in app.state.seen:
        raise HTTPException(409, "Duplicate batch")

    app.state.seen.add(batch_hash)

    # Build Graph
    G = nx.DiGraph()
    for tx in txs:
        G.add_edge(tx.sender, tx.receiver, amount=tx.amount, time=tx.time)

    if len(G.nodes) == 0:
        return {"batch_risk_score": 0, "batch_risk_level": "LOW"}

    node_list = list(G.nodes())
    node_to_idx = {node: idx for idx, node in enumerate(node_list)}

    # =========================================================
    # Feature Extraction
    # =========================================================
    features = []
    node_times = {node: [] for node in node_list}

    for node in node_list:
        in_deg = G.in_degree(node)
        out_deg = G.out_degree(node)

        total_in = sum(G[u][node]['amount'] for u in G.predecessors(node)) if in_deg else 0
        total_out = sum(G[node][v]['amount'] for v in G.successors(node)) if out_deg else 0

        for u in G.predecessors(node):
            node_times[node].append(G[u][node]['time'])
        for v in G.successors(node):
            node_times[node].append(G[node][v]['time'])

        fan_in_ratio = in_deg / (in_deg + out_deg + 1)
        amount_ratio = total_in / (total_in + total_out + 1)

        features.append([
            in_deg,
            out_deg,
            total_in,
            total_out,
            fan_in_ratio,
            amount_ratio
        ])

    features = np.array(features)
    features = StandardScaler().fit_transform(features)

    # Structural anomaly score
    anomaly_scores = np.linalg.norm(features, axis=1)
    if anomaly_scores.max() > 0:
        anomaly_scores = anomaly_scores / anomaly_scores.max()

    x = torch.tensor(features, dtype=torch.float)

    edges = [[node_to_idx[u], node_to_idx[v]] for u, v in G.edges()]
    edge_index = torch.tensor(np.array(edges).T, dtype=torch.long)

    data = Data(x=x, edge_index=edge_index)

    # =========================================================
    # Run GNN
    # =========================================================
    with torch.no_grad():
        logits = model(data.x, data.edge_index)
        probs = torch.softmax(logits, dim=1)
        fraud_probs = probs[:, 1].numpy()

    centrality_scores = nx.degree_centrality(G)

    # Ring detection
    rings = []
    try:
        for cycle in nx.simple_cycles(G):
            if 3 <= len(cycle) <= 6:
                rings.append(cycle)
    except:
        pass

    ring_nodes = set()
    for r in rings:
        ring_nodes.update(r)

    # =========================================================
    # FINAL HYBRID RISK SCORING
    # =========================================================
    accounts = []
    hybrid_scores = []

    for idx, node in enumerate(node_list):

        gnn_score = float(fraud_probs[idx])
        anomaly_score = float(anomaly_scores[idx])
        centrality_score = float(centrality_scores[node])

        velocity_bonus = 0
        explanation_parts = []

        in_deg = G.in_degree(node)
        out_deg = G.out_degree(node)

        # Velocity Detection
        times = sorted(node_times[node])
        if len(times) >= 3:
            for i in range(len(times) - 2):
                delta = (times[i + 2] - times[i]).total_seconds()
                if delta <= 60:
                    velocity_bonus = 0.2
                    explanation_parts.append("High velocity burst (≤60s)")
                    break

        if node in ring_nodes:
            explanation_parts.append("Circular transaction ring")

        if centrality_score > 0.45:
            explanation_parts.append("High network centrality")

        if in_deg > 3 and out_deg > 3:
            explanation_parts.append("High bidirectional activity")

        final_score = (
            0.5 * gnn_score +
            0.2 * anomaly_score +
            0.1 * centrality_score +
            velocity_bonus
        )

        if len(G.nodes) < 4:
            final_score *= 0.6

        final_score = min(final_score, 0.95)
        hybrid_scores.append(final_score)

        if final_score > 0.5:
            if not explanation_parts:
                explanation_parts.append("Graph structural anomaly")

            accounts.append({
                "account": node,
                "risk_score": round(final_score, 3),
                "confidence": round(gnn_score, 3),
                "centrality": round(centrality_score, 3),
                "top_drivers": explanation_parts,
                "explanation": ", ".join(explanation_parts)
            })

    # =========================================================
    # Batch Risk Logic
    # =========================================================
    sorted_scores = sorted(hybrid_scores, reverse=True)
    top_k = sorted_scores[:min(3, len(sorted_scores))]
    base_score = float(sum(top_k) / len(top_k))

    high_risk_nodes = sum(score > 0.7 for score in hybrid_scores)
    concentration_bonus = high_risk_nodes * 0.015

    batch_risk = min(base_score + concentration_bonus, 0.95)

    batch_level = (
        "HIGH" if batch_risk >= 0.72
        else "MEDIUM" if batch_risk >= 0.45
        else "LOW"
    )

    return {
        "batch_risk_score": round(batch_risk, 3),
        "batch_risk_level": batch_level,
        "accounts": accounts,
        "rings": rings,
        "transactions": [tx.dict() for tx in txs]
    }

