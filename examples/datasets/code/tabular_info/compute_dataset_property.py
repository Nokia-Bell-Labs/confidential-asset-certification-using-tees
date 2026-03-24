# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

from pathlib import Path
import json
import sys
import time

import libprop.tabular as lptab
import libprop.file_utils as lpf
import libprop.stats as lps

from libprop.tabular import CELL_TYPES_NUMERIC, CELL_TYPES_SEQUENCE

# 1. record each file name included
# 1.1 read different file formats depending on parameters (i.e., filetype)
# 2. determine column types and report how many rows for each type (format check)
# (in a well-formatted dataset, each column should only have one type)
# 3. report on the null values
# 4. for certain column types, report statistics
# 4.1 uniqueness: if all rows are of a small number of <string> values, treat the column as 'categorical' < 10.
# 4.2 strings: length ranges
# 4.3 lists: length ranges
# 4.3 int/float/double: their percentiles, min, max, mean

def find_files(data_path, glob):
    data_dir = Path(data_path)

    prefixed_filenames = {}
    prefixed_filepaths = {}
    filepaths = list(data_dir.glob(glob))
    for f in filepaths:
        print(str(f))
        base_fname = str(f)[len(str(data_path)):]
        if not data_path.endswith("/"):
            base_fname = base_fname[1:]
        tokens = base_fname.split("/")
        prefix = tokens[-2]
        if prefix not in prefixed_filepaths:
            prefixed_filepaths[prefix] = []
        if prefix not in prefixed_filenames:
            prefixed_filenames[prefix] = []

        prefixed_filepaths[prefix].append(f)
        prefixed_filenames[prefix].append(base_fname)

    return prefixed_filepaths, prefixed_filenames

def compute_property(filenames, df):
    output = {}
    output["filenames"] = filenames

    info = {}

    for column_name in df.columns:
        column_values = df[column_name].to_list()
        column_info, additional_info = lptab.extract_column_info(column_name, column_values)

        clrs = {}
        ccs = {}
        for cell_type in CELL_TYPES_SEQUENCE:
            cell_lengths = additional_info["cell_lengths"]
            if cell_type in cell_lengths:
                # first check if this is categorical string data
                # with a small number of unique string values (i.e., 0 < L < 10)
                cell_unique_string_values = additional_info["cell_unique_string_values"]
                cc = lptab.compute_data_categories(cell_unique_string_values)

                if cc and cell_type == "<class 'str'>":
                    ccs[cell_type] = cc
                else:
                    clr = lptab.compute_data_length_ranges(cell_lengths[cell_type])
                    clrs[cell_type] = clr

        css = {}
        for cell_type in CELL_TYPES_NUMERIC:
            cell_numeric_values = additional_info["cell_numeric_values"]
            if cell_type in cell_numeric_values:
                cell_stats = lps.compute_cell_value_statistics(cell_numeric_values[cell_type])
                css[cell_type] = cell_stats


        if clrs:
            column_info["data_length_ranges"] = clrs
        if ccs:
            column_info["data_categories"] = ccs
        if css:
            column_info["data_statistics"] = css

        info[column_name] = column_info

    output["columns"] = info
    output["number_of_items"] = len(df)
    output["timestamp"] = time.time()
    
    return output


if __name__ == "__main__":
    print(sys.argv)

    data_path = "/tmp/inputs"

    data_dir = Path(data_path)
    num_filetypes = {}
    for filetype in ["csv", "parquet", "jsonl", "json", "arrow"]:
        glob = "**/*." + filetype
        num_filetypes[filetype] = len(list(data_dir.glob(glob)))

    filetype = max(num_filetypes, key=num_filetypes.get)
    glob = "**/*." + filetype

    print(data_path, glob)
    prefixed_filepaths, prefixed_filenames = find_files(data_path, glob)
    prefixed_output = {}
    for prefix in prefixed_filenames:
        df = lpf.read_files(prefixed_filepaths[prefix])
        prefixed_output[prefix] = compute_property(prefixed_filenames[prefix], df)

    print(json.dumps(prefixed_output, indent=4, sort_keys=True))
    with open("/tmp/outputs/computation_result.json", "w") as f:
        json.dump(prefixed_output, f, indent=4, sort_keys=True)
