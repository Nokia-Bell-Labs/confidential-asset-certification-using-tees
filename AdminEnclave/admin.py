# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

from argparse import ArgumentParser
import base64
import json
import logging
from logging.config import dictConfig
import os
import random
import sys
import signal
import time

from cryptography.hazmat.primitives import serialization

from flask import Flask, request

import requests

from urllib3.exceptions import SubjectAltNameWarning

try:
    from .cloud_client_azure import AzureClient
    from .utils.config import extend_configuration, read_commands_from_file,\
                            check_missing_parameters, load_expected_hashes, check_azure_configuration
    from .utils.crypto import generate_rsa_keypair, generate_ephemeral_rsa_key_for_cvm,\
                            sign_data_with_private_key, generate_tls_certificate,\
                            verify_signature_with_public_key_pem, compute_hash
except Exception as _:
    from cloud_client_azure import AzureClient
    from utils.config import extend_configuration, read_commands_from_file,\
                            check_missing_parameters, load_expected_hashes, check_azure_configuration
    from utils.crypto import generate_rsa_keypair, generate_ephemeral_rsa_key_for_cvm,\
                            sign_data_with_private_key, generate_tls_certificate,\
                            verify_signature_with_public_key_pem, compute_hash

requests.packages.urllib3.disable_warnings(category=SubjectAltNameWarning)

dictConfig({
    "version": 1,
    "formatters": {"default": {
        "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
    }},
    "handlers": {"wsgi": {
        "class": "logging.StreamHandler",
        "formatter": "default"
    }},
    "root": {
        "level": "INFO",
        "handlers": ["wsgi"]
    }
})

app = Flask(__name__)

DUET_ADMIN = None

class DuetAdmin():
    """
    The duet controller class.

    It can be instantiated in `direct' mode (e.g., for debugging)
    or in `sgx' mode (i.e., after graminization).

    It holds metadata for tracking the confidential VMs.
    It uses them to deploy and start a service,
    after which it proxies service requests to a CVM.
    While proxying, it implements a rudimentary sticky session
    with the help of the service (i.e., `cvm_id' field in a response),
    so that related service requests are routed to the same service instance.
    Again with the help of the service (i.e., `service_result' field in a response),
    it signs responses with its ephemeral private key.
    """
    def __init__(self, environment, logger):
        self._logger = logger
        self._private_key = None
        self._public_key = None
        # self._serialized_public_key = None
        self._owner_public_key_pem = None
        self._environment = environment

        self._cvm_map = {}
        self._service_cvm_map = {}
        self._cloud_config_map = {}

        self._service_code_hash = None
        self._service_tools_hashes = {}
        self._service_dependencies_hash = None
        self._service_location = {}

        try:
            resp = requests.get("https://ipecho.net/plain")
            self._ip_address = resp.text
        except Exception as _:
            self._logger.info("[ERROR] Cannot determine our IP address.")
            raise

        if self._environment == "direct":
            self._local_tmp_path = "/tmp/"
            self._home_filepath = "AdminEnclave/"
        elif self._environment == "sgx":
            self._local_tmp_path = "/home/duet/tmp/"
            self._home_filepath = "/home/duet/AdminEnclave/"

        self._expected_hashes = load_expected_hashes(self._home_filepath + "expected_hashes.json")

        self._private_key_filename = self._local_tmp_path + "private_key.pem"
        self._tls_certificate_filename = self._local_tmp_path + "tls_certificate.pem"

        if self._environment == "direct":
            self._init_key_pair()
            self._init_tls_certificate()

    def _init_key_pair(self):
        """
        Initializes an ephemeral public/private keypair for this duet controller.
        """
        # command = "openssl req -x509 -newkey rsa:4096 -keyout " + key_filename + " -out " + cert_filename + " -days 365 -nodes -subj \"/C=DE/ST=Baden-Wuerttemberg/L=Stuttgart/O=Nokia Bell Labs/OU=SDSR/CN=" + self._ip_address + "\""
        # Generate a new RSA key pair
        self._public_key, self._private_key = generate_rsa_keypair(4096)

        with open(self._private_key_filename, "wb") as f_private_key_filename:
            f_private_key_filename.write(self._private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))

        self._logger.info("Generated new RSA key pair for duet admin enclave.")

    def _init_tls_certificate(self):
        """
        Initializes a TLS certificate for this duet controller using its
        ephemerally generated public/private keypair,
        so that clients can communicate with it using TLS.
        """
        cert = generate_tls_certificate(self._ip_address, self._public_key, self._private_key)

        with open(self._tls_certificate_filename, "wb") as f_tls_certificate:
            f_tls_certificate.write(cert.public_bytes(encoding=serialization.Encoding.PEM))

        with open(self._tls_certificate_filename, "r") as f_tls_certificate:
            self._tls_certificate = f_tls_certificate.read()

        self._logger.info("Generated new TLS certificate for duet admin enclave.")

    def register_owner(self, public_key_pem):
        """
        Register the public key of a service owner,
        so that only the service owner can issue privileged operations
        on the confidential VM
        (e.g., installing dependencies, starting service, stopping service).
        """
        result = {}
        result["success"] = False
        if self._owner_public_key_pem is None:
            self._owner_public_key_pem = public_key_pem
            result["success"] = True

        return result

    def get_tls_certificate(self):
        """
        Return the TLS certificate of this duet controller.
        """
        return self._tls_certificate

    def get_tls_certificate_filenames(self):
        """
        Return the TLS certificate filenames of this duet controller.
        """
        return self._tls_certificate_filename, self._private_key_filename

    def get_random_service_cvm(self):
        """
        Pick a random confidential VM to handle a service request.
        """
        # pick a CVM from the list
        cvm_list = list(self._service_cvm_map.keys())
        if len(cvm_list) > 0:
            ridx = random.randint(0,len(cvm_list)-1)
            cvm_id = cvm_list[ridx]
            return self._service_cvm_map[cvm_id]

        return None

    def _sign_data(self, data: bytes) -> bytes:
        """
        Sign data with the private key of this duet controller.
        """
        return sign_data_with_private_key(data, self._private_key)

    def verify_owner_signature(self, signature, data):
        """
        Verify the signature of the service owner for privileged
        operations on the confidential VM.
        """
        return verify_signature_with_public_key_pem(signature, data, self._owner_public_key_pem)

    def set_cloud_config(self, cloud_config):
        """
        Set the cloud configuration of the service owner for provisioning
        confidential VMs.
        """
        result = {}
        cloud_provider = cloud_config["cloud_provider"]
        if cloud_provider == "azure":
            if check_azure_configuration(cloud_config):
                self._cloud_config_map["azure"] = cloud_config
                result["success"] = True
            else:
                result["error"] = "Missing cloud config parameter(s)."
        else:
            result["error"] = "Cloud provider not supported yet."

        return result

    def get_service_info(self, cvm_id=None):
        """
        Return the service info that includes the SHA-256 hashes of
        the service code archive, the service dependencies
        and additional tools that were deployed with the service
        as well as the location where the service is running.
        """
        service_info = {}
        service_info["service_code_hash"] = ""
        service_info["service_tools_hashes"] = {}
        service_info["service_dependencies_hash"] = ""
        service_info["service_location"] = {}
        if self._service_code_hash:
            service_info["service_code_hash"] = self._service_code_hash

        if self._service_tools_hashes:
            service_info["service_tools_hashes"] = self._service_tools_hashes

        if self._service_dependencies_hash:
            service_info["service_dependencies_hash"] = self._service_dependencies_hash

        if self._service_location:
            if cvm_id:
                service_info["service_location"][cvm_id] = self._service_location[cvm_id]
            else:
                service_info["service_location"] = self._service_location

        return service_info

    def stop_service(self):
        """
        Stop the service and the confidential VMs it is running on.
        """
        result = {}
        for cvm_id in list(self._service_cvm_map.keys()):
            cvm = self._service_cvm_map[cvm_id]
            result[cvm_id] = self._stop_cvm(cvm)
            del self._service_cvm_map[cvm_id]

        return result

    def stop_cvm(self, cvm_id):
        """
        Stop a confidential VM with its unique id.
        """
        result = {}

        cvm_ids = list(self._cvm_map.keys())
        if cvm_id in cvm_ids:
            cvm = self._cvm_map[cvm_id]
            result[cvm_id] = self._stop_cvm(cvm)
            del self._cvm_map[cvm_id]
        else:
            result["error"] = "No such CVM."

        return result

    def _stop_cvm(self, cvm):
        """
        Internal function to stop a confidential VM and delete its
        provisioned resources.
        """
        result = {}
        cvm_provider = cvm.get_cloud_provider()
        config = cvm.get_config()
        if cvm_provider == "azure":
            azure_client = AzureClient(config, self._ip_address, app.logger)
            azure_client.delete_resources()
            result["success"] = True
        else:
            result["success"] = False
            result["error"] = "Other cloud provider(s) are not supported yet."

        return result

    def start_service(self, service_code_data, service_dependencies_data, service_tools_data, use_gpu):
        """
        Deploy and start a service in suitabe confidential VMs that have already
        been provisioned.

        The duet controller records the service info that includes
        the hashes of the service code archive, the service dependencies
        and the additional tools that the service utilizes.

        Afterwards, the duet controller copies the necessary files to the
        confidential VM, installs the dependencies by executing commands
        on the CVM, initializes the build processes for the tools and
        starts the service.
        """
        # record the hash of the service code
        self._service_code_hash = compute_hash(service_code_data)

        service_code_filename = "service_code.tar"
        with open(self._local_tmp_path + service_code_filename, "wb") as f_service_code:
            f_service_code.write(service_code_data)

        # record the hash of the service tools
        service_tools_filenames = []
        for tool_name in service_tools_data:
            self._service_tools_hashes[tool_name] = compute_hash(service_tools_data[tool_name])
            tool_filename = "service_tools_" + tool_name + ".tar"
            service_tools_filenames.append(tool_filename)
            with open(self._local_tmp_path + tool_filename, "wb") as f_tool_filename:
                f_tool_filename.write(service_tools_data[tool_name])

        # record the hash of the service dependencies
        self._service_dependencies_hash = compute_hash(service_dependencies_data)

        service_dependencies_filename = "service_dependencies.sh"
        with open(self._local_tmp_path + service_dependencies_filename, "wb") as f_dependencies_filename:
            f_dependencies_filename.write(service_dependencies_data)

        # obtain service dependencies
        dependency_commands = []
        with open(self._local_tmp_path + service_dependencies_filename, "r", encoding="utf-8") as f_dependencies:
            lines = f_dependencies.readlines()
            for line in lines:
                line = line.strip()
                if line == "" or line.startswith("#"):
                    continue
                dependency_commands.append(line)

        if dependency_commands:
            commands_file_content = "\n".join(dependency_commands)
            commands_file_content = commands_file_content.replace("\\\n", "")
            dependency_commands = commands_file_content.split("\n")

        # deploy service in each cvm
        num_deployed = 0
        available_cvm_ids = list(self._cvm_map.keys())
        for cvm_id in available_cvm_ids:
            cvm = self._cvm_map[cvm_id]

            if use_gpu != cvm.has_gpu():
                continue

            self._prepare_deploy_service(cvm, service_code_filename, service_tools_filenames, dependency_commands)
            self._service_location[cvm_id] = cvm.get_cvm_location()
            self._service_cvm_map[cvm_id] = cvm
            del self._cvm_map[cvm_id]

            num_deployed += 1

        result = {}
        if num_deployed > 0:
            result["success"] = True
            result["service_code_hash"] = self._service_code_hash
            result["service_tools_hashes"] = self._service_tools_hashes
            result["service_dependencies_hash"] = self._service_dependencies_hash
            result["service_location"] = self._service_location
        else:
            result["success"] = False
            result["error"] = "No suitable CVM found."

        return result

    def start_cvm(self, cloud_provider, cvm_type, cvm_num_cpus):
        """
        Provision resources and start a confidential VM on the infrastructure
        of the cloud provider.

        The `cvm_type' can be `snp' or `snp-h100'.
        The `cvm_num_cpus' variable is ignored when using `snp-h100',
        because Azure assigns a fixed number of CPUs to the
        confidential VM with an H100 GPU TEE.

        After provisioning the CVM, the duet controller first checks
        its attestation report. For this purpose, it has to install
        some packages.
        If `cvm_type' is `snp-h100', it install additional packages
        for the attestation of the GPU TEE H100.
        """
        result = {}
        result["success"] = False

        if cloud_provider in self._cloud_config_map:
            config = extend_configuration(self._cloud_config_map[cloud_provider], cvm_type, cvm_num_cpus)

            if cloud_provider == "azure":
                cloud_client = AzureClient(config, self._ip_address, app.logger)
            else:
                cloud_client = None
                result["error"] = "Cloud provider not supported yet."

            if cloud_client:
                # 2. create an ephemeral RSA keypair to be used for login
                serialized_public_key, serialized_private_key = generate_ephemeral_rsa_key_for_cvm()
                # app.logger.info(serialized_public_key)
                # app.logger.info(serialized_private_key)

                if self._environment == "direct":
                    # write them to a file
                    # can be used for debugging
                    with open("ephemeral_private_key", "w") as f_ephemeral_private_key_filename:
                        f_ephemeral_private_key_filename.write(serialized_private_key)
                    os.chmod("ephemeral_private_key", 0o600)
                    with open("ephemeral_private_key.pub", "w") as f_ephemeral_public_key_filename:
                        f_ephemeral_public_key_filename.write(serialized_public_key)

                # 3. use the azure client to provision resources
                cvm = cloud_client.provision_resources(serialized_public_key)

                cvm.set_private_key(serialized_private_key)

                # give time to the provider to update firewall rules etc.
                time.sleep(30)

                nonce_filename, attestation_token_filename = self._install_cvm_packages(cvm)

                # check CVM attestation
                valid_cvm, attestation_info = cloud_client.check_attestation(attestation_token_filename, nonce_filename)

                # cleanup
                os.remove(nonce_filename)

                if valid_cvm:
                    self._logger.info("Valid " + cloud_provider + " CVM.")
                    self._logger.info(json.dumps(attestation_info, indent=4))

                    if cvm.get_cvm_type()[3:] == "-h100":
                        h100_attestation_filename = self._install_h100_packages(cvm)
                        valid_cgpu, cgpu_info = cloud_client.check_gpu_attestation(h100_attestation_filename)
                        if valid_cgpu:
                            self._logger.info("Valid H100.")
                            self._logger.info(json.dumps(cgpu_info, indent=4))
                        else:
                            valid_cvm = False

                if valid_cvm:
                    cvm_id = cvm.get_cvm_id()
                    cvm_ip = cvm.get_cvm_ip()

                    self._cvm_map[cvm_id] = cvm

                    # obtain cvm location via the geolocation measurement tool
                    self._measure_cvm_location(cvm)

                    cvm_location = cvm.get_cvm_location()

                    self._logger.info(f"Started cvm_id: {cvm_id} cvm_ip: {cvm_ip}")
                    self._logger.info(f"CVM location: {cvm_location}")

                    result["success"] = True
                    result["cvm_id"] = cvm_id
                    result["cvm_location"] = cvm_location

                else:
                    self._logger.info("[ERROR] Invalid CVM or H100 attestation.")
                    result["error"] = "Invalid CVM or H100 attestation."

        else:
            result["error"] = "Cloud config for this provider is not present."

        return result

    def _run_commands(self, cvm, commands):
        """
        Internal function to run commands on the confidential VM.

        For any file that has to be downloaded from the internet,
        the duet controller also checks its expected hash value taken
        from the `expected_hashes.json' file.
        """
        for command in commands:
            if command.startswith("sha256sum"):
                output = cvm.execute_command(command)
                tokens = output[0].split(" ")
                hash_value = tokens[0]
                name = tokens[-1]
                if name in self._expected_hashes and self._expected_hashes[name] == hash_value:
                    self._logger.info("[OK] Downloaded file matches its expected hash: " + name + " " + hash_value)
                else:
                    self._logger.info("[ERROR] Mismatch of hash of downloaded file: " + name)
                    sys.exit(1)
            elif command.startswith("sudo ") and command.find(" apt-get ") != -1:
                while True:
                    success = True
                    output = cvm.execute_command(command)
                    for line in output:
                        if line.startswith("E: Could not get lock /var/lib/dpkg/lock-frontend."):
                            success = False
                    if success:
                        break
                    time.sleep(2.0)
            else:
                _ = cvm.execute_command(command)

            time.sleep(1.0)

    def _install_h100_packages(self, cvm):
        """
        Internal function to install packages for attesting the
        GPU TEE NVIDIA H100.
        """
        cvm_provider = cvm.get_cloud_provider()
        cvm_type = cvm.get_cvm_type()
        vm_username = cvm.get_cvm_username()

        cfilename = "cvm_commands/" + cvm_provider + "/" + cvm_type + ".sh"
        commands = read_commands_from_file(self._home_filepath + cfilename, vm_username)

        self._run_commands(cvm, commands)

        cvm_id = cvm.get_cvm_id()
        cvm_homepath = "/home/" + cvm.get_cvm_username() + "/"
        h100_attestation_filename = self._local_tmp_path + cvm_id + "_h100_attestation.txt"
        cvm.get_file(cvm_homepath + "h100_attestation.txt", h100_attestation_filename)

        return h100_attestation_filename

    def _install_cvm_packages(self, cvm):
        """
        Internal function to install package for attesting the
        confidential VM.
        """
        # 1. generate and obtain the tls certificate for proxying later
        vm_username = cvm.get_cvm_username()
        cvm_homepath = "/home/" + vm_username + "/"
        cvm_certs_dir = cvm_homepath + "certs/"
        cvm_key_filename = cvm_certs_dir + "key.pem"

        cvm_cert_filename = cvm_certs_dir + "cert.pem"
        initial_commands = [
            "mkdir -p " + cvm_certs_dir,
            "openssl req -x509 -newkey rsa:4096 -keyout " + cvm_key_filename + " -out " + cvm_cert_filename + " -days 3650 -nodes -subj \"/C=DE/ST=Baden-Wuerttemberg/L=Stuttgart/O=Nokia Bell Labs/OU=SDSR/CN=" + cvm.get_cvm_ip() + "\"",
        ]
        self._run_commands(cvm, initial_commands)

        cvm_tls_certificate_filename = self._local_tmp_path + cvm.get_cvm_id() + "_cert.pem"
        cvm.get_file(cvm_cert_filename, cvm_tls_certificate_filename)
        cvm.set_cvm_tls_certificate_filename(cvm_tls_certificate_filename)

        # 2. install required packages for attestation
        cvm_id = cvm.get_cvm_id()
        cvm_type = cvm.get_cvm_type()[:3]
        cvm_provider = cvm.get_cloud_provider()

        # sha256 of random bytes as 'nonce' to be used in attestation
        nonce = os.urandom(1048576)
        nonce_hash = compute_hash(nonce)

        nonce_filename = self._local_tmp_path + cvm_id + "_nonce"
        with open(nonce_filename, "w") as f_nonce:
            f_nonce.write(nonce_hash)

        cvm.copy_file(nonce_filename, "/home/" + vm_username + "/nonce")

        # initial installation
        commands_filename = "cvm_commands/" + cvm_provider + "/" + cvm_type + ".sh"
        commands = read_commands_from_file(self._home_filepath + commands_filename, vm_username)

        self._run_commands(cvm, commands)

        attestation_token_filename = self._local_tmp_path + cvm_id + "_attestation_token.txt"
        cvm.get_file(cvm_homepath + "attestation_token.txt", attestation_token_filename)

        return nonce_filename, attestation_token_filename

    def _prepare_deploy_service(self, cvm, service_code_filename, service_tools_filenames, dependency_commands):
        """
        Internal function to prepare for the deployment of the service.

        The duet controller copies the necessary files for service code
        and the tools.
        Finally, it starts the service.
        """
        cvm_homepath = "/home/" + cvm.get_cvm_username() + "/"

        # 1. copy service tools
        for tool_filename in service_tools_filenames:
            cvm.copy_file(self._local_tmp_path + tool_filename, cvm_homepath + tool_filename)

        # 2. install service dependencies
        self._run_commands(cvm, dependency_commands)

        # 3. build service tools
        commands = [
            "mkdir -p " + cvm_homepath + "service_tools",
            "mv " + cvm_homepath + "service_tools_*.tar" + " " + cvm_homepath + "service_tools",
            "cd " + cvm_homepath + "service_tools; tar -xvf service_tools_build_tools.py.tar; python3 build_tools.py"
        ]

        self._run_commands(cvm, commands)

        # 4. copy service code archive
        cvm.copy_file(self._local_tmp_path + service_code_filename, cvm_homepath + service_code_filename)

        # 5. extract service code archive and start service via run_service.sh
        commands = [
            "mkdir -p " + cvm_homepath + "service",
            "mv " + cvm_homepath + service_code_filename + " " + cvm_homepath + "service",
            "echo " + cvm.get_cvm_id() + " > " + cvm_homepath + "cvm_id.txt",
            "cd " + cvm_homepath + "service; tar -xvf " + service_code_filename + "; chmod +x run_service.sh; nohup ./run_service.sh"
        ]

        self._run_commands(cvm, commands)

    def _measure_cvm_location(self, cvm):
        # 1. copy the tar archive of geolocation measurement tool
        cvm_homepath = "/home/" + cvm.get_cvm_username() + "/"
        cvm.copy_file(self._home_filepath + "geoloc.tar", cvm_homepath + "geoloc.tar")

        # 2. extract tar, run geolocation measurement
        commands = [
            "mkdir -p " + cvm_homepath + "geoloc",
            "mv " + cvm_homepath + "geoloc.tar" + " " + cvm_homepath + "geoloc",
            "cd " + cvm_homepath + "geoloc; tar -xvf geoloc.tar",
            "cd " + cvm_homepath + "geoloc; python3 geoloc.py >> geoloc_log.txt"
        ]

        self._run_commands(cvm, commands)

        # 3. retrieve the output log
        geoloc_log_filename = self._local_tmp_path + cvm.get_cvm_id() + "_geoloc_log.txt"
        cvm.get_file(cvm_homepath + "geoloc/geoloc_log.txt", geoloc_log_filename)

        # 4. parse the output log
        with open(geoloc_log_filename, "r") as geoloc_log_file:
            lines = geoloc_log_file.read()
            lines = lines.split("\n")

        report_lines = []
        start_recording = False
        for line in lines:
            if line.startswith("-----"):
                start_recording = True
                continue
            if start_recording:
                report_lines.append(line.strip())

        report = ''.join(report_lines)
        cvm_location = json.loads(report)

        # 5. set the cvm location
        cvm.set_cvm_location(cvm_location)

    def handle_service_request(self, request_json_data):
        """
        Proxy a service request to a suitable confidential VM
        with the service running on it.

        The duet controller follows a rudimentary sticky session
        by extracting the `cvm_id' from the request parameters.
        If the client supplies an incorrect `cvm_id',
        the service running on that CVM will simply reject the request.
        """
        cvm = None
        if "request_cvm_id" in request_json_data:
            cvm_id = request_json_data["request_cvm_id"]
            if cvm_id in self._service_cvm_map:
                cvm = self._service_cvm_map[cvm_id]
            else:
                result = {"error": "No such CVM."}
        else:
            cvm = self.get_random_service_cvm()

        if cvm:
            result = cvm.handle_service_request(request_json_data)

            if "service_result" in result:
                res = {}
                res["service_info"] = self.get_service_info(cvm.get_cvm_id())
                res["service_result"] = result["service_result"]
                del result["service_result"]
                result["duet_service_result"] = res
                # sign the certificate to make it self-contained
                output = json.dumps(res, sort_keys=True)
                signature = self._sign_data(bytes(output, "utf-8"))
                result["duet_admin_signature"] = base64.b64encode(signature).decode("utf-8")
        else:
            result = {"error": "No suitable CVM found."}

        return result

class DuetAdminEnclave(DuetAdmin):
    """
    The duet controller class when running in `sgx' mode.
    """
    def __init__(self, environment, logger):
        super().__init__(environment, logger)
        self._init_key_pair()
        self._write_enclave_report_data()

        quote = self.get_quote()
        self._logger.info("MRENCLAVE value: " + quote[112:144].hex())

    def _init_key_pair(self):
        """
        Internal function to initialize an ephemeral public/private
        keypair.

        First, check whether we have a sealed private key.
        If not, the duet controller simply generates a new keypair
        and records it in sealed file.
        """
        sealed_key = "/home/duet/AdminEnclave/sealed/private_key"
        if os.path.isfile(sealed_key):
            with open(sealed_key, "rb") as f_sealed_key:
                private_key_pem = f_sealed_key.read()
            private_key  = serialization.load_pem_private_key(private_key_pem, password=None)
            self._private_key = private_key
            self._public_key = self._private_key.public_key()
            self._logger.info(f"Loaded RSA key from sealed file `{sealed_key}`")
        else:
            super()._init_key_pair()
            # Seal serialized private key to a file
            while True:
                try:
                    with open(sealed_key, "wb") as f_sealed_key:
                        private_key_pem = self._private_key.private_bytes(
                            encoding=serialization.Encoding.PEM,
                            format=serialization.PrivateFormat.PKCS8,
                            encryption_algorithm=serialization.NoEncryption()
                        )
                        f_sealed_key.write(private_key_pem)
                        self._logger.info(f"Stored sealed RSA key in file `{sealed_key}`")
                        break
                except Exception as exc:
                    self._logger.error(exc)
                    time.sleep(1)

        super()._init_tls_certificate()

    def _write_enclave_report_data(self):
        """
        Internal function to write secure hash of the
        ephemerally generated public key into the `REPORTDATA'
        field of the SGX quote,
        so that a client can later use this information to verify
        the signature of the duet controller.
        """
        # Write the secure hash of the public key into the user_report_data
        serialized_public_key = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        hash_value = compute_hash(serialized_public_key, hex=False)
        try:
            with open("/dev/attestation/user_report_data", "wb") as f_report_data:
                f_report_data.write(hash_value)
        except Exception as exc:
            message = ("Could not write to `/dev/attestation/user_report_data`; "
                       "are you running with remote attestation enabled?")
            raise type(exc)(message).with_traceback(exc.__traceback__)

    def get_quote(self) -> bytes:
        """
        Return the SGX quote of the duet controller running in an SGX enclave.
        """
        try:
            with open("/dev/attestation/quote", "rb") as f_quote:
                quote = f_quote.read()
        except Exception as exc:
            message = ("Cannot find `/dev/attestation/quote`; "
                       "are you running with remote attestation enabled?")
            raise type(exc)(message).with_traceback(exc.__traceback__)

        return quote

class DuetAdminFactory:
    """
    The class to generate a duet controller instance according to the
    mode it was launched with.
    """
    @staticmethod
    def create_duet_admin(environment="direct"):
        """
        Create and return a duet controller instance.
        """
        duet_admin = None
        if environment == "direct":
            duet_admin = DuetAdmin(environment, logger=app.logger)
        elif environment == "sgx":
            duet_admin = DuetAdminEnclave(environment, logger=app.logger)
        else:
            app.logger.error(f"create_duet_admin {environment}: Unknown environment type.")
        return duet_admin

@app.route("/quote", methods=["GET"])
def handle_quote_request():
    """
    Route to return the SGX quote of the duet controller.

    If it was launched in `direct' mode, it will just be an empty
    quote.

    The TLS certificate that was based on the ephemerally generated
    public/private keypair of the duet controller
    is also supplied in the response.
    """
    quote = b""
    if isinstance(DUET_ADMIN, DuetAdminEnclave):
        quote = DUET_ADMIN.get_quote()

    result = {}
    result["duet_admin_quote"] = base64.b64encode(quote).decode("utf-8")
    result["duet_admin_tls_certificate"] = DUET_ADMIN.get_tls_certificate()

    return result

@app.route("/info", methods=["GET"])
def handle_service_info_request():
    """
    This function returns the service info that includes
    the secure hashes of the service code archive,
    the service dependencies and the tools that were deployed
    with the service.
    """
    result = {}
    result["duet_service_info"] = DUET_ADMIN.get_service_info()

    return result

@app.route("/", methods=["POST"])
def handle_service_request():
    """
    This function proxies service requests to the service in a CVM.
    """
    result = DUET_ADMIN.handle_service_request(request.get_json())

    return result

@app.route("/admin", methods=["POST"])
def handle_admin_request():
    """
    This function handles a privileged request to maintain the service
    (e.g., provisioning a CVM, installing service dependencies,
    starting the service).

    Once a service owner is registered with a public key,
    the duet controller cannot be used for deploying other services.

    All privileged requests require the signature of the service owner,
    which is verified with the registered public key.
    """
    data = request.get_json()

    if "signature" in data and "params" in data and "action" in data["params"]:
        signature = base64.b64decode(data["signature"])
        params = data["params"]
        action = params["action"]

        # this can only be called once to register the owner
        if action == "register":
            if "public_key" in data["params"]:
                # check signature
                public_key_pem = params["public_key"]
                verified = verify_signature_with_public_key_pem(signature, json.dumps(params, sort_keys=True), public_key_pem)
                if verified:
                    result = DUET_ADMIN.register_owner(public_key_pem)
                else:
                    result = {"error": "Owner registration failed due to incorrect signature."}
            else:
                result = {"error": "Missing parameter(s)."}
        else:
            verified = DUET_ADMIN.verify_owner_signature(signature, json.dumps(params, sort_keys=True))
            if verified:
                required_params = []
                if action == "config":
                    required_params.extend(["cloud_config"])
                elif action == "start_cvm":
                    required_params.extend(["cloud_provider", "cvm_type", "cvm_num_cpus"])
                elif action == "stop_cvm":
                    required_params.extend(["cvm_id"])
                elif action == "start_service":
                    required_params.extend(["service_code_data", "service_tools", "service_dependencies_data", "use_gpu"])

                if check_missing_parameters(params, required_params, empty_ok=False):
                    if action == "config":
                        cloud_config = params["cloud_config"]
                        result = DUET_ADMIN.set_cloud_config(cloud_config)
                    elif action == "start_cvm":
                        cloud_provider = params["cloud_provider"]
                        cvm_type = params["cvm_type"]
                        cvm_num_cpus = params["cvm_num_cpus"]
                        result = DUET_ADMIN.start_cvm(cloud_provider, cvm_type, cvm_num_cpus)
                    elif action == "stop_cvm":
                        cvm_id = params["cvm_id"]
                        result = DUET_ADMIN.stop_cvm(cvm_id)
                    elif action == "start_service":
                        service_code = base64.b64decode(params["service_code_data"])
                        service_dependencies = base64.b64decode(params["service_dependencies_data"])
                        service_tools = params["service_tools"]
                        service_tools_data = {}
                        for tool_name in service_tools:
                            service_tools_data[tool_name] = base64.b64decode(service_tools[tool_name])
                        use_gpu = params["use_gpu"]
                        result = DUET_ADMIN.start_service(service_code, service_dependencies, service_tools_data, use_gpu)
                    elif action == "stop_service":
                        result = DUET_ADMIN.stop_service()
                else:
                    result = {"error": "Missing parameter(s)."}
            else:
                result = {"error": action + ": This privileged operation is only permitted to the owner."}
    else:
        result = {"error": "Missing parameter(s)."}

    response = result

    return response

def parse_args():
    """
    Parse the arguments to instantiate the controller.
    """
    parser = ArgumentParser()
    parser.add_argument("-p", "--port", default=6037, help="Server port")
    parser.add_argument("-t", "--type", choices=["direct", "sgx"], default="sgx", help="TEE type for duet/admin")
    args = parser.parse_args()
    return args

# Register a signal handler for SIGINT
def handle_sigint(signal_, frame_):
    """
    Register the signal handler when running in direct mode.
    """
    app.logger.info("SIGINT received. Stopping DuetAdmin...")
    sys.exit()

def main():
    """
    Main function to initialize the duet controller.
    """
    app.logger.setLevel(logging.INFO)

    logger = logging.getLogger("azure")
    logger.setLevel(logging.WARNING)

    logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
    logger.setLevel(logging.ERROR)

    signal.signal(signal.SIGINT, handle_sigint)

    args = parse_args()
    port = args.port

    app.logger.info(f"Starting duet/admin in '{args.type}' mode...")

    global DUET_ADMIN
    DUET_ADMIN = DuetAdminFactory.create_duet_admin(args.type)

    cert_filename, key_filename = DUET_ADMIN.get_tls_certificate_filenames()

    app.run(port=port, host="0.0.0.0", threaded=True, load_dotenv=False, ssl_context=(cert_filename, key_filename))

if __name__ == "__main__":
    main()
