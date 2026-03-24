# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

from abc import ABC, abstractmethod

class CloudClient(ABC):
    """
    Abstract class for interacting with different cloud service providers.
    """
    def __init__(self, config, ip_address, logger):
        self._config = config
        self._logger = logger
        self._ip_address = ip_address

    @abstractmethod
    def provision_resources(self, serialized_public_key):
        """
        This function's implementation will provision necessary resources for
        a confidential VM.
        """
        self._logger.info("[ERROR] There is no default implementation.")
    
    @abstractmethod
    def delete_resources(self):
        """
        This function's implementation will delete provisioned resources for
        a confidential VM.
        """
        self._logger.info("[ERROR] There is no default implementation.")
    
    @abstractmethod
    def check_attestation(self, attestation_token_filename, nonce_filename):
        """
        This function's implementation will check the attestation report
        of the provisioned confidential VM.
        """
        self._logger.info("[ERROR] There is no default implementation.")
    
    @abstractmethod
    def check_gpu_attestation(self, gpu_attestation_filename):
        """
        This function's implementation will check the attestation report
        of the GPU TEE (e.g., NVIDIA H100).
        """
        self._logger.info("[ERROR] There is no default implementation.")
