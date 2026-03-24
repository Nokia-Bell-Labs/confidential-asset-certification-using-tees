# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

from PIL import Image
from PIL.ExifTags import TAGS

import exifread

def extract_metadata_pillow(image_path):
    image = Image.open(image_path)
    exif_data = image.getexif()
    
    metadata = {}
    metadata["width"], metadata["height"] = image.size

    if exif_data:
        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, tag_id)
            metadata[str(tag_name)] = str(value)
            # print(f"{tag_name}: {value}")

    return metadata

def extract_metadata_exifread(image_path):
    metadata = {}
    with open(image_path, "rb") as f:
        tags = exifread.process_file(f)

        for tag_name, value in tags.items():
            metadata[str(tag_name)] = str(value)
            # print(f"{tag_name}: {value}")

    return metadata

def extract_metadata(image_path, to_include=None, to_delete=None):
    metadata = {}
    metadata_pillow = {}
    metadata_exifread = {}

    try:
        metadata_pillow = extract_metadata_pillow(image_path)
    except Exception as _:
        pass

    try:
        metadata_exifread = extract_metadata_exifread(image_path)
    except Exception as _:
        pass
    
    metadata = metadata_pillow.copy()
    metadata.update(metadata_exifread)
    
    if to_delete:
        for key in to_delete:
            if key in metadata:
                del metadata[key]

    if to_include:
        for key in list(metadata.keys()):
            if key not in to_include:
                del metadata[key]

    return metadata
