# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
from pathlib import Path
import shutil
import tarfile

from PIL import TiffImagePlugin

import libprop.image as lpi

TO_INCLUDE_EXIF_TAGS = [
    "ImageWidth", "ImageLength", "EXIF ExifImageWidth", "EXIF ExifImageLength",
    "width", "height",
    "BitsPerSample", "Compression", 
    "XResolution", "YResolution", "ResolutionUnit",
    "Image XResolution", "Image YResolution", "Image ResolutionUnit"
    "GPS GPSVersionID", "GPS GPSLatitude", "GPS GPSLongitude", "GPS GPSAltitude", 
    "GPS GPSTimeStamp", "GPS GPSDate",
    "Datetime",
    "ColorSpace", "EXIF ColorSpace",
    "Contrast", "Saturation", "Sharpness",
    "LensModel", "LensMake", "LensSpecification",
    "FocalLength", "Flash", "Noise", "ISOSpeed"
    ]

def find_files(data_path, glob):
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

def compute_property(filepaths, image_folder):
    output = {}
    
    # count items
    output["num_images"] = len(filepaths)
    # summarize width, height information
    image_sizes = {}
    # summarize colorspace
    colorspaces = {}
    colorspaces["NoColorSpace"] = 0

    for filepath in filepaths:
        # print(filepath)
        metadata = lpi.extract_metadata(filepath, to_include=TO_INCLUDE_EXIF_TAGS)

        # count different sized images
        size = str((metadata["width"], metadata["height"]))
        if size not in image_sizes:
            image_sizes[size] = 0
        
        image_sizes[size] += 1

        cs = None
        if "ColorSpace" in metadata:
            cs = metadata["ColorSpace"]
        elif "EXIF ColorSpace" in metadata:
            cs = metadata["EXIF ColorSpace"]

        if cs:
            if cs not in colorspaces:
                colorspaces[cs] = 0
            colorspaces[cs] = +1
        else:
            colorspaces["NoColorSpace"] += 1

    output["image_size_counts"] = image_sizes
    output["colorspace_counts"] = colorspaces
    
    return output

if __name__ == "__main__":
    data_path = "/tmp/inputs"
    data_dir = Path(data_path)
    
    # extract the tar files first
    glob = "**/*.tar"
    tar_files = list(data_dir.glob(glob))
    
    output = {}
    output["filenames"] = []
    for tf in tar_files:
        print(str(tf))
        output["filenames"].append(str(tf))
        output[str(tf)] = {}
        file = tarfile.open(tf)
        image_folder = str(tf)[:-7]
        image_dir = Path(image_folder)
        file.extractall(image_folder)
        file.close()
    
        num_filetypes = {}
        image_files = {}
        for filetype in ["jpeg", "JPEG", "jpg", "JPG"]:
            glob = "**/*." + filetype
            image_files[filetype] = list(image_dir.glob(glob))

        output[str(tf)]["filetypes"] = {}
        for filetype in image_files:
            output[str(tf)]["filetypes"][filetype] = compute_property(image_files[filetype], image_folder)
        
        shutil.rmtree(image_folder, ignore_errors=True)

    print(json.dumps(output, indent=4, sort_keys=True))
    with open("/tmp/outputs/computation_result.json", "w") as f:
        json.dump(output, f, indent=4, sort_keys=True)
