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
    from .asset_certification_client.duet_admin_client import DuetAdminClient
except Exception as _:
    from archive_utils import create_archive, compute_hash
    from asset_certification_client.duet_admin_client import DuetAdminClient
    
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
#handler = logging.FileHandler('mylog.log')
handler = logging.StreamHandler(sys.stdout)
# create a logging format
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
handler.setFormatter(formatter)
log.addHandler(handler)

# current implementation only support Azure attestation for SGX
ATTESTATION_SERVICE_URL = os.getenv("ATTESTATION_SERVICE_URL", "https://sharedneu.neu.attest.azure.net")

# The URL for the duet controller
DUET_ADMIN_URL = os.getenv("DUET_ADMIN_URL", "https://127.0.0.1:6037")

# The certification service code base
SERVICE_FOLDER = "property_computation_server/"
SERVICE_TOOLS_FOLDER = "property_computation_server_tools/"

# Expected measurement values for the duet controller and the service code
EXPECTED_DUET_ADMIN_MRENCLAVE = None
EXPECTED_DUET_SERVICE_INFO = {}
try:
    with open("duet_expected_hashes.json", "r", encoding="utf-8") as f_hashes:
        expected_values = json.load(f_hashes)
    EXPECTED_DUET_ADMIN_MRENCLAVE = expected_values["EXPECTED_DUET_ADMIN_MRENCLAVE"]
    EXPECTED_DUET_SERVICE_INFO = expected_values["EXPECTED_DUET_SERVICE_INFO"]
except Exception as _:
    pass


def initialize():
    """
    This function initializes a duet client to interact with the duet controller.
    It verifies its authenticity by checking its SGX quote.
    Afterwards, it registers the service owner's public key.
    """
    # Get a client to duet controller as the service owner
    log.info("Setting up the duet controller interaction...")
    duet_client = DuetAdminClient(DUET_ADMIN_URL, ATTESTATION_SERVICE_URL, "azure")

    # Obtain the controller's quote and verify it
    log.info("Verifying the state of the duet controller...")
    result = duet_client.verify_controller(EXPECTED_DUET_ADMIN_MRENCLAVE)
    # log.info(json.dumps(result, indent=4))

    # Register our public key with the duet controller,
    # so that maintenance actions can only be taken by us
    log.info("Registering as owner...")
    registration_result = duet_client.register_owner("service_owner_public_key", "service_owner_private_key")
    if registration_result["success"]:
        log.info("Registered owner public key successfully.")
    else:
        log.info("Owner already registered.")

    return duet_client

def start_cvm(duet_client, cvm_type):
    """
    This function lets the duet controller to start a new CVM,
    so that it can host our service.
    For this purpose, we need to let the duet controller use
    a cloud configuration with our preferred setup,
    including location, prefixes, naming conventions and OS image
    as well as cloud credentials to interact with the cloud service provider
    See `azure_config.json.template` for all parameters.

    Note that this set up happens *after* the SGX quote verification;
    thus, the sensitive content (i.e., cloud credentials) stay confidential
    inside the duet controller
    """
    log.info("Instructing the controller to set a new cloud config...")
    with open("azure_config.json", "r") as f:
        cloud_config = json.load(f)

    # set the cloud the config to be used
    result = duet_client.set_cloud_config(cloud_config)
    log.info(json.dumps(result, indent=4))

    # start a new cvm
    # cvm_type can be "snp", "snp-h100" and "tdx".
    # for "snp-h100", the `cvm_num_cpus` parameter will be ignored
    # by the duet controller
    # (because Azure fixes "snp-h100" to 40)
    log.info("Instructing the controller to start a new CVM...")
    result = duet_client.start_cvm("azure", cvm_type, 32)

    cvm_id = result["cvm_id"]
    cvm_location = result["cvm_location"]
    log.info("-- Deployed a new CVM with id: " + cvm_id)
    log.info("-- CVM location: " + json.dumps(cvm_location, indent=4))

def start_service(duet_client, cvm_type):
    """
    This function deploys the service in all CVMs with the given `cvm_type`.
    To do so, it first archives and reads the service code as well as the code
    of the additional tools to be deployed with our service.
    It also reads the service dependencies commands to be executed in the CVM
    before the service can be started.
    Finally, it uploads these data to the duet controller and instructs it to
    prepare and deploy the service.
    """

    log.info("Preparing to deploy service: " + SERVICE_FOLDER)
    log.info("Using service tools: " + SERVICE_TOOLS_FOLDER)

    # archive the service code
    service_buffer = create_archive(SERVICE_FOLDER)

    service_code_data = service_buffer.getvalue()
    print("Service code hash: " + compute_hash(service_code_data))

    # archive additional tools individually
    service_tools = {}
    service_tools_path = pathlib.Path(SERVICE_TOOLS_FOLDER)
    tool_list_folders = [d for d in os.listdir(service_tools_path) if os.path.isdir(SERVICE_TOOLS_FOLDER + d)]
    for tool_name in tool_list_folders:
        tool_folder = SERVICE_TOOLS_FOLDER + tool_name

        tool_buffer = create_archive(tool_folder)

        tool_data = tool_buffer.getvalue()
        service_tools[tool_name] = tool_data
        print("Service tool hash: " + tool_name + " " + compute_hash(tool_data))

    # as well as the script to build the additional tools
    tool_builder_filename = SERVICE_TOOLS_FOLDER + "build_tools.py"
    tool_builder_buffer = create_archive(SERVICE_TOOLS_FOLDER, files=[tool_builder_filename])

    tool_data = tool_builder_buffer.getvalue()
    service_tools["build_tools.py"] = tool_data
    print("Service tool hash: build_tools.py " + compute_hash(tool_data))

    # read also the service dependencies
    if cvm_type == "snp":
        dependencies_filename = "service_dependencies.sh"
        use_gpu = False
    elif cvm_type == "snp-h100":
        dependencies_filename = "service_dependencies_h100.sh"
        use_gpu = True

    with open(SERVICE_FOLDER + dependencies_filename, "rb") as f:
        service_dependencies_data = f.read()

    # upload service tarball and start service
    log.info("-- Instructing the controller to deploy and start the service...")
    result = duet_client.start_service(service_code_data, service_dependencies_data, service_tools, use_gpu)
    log.info(json.dumps(result, indent=4))
    if result["success"]:
        log.info("-- Successfully started service.")
    else:
        log.info("-- Service could not be started.")

    result = duet_client.get_service_info()
    log.info("-- Deployed service info: ")
    log.info(json.dumps(result, indent=4))

if __name__ == "__main__":
    duet_client = initialize()

    if sys.argv[1] == "start-cvm":
        cvm_type = sys.argv[2]
        start_cvm(duet_client, cvm_type)

    elif sys.argv[1] == "start":
        cvm_type = sys.argv[2]
        start_service(duet_client, cvm_type)

    elif sys.argv[1] == "stop":
        # To stop the service, the duet controller will stop all CVMs hosting the service
        log.info("-- Instructing the controller to stop the service and CVM(s)...")
        duet_client.stop_service()

    elif sys.argv[1] == "stop-cvm":
        # If needed, the duet controller can also be instructed
        # to stop a specific CVM with its id.
        # The CVM id is obtained when the CVM is first deployed.
        cvm_id = sys.argv[2]

        duet_client.stop_cvm(cvm_id)
