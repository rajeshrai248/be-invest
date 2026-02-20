"""Shared constants for Langfuse evaluation scripts."""

import os

BROKERS = [
    "Degiro Belgium",
    "Bolero",
    "Keytrade Bank",
    "ING Self Invest",
    "Rebel",
    "Revolut",
]

INSTRUMENTS = ["stocks", "etfs", "bonds"]

AMOUNTS = [250, 500, 1000, 2500, 5000, 10000, 50000]

DATASET_FEE_ACCURACY = "chat-fee-accuracy"
DATASET_BROKER_COMPARISON = "chat-broker-comparison"

API_BASE_URL = os.environ.get("EVAL_API_BASE_URL", "http://localhost:8000")

TOLERANCE = 0.01  # EUR
