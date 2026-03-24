# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

from pathlib import Path
import json
import sys
import os

import numpy as np
import soundfile as sf

import libprop.audio as lpa
import libprop.stats as lps

def analyze_signal_quality(file_path):
    """
    Analyze the signal quality and consistency for an audio file.
    
    Computes various metrics including duration distribution (with percentiles and outlier count),
    sampling rate, bit depth, file format consistency, SNR, clipping, distortion, and background noise.
    
    Args:
        file_path: Path to the audio file.
        
    Returns:
        dict: Aggregated quality metrics for the audio file.
    """
    durations = []
    sampling_rates = []
    bit_depths = []
    file_formats = []
    snrs = []
    clip_percentages = []
    distortions = []
    noise_rms_list = []

    if os.path.exists(file_path):
        try:
            data, sr = sf.read(file_path)
        except Exception as e:
            print(f"Warning: Could not read file {file_path}: {e}")
            return None

        audio_info = {"path": file_path}
        metadata = lpa.get_audio_metadata(audio_info)
        if metadata is not None:
            durations.append(metadata["duration"])
            sampling_rates.append(metadata["sampling_rate"])
            bit_depths.append(metadata["bit_depth"])
            file_formats.append(metadata["file_format"])

        # Convert to mono if multi-channel.
        if data.ndim > 1:
            data = np.mean(data, axis=1)

        snr = lpa.estimate_snr(data, sr)
        snrs.append(snr if snr is not None else 0)

        clip_pct, _ = lpa.detect_clipping(data)
        clip_percentages.append(clip_pct)

        distortion_flag = lpa.detect_distortion(data)
        distortions.append(distortion_flag)

        noise_profile = lpa.profile_background_noise(data, sr)
        noise_rms_list.append(noise_profile["noise_rms"] if noise_profile["noise_rms"] is not None else 0)

    quality_stats = {}
    snrs_np = np.array(snrs)
    clip_np = np.array(clip_percentages)
    noise_np = np.array(noise_rms_list)

    quality_stats["sampling_rate"] = lpa.check_sampling_rate_consistency(sampling_rates)
    quality_stats["bit_depth"] = lpa.check_bit_depth_consistency(bit_depths)
    quality_stats["file_format"] = lpa.check_file_format_consistency(file_formats)

    quality_stats["duration"] = lps.compute_cell_value_statistics(durations)

    quality_stats["snr"] = lps.compute_cell_value_statistics(snrs_np)
    quality_stats["clipping"] = lps.compute_cell_value_statistics(clip_np)

    quality_stats["distortion"] = {
         "num_distorted": int(np.sum(distortions)),
         "percentage_distorted": float(np.sum(distortions) / len(distortions) * 100) if len(distortions) > 0 else None
    }

    quality_stats["background_noise"] = lps.compute_cell_value_statistics(noise_np)

    return quality_stats

def aggregate_quality_stats(all_quality_stats):
    aggregated_stats = {
        "duration": [],
        "sampling_rate": [],
        "bit_depth": [],
        "file_format": [],
        "snr": [],
        "clipping": [],
        "distortion": [],
        "background_noise": []
    }

    for stats in all_quality_stats:
        aggregated_stats["duration"].append(stats["duration"]["mean"])
        aggregated_stats["sampling_rate"].extend(stats["sampling_rate"]["unique"])  # Use extend instead of append
        aggregated_stats["bit_depth"].extend(stats["bit_depth"]["unique"])  # Use extend instead of append
        aggregated_stats["file_format"].extend(stats["file_format"]["unique"])  # Use extend instead of append
        aggregated_stats["snr"].append(stats["snr"]["mean"])
        aggregated_stats["clipping"].append(stats["clipping"]["mean"])
        aggregated_stats["distortion"].append(stats["distortion"]["percentage_distorted"])
        aggregated_stats["background_noise"].append(stats["background_noise"]["mean"])

    return {
        "duration": lps.compute_cell_value_statistics(aggregated_stats["duration"]),
        "sampling_rate": lpa.check_sampling_rate_consistency(aggregated_stats["sampling_rate"]),
        "bit_depth": lpa.check_bit_depth_consistency(aggregated_stats["bit_depth"]),
        "file_format": lpa.check_file_format_consistency(aggregated_stats["file_format"]),
        "snr": lps.compute_cell_value_statistics(aggregated_stats["snr"]),
        "clipping": lps.compute_cell_value_statistics(aggregated_stats["clipping"]),
        "distortion": lps.compute_cell_value_statistics(aggregated_stats["distortion"]),
        "background_noise": lps.compute_cell_value_statistics(aggregated_stats["background_noise"])
    }

if __name__ == "__main__":
    
    in_container = True
    if len(sys.argv) > 1:
        data_path = sys.argv[1]
        glob_pattern = sys.argv[2]
        filetype = sys.argv[3]

        glob_pattern = "**/" + glob_pattern + "*." + filetype
        in_container = False
    else:
        data_path = "/tmp/inputs"

        data_dir = Path(data_path)
        num_filetypes = {}
        for filetype in ["wav"]:
            glob_pattern = "**/*." + filetype
            num_filetypes[filetype] = len(list(data_dir.glob(glob_pattern)))

        filetype = max(num_filetypes, key=num_filetypes.get)

        glob_pattern = "**/*." + filetype

    print(data_path, glob_pattern)

    all_quality_stats = []
    for file_path in Path(data_path).rglob(glob_pattern):
        print(file_path)
        quality_stats = analyze_signal_quality(file_path)
        if quality_stats:
            all_quality_stats.append(quality_stats)

    aggregated_stats = aggregate_quality_stats(all_quality_stats)

    output = {
        "files_analyzed": len(all_quality_stats),
        "quality": aggregated_stats
    }

    print(json.dumps(output, indent=4, sort_keys=True))
    if in_container:
        with open("/tmp/outputs/computation_result.json", "w") as f:
            json.dump(output, f, indent=4, sort_keys=True)
