import pandas as pd
import networkx as nx

# load transaction data
df = pd.read_csv("data/transactions.csv")

# create a directed graph
G = nx.DiGraph()

# add transactions to graph
for _, row in df.iterrows():
    sender = row["sender"]
    receiver = row["receiver"]
    amount = row["amount"]
    time = row["time"]
    device = row["device"]

    # money flow: sender -> receiver
    G.add_edge(sender, receiver, amount=amount, time=time)

    # device usage: device -> sender
    G.add_edge(device, sender)

print("✅ Transaction network created")
print("Total nodes:", G.number_of_nodes())
print("Total edges:", G.number_of_edges())
print("Sample nodes:", list(G.nodes())[:10])

