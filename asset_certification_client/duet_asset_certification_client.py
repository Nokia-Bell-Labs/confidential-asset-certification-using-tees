# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import base64
import json

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

try:
    from .duet_admin_client import DuetAdminClient
    from .asset_certificate import AssetCertificate
except Exception as _:
    from duet_admin_client import DuetAdminClient
    from asset_certificate import AssetCertificate

class DuetAssetCertificationServiceClient(DuetAdminClient):
    """
    Asset Certification Client.

    This class is used to interact with the certification service via
    the duet controller.
    """
    def __init__(self, controller_url, attestation_service_url, expected_mrenclave, expected_service_info):
        # will receive a certification token for our request,
        # which we'll use to authenticate our actions
        self._certification_request_id = None
        self._certification_request_token = None
        self._certification_request_cvm_id = None

        self._certification_input_hashes = {}
        self._certification_code_hash = {}

        self._expected_mrenclave = expected_mrenclave
        self._expected_service_info = expected_service_info

        self._asset_certificate = AssetCertificate()

        super().__init__(controller_url, attestation_service_url)
        self.verify_controller(expected_mrenclave)
        self._verify_service_info()
        self._asset_certificate.set_controller_quote({"quote": self._controller_quote, "public_key": self._controller_public_key_pem.decode()})
        self._asset_certificate.set_attestation_service_url(attestation_service_url)

    def _action(self, action, data_to_send=None):
        """
        Internal function to interact with the certification service.
        """
        if data_to_send is None:
            data_to_send = {}
        # if we have a set request id and token, include them in all our interactions
        if self._certification_request_id and self._certification_request_token:
            data_to_send["request_id"] = self._certification_request_id
            data_to_send["request_token"] = self._certification_request_token
            data_to_send["request_cvm_id"] = self._certification_request_cvm_id

        data_to_send["action"] = action

        return super()._action(action, data_to_send)

    def _verify_service_info(self):
        """
        This function is used to verify the service info,
        so that it is checked against expected values
        before interacting with the certification service using confidential assets.
        """
        response_data = self.get_service_info()

        service_info = response_data["duet_service_info"]

        verified = True

        h = "service_code_hash"
        if h not in service_info or self._expected_service_info[h] != service_info[h]:
            print("[WARNING]: Unverified service info: service code hashes do not match.")
            verified = False

        h = "service_tools_hashes"
        if h not in service_info or self._expected_service_info[h] != service_info[h]:
            print("[WARNING]: Unverified service info: service tools hashes do not match.")

        h = "service_dependencies_hash"
        if h not in service_info or service_info[h] not in self._expected_service_info[h].values():
            print("[WARNING]: Unverified service info: service dependencies hashes do not match.")
            verified = False

        if verified:
            print("[OK] Verified service info.")

        return response_data

    def _verify_controller_signature(self, signature, data):
        """
        This function is used to check the signature of the duet controller
        using its ephemerally generated public key.
        """
        if not isinstance(signature, bytes):
            signature = bytes(signature, "utf-8")

        if not isinstance(data, bytes):
            data = bytes(data, "utf-8")

        try:
            self._controller_public_key.verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256())
        except Exception as _:
            return False

        return True

    def create_certification_request(self):
        """
        Initiates a new certification request and starts
        keeping track of it.

        The request token is used as an authentication mechanism
        for interacting with the certification request at the server.
        """
        resp = self._action("new")
        
        if "error" in resp:
            return resp

        self._certification_request_id = resp["request_id"]
        self._certification_request_token = resp["request_token"]
        self._certification_request_cvm_id = resp["request_cvm_id"]

        return resp

    def upload(self, input_type, upload_name, upload_method, upload_data, associated_input_name=None, hash_value=None, code_build_args=None):
        """
        Upload an input file to set up the current certification request.

        The input type can refer to:
        1) "inputs": files that are read by the processing code.
        2) "code": the processing code.
        3) "certificates": files that are included in the service output.

        There can only be one "code" type file, which overwrites previously uploaded
        "code" type input files.

        The upload name refers to the name the file will be stored at the server's
        temporary folder specific for this request. These names can be referred to
        in the code, so that the code can read the corresponding input files and
        process them.

        The upload methods indicates how the input file is to be received by the
        server:
        1) "url": If the method is "url", then it needs to be publicly accessible, so that
        it can be downloaded by the server. The download happens when the
        request is started by the client.
        2) "b64data": If the method is "b64data", then the client is responsible for
        reading the file contents and passing them via `upload_data`.
        3) "hf_cache": If the method is "hf_cache", then the server will utilize the
        `huggingface` tool at the server side to download the assets from huggingface
        into its cache, and use the assets from that cache, allowing the service to
        compute the hashes of the inputs.

        The upload data can be a publicly accessible URL for the input file or the binary
        file content, which will be base64-encoded.

        If the input file is of type "certificates", then the `associated_input_name` must be
        set. The server will then include the certificate in the service output with that
        name, so that the certificate content can be matched to the corresponding input when
        checking the asset certificate at the verifying party (i.e., by checking the hash value
        of the input file in the certificate and matching it to the hash value of the input file).

        The hashes of all input files are computed and kept track, so that the client can keep
        track of what has been used as input in the certification request to later verify the
        content of the certification service output.

        If the upload method is "url", then the corresponding `hash_value` of the to-be-downloaded
        file must be given.
        """
        assert input_type in ["inputs", "code", "certificates"]
        assert upload_method in ["url", "b64data", "hf_cache"]

        if upload_method == "url":
            assert hash_value
        elif upload_method == "b64data":
            # compute hash of the upload_data if b64data
            hash_object = hashes.Hash(hashes.SHA256())
            hash_object.update(upload_data)
            hash_value = hash_object.finalize().hex()
        elif upload_method == "hf_cache":
            pass

        if input_type == "inputs":
            self._certification_input_hashes[upload_name] = hash_value
        elif input_type == "code":
            self._certification_code_hash[upload_name] = hash_value

        data_to_send = {}
        data_to_send["input_type"] = input_type
        data_to_send["upload_method"] = upload_method
        data_to_send["upload_name"] = upload_name
        if input_type == "certificates":
            data_to_send["associated_input_name"] = associated_input_name

        if input_type == "code" and code_build_args:
            data_to_send["code_build_args"] = code_build_args

        if upload_method == "b64data":
            upload_data = base64.b64encode(upload_data).decode()
        data_to_send["upload_data"] = upload_data

        resp = self._action("upload", data_to_send)

        return resp

    def prepare(self):
        """
        Takes the necessary steps to prepare a computation.

        These steps include downloading necessary files and building the container image.
        The preparation takes place in an asynchronous way, so that one has to call get_status()
        to check whether a computation can be started via start().
        """
        resp = self._action("prepare")
        return resp

    def start(self):
        """
        Starts an already set up certification request.
        Before this call, prepare() needs to be called and finished.

        The certification request is considered ready when all necessary
        inputs and code (or their metadata on how to obtain them)
        have been uploaded to the server and prepared.
        """
        resp = self._action("start")
        return resp

    def get_status(self):
        """
        Checks the status of an already started certification request.
        """
        resp = self._action("status")
        return resp

    def get_result(self):
        """
        Obtains the certification result as well as the outputs from the server.

        If the certification request has not finished processing, the server
        returns an error.

        If it has finished, the server will return the service result as well as
        the outputs that were produced.

        First, the signature on the service result will be checked using the public
        key of the duet controller.

        The service result contains the service info. The service info identifies
        the certification service code, its dependencies and any tools that were
        deployed with it. The service info is then checked against expected values.

        The service result also includes the service output.
        The service output will contain the hashes of the input and code that were
        uploaded, which are then compared with the local information about them (if any).

        Finally, the service result is stored as part of the certificate content
        that will now contain all three pieces of the asset certificate:
        1) duet controller quote, 2) service result with service info, 3) controller signature.

        The response also contains a map of output names with their respective hashes,
        which match their corresponding names in the service output. The client
        can then download each such output.
        """
        resp = self._action("result")

        print(json.dumps(resp, indent=4))

        # check signature
        signature = base64.b64decode(resp["duet_admin_signature"])
        duet_service_result = resp["duet_service_result"]
        service_result_bytes = bytes(json.dumps(duet_service_result, sort_keys=True), "utf-8")
        
        verified = self._verify_controller_signature(signature, service_result_bytes)
        if not verified:
            print("[ERROR] Duet controller signature is not valid.")

        # check the service info
        service_info = duet_service_result["service_info"]

        for h in ["service_code_hash", "service_tools_hashes"]:
            if h not in service_info:
                print("[ERROR] Expected hash not in asset certificate: " + h)
            elif self._expected_service_info[h] != service_info[h]:
                print("[ERROR] Expected hash value not matching: " + h)

        h = "service_dependencies_hash"
        if h == "service_dependencies_hash" and service_info[h] not in self._expected_service_info[h].values():
            print("[ERROR] Expected hash value not matching: " + h)

        service_result = duet_service_result["service_result"]

        for input_name in service_result["hashes"]["inputs"]:
            if input_name in self._certification_input_hashes:
                if service_result["hashes"]["inputs"][input_name] != self._certification_input_hashes[input_name]:
                    print("[ERROR] Input hash does not match: " + input_name)

        for code_name in service_result["hashes"]["code"]:
            if service_result["hashes"]["code"][code_name] != self._certification_code_hash[code_name]:
                print("[ERROR] Code hash does not match: " + code_name)

        self._asset_certificate.set_controller_signature(resp["duet_admin_signature"])
        self._asset_certificate.set_service_result(duet_service_result)

        return resp

    def download(self, output_name):
        """
        Download an output that was produced by the certification request.
        """
        data_to_send = {}
        data_to_send["output_name"] = output_name

        resp = self._action("download", data_to_send)

        output = resp["output"]
        assert output_name == output["name"]
        if output["method"] == "b64data":
            output_data = base64.b64decode(output["data"])
        else:
            output_data = output["data"]

        return output_data

    def get_asset_certificate(self):
        """
        Returns the compiled asset certificate.
        """
        return self._asset_certificate.get_asset_certificate()
