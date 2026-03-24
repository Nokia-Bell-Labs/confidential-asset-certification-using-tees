# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import base64
import json
import os
import pathlib
import shutil
import subprocess
from threading import Thread, Lock
import time

from cryptography.hazmat.primitives import hashes

# from carbontracker.tracker import CarbonTracker
from codecarbon import OfflineEmissionsTracker

import docker

import requests

class PropertyComputationRequest():
    """
    Data structure that holds the necessary data
    and metadata to keep track of a property computation request.
    """
    def __init__(self, request_id, request_token, base_tmp_folder):
        self._request_id = request_id
        self._request_token = request_token

        self._upload_map = {}
        self._code_input_name = None
        self._code_build_args = {}

        # inputs, code, outputs
        self._hashes = {}
        # also keep track of uploaded certificates for inputs, which includes code/model
        self._certificates = {}

        self._output_map = {}

        self._request_tmp_folder = base_tmp_folder + request_id
        os.makedirs(self._request_tmp_folder)
        for foldername in ["uploads", "inputs", "outputs", "code", "certificates"]:
            os.makedirs(self._request_tmp_folder + "/" + foldername + "/")

        self._power_usage = {}
        # self._tracker_names = ["codecarbon", "carbontracker"]
        self._tracker_names = ["codecarbon"]
        for tracker_name in self._tracker_names:
            self._power_usage[tracker_name] = {}

        self._log_lines = []

        self._status = "INITIALIZING"

        self._status_lock = Lock()

        self._docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')

    def _start_power_trackers(self):
        """
        This function sets up the trackers regarding the power usage.
        """
        trackers = {}
        trackers["codecarbon"] = OfflineEmissionsTracker(
                                    save_to_api=False,
                                    save_to_file=False,
                                    log_level="error",
                                    measure_power_secs=1.0,
                                    tracking_mode="process"
                                    )
        trackers["codecarbon"].start()

        # trackers["carbontracker"] = CarbonTracker(epochs=1,
        #                                 monitor_epochs=10,
        #                                 verbose=1,
        #                                 update_interval=1,
        #                                 interpretable=False,
        #                                 epochs_before_pred=10)

        # trackers["carbontracker"].epoch_start()

        return trackers

    def _stop_power_trackers(self, trackers, stage_name):
        """
        This function stops the power trackers and stores
        the power usage for the respective stage.
        """
        tracker_cc = trackers["codecarbon"]
        tracker_cc.stop()
        values = tracker_cc.final_emissions_data.values
        energy_consumed = values["energy_consumed"]
        if stage_name not in self._power_usage["codecarbon"]:
            self._power_usage["codecarbon"][stage_name] = 0.0
        self._power_usage["codecarbon"][stage_name] += energy_consumed

        tracker_cc.stop()

        # tracker_ct = trackers["carbontracker"]
        # tracker_ct.epoch_end()
        # energy_consumed = tracker_ct.tracker.total_energy_per_epoch()
        # energy_consumed = energy_consumed.sum()
        # if stage_name not in self._power_usage["carbontracker"]:
        #     self._power_usage["carbontracker"][stage_name] = 0.0
        # self._power_usage["carbontracker"][stage_name] += energy_consumed

        # tracker_ct.stop()

    def get_request_id(self):
        """
        Return the request id of this request.
        """
        return self._request_id

    def _create_necessary_subfolders(self, name, dest):
        """
        Internal function to create the necessary folder structure for uploaded files
        according to their names.
        """
        if name.find("/") != -1:
            subfolder = name[:name.rfind("/")]
            os.makedirs(self._request_tmp_folder + "/" + dest + "/" + subfolder, exist_ok=True)

    def _store_file(self, fname, data):
        """
        Store a file on disk.
        """
        with open(fname, "wb") as f:
            f.write(data)

    def _download_and_store_file(self, url, fname):
        """
        Download and store a file from a URL.
        """
        retry = 0
        while retry < 3:
            try:
                with requests.get(url, stream=True) as r:
                    r.raise_for_status()
                    with open(fname, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                    break
            except Exception as exc:
                retry += 1
                if retry == 3:
                    raise exc
                time.sleep((retry + 1) * 1.0)

    def _download_necessary_files(self):
        """
        Internal function to download necessary input files.

        The upload method can be "url" or "hf_cache".

        If it is "url", the file is downloaded from the URL.

        If it is "hf_cache", the `huggingface` tool is used to make
        the contents of the repo available offline in the cache.
        """
        for name in self._upload_map:
            if self._upload_map[name]["method"] == "url":
                self._create_necessary_subfolders(name, "uploads")
                url = self._upload_map[name]["data"]
                fname = self._request_tmp_folder + "/uploads/" + name
                self._download_and_store_file(url, fname)
                self._upload_map[name]["data"] = fname
            elif self._upload_map[name]["method"] == "hf_cache":
                self._create_necessary_subfolders("HF_CACHE/", "uploads")
                input_info = self._upload_map[name]["data"]
                asset_type = input_info["asset_type"]
                asset_id = input_info["asset_id"]

                # TODO: check repo size before downloading
                hf_config = {}
                hf_config["asset_type"] = asset_type
                hf_config["asset_id"] = asset_id
                if "hf_token" in input_info:
                    hf_config["hf_token"] = input_info["hf_token"]

                if asset_type == "dataset" and "configs" in input_info:
                    hf_config["dataset_configs"] = ",".join(input_info["configs"])

                with open(self._request_tmp_folder + "/uploads/hf_config.json", "w") as f:
                    f.write(json.dumps(hf_config, indent=4))

                volume_input = "type=bind,source=" + self._request_tmp_folder + "/uploads/HF_CACHE,destination=/tmp/HF_CACHE"
                volume_input2 = "type=bind,source=" + self._request_tmp_folder + "/uploads/hf_config.json,destination=/tmp/hf_config.json"

                # TODO: add error handling
                command = "docker run --init --rm --name tools-huggingface_" + self._request_id\
                        + " --mount " + volume_input\
                        + " --mount " + volume_input2\
                        + " --user 1000:1000"\
                        + " computation-tool-huggingface"
                command = command.split(" ")
                # print(command)
                subprocess.run(command, check=True)

                self._upload_map[name]["data"] = self._request_tmp_folder + "/uploads/HF_CACHE/"

    def _get_files(self, filetype):
        """
        Internal function to find files in a folder.
        """
        folder_name = self._request_tmp_folder + "/" + filetype + "/"
        folder_path = pathlib.Path(folder_name)
        files = [str(file) for file in list(folder_path.rglob("*")) if file.is_file()]
        return folder_name, files

    def _compute_and_set_hashes(self, filetype):
        """
        Internal function to compute and set the hashes of the files
        (i.e., inputs, code, outputs).
        """
        hash_map = {}
        folder_path, files = self._get_files(filetype)

        for filename in files:
            name = filename[len(folder_path):]
            with open(filename, "rb") as f:
                data = f.read()

                hash_object = hashes.Hash(hashes.SHA256())
                hash_object.update(data)
                hash_map[name] = hash_object.finalize().hex()

        self._hashes[filetype] = hash_map

    def _check_status(self):
        """
        This function checks the status of the running computation.

        If the computation is finished, the logs of the computation are collected.
        The hashes of the outputs are computed and set.
        """
        self._status_lock.acquire()
        if self._status == "RUNNING":
            try:
                # check container status
                container = self._docker_client.containers.get(self._request_id)

                if container.status.lower().startswith("exited"):
                    # get container logs
                    for line in container.logs(stream=True):
                        self._log_lines.append(line.decode().strip("\n"))

                    # cleanup
                    container.remove()
                    self._upload_map = None
                    for foldername in ["uploads", "inputs", "code", "certificates"]:
                        shutil.rmtree(self._request_tmp_folder + "/" + foldername, ignore_errors=True)

                    # set the hashes
                    self._compute_and_set_hashes("outputs")
                    self._status = "FINISHED"
            except Exception as exc:
                print(exc)

        self._status_lock.release()

    def valid_token(self, rt):
        """
        Checks the validity of the authentication token assigned
        during the creation of this request.
        """
        return self._request_token == rt

    def _add_certificate(self, associated_input_name, certificate_content):
        """
        Adds a certificate associated with an input.
        """
        self._certificates[associated_input_name] = certificate_content

    def add_to_upload_map(self, input_type, upname, updata, upmethod, associated_input_name=None, code_build_args=None):
        """
        Keep track of the data and metadata for an input file.

        If its upload method is "b64data", it will store it in the request's
        temporary folder.

        If it is a certificate, it will record the associated input name.

        If it is a code, then it will overwrite the internal reference to the code archive,
        which will be used during preparation to build the container image.
        """
        trackers = self._start_power_trackers()

        if upmethod == "b64data":
            fname = self._request_tmp_folder + "/uploads/" + upname
            data = base64.b64decode(updata)
            self._create_necessary_subfolders(upname, "uploads")
            self._store_file(fname, data)
            data = fname
        else: # upmethod == "url" or upmethod == "hf_cache":
            data = updata

        self._upload_map[upname] = {}
        self._upload_map[upname]["method"] = upmethod
        self._upload_map[upname]["data"] = data
        self._upload_map[upname]["type"] = input_type
        if input_type == "certificates":
            self._upload_map[upname]["associated_input_name"] = associated_input_name

        if input_type == "code":
            self._code_input_name = upname
            if code_build_args:
                self._code_build_args = code_build_args

        self._stop_power_trackers(trackers, "01_uploads")

    def _prepare_async(self):
        """
        This function runs in a separate thread to prepare for the computation.

        It first downloads the necessary input files.
        Then it moves uploaded files (and the downloaded files) to `inputs/` and `code/`.
        The hashes of these files are computed and recorded for the service result.
        Finally, the computation code archive is used to build the container image.
        """
        trackers = self._start_power_trackers()

        self._status_lock.acquire()
        self._status = "PREPARING_DOWNLOADING_FILES"
        self._status_lock.release()

        self._download_necessary_files()

        self._status_lock.acquire()
        self._status = "PREPARING_MOVING_FILES"
        self._status_lock.release()

        # handle any hf_cache related folders first
        if os.path.exists(self._request_tmp_folder + "/uploads/HF_CACHE"):
            shutil.move(self._request_tmp_folder + "/uploads/HF_CACHE", self._request_tmp_folder + "/inputs/")

        for name in self._upload_map:
            uploaded = self._upload_map[name]
            # we handled any hf_cache related folders above
            if uploaded["method"] == "hf_cache":
                continue

            self._create_necessary_subfolders(name, "inputs")
            # move the code archive
            if uploaded["type"] == "certificates":
                with open(uploaded["data"], "r") as f:
                    cert_content = f.read()
                self._add_certificate(uploaded["associated_input_name"], cert_content)
            else:
                # all remaining uploads are inputs or code
                shutil.move(uploaded["data"], self._request_tmp_folder + "/" + uploaded["type"] + "/" + name)

        self._stop_power_trackers(trackers, "02_preparing_downloading_files")

        trackers = self._start_power_trackers()

        self._status_lock.acquire()
        self._status = "PREPARING_COMPUTING_HASHES"
        self._status_lock.release()

        self._compute_and_set_hashes("inputs")
        self._compute_and_set_hashes("code")
        # also compute the hash of the code_build_args
        hash_map = {}
        for key in self._code_build_args:
            value = json.dumps(self._code_build_args[key], sort_keys=True)
            hash_object = hashes.Hash(hashes.SHA256())
            hash_object.update(bytes(value, "utf-8"))
            hash_map[str(key)] = hash_object.finalize().hex()
        self._hashes["code_build_args"] = hash_map

        self._stop_power_trackers(trackers, "03_preparing_computing_hashes")

        trackers = self._start_power_trackers()

        self._status_lock.acquire()
        self._status = "PREPARING_BUILDING_CONTAINER_IMAGE"
        self._status_lock.release()

        success_container = True
        success_code = True
        code_archive_filename = self._request_tmp_folder + "/code/" + self._code_input_name
        if os.path.isfile(code_archive_filename):
            with open(code_archive_filename, "rb") as f:
                try:
                    self._docker_client.images.build(fileobj=f, custom_context=True, tag=self._request_id, buildargs=self._code_build_args)
                except docker.errors.BuildError as err:
                    success_container = False

        else:
            success_code = False

        self._stop_power_trackers(trackers, "04_preparing_building_container_image")

        self._status_lock.acquire()
        if success_container:
            self._status = "READY"
        elif success_code:
            self._status = "ERROR_BUILDING_CONTAINER_IMAGE"
        else:
            self._status = "ERROR_NO_CODE_ARCHIVE"
        self._status_lock.release()

    def prepare(self):
        """
        Prepare to run the request's computation in a container.

        It will download any necessary files (i.e., whose upload methods were "url").
        Then, it will place the files in their respective folders (i.e., inputs, code).
        It will also compute the hashes of these files for the service result.
        Finally, it will build the corresponding container image referred by the code archive.
        """
        if self._status == "INITIALIZING":
            t1 = Thread(target=self._prepare_async, args=())
            t1.start()

    def _run_computation_async(self, has_gpu):
        trackers = self._start_power_trackers()

        # map the inputs/ and outputs/ volumes
        volume_map = {}
        volume_map[self._request_tmp_folder + "/inputs/"] = {"bind": "/tmp/inputs", "mode": "rw"}
        volume_map[self._request_tmp_folder + "/outputs/"] = {"bind": "/tmp/outputs", "mode": "rw"}

        # launch the container image
        # run with no detach for power measuring purposes, because we are already in a separate thread
        if has_gpu:
            device_requests = [docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])]
            self._docker_client.containers.run(self._request_id, init=True, name=self._request_id, device_requests=device_requests, volumes=volume_map, network_disabled=True)
        else:
            self._docker_client.containers.run(self._request_id, init=True, name=self._request_id, volumes=volume_map, network_disabled=True)

        self._stop_power_trackers(trackers, "05_running")

    def run_computation(self, has_gpu):
        """
        Run the request's computation in a container.

        The mounted folders are for inputs and outputs
        to be utilized by the computation code.
        """
        self._status_lock.acquire()
        if self._status == "READY":
            t1 = Thread(target=self._run_computation_async, args=(has_gpu,))
            t1.start()
            self._status = "RUNNING"

        self._status_lock.release()

    def get_output(self, output_name):
        """
        Retrieve the output that was produced by the request's computation.
        """
        self._check_status()

        output = {}

        if self._status == "FINISHED":
            if output_name in self._hashes["outputs"]:
                fname = self._request_tmp_folder + "/outputs/" + output_name
                with open(fname, "rb") as f:
                    data = f.read()
                    output["name"] = output_name
                    output["data"] = base64.b64encode(data).decode()
                    output["method"] = "b64data"

        return output

    def get_log_lines(self):
        """
        This function returns the log lines of the computation container
        to the asset owner, so that any errors can be debugged.
        """
        return self._log_lines

    def get_status(self):
        """
        Retrieve the status of the request's computation.
        """
        self._check_status()

        return self._status

    def get_service_result(self):
        """
        Returns the content of the service result with the hashes
        of PCC, inputs and outputs, and energy usage.
        """
        content = {}
        self._check_status()

        if self._status == "FINISHED":
            content["hashes"] = self._hashes
            content["certificates"] = self._certificates
            content["timestamp"] = time.time()
            for tracker_name in self._tracker_names:
                total_power_usage = 0.0
                for stage_name in self._power_usage[tracker_name]:
                    total_power_usage += self._power_usage[tracker_name][stage_name]
                self._power_usage[tracker_name]["99_total_power_usage_KWh"] = total_power_usage
            content["power_usage"] = self._power_usage

        return content
