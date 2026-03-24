# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
import logging
import os
import pathlib
import sys

# import sdk client and set up other utils
try:
    from .archive_utils import create_archive, compute_hash
except Exception as _:
    from archive_utils import create_archive, compute_hash

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
#handler = logging.FileHandler('mylog.log')
handler = logging.StreamHandler(sys.stdout)
# create a logging format
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
handler.setFormatter(formatter)
log.addHandler(handler)

SERVICE_FOLDER = "property_computation_server/"
SERVICE_TOOLS_FOLDER = "property_computation_server_tools/"

log.info("Preparing to deploy service: " + SERVICE_FOLDER)
log.info("Using service tools: " + SERVICE_TOOLS_FOLDER)

def compute_service_info():
    service_info = {}
    service_tools_hashes = {}

    # archive the service code
    service_code_buffer = create_archive(SERVICE_FOLDER)

    service_code_data = service_code_buffer.getvalue()

    # archive additional tools individually
    service_tools_path = pathlib.Path(SERVICE_TOOLS_FOLDER)
    tool_list_folders = [d for d in os.listdir(service_tools_path) if os.path.isdir(SERVICE_TOOLS_FOLDER + d)]
    for tool_name in tool_list_folders:
        tool_folder = SERVICE_TOOLS_FOLDER + tool_name

        tool_buffer = create_archive(tool_folder)

        tool_data = tool_buffer.getvalue()
        tool_hash = compute_hash(tool_data)
        service_tools_hashes[tool_name] = tool_hash

    # as well as the script to build the additional tools
    tool_builder_filename = SERVICE_TOOLS_FOLDER + "build_tools.py"
    tool_builder_buffer = create_archive(SERVICE_TOOLS_FOLDER, files=[tool_builder_filename])

    tool_data = tool_builder_buffer.getvalue()
    tool_hash = compute_hash(tool_data)
    service_tools_hashes["build_tools.py"] = tool_hash

    service_info["service_code_hash"] = compute_hash(service_code_data)
    service_info["service_tools_hashes"] = service_tools_hashes
    service_info["service_dependencies_hash"] = {}

    for dependencies_filename in ["service_dependencies.sh", "service_dependencies_h100.sh"]:
        with open(SERVICE_FOLDER + dependencies_filename, "rb") as f:
            service_dependencies_data = f.read()
    
        if dependencies_filename == "service_dependencies.sh":
            key = "cpu"
        else:
            key = "gpu"

        service_info["service_dependencies_hash"][key] = compute_hash(service_dependencies_data)

    # log.info("-- Service info to deploy:")
    # log.info(json.dumps(service_info, indent=4))

    return service_info

def set_service_info(service_info):
    with open("duet_expected_hashes.json", "r") as f:
        manifest = json.load(f)
        # log.info("-- Existing manifest:")
        # log.info(json.dumps(manifest, indent=4))
        
    manifest["EXPECTED_DUET_SERVICE_INFO"] = service_info
    log.info("-- Updated manifest:")
    log.info(json.dumps(manifest, indent=4))

    with open("duet_expected_hashes.json", "w") as f:
        f.write(json.dumps(manifest, indent=4))

if __name__ == "__main__":
    service_info = compute_service_info()
    set_service_info(service_info)
