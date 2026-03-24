# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import numpy as np

PERCENTILES = [0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 75.0, 90.0, 95.0, 99.0, 99.5, 99.9]

def compute_percentiles(values, percentiles=PERCENTILES, precision=6):
    """
    Compute specified percentiles for a list or numpy array of values.
    
    Args:
        values (array-like): List or array of numeric values.
        percentiles (list): List of percentiles to compute.
        
    Returns:
        dict: Mapping each percentile (as a float) to its computed value.
    """
    values_np = np.array(values)
    percentile_values = {}
    for p in percentiles:
        percentile_values[float(p)] = round(float(np.percentile(values_np, p)), precision)
    return percentile_values

def count_outliers_iqr(values, multiplier=1.5):
    """
    Count the number of outliers in the given values using the IQR method.
    
    Outliers are defined as values below Q1 - multiplier * IQR or above Q3 + multiplier * IQR.
    
    Args:
        values (array-like): List or array of numeric values.
        multiplier (float): Multiplier for the IQR to define outlier boundaries.
        
    Returns:
        int: Count of outlier values.
    """
    values_np = np.array(values)
    if len(values_np) == 0:
        return 0
    Q1 = np.percentile(values_np, 25)
    Q3 = np.percentile(values_np, 75)
    IQR = Q3 - Q1
    lower_bound = Q1 - multiplier * IQR
    upper_bound = Q3 + multiplier * IQR
    return int(np.sum((values_np < lower_bound) | (values_np > upper_bound)))

def compute_cell_value_statistics(cell_values):
    """
    Compute distribution statistics for a list of values.
    
    Statistics include the minimum, maximum, mean, median, standard deviation, 
    variance, percentiles, and the count of outliers (using the IQR method).
    
    Args:
        durations (list): List of duration values.
        
    Returns:
        dict: Dictionary containing computed statistics.
    """
    stats = {}
    if len(cell_values):
        cell_values = sorted(cell_values)

        stats["min"] = float(np.min(cell_values))
        stats["max"] = float(np.min(cell_values))
        stats["mean"] = float(np.mean(cell_values))
        stats["median"] = float(np.median(cell_values))
        stats["stdev"] = float(np.std(cell_values))
        stats["variance"] = float(np.var(cell_values))
        stats["percentiles"] = compute_percentiles(cell_values)
        stats["count_outliers"] = count_outliers_iqr(cell_values)

    return stats
