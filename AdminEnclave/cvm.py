# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import io
import time

import paramiko

import requests

try:
    from .utils.crypto import compute_hash
except Exception as _:
    from utils.crypto import compute_hash

class ConfidentialVM():
    """
    The class to hold metadata for a confidential VM.
    """
    def __init__(self, config, ip_address, serialized_public_key, logger):
        self._logger = logger
        self._config = config
        self._ip_address = ip_address
        self._serialized_public_key = serialized_public_key
        if self._config["cloud_provider"] == "azure":
            self._has_gpu = self._config["vm_size"] == "Standard_NCC40ads_H100_v5"
        else:
            self._has_gpu = False

        self._cvm_id = compute_hash(self._serialized_public_key)

        self._cvm_location = {}
        self._cvm_location["service_owner_config_result"] = self._config["location"]

        self._ssh_private_key = None

        self._tls_certificate_filename = None

    def get_cloud_provider(self):
        """
        Return the cloud provider for this CVM.
        """
        return self._config["cloud_provider"]

    def get_cvm_location(self):
        """
        Return the location info for this CVM.

        This info includes:
        1) service owner cloud config location (e.g., "westeurope" for Azure),
        2) cloud provider metadata (e.g., "westeurope" for Azure),
        3) GeoIP API lookup results,
        4) RTT-based estimated location.
        """

        return self._cvm_location

    def set_cvm_location(self, cvm_location):
        """
        Update the location info for this CVM via the geolocation tool report.

        It will include the items from the `get_cvm_location()' description
        (Items 2-4):
        1) cloud provider metadata (e.g., "westeurope" for Azure),
        2) GeoIP API lookup results,
        3) RTT-based estimated location.
        """

        self._cvm_location.update(cvm_location)

    def get_cvm_type(self):
        """
        Return the type of the CVM (e.g., snp, snp-h100).
        """
        return self._config["cvm_type"]

    def get_config(self):
        """
        Return the cloud configuration that was used to set up this CVM.
        """
        return self._config

    def get_cvm_username(self):
        """
        Return the username that was used to set up this CVM.
        """
        return self._config["vm_username"]

    def get_cvm_id(self):
        """
        Return the id of this CVM.
        """
        return self._cvm_id

    def get_cvm_ip(self):
        """
        Return the IP address of this CVM.
        """
        return self._ip_address

    def has_gpu(self):
        """
        Return whether this CVM has a GPU TEE.
        """
        return self._has_gpu

    def set_cvm_tls_certificate_filename(self, cvm_tls_certificate_filename):
        """
        Set the TLS certificate filename for this CVM,
        so that the duet controller can securely communicate with it for service requests.
        """
        self._tls_certificate_filename = cvm_tls_certificate_filename

    def set_private_key(self, pkey):
        """
        Set the private SSH key for this CVM.
        """
        pkeyfile = io.StringIO(pkey)
        self._ssh_private_key = paramiko.RSAKey.from_private_key(pkeyfile)
        #self._ssh_private_key = paramiko.RSAKey.from_private_key_file("ephemeral_private_key")

    def execute_command(self, command):
        """
        Execute a command on this CVM (e.g., for installing service dependencies).
        """
        ssh_client = self._get_ssh_client()
        _stdin, _stdout, _stderr = ssh_client.exec_command(command, get_pty=True)
        self._logger.info("-"*50)
        self._logger.info("Executing command: " + command)
        self._logger.info("Waiting output...")
        output = []
        for line in iter(_stdout.readline, ""):
            line = line.replace("\r", " ").strip()
            output.append(line)
            # self._logger.info(line)
            if len(output) % 50 == 0:
                self._logger.info("Accumulating output lines: " + str(len(output)))
            if len(output) % 300 == 0:
                for line in output:
                    self._logger.info(line)
                output = []

        ssh_client.close()

        for line in output:
            self._logger.info(line)

        self._logger.info("\n")

        return output

    def _get_ssh_client(self):
        """
        Internal function to return an SSH client to communicate with the CVM.
        """
        ssh_client = paramiko.SSHClient()
        policy = paramiko.AutoAddPolicy()
        ssh_client.set_missing_host_key_policy(policy)

        while True:
            try:
                ssh_client.connect(self._ip_address, username=self._config["vm_username"], pkey=self._ssh_private_key, timeout=15)
                break
            except Exception as _:
                self._logger.info("Trying to connect to the CVM...")
                time.sleep(15)

        return ssh_client

    def copy_file(self, local_filepath, remote_filepath):
        """
        Securely copy a local file from the duet controller to the CVM.
        """
        ssh_client = self._get_ssh_client()
        sftp_client = ssh_client.open_sftp()
        sftp_client.put(local_filepath, remote_filepath)
        sftp_client.close()
        ssh_client.close()

    def get_file(self, remote_filepath, local_filepath):
        """
        Securely copy a remote file from the CVM to the duet controller.
        """
        ssh_client = self._get_ssh_client()
        sftp_client = ssh_client.open_sftp()
        sftp_client.get(remote_filepath, local_filepath)
        sftp_client.close()
        ssh_client.close()

    def handle_service_request(self, request_json_data):
        """
        Proxy a service request to the service running in this CVM.
        """
        try:
            url = "https://" + self._ip_address + ":6038"
            response = requests.post(url, json=request_json_data, verify=self._tls_certificate_filename)

            if response.status_code == 200:
                return response.json()

            raise Exception(f"Request did not succeed: {response.status_code}")
        except Exception as _:
            raise
