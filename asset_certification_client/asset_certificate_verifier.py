# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import base64
from io import BytesIO
import json
import os
import pathlib
import tarfile

from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import load_pem_public_key

try:
    from .SGXQuoteVerifier.sgx_quote_verifier import AzureSGXQuoteVerifier
except Exception as _:
    from SGXQuoteVerifier.sgx_quote_verifier import AzureSGXQuoteVerifier

ATTESTATION_SERVICE_URL = os.getenv("ATTESTATION_SERVICE_URL", "https://sharedneu.neu.attest.azure.net")

def verify_signature(signature, data, public_key_pem):
    """
    Verify the signature on data given a public key.
    """
    if not isinstance(signature, bytes):
        signature = bytes(signature, "utf-8")

    if not isinstance(data, bytes):
        data = bytes(data, "utf-8")

    if not isinstance(public_key_pem, bytes):
        public_key_pem = bytes(public_key_pem, "utf-8")

    public_key = load_pem_public_key(public_key_pem)

    try:
        public_key.verify(
            signature,
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256())
        return True
    except Exception as exc:
        # raise exc
        return False

def compute_hash(data):
    """
    Compute the secure hash (i.e., SHA-256) of some data.
    """
    if not isinstance(data, bytes):
        data = bytes(data, "utf-8")

    hash_object = hashes.Hash(hashes.SHA256())
    hash_object.update(data)
    hash_value = hash_object.finalize().hex()

    return hash_value

def reset(tarinfo):
    """
    Utility function to change the ownership of files put into a tar archive
    tar archive record also user and group names,
    meaning that if built in different environment by different users,
    the tar archives and their corresponding hash would be different
    Avoid this issue by calling this function when build the tar archive    
    """
    tarinfo.mode = 0o644
    tarinfo.uid = tarinfo.gid = 0
    tarinfo.uname = tarinfo.gname = "root"
    tarinfo.mtime = 1
    return tarinfo

class AssetCertificateVerifier():
    """
    This class is for verifying a given asset certificate.
    The asset certificate contains:
    1) duet controller's SGX quote, its ephemeral public key, attestation URL
    2) service result, including the service info and the service output
    3) duet controller's signature over the service result
    
    The service output contains the secure hash values of 
    the inputs, the computation code archive and the computation result.
    The code build arguments will also be individually hashed.
    It can also contain any additional self-contained certificates of the inputs.
    """
    def __init__(self, certificate_filename, code_folder, output_folder, input_folders, code_build_args, duet_manifest):
        self._certificate_filename = certificate_filename
        self._code_folder = code_folder
        self._output_folder = output_folder
        self._input_folders = input_folders
        self._code_build_args = code_build_args
        self._duet_manifest = duet_manifest
        self._expected_controller_code_hash = duet_manifest["EXPECTED_DUET_ADMIN_MRENCLAVE"]
        self._expected_service_info = duet_manifest["EXPECTED_DUET_SERVICE_INFO"]

    def _verify_service_info(self, service_info):
        """
        Internal function to ensure that the service info in the asset certificate
        matches the expected values.
        """
        h = "service_code_hash"
        if h not in service_info or self._expected_service_info[h] != service_info[h]:
            return False

        h = "service_tools_hashes"
        if h not in service_info or self._expected_service_info[h] != service_info[h]:
            return False

        # Depending on whether the certification service used a GPU TEE (e.g., NVIDIA H100),
        # the dependencies can be different.
        # Both are present in the expected hashes.
        h = "service_dependencies_hash"
        if h not in service_info or service_info[h] not in self._expected_service_info[h].values():
            return False

        return True
        
    def verify_certificate(self, duet_admin_sgx_quote_provider="azure"):
        """
        This function verifies the asset certificate.
        
        It starts with verifying the duet controller's SGX quote 
        that embeds the public key in its REPORTDATA field.
        Then it uses the public key to verify the signature on the service result.
        The service results contains two parts: service info and service output.
        The service info is checked against the expected values
        of the service code archive, service dependencies and the tool code archives.
        The service output contains the hashes of the property computation code archive
        and the input files (optional).
        If input files are available locally, their hashes are checked as well.
        
        The result of each verification step is recorded and returned along
        with the verification result.
        
        Note that currently Azure attestation is supported.
        """
        result_verification_steps = {}
        with open(self._certificate_filename, "r") as f:
            asset_certificate = json.load(f)

        # 1. extract the duet controller's SGX quote and its public key
        # and verify its authenticity
        duet_admin_quote = asset_certificate["duet_admin_quote"]
        quote = base64.b64decode(duet_admin_quote["quote"])
        controller_public_key_pem = duet_admin_quote["public_key"]
        attestation_service_url = asset_certificate["duet_admin_attestation_service_url"]
        if duet_admin_sgx_quote_provider == "azure":
            quote_verifier = AzureSGXQuoteVerifier(attestation_service_url)
        else:
            raise Exception("Other SGX quote providers are not yet supported.")

        verified = quote_verifier.verify_remote_enclave(quote, controller_public_key_pem, self._expected_controller_code_hash)
        if verified:
            print("[OK] Valid SGX quote for duet controller.")
        else:
            print("[ERROR] Invalid SGX quote for duet controller.")

        result_verification_steps["01_duet_admin_quote"] = verified
        
        # 2. get service result and verify the signature on it with controller public key
        duet_service_result = asset_certificate["duet_service_result"]
        
        verified = verify_signature(base64.b64decode(asset_certificate["duet_admin_signature"]), json.dumps(duet_service_result, sort_keys=True), controller_public_key_pem)
        if verified:
            print("[OK] Valid signature on certification output by duet admin.")
        else:
            print("[ERROR] Invalid duet admin signature on certification output.")

        result_verification_steps["02_controller_signature"] = verified

        # 3. verify the service info matches the expected measurements
        service_info = duet_service_result["service_info"]
        verified_service = self._verify_service_info(service_info)
        if verified_service:
            print("[OK] Valid service info.")
        else:
            print("[ERROR] Invalid service info.")
        
        result_verification_steps["03_duet_service_info"] = verified_service

        service_result = duet_service_result["service_result"]
        service_result_hashes = service_result["hashes"]

        # 4. check the hashes of the computation code archive
        # the code folder must be available
        code_hashes = service_result_hashes["code"]
        result_verification_steps["04_code_hashes"] = {}
        for code_name in code_hashes:
            code_path = pathlib.Path(self._code_folder)
            code_files = [str(file) for file in list(code_path.rglob("*"))]
            code_files = sorted(code_files)
            buf = BytesIO()
            with tarfile.open(fileobj=buf, mode="w", dereference=True) as tar:
                for fname in code_files:
                    base_fname = fname[len(self._code_folder):]
                    if not self._code_folder.endswith("/"):
                        base_fname = base_fname[1:]
                    tar.add(fname, base_fname, filter=reset)

            data = buf.getvalue()
            hash_value = compute_hash(data)
            # print(hash_value)
            if service_result_hashes["code"][code_name] == hash_value:
                print("[OK] Matching computation code hash.")
                result_verification_steps["04_code_hashes"][code_name] = True
            else:
                print("[ERROR] Mismatch of computation code hash.")
                result_verification_steps["04_code_hashes"][code_name] = False
            
        # 5. check the hashes of the outputs
        # the output folder must be available
        output_map = service_result_hashes["outputs"]
        result_verification_steps["05_output_hashes"] = {}
        for output_name in output_map:
            with open(self._output_folder + "/" + output_name, "rb") as f:
                data = f.read()
                
                hash_value = compute_hash(data)

                if service_result_hashes["outputs"][output_name] == hash_value:
                    print("[OK] Matching computation output hash: " + output_name)
                    result_verification_steps["05_output_hashes"][output_name] = True
                else:
                    print("[ERROR] Mismatch of computation output hash: " + output_name)
                    result_verification_steps["05_output_hashes"][output_name] = False

        # 6. check the hashes of the input files if they are available (optional)
        # If the assets are confidential, this will usually be the case.

        # Their hashes can be checked afterwards:
        # For example, after checking the certificate's authenticity and
        # ensuring the asset's properties satisfy use case requirements,
        # one might purchase the asset from a marketplace.
        # As a final step, one could check the input files to ensure that the
        # purchased asset is referred by this certificate.
        # If not purchased, the asset still stays confidential.
        # The certificate allows a potential buyer to assess
        # its properties for the use case.
        input_hashes = service_result_hashes["inputs"]
        result_verification_steps["06_input_hashes"] = {}
        if self._input_folders:
            for input_folder in self._input_folders:
                for input_name in input_hashes:
                    if os.path.exists(input_folder + "/" + input_name):
                        with open(input_folder + "/" + input_name, "rb") as f:
                            data = f.read()
                            
                            hash_value = compute_hash(data)
                
                            if input_hashes[input_name] == hash_value:
                                print("[OK] Matching input hash: " + input_name)
                                result_verification_steps["06_input_hashes"][input_name] = True
                            else:
                                print("[ERROR] Mismatch of input hash: " + input_name)
                                result_verification_steps["06_input_hashes"][input_name] = False
        else:
            print("[INFO] No input files to check.")
            result_verification_steps["06_input_hashes"][None] = True

        # 7. check the hashes of the given code_build_args
        # some arguments may be confidential (e.g., API tokens);
        # only their hashes will be visible
        code_build_arg_hashes = service_result_hashes["code_build_args"]
        result_verification_steps["07_code_build_args_hashes"] = {}
        if self._code_build_args:
            for key in self._code_build_args:
                value = json.dumps(self._code_build_args[key], sort_keys=True)
                hash_value = compute_hash(value)

                if code_build_arg_hashes[key] == hash_value:
                    print("[OK] Matching code build arg hash: " + key)
                    result_verification_steps["07_code_build_args_hashes"][key] = True
                else:
                    print("[ERROR] Mismatch of code build arg hash: " + key)
                    result_verification_steps["07_code_build_args_hashes"][key] = False
        else:
            print("[INFO] No code build args to check.")
            result_verification_steps["07_code_build_args_hashes"][None] = True

        matching = True
        for x in ["04_code_hashes", "05_output_hashes", "06_input_hashes"]:
            matching = matching and all(result_verification_steps[x].values())

        matching = matching and all(result_verification_steps.values())
        return matching, result_verification_steps
