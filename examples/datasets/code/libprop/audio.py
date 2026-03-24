# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import os

import numpy as np
import soundfile as sf

def check_sampling_rate_consistency(sampling_rates):
    """
    Check for consistency in sampling rates across the dataset.
    
    Args:
        sampling_rates (list): List of sampling rate values.
        
    Returns:
        dict: Contains the unique sampling rates and a flag indicating if they are consistent.
    """
    unique_sampling_rates = list(set(sampling_rates))
    return {
        "unique": unique_sampling_rates,
        "consistent": len(unique_sampling_rates) == 1
    }

def check_bit_depth_consistency(bit_depths):
    """
    Check for consistency in bit depth across the dataset, ignoring None values.
    
    Args:
        bit_depths (list): List of bit depth values.
        
    Returns:
        dict: Contains the unique bit depths and a flag indicating if they are consistent.
    """
    valid_bit_depths = [bd for bd in bit_depths if bd is not None]
    unique_bit_depths = list(set(valid_bit_depths))
    return {
        "unique": unique_bit_depths,
        "consistent": len(unique_bit_depths) == 1 if valid_bit_depths else None
    }

def check_file_format_consistency(file_formats):
    """
    Check for consistency in file formats across the dataset, ignoring None values.
    
    Args:
        file_formats (list): List of file format strings.
        
    Returns:
        dict: Contains the unique file formats and a flag indicating if they are consistent.
    """
    valid_formats = [fmt for fmt in file_formats if fmt is not None]
    unique_formats = list(set(valid_formats))
    return {
        "unique": unique_formats,
        "consistent": len(unique_formats) == 1 if valid_formats else None
    }

def estimate_snr(audio, sampling_rate, frame_duration=0.02, noise_percentile=10):
    """
    Estimate the Signal-to-Noise Ratio (SNR) for an audio signal.
    
    The method segments the audio into frames, computes the RMS of each frame,
    and uses the lower 'noise_percentile' percentile as an estimate for the noise level.
    SNR is computed as 20 * log10(overall_rms / noise_rms).
    
    Args:
        audio (np.array): Audio signal as a 1D numpy array.
        sampling_rate (int): Sampling rate of the audio signal.
        frame_duration (float): Duration (in seconds) of each frame.
        noise_percentile (float): Percentile used to estimate the noise level.
        
    Returns:
        float or None: Estimated SNR in dB, or None if noise level is zero.
    """
    frame_length = int(frame_duration * sampling_rate)
    if frame_length <= 0:
        return None
    num_frames = len(audio) // frame_length
    if num_frames == 0:
        return None
    
    rms_values = []
    for i in range(num_frames):
        frame = audio[i * frame_length : (i + 1) * frame_length]
        if len(frame) == 0:
            continue
        rms = np.sqrt(np.mean(frame**2))
        rms_values.append(rms)
    rms_values = np.array(rms_values)
    
    noise_level = np.percentile(rms_values, noise_percentile)
    overall_rms = np.sqrt(np.mean(audio**2))
    
    if noise_level == 0:
        return None
    return 20 * np.log10(overall_rms / noise_level)

def detect_clipping(audio, clip_threshold=0.99):
    """
    Detect clipping in an audio signal.
    
    Clipping is identified when the absolute value of samples exceeds the clip_threshold.
    
    Args:
        audio (np.array): Audio signal as a 1D numpy array.
        clip_threshold (float): Threshold above which samples are considered clipped.
        
    Returns:
        tuple: (clipping_percentage (float), clipped_samples (int))
    """
    total_samples = len(audio)
    if total_samples == 0:
        return 0, 0
    clipped_samples = np.sum(np.abs(audio) >= clip_threshold)
    clipping_percentage = (clipped_samples / total_samples) * 100
    return clipping_percentage, int(clipped_samples)

def detect_distortion(audio, clip_threshold=0.99, clipping_flag_threshold=1.0):
    """
    Detect potential distortion in the audio signal based on clipping.
    
    A sample is flagged as distorted if the percentage of clipped samples exceeds
    the clipping_flag_threshold.
    
    Args:
        audio (np.array): Audio signal as a 1D numpy array.
        clip_threshold (float): Threshold to identify clipped samples.
        clipping_flag_threshold (float): Percentage threshold to flag distortion.
        
    Returns:
        bool: True if the sample is potentially distorted, False otherwise.
    """
    clip_pct, _ = detect_clipping(audio, clip_threshold=clip_threshold)
    return clip_pct > clipping_flag_threshold

def profile_background_noise(audio, sampling_rate, frame_duration=0.02, noise_percentile=10):
    """
    Profile background noise by analyzing low-energy frames of an audio signal.
    
    The function divides the audio into frames, computes the RMS for each frame,
    and then uses the specified noise_percentile to determine a noise threshold.
    Frames with RMS values below or equal to this threshold are considered noise.
    
    Args:
        audio (np.array): Audio signal as a 1D numpy array.
        sampling_rate (int): Sampling rate of the audio signal.
        frame_duration (float): Duration (in seconds) of each frame.
        noise_percentile (float): Percentile used to estimate the noise threshold.
        
    Returns:
        dict: Contains:
            - noise_rms (float): Average RMS of low-energy frames.
            - noise_threshold (float): RMS threshold used.
    """
    frame_length = int(frame_duration * sampling_rate)
    num_frames = len(audio) // frame_length
    if num_frames == 0:
        return {"noise_rms": None, "noise_threshold": None}
    
    rms_values = []
    for i in range(num_frames):
        frame = audio[i * frame_length : (i + 1) * frame_length]
        if len(frame) == 0:
            continue
        rms = np.sqrt(np.mean(frame**2))
        rms_values.append(rms)
    rms_values = np.array(rms_values)
    
    noise_threshold = np.percentile(rms_values, noise_percentile)
    noise_frames = rms_values[rms_values <= noise_threshold]
    noise_rms = float(np.mean(noise_frames)) if len(noise_frames) > 0 else None
    
    return {"noise_rms": noise_rms, "noise_threshold": noise_threshold}

def get_audio_metadata(audio_info):
    """
    Retrieve audio metadata from an audio_info dict.
    
    The audio_info may contain:
      - A "path" key pointing to an audio file (metadata extracted using soundfile), or
      - Raw audio data with "array" and "sampling_rate" keys.
      
    Returns:
        dict or None: Contains 'duration', 'sampling_rate', 'bit_depth', and 'file_format' if available.
    """
    file_path = audio_info.get("path", None)
    
    if file_path is not None and os.path.exists(file_path):
        try:
            info = sf.info(file_path)
            sr = info.samplerate
            duration = info.frames / sr
            
            # Extract bit depth from the subtype (e.g., "PCM_16")
            subtype = info.subtype
            if "PCM" in subtype and "_" in subtype:
                try:
                    bd = int(subtype.split("_")[1])
                except ValueError:
                    bd = None
            else:
                bd = None
            return {
                "duration": duration,
                "sampling_rate": sr,
                "bit_depth": bd,
                "file_format": info.format,
            }
        except Exception as e:
            print(f"Warning: Could not process file {file_path}: {e}")
            return None
    else:
        # Fallback: use raw audio data if available.
        if "array" in audio_info and "sampling_rate" in audio_info:
            data = audio_info["array"]
            sr = audio_info["sampling_rate"]
            duration = len(data) / sr
            return {
                "duration": duration,
                "sampling_rate": sr,
                "bit_depth": None,      # Not available from raw array
                "file_format": None,    # Not available from raw array
            }
        else:
            print("Warning: Audio sample missing both 'path' and raw audio data.")
            return None
