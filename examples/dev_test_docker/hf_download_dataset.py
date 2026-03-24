# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import os
import sys

from datasets import get_dataset_config_names, load_dataset

HF_TOKEN_PATH = os.getenv("HF_TOKEN_PATH", "")

if HF_TOKEN_PATH != "":
    with open(HF_TOKEN_PATH, "r") as f:
        hf_token = f.read().strip()

DATASET_CONFIGS = os.getenv("DATASET_CONFIGS", "")

dataset_name = sys.argv[1]

# by default, download all configs
if DATASET_CONFIGS == "":
    configs = get_dataset_config_names(dataset_name, token=hf_token)
else:
    configs = DATASET_CONFIGS.split(",")

for config in configs:
    load_dataset(dataset_name, config, token=hf_token)

print(f'Downloaded configs: {configs}')
