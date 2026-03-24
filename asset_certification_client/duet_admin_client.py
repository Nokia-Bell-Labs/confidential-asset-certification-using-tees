# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import base64
import json

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key

import requests

from urllib3.exceptions import SubjectAltNameWarning

try:
    from .SGXQuoteVerifier.sgx_quote_verifier import AzureSGXQuoteVerifier
except Exception as _:
    from SGXQuoteVerifier.sgx_quote_verifier import AzureSGXQuoteVerifier

requests.packages.urllib3.disable_warnings(category=SubjectAltNameWarning)

# Decode base64-encoded data
def decode_base64(data):
    try:
        decoded = base64.b64decode(data)
    except Exception as _:
        decoded = data

    return decoded

class DuetAdminClient():
    """
    This is the base class to interact with the duet controller running in an SGX enclave.

    It includes basic variables to hold information about the duet controller,
    such as its ephemeral public key and its quote.

    The client communicates with the duet controller using its TLS certificate,
    so that any data being sent is encrypted and can only be decrypted inside the
    SGX enclave of the duet controller.

    The only exception is to retrieve the duet controller's quote,
    which later is verified via the attestation service provider.

    Limitations: Currently, only Azure Attestation Service is supported.
    """
    def __init__(self, base_url, attestation_service_url, sgx_quote_provider="azure"):
        self._base_url = base_url
        self._attestation_service_url = attestation_service_url

        self._private_key = None

        self._controller_public_key = None
        self._controller_public_key_pem = None
        self._controller_quote = None

        self._controller_tls_certificate = None
        self._controller_tls_certificate_filename = "duet_admin_certificate.pem"

        if sgx_quote_provider == "azure":
            self._quote_verifier = AzureSGXQuoteVerifier(self._attestation_service_url)
        else:
            raise Exception("Other SGX quote providers are not yet supported.")

    def _sign_data(self, data):
        """
        Internal function to sign data when registering the owner
        of the certification service.
        """
        if not isinstance(data, bytes):
            data = bytes(data, "utf-8")

        signature = self._private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

        return signature

    def _action(self, action, data_to_send):
        """
        Internal function to interact with the duet controller.
        """
        url = self._base_url
        if action in ["quote", "info"]:
            url += "/" + action
        elif action in ["register", "config", "start_cvm", "stop_cvm", "start_service", "stop_service"]:
            url += "/admin"
            # privileged operations need to be signed by the owner
            data_to_send["signature"] = base64.b64encode(self._sign_data(json.dumps(data_to_send["params"], sort_keys=True))).decode()

        try:
            if action == "quote":
                # need to first get an unverified quote with the TLS certificate
                # we then set the tls certificate, so that any subsequent connections
                # happen through TLS
                response = requests.get(url, verify=False)
            elif action == "info":
                response = requests.get(url, verify=self._controller_tls_certificate_filename)
            else:
                response = requests.post(url, json=data_to_send, verify=self._controller_tls_certificate_filename)
                # response = requests.post(url, json=data_to_send, verify=False)

            if response.status_code == 200:
                response_data = response.json()
                return response_data

            raise Exception(f"Request did not succeed: {response.status_code}")
        except requests.exceptions.RequestException as exc:
            print("Request encountered an exception:", exc)
            raise

    def verify_controller(self, expected_mrenclave):
        """
        This function verifies the authenticity of the duet controller running in an SGX
        enclave.

        It sets up the TLS certificate, so that any future communication
        with the controller uses a TLS channel.

        It also extracts the ephemeral public key of the controller,
        so that it can later be used to verify the signature of the controller
        on any response.
        """
        response_data = self.get_controller_quote()

        quote = response_data["duet_admin_quote"]
        tls_cert = response_data["duet_admin_tls_certificate"]

        with open(self._controller_tls_certificate_filename, "w", encoding="utf-8") as f:
            f.write(tls_cert)

        cert_pem_data = bytes(tls_cert, "utf-8")

        self._controller_tls_certificate = x509.load_pem_x509_certificate(cert_pem_data, default_backend())
        self._controller_public_key = self._controller_tls_certificate.public_key()

        self._controller_public_key_pem = self._controller_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        controller_quote_verified = self._quote_verifier.verify_remote_enclave(decode_base64(quote), self._controller_public_key_pem, expected_mrenclave)
        print(f"Valid SGX controller: {controller_quote_verified}")
        if not controller_quote_verified:
            print("[WARNING]: Unverified SGX controller.")
        
        self._controller_quote = quote

        return response_data

    # non-privileged operation to establish trust in the controller
    def get_controller_quote(self):
        """
        This function obtains the SGX quote of the duet controller
        along with its ephemeral public key and its TLS certificate.
        """
        return self._action("quote", None)

    def get_service_info(self):
        """
        This function obtains the service info that was deployed using the duet controller.
        """
        return self._action("info", None)

    def register_owner(self, public_key_filename, private_key_filename):
        """
        This function registers the public key of the service owner.

        All future maintenance actions are signed with the private key of the service owner,
        so that such actions can only be issued by the registered owner.
        """
        with open(private_key_filename, "rb") as f:
            private_key_pem = f.read()
            self._private_key = load_pem_private_key(private_key_pem, password=None)

        with open(public_key_filename, "r", encoding="utf-8") as f:
            owner_public_key_pem = f.read()

        data = {}
        params = {}
        params["action"] = "register"
        params["public_key"] = owner_public_key_pem
        data["params"] = params

        return self._action(params["action"], data)

    def set_cloud_config(self, cloud_config):
        """
        This function sets the cloud configuration that will be used the by duet controller
        to launch Confidential VMs when deploying the service.
        """
        data = {}
        params = {}
        params["action"] = "config"
        params["cloud_config"] = cloud_config
        data["params"] = params

        return self._action(params["action"], data)

    def start_cvm(self, cloud_provider, cvm_type, cvm_num_cpus):
        """
        This function instructs the duet controller to start a CVM.
        """
        data = {}
        params = {}
        params["action"] = "start_cvm"
        params["cloud_provider"] = cloud_provider
        params["cvm_type"] = cvm_type
        params["cvm_num_cpus"] = cvm_num_cpus
        data["params"] = params

        return self._action(params["action"], data)

    def stop_cvm(self, cvm_id):
        """
        This function instructs the duet controller to stop a CVM.
        """
        data = {}
        params = {}
        params["action"] = "stop_cvm"
        params["cvm_id"] = cvm_id
        data["params"] = params

        return self._action(params["action"], data)

    def start_service(self, service_code_data, service_dependencies_data, service_tools, use_gpu):
        """
        This function instructs the duet controller to deploy a service
        along with its dependencies and any additional tools that are
        useful for the service.
        """
        data = {}
        params = {}
        params["action"] = "start_service"
        params["service_code_data"] = base64.b64encode(service_code_data).decode()
        params["service_dependencies_data"] = base64.b64encode(service_dependencies_data).decode()
        params["service_tools"] = {}
        for tool_name in service_tools:
            params["service_tools"][tool_name] = base64.b64encode(service_tools[tool_name]).decode()
        params["use_gpu"] = use_gpu
        data["params"] = params

        return self._action(params["action"], data)

    def stop_service(self):
        """
        This function instructs the duet controller to stop the deployed service
        as well as the corresponding CVMs.
        """
        data = {}
        params = {}
        params["action"] = "stop_service"
        data["params"] = params
        
        return self._action(params["action"], data)
