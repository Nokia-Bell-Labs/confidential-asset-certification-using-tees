# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
import logging
import os
import pathlib
import sys
import time

from cryptography.hazmat.primitives import hashes

import requests

# import sdk client and set up other utils
try:
    from .archive_utils import create_archive, compute_hash
    from .asset_certification_client.duet_asset_certification_client import DuetAssetCertificationServiceClient
    from .hf_utils import get_repo_urls
except Exception as _:
    from archive_utils import create_archive, compute_hash
    from asset_certification_client.duet_asset_certification_client import DuetAssetCertificationServiceClient
    from hf_utils import get_repo_urls

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

# Retrieve a file from a URL
def download_file(url, local_filename, headers={}):
    with requests.get(url, headers=headers, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_filename

def setup_folders(input_folder):
    # setup local folders as working space
    test_results_folder = "test_results/certifications/" + input_folder + "/"
    os.makedirs(test_results_folder, exist_ok=True)

    test_temp_folder = "test_temp/certifications/" + input_folder + "/"
    os.makedirs(test_temp_folder, exist_ok=True)

    return test_results_folder, test_temp_folder

def setup_certification_client(controller_url, expected_mrenclave, expected_service_info):
    # get a new client for our certification service
    # we use the duet controller as a name service, load balancer and root of trust
    log.info("Setting up duet controller interaction...")
    log.info("Obtaining and verifying the state of the duet admin...")
    client = DuetAssetCertificationServiceClient(controller_url, ATTESTATION_SERVICE_URL, expected_mrenclave, expected_service_info)

    return client

def start_certification_and_wait(client):
    """
    This functions starts the computation of the certification request
    and waits until it's finished.
    """
    log.info("-- Preparing the computation...")
    client.prepare()
    
    log.info("-- Waiting until preparation finishes...")
    success = True
    while True:
        status = client.get_status()
        log.info(status)
        if status["status"] == "READY":
            break
        elif status["status"].startswith("ERROR_"):
            success = False
            break
        time.sleep(5.0)

    if success:
        log.info("-- Starting certification computation...")
        client.start()

        log.info("-- Waiting until computation finishes...")
        while True:
            status = client.get_status()
            log.info(status)
            if status["status"] == "FINISHED":
                break
            time.sleep(5.0)

    return success

def upload_computation_code(client, code_folder, test_temp_folder, code_build_args):
    """
    This function archives and uploads the computation code for the certification request.
    """
    # upload the necessary computation code
    log.info("-- Creating the computation code archive...")
    log.info(code_folder)

    # archive the service code
    code_buffer = create_archive(code_folder)

    log.info("-- Uploading the computation code archive...")
    code_data = code_buffer.getvalue()
    print("Property computation code hash: " + compute_hash(code_data))
    client.upload("code", "code.tar", "b64data", code_data, code_build_args=code_build_args)

def get_certification_result(client, test_results_folder):
    """
    This function retrieves the asset certificate as well as the outputs
    produced by the computation.
    The outputs are referred to in the asset certificate.
    """
    # get and store the certification for the computation
    log.info("-- Obtaining the certification result...")
    resp = client.get_result()

    log.info("-- Storing the asset certificate...")
    asset_certificate = client.get_asset_certificate()

    with open(test_results_folder + "asset_certificate.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(asset_certificate, indent=4))

    # download the computation results referenced in the certificate
    log.info("-- Obtaining the computation outputs referred in the asset certificate...")
    output_map = resp["duet_service_result"]["service_result"]["hashes"]["outputs"]
    for output_name in output_map:
        log.info("--- Downloading and storing: " + output_name)
        output = client.download(output_name)
        output_filename = test_results_folder + output_name
        output_folder = output_filename[:output_filename.rfind("/")]
        os.makedirs(output_folder, exist_ok=True)
        with open(test_results_folder + output_name, "wb") as f:
            f.write(output)

def certify_one_asset(client, cert_config, relative_folder, test_temp_folder, test_results_folder):
    """
    This function sets up a certification request, starts the computation and retrieves
    the certificate and the results.
    """
    assert "name" in cert_config and cert_config["name"] and cert_config["name"] != ""
    assert "code_folder" in cert_config and cert_config["code_folder"] and cert_config["code_folder"] != ""

    # new certification request
    while True:
        log.info("Creating a certification request for: " + cert_config["name"])
        try:
            req = client.create_certification_request()
        except Exception as exc:
            print(exc)
            time.sleep(30)
            continue

        log.info("Certification request: " + json.dumps(req, indent=4))
        break

    # For each input for the certification, prepare and upload the necessary files
    for cert_input in cert_config["inputs"]:
        if "upload_method" not in cert_input or\
            not cert_input["upload_method"] or\
            cert_input["upload_method"] not in ["direct", "hf_url", "hf_cache", "url"]:
            log.info("-- Ignoring input due to missing upload method.")
            continue

        upload_method = cert_input["upload_method"]
        # If it is direct, the files will be read from local storage and uploaded directly
        # using b64 encoding
        if upload_method == "direct":
            if "input_folder" not in cert_input or\
                not cert_input["input_folder"] or\
                cert_input["input_folder"] == "":
                continue
            input_folder = relative_folder + cert_input["input_folder"]
            # upload the necessary input files
            log.info("-- Uploading necessary input files...")
            input_path = pathlib.Path(input_folder)
            input_files = [str(file) for file in list(input_path.rglob("*")) if file.is_file()]
            for fname in input_files:
                base_fname = fname[len(input_folder):]

                if not input_folder.endswith("/"):
                    base_fname = base_fname[1:]

                log.info("--- Uploading input: " + fname + " " + base_fname)
                with open(fname, "rb") as f:
                    data = f.read()
                    if base_fname.find("_asset_certificate.json") != -1:
                        associated_input_name = base_fname[:base_fname.find("_asset_certificate.json")]
                        resp = client.upload("certificates", base_fname, "b64data", data, associated_input_name=associated_input_name)
                    else:
                        resp = client.upload("inputs", base_fname, "b64data", data)
                    log.info(resp)

        # If the input files come from HuggingFace repos
        elif upload_method in ["hf_url", "hf_cache"]:
            assert "asset_id" in cert_input and cert_input["asset_id"] and cert_input["asset_id"] != ""
            assert "asset_type" in cert_input and cert_input["asset_type"] in ["dataset", "model"]
            asset_id = cert_input["asset_id"]
            asset_type = cert_input["asset_type"]

            # Some repos are just too large,
            # or we are interested in certain files from the repo.
            # We can use prefix filter to only use those files
            # One prefix per line
            input_filter_filename = None
            filters = []
            if "input_filter_filename" in cert_input and\
                cert_input["input_filter_filename"] != "":
                input_filter_filename = relative_folder + cert_input["input_filter_filename"]

                with open(input_filter_filename, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line == "" or line.startswith("#"):
                            continue
                        filters.append(line)
                    print("-- Using prefix filters: " + json.dumps(filters, indent=4))

            # If the repo is publicly accessible, we can just obtain the input file's URL
            # and upload it as a URL
            if upload_method == "hf_url":
                asset_urls = get_repo_urls(asset_id, asset_type, filters)
                i = 0
                for url in asset_urls:
                    i += 1
                    print(url, i, len(asset_urls), float(i)/float(len(asset_urls)))
                    base_fname = url["rfilename"]
                    asset_url = url["asset_url"]

                    if "local_folder" in cert_input and cert_input["local_folder"]:
                        local_folder = relative_folder + cert_input["local_folder"]
                    else:
                        local_folder = asset_id

                    local_name = local_folder + "/" + base_fname

                    # Some repos require accepted terms & conditions.
                    # One can do so by manually accepting them via HuggingFace website.
                    # Afterwards a HuggingFace token can be utilized to access the files.
                    # Note that the duet controller runs in an SGX enclave
                    # (and the certificate service runs in a CVM)
                    # The upload of this token happens *after* the duet controller's
                    # quote verification.
                    # (The controller does the attestation for the CVM.)
                    if "token_path" in cert_input:
                        token_path = relative_folder + cert_input["token_path"]
                        with open(token_path, "r", encoding="utf-8") as f:
                            token = f.read().strip()
                        headers = {"Authorization": "Bearer " + token}

                        if base_fname.rfind("/") != -1:
                            base_folder = base_fname[:base_fname.rfind("/")]
                            os.makedirs(test_temp_folder + "/" + base_folder, exist_ok=True)

                        download_file(asset_url, test_temp_folder + "/" + base_fname, headers=headers)

                        with open(test_temp_folder + "/" + base_fname, "rb") as f:
                            data = f.read()

                        log.info(base_fname + " switching to direct upload due to authorization requirements")
                        resp = client.upload("inputs", base_fname, "b64data", data)

                    else:
                        # We need to ensure that the hash value of the URL corresponds
                        # to the file we want from the URL
                        if "sha256" in url:
                            hash_value = url["sha256"]
                        else:
                            if base_fname.rfind("/") != -1:
                                base_folder = base_fname[:base_fname.rfind("/")]
                                os.makedirs(test_temp_folder + "/" + base_folder, exist_ok=True)

                            download_file(asset_url, test_temp_folder + "/" + base_fname)

                            with open(test_temp_folder + "/" + base_fname, "rb") as f:
                                data = f.read()

                                hash_object = hashes.Hash(hashes.SHA256())
                                hash_object.update(data)
                                hash_value = hash_object.finalize().hex()

                        log.info(base_fname + " asset_url: " + url["asset_url"])
                        resp = client.upload("inputs", local_name, "url", asset_url, hash_value=hash_value)

            # For certain HuggingFace repos, the computation code uses libraries
            # that do not allow access to input files directly.
            # We can utilize the HuggingFace's cache option for using such code.
            elif upload_method == "hf_cache":
                print("-- Providing input as hf_cache... " + cert_input["asset_id"] + " " + cert_input["asset_type"])
                if "token_path" in cert_input:
                    token_path = relative_folder + cert_input["token_path"]
                    with open(token_path, "r", encoding="utf-8") as f:
                        hf_token = f.read()
                        cert_input["hf_token"] = hf_token
                        del cert_input["token_path"]
                    del cert_input["upload_method"]

                resp = client.upload("inputs", "HF_CACHE" + cert_input["asset_id"], "hf_cache", cert_input)

        # If the input files are provided as inputs directly accessible via a URL
        elif upload_method == "url":
            assert "asset_id" in cert_input and cert_input["asset_id"] and cert_input["asset_id"] != ""
            assert "sha256" in cert_input
            assert "asset_url" in cert_input

            asset_id = cert_input["asset_id"]
            hash_value = cert_input["sha256"]
            asset_url = cert_input["asset_url"]

            if "local_folder" in cert_input and cert_input["local_folder"]:
                local_folder = relative_folder + cert_input["local_folder"]
            else:
                local_folder = asset_id

            base_fname = asset_url[asset_url.rfind("/")+1:]

            local_name = local_folder + "/" + base_fname

            log.info(base_fname + " asset_url: " + asset_url)
            resp = client.upload("inputs", local_name, "url", asset_url, hash_value=hash_value)

    # upload computation code
    code_folder = relative_folder + cert_config["code_folder"]
    code_build_args = {}
    if "code_build_args" in cert_config and cert_config["code_build_args"]:
        code_build_args = cert_config["code_build_args"]
    upload_computation_code(client, code_folder, test_temp_folder, code_build_args)

    # start certification
    success = start_certification_and_wait(client)

    if success:
        # get the result when the computation is finished
        get_certification_result(client, test_results_folder)
    else:
        log.info("Error in certification.")

def main(config_filename):
    """
    This function first sets up the necessary folders as temporary working space
    as well as for the certification results.
    """
    t_start = time.time()

    relative_folder = "./"
    if config_filename.rfind("/") != -1:
        relative_folder = config_filename[:config_filename.rfind("/")+1]
    log.info(relative_folder)

    with open(config_filename, "r", encoding="utf-8") as f:
        cert_config = json.load(f)

    print(cert_config)

    # setup local folder for results
    test_results_folder, test_temp_folder = setup_folders(cert_config["name"])

    # setup the certification client
    client = setup_certification_client(DUET_ADMIN_URL, EXPECTED_DUET_ADMIN_MRENCLAVE, EXPECTED_DUET_SERVICE_INFO)

    certify_one_asset(client, cert_config, relative_folder, test_temp_folder, test_results_folder)

    log.info("="*50)

    t_total = time.time() - t_start

    print("Total time (s): " + str(t_total))

def usage():
    print("Usage: python3 test_asset_certification.py <cert_config_filename>")

if __name__ == "__main__":
    if len(sys.argv) == 2:
        config_fname = sys.argv[1]
        main(config_fname)
    else:
        usage()
