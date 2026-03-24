Contributed by: Lode Hoste

Integrated and tested by: Istemi Ekin Akkus

This folder contains property computation code for the [HuggingFace AquaV/fallout-4-voices](https://huggingface.co/datasets/AquaV/fallout-4-voices) dataset.

It uses the `libprop` package available under [`datasets/code/libprop`](../../code/libprop/).

## Properties extracted:
- Number of files analyzed
- Aggregated statistics about quality, consisting of:
    - duration: Check the total duration of each audio clip and the distribution across the dataset. This helps in identifying outliers (too short or excessively long samples) and ensuring uniformity for processing.
    - sampling_rate: Verify if all files share a consistent sampling rate. Variability might require resampling or conversion.
    - bit_depth: Verify if all files share a consistent bit depth. Variability might require resampling or conversion.
    - file_format: Confirm that all audio files are in expected formats (e.g., WAV, MP3) and encoded similarly.
    - snr: Evaluate the level of background noise versus the actual signal. Algorithms can estimate SNR to identify recordings that might be too noisy.
    - clipping: Detect if parts of the audio are clipping (peaks are hitting the maximum amplitude) or if there’s any distortion.
    - distortion: Flag potential distortion in the audio signal based on clipping.
    - background_noise: Analyze ambient noise levels, which can be crucial if you’re interested in datasets for speech recognition or environmental sound analysis.

## Example output (on fallout-4-voice test dataset):

```json
{
    "aggregated_stats": {
        "background_noise": {
            "max": "0.045932",
            "mean": "0.001474",
            "median": "0.000093",
            "min": "0.000000",
            "outliers_count": 690,
            "percentiles": {
                "05th": "0.000000",
                "10th": "0.000000",
                "25th": "0.000014",
                "50th": "0.000093",
                "75th": "0.000782",
                "90th": "0.003327",
                "95th": "0.004320"
            },
            "std": "0.004872"
        },
        "bit_depth": {
            "consistent": true,
            "unique": [
                16
            ]
        },
        "clipping": {
            "max": "5.770030",
            "mean": "0.016099",
            "median": "0.000000",
            "min": "0.000000",
            "outliers_count": 80,
            "percentiles": {
                "05th": "0.000000",
                "10th": "0.000000",
                "25th": "0.000000",
                "50th": "0.000000",
                "75th": "0.000000",
                "90th": "0.000000",
                "95th": "0.000000"
            },
            "std": "0.226461"
        },
        "distortion": {
            "max": "100.000000",
            "mean": "0.431034",
            "median": "0.000000",
            "min": "0.000000",
            "outliers_count": 16,
            "percentiles": {
                "05th": "0.000000",
                "10th": "0.000000",
                "25th": "0.000000",
                "50th": "0.000000",
                "75th": "0.000000",
                "90th": "0.000000",
                "95th": "0.000000"
            },
            "std": "6.551157"
        },
        "duration": {
            "max": "16.811247",
            "mean": "4.668848",
            "median": "4.179592",
            "min": "0.464399",
            "outliers_count": 57,
            "percentiles": {
                "05th": "1.253878",
                "10th": "1.625397",
                "25th": "2.507755",
                "50th": "4.179592",
                "75th": "6.269388",
                "90th": "8.544943",
                "95th": "9.845261"
            },
            "std": "2.713132"
        },
        "file_format": {
            "consistent": true,
            "unique": [
                "WAV"
            ]
        },
        "sampling_rate": {
            "consistent": false,
            "unique": [
                48000,
                44100
            ]
        },
        "snr": {
            "max": "100.159579",
            "mean": "37.649832",
            "median": "38.709072",
            "min": "0.000000",
            "outliers_count": 0,
            "percentiles": {
                "05th": "0.000000",
                "10th": "0.000000",
                "25th": "21.036470",
                "50th": "38.709072",
                "75th": "55.491805",
                "90th": "69.449071",
                "95th": "73.050082"
            },
            "std": "22.797858"
        }
    },
    "files_analyzed": 3712
}
```