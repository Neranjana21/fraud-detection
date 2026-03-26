import random
import numpy as np
import pandas as pd
import networkx as nx

NUM_ACCOUNTS = 1000
NUM_TRANSACTIONS = 10000
NUM_FRAUD_RINGS = 10
RING_SIZE = 5

accounts = [f"A{i}" for i in range(NUM_ACCOUNTS)]
G = nx.DiGraph()

# Normal transactions
for _ in range(NUM_TRANSACTIONS):
    sender = random.choice(accounts)
    receiver = random.choice(accounts)
    if sender != receiver:
        amount = random.randint(100, 5000)
        G.add_edge(sender, receiver, amount=amount)

# Inject Fraud Rings
fraud_nodes = set()

for _ in range(NUM_FRAUD_RINGS):
    ring = random.sample(accounts, RING_SIZE)
    for i in range(RING_SIZE):
        sender = ring[i]
        receiver = ring[(i + 1) % RING_SIZE]
        G.add_edge(sender, receiver, amount=random.randint(10000, 20000))
        fraud_nodes.add(sender)
        fraud_nodes.add(receiver)

# Inject Sleeper Mules
for _ in range(20):
    mule = random.choice(accounts)
    fraud_nodes.add(mule)
    for _ in range(15):
        sender = random.choice(accounts)
        if sender != mule:
            G.add_edge(sender, mule, amount=random.randint(8000, 15000))

# Create node features
features = []
labels = []

for node in G.nodes():
    in_deg = G.in_degree(node)
    out_deg = G.out_degree(node)
    total_in = sum(G[u][node]['amount'] for u in G.predecessors(node)) if in_deg > 0 else 0
    total_out = sum(G[node][v]['amount'] for v in G.successors(node)) if out_deg > 0 else 0

    features.append([in_deg, out_deg, total_in, total_out])
    labels.append(1 if node in fraud_nodes else 0)

features = np.array(features)
labels = np.array(labels)

# Save
np.save("node_features.npy", features)
np.save("labels.npy", labels)

# Map node IDs to integers
node_to_idx = {node: idx for idx, node in enumerate(G.nodes())}

edges = []
for u, v in G.edges():
    edges.append([node_to_idx[u], node_to_idx[v]])

edge_index = np.array(edges).T


np.save("edge_index.npy", edge_index)

print("Dataset generated successfully.")
print("Total Nodes:", len(G.nodes()))
print("Fraud Nodes:", sum(labels))

