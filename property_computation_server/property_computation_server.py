# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import hashlib
import time
import uuid

try:
    from .property_computation_request import PropertyComputationRequest
except Exception as _:
    from property_computation_request import PropertyComputationRequest

class PropertyComputationServer():
    """
    The Property Computation Server.
    """
    def __init__(self, cvm_id, base_folder, has_gpu):
        self._cvm_id = cvm_id
        self._base_folder = base_folder
        self._has_gpu = has_gpu

        self._request_map = {}

    def create_request(self):
        """
        Initialize a server data structure for a property computation request.

        It creates a unique id for this request and an authentication token for allowing
        the client to refer to this request in later interactions
        to set up the processing. It keeps track of it in its internal map.

        The initialization of the computation request also creates a temporary storage
        location at the server, in which various input files (i.e., inputs, code, certificates)
        will be stored when they are uploaded.
        """
        # generate a unique id
        request_id = str(uuid.uuid4())
        request_token = hashlib.sha256((request_id + str(time.time())).encode()).hexdigest()

        req = PropertyComputationRequest(request_id, request_token, self._base_folder)

        self._request_map[request_id] = req

        result = {}
        result["request_id"] = request_id
        result["request_token"] = request_token
        # return current CVM id, so that the client can use it to ask for status updates, downloads etc.
        result["request_cvm_id"] = self._cvm_id

        return result

    def get_request(self, rid, rt):
        """
        Get a reference to an existing computation request and check
        its token to authenticate it.
        """
        msg = None
        req = self._request_map[rid]
        if not req:
            msg = "No such request."
        elif not req.valid_token(rt):
            msg = "Invalid token for request."

        return req, msg

    def upload(self, data, req):
        """
        Update the given request with the currently uploaded input data.

        The input can be an input file, a code archive or a certificate.

        If it is a certificate, then its `associated_input_name` must be present.

        The upload method can be a publicly accessible "url", so that the server will download
        the corresponding file before request's computation starts.
        If it is "b64data", then the server retrieves the contents and stores the file
        in the certification request's temporary file storage.
        If it is "hf_cache", the server will use the huggingface tool to make the repo
        available as huggingface cache.

        The corresponding data and metadata are kept track in the request's
        upload map, using the names given by the client.

        The code archive must contain a `Dockerfile` with its directives. The server
        will build the container image and use it when running the computation.
        """
        input_type = data["input_type"]
        if input_type not in ["inputs", "code", "certificates"]:
            return {"error": "Invalid parameters."}

        associated_input_name = None
        if input_type == "certificates":
            if "associated_input_name" not in data:
                return {"error": "Missing parameters: associated_input_name"}

            associated_input_name = data["associated_input_name"]

        code_build_args = None
        if input_type == "code" and "code_build_args" in data and data["code_build_args"]:
            code_build_args = data["code_build_args"]

        upmethod = data["upload_method"]
        if upmethod not in ["url", "b64data", "hf_cache"]:
            return {"error": "Invalid parameters."}

        updata = data["upload_data"]
        upname = data["upload_name"]
        req.add_to_upload_map(input_type, upname, updata, upmethod, associated_input_name, code_build_args)

        return {"message": "Input/code uploaded successfully."}

    def prepare_computation(self, req):
        """
        Prepare the property computation.

        Depending on the upload map of the request,
        the necessary input files will be downloaded and stored.
        Afterwards, the hashes of the input files and the
        computation code archive will be computed
        as well as the build arguments for container image.
        Finally, the computation container image will be built with the computaiton
        code archive.
        """
        req.prepare()

        return {"message": "Preparation started successfully."}

    def start_computation(self, req):
        """
        Start the computation of a request.

        The computation will be started in a Docker container to which 2 folders
        will be given as mount points:
        1) "inputs" (read-only): The computation code will find the input files that were
        uploaded here and can access them using the `name` it gave during the upload.
        2) "outputs" (read-write): The computation code might produce some output files
        that might be stored here. The property computation server will
        compute their hashes and include them in the service result.
        """
        # start the container image
        req.run_computation(self._has_gpu)

        return self.check_status(req)

    def check_status(self, req):
        """
        Check the status of the request's computation.

        If container is still running or finished, it will be indicated as its
        status.

        It is the client's responsibility to check whether the computation has
        finished.
        """
        status = req.get_status()

        result = {}
        result["request_id"] = req.get_request_id()
        result["status"] = status
        if status == "FINISHED":
            result["log_lines"] = req.get_log_lines()

        return result

    def get_service_result(self, req):
        """
        Retrieve the result of a finished property computation.

        It obtains the output map to return to the client.

        It also retrieves the service result that contains the hashes
        of PCC, inputs and outputs, and energy usage
        as well as any certificates belonging to the inputs.
        """
        if req.get_status() != "FINISHED":
            return {"error": "Not ready yet."}

        result = {}
        result["service_result"] = req.get_service_result()

        return result

    def download_output(self, output_name, req):
        """
        Download the output that was produced by the property computation
        request.
        """
        if req.get_status() != "FINISHED":
            return {"error": "Not ready yet."}

        output = req.get_output(output_name)

        result = {}
        result["output"] = output

        return result
