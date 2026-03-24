# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

from pathlib import Path
import json
import math
import sys
import time

import libprop.file_utils as lpf

def find_files(data_path, glob, filetype):
    data_dir = Path(data_path)

    filenames = []
    filepaths = list(data_dir.glob(glob))
    for f in filepaths:
        print(str(f))
        base_fname = str(f)[len(str(data_path)):]
        if not data_path.endswith("/"):
            base_fname = base_fname[1:]
        filenames.append(base_fname)

    return filepaths, filenames

def compute_property(filenames, df):
    output = {}
    output["filenames"] = filenames

    column_info = {}

    # Count the entries per system prompt
    if "system_prompt" in df.columns:
        column_info["system_prompt"] = {}
        prompt_col = df["system_prompt"]
        unique_prompts = prompt_col.unique()
        count_per_prompt = {}
        for prompt in unique_prompts:
            prompt_count = prompt_col[prompt_col == prompt].count()
            count_per_prompt[prompt] = int(prompt_count)
        column_info["system_prompt"]["cell_unique_count"] = len(unique_prompts)
        column_info["system_prompt"]["cell_count_per_unique"] = count_per_prompt

    output["column_info"] = column_info
    output["number_of_items"] = len(df)
    output["timestamp"] = time.time()
    
    return output

if __name__ == "__main__":
    
    data_path = "/tmp/inputs"

    data_dir = Path(data_path)
    num_filetypes = {}
    for filetype in ["csv", "parquet", "jsonl", "json", "arrow"]:
        glob = "**/*." + filetype
        num_filetypes[filetype] = len(list(data_dir.glob(glob)))

    filetype = max(num_filetypes, key=num_filetypes.get)
    print(filetype)

    glob = "**/*." + filetype

    print(data_path, glob)

    filepaths, filenames = find_files(data_path, glob, filetype)
    df = lpf.read_files(filepaths)
    output = compute_property(filenames, df)

    print(json.dumps(output, indent=4, sort_keys=True))
    with open("/tmp/outputs/computation_result.json", "w") as f:
        json.dump(output, f, indent=4, sort_keys=True)
