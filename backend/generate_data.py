import pandas as pd
from faker import Faker
import random
from datetime import datetime, timedelta

fake = Faker()

# configuration
NUM_ACCOUNTS = 20
NUM_TRANSACTIONS = 100

accounts = [f"A{i:03d}" for i in range(NUM_ACCOUNTS)]
devices = [f"Phone_{i}" for i in range(5)]

transactions = []

current_time = datetime.now()

for _ in range(NUM_TRANSACTIONS):
    sender = random.choice(accounts)
    receiver = random.choice(accounts)

    while receiver == sender:
        receiver = random.choice(accounts)

    amount = random.randint(500, 5000)
    device = random.choice(devices)

    current_time += timedelta(minutes=random.randint(1, 5))

    transactions.append([
        sender,
        receiver,
        amount,
        current_time.strftime("%H:%M"),
        device
    ])

df = pd.DataFrame(
    transactions,
    columns=["sender", "receiver", "amount", "time", "device"]
)

df.to_csv("data/transactions.csv", index=False)

print("✅ Fake UPI transactions generated successfully.")
