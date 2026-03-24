# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json

from datasets import Dataset

import pandas as pd

def _get_filetype(filepath):
    if not isinstance(filepath, str):
        filepath = str(filepath)

    return filepath[filepath.rfind(".")+1:]

def read_file(filepath):
    filetype = _get_filetype(filepath)

    if filetype == "json":
        df = pd.read_json(filepath)
    elif filetype == "jsonl":
        with open(filepath, "r") as f:
            all_lines = f.readlines()
        df = pd.concat([pd.DataFrame.from_dict([json.loads(line)]) for line in all_lines])
    elif filetype == "parquet":
        df = pd.read_parquet(filepath)
    elif filetype == "csv":
        df = pd.read_csv(filepath)
    elif filetype == "arrow":
        ds = Dataset.from_file(str(filepath))
        df = pd.DataFrame(data=ds)
    else:
        df = None
    
    return df

def read_files(filepaths):
    all_dfs = []
    for filepath in filepaths:
        df = read_file(filepath)
        all_dfs.append(df)
    
    df = pd.concat(all_dfs)

    return df

