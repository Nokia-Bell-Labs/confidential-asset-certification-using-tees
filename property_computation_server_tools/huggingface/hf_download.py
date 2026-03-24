# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
import os
import subprocess

from datasets import get_dataset_config_names, load_dataset

config_filename = "/tmp/hf_config.json"
with open(config_filename, "r") as f:
    config = json.load(f)

asset_type = config["asset_type"]
asset_id = config["asset_id"]
hf_token = None
if "hf_token" in config:
    hf_token = config["hf_token"]
    with open("/tmp/hf_token", "w") as f:
        f.write(hf_token)

# TODO: check repo size before downloading

if asset_type == "dataset":
    dataset_configs = config.get("dataset_configs", "")

    # by default, download all configs
    if dataset_configs == "":
        if hf_token:
            configs = get_dataset_config_names(asset_id, token=hf_token)
        else:
            configs = get_dataset_config_names(asset_id)
    else:
        configs = dataset_configs.split(",")

    for config in configs:
        if hf_token:
            load_dataset(asset_id, config, token=hf_token)
        else:
            load_dataset(asset_id, config)

    print(f'Downloaded configs: {configs}')

elif asset_type == "model":
    my_env = os.environ.copy()
    my_env["HF_HOME"] = "/tmp/HF_CACHE"
    if hf_token:
        my_env["HF_TOKEN"] = "/tmp/hf_token"

    command = [
        "huggingface-cli",
        "download",
        "--repo-type", "model",
        #"--quiet",
        asset_id
    ]

    # Execute the command
    subprocess.run(command, env=my_env, check=True)
