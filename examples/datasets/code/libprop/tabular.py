# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import math

CELL_TYPES_SEQUENCE = ["<class 'str'>", "<class 'list'>", "<class 'numpy.ndarray'>"]
CELL_TYPES_NUMERIC = ["<class 'int'>", "<class 'float'>"]

def compute_data_length_ranges(cell_lengths):
    cell_length_ranges = {}
    if cell_lengths:
        cell_lengths = sorted(cell_lengths)
        min_val = cell_lengths[0]
        max_val = cell_lengths[-1]
        distance = math.ceil((max_val - min_val) / 10.0)
        ranges = []
        if min_val != max_val:
            for j in range(min_val, max_val, distance):
                ranges.append(j)
            for j in range(len(ranges)-1):
                cell_length_ranges[str(ranges[j]) + "-" + str(ranges[j+1])] = 0
            ranges.append(max_val)

            j = 1
            c = 0
            for k in cell_lengths:
                if j == len(ranges) or k < ranges[j]:
                    c += 1
                else:
                    cell_length_ranges[str(ranges[j-1]) + "-" + str(ranges[j])] = c
                    j += 1
                    c = 1

            cell_length_ranges[str(ranges[j-1]) + "-" + str(max_val)] = c

        else:
            ranges = [min_val]
            c = len(cell_lengths)
            cell_length_ranges[str(min_val)] = c
    
    return cell_length_ranges

def compute_data_categories(cell_unique_string_values):
    string_categorical = None
    # this is probably a 'categorical' (i.e., 'classes' in HuggingFace) value 
    # with few unique items (need to check that while reading the cell),
    # so no need to treat it as a normal string
    count_unique = len(cell_unique_string_values)
    if count_unique > 0 and count_unique <= 10:
        string_categorical = str(count_unique) + " class(es)"

    return string_categorical


def check_null(cell, cell_type):
    if cell_type == "<class 'float'>":
        if math.isnan(cell):
            return True
    elif cell is None:
        return True
    return False


def extract_column_info(column_name, column_values):
    count_null = 0
    
    info = {}
    info["column_name"] = column_name

    cell_types = {}

    cell_lengths = {}
    cell_unique_string_values = {}
    cell_numeric_values = {}

    for cell in column_values:
        cell_type = str(type(cell))
        # print(cell, cell_type)
        if check_null(cell, cell_type):
            count_null += 1
            continue

        if cell_type not in cell_types:
            cell_types[cell_type] = 0
        
        cell_types[cell_type] += 1

        if cell_type in CELL_TYPES_SEQUENCE:
            cell_length = len(cell)
            if cell_type not in cell_lengths:
                cell_lengths[cell_type] = []
            
            cell_lengths[cell_type].append(cell_length)

            if cell_type == "<class 'str'>":
                cell_unique_string_values[cell] = True

        elif cell_type in CELL_TYPES_NUMERIC:
            if cell_type not in cell_numeric_values:
                cell_numeric_values[cell_type] = []

            cell_numeric_values[cell_type].append(cell)

        else:
            print(cell_type)
    
    info["column_count_datatypes"] = cell_types
    info["column_count_null"] = count_null
    
    additional_info = {}
    additional_info["cell_lengths"] = cell_lengths
    additional_info["cell_unique_string_values"] = cell_unique_string_values
    additional_info["cell_numeric_values"] = cell_numeric_values

    return info, additional_info

# if __name__ == "__main__":
#     filename = sys.argv[1]
#     filetype = filename[filename.rfind(".")+1:]
#     print(filetype)
#     df = read_data([filename], filetype)

#     column_info = {}

#     for col_name in df.columns:
#         if col_name not in column_info:
#             column_info[col_name] = {}

#         data_type = df[col_name].dtype
#         print(col_name, data_type)
#         # potential string; need to check for empty strings
#         # pandas does not give you "" as 'null'
#         if data_type == "object":
#             cells = df[col_name].to_list()
#             print(df[col_name].isnull().sum())
#             print(cells)
#             continue
#             length_ranges = compute_cell_length_ranges(df[col_name].to_list(), [])
#         elif data_type == "int64" or data_type == "float64":
#             print(df[col_name].isnull().sum())
#             stats = compute_cell_value_statistics(df[col_name].to_list())
#             print(stats)
#         else:
#             print(data_type)
#         print("------")
#         # col_values = df[col_name].to_list()
#         # # print(col_values)
#         # for cell in col_values:
#         #     print(cell)