# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import subprocess
import sys
from dotenv import load_dotenv
import os

device_type = sys.argv[1]

print("RUNNING eval.py")

# Load environment variables from dotenv file
dotenv_path = "/tmp/inputs/dotenv"
load_dotenv(dotenv_path, override=True)

# Retrieve environment variables
HF_HOME = os.getenv("HF_HOME")
HF_HUB_OFFLINE = os.getenv("HF_HUB_OFFLINE")

MODEL_ID = os.getenv("MODEL_ID")
DATASET_IDS = os.getenv("DATASET_IDS", "").split(",")
TASKS = os.getenv("TASKS")

# Print the values (similar to echo in shell)
print(f"HF_HOME: {HF_HOME}")
print(f"HF_HUB_OFFLINE: {HF_HUB_OFFLINE}")
print(f"MODEL_ID: {MODEL_ID}")
print(f"DATASET_IDS: {DATASET_IDS}")
print(f"TASKS: {TASKS}")

sys.stdout.flush()

# Construct the command for launching lm_eval
command = [
    "accelerate", "launch", "-m", "lm_eval",
    "--model", "hf",
    "--model_args", f"pretrained={MODEL_ID},dtype=float32",
    "--tasks", TASKS,
    "--batch_size", "8",
    "--output_path", "/tmp/outputs/",
    "--device", device_type
]

my_env = os.environ.copy()
my_env["HF_HOME"] = HF_HOME
my_env["HF_HUB_OFFLINE"] = HF_HUB_OFFLINE

hf_env = [e if e.startswith("HF_") else "" for e in my_env]
for e in my_env:
    if e.startswith("HF_"):
        print(e, my_env[e])

# Execute the command
subprocess.run(command, env=my_env, check=True)
