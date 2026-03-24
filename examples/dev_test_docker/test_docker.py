# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
import pathlib
import os
import shutil
import subprocess
import sys
import tarfile
import time

import docker

import requests

from hf_utils import get_repo_urls

client = docker.DockerClient(base_url='unix://var/run/docker.sock')

HTTP_PROXY = os.getenv("http_proxy", "")
print(HTTP_PROXY)

def build_image2(filename, tag, code_build_args):
    code_build_args["http_proxy"] = HTTP_PROXY
    docker_api_client = docker.APIClient(base_url='unix://var/run/docker.sock')

    with open(filename, "rb") as f:
        build_log = docker_api_client.build(fileobj=f, custom_context=True, decode=True, tag=tag, buildargs=code_build_args)
        for output in build_log:
            if "stream" in output:
                lines = output["stream"].split("\n")
                for line in lines:
                    if line != "":
                        print(line)

        docker_api_client.close()
    #     client.images.build(fileobj=f, custom_context=True, tag=tag, buildargs={"http_proxy": HTTP_PROXY})

def download_file(url, local_filename, headers={}, params={}):
    if not os.path.exists(local_filename):
        with requests.get(url, params, headers=headers, stream=True) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
    return local_filename

def prepare_folders(folders):
    for f in folders:
        folder_path = folders[f]
        # only remove the outputs; use inputs as if it is like a cache
        if f == "outputs" and os.path.exists(folder_path):
            shutil.rmtree(folder_path, ignore_errors=True)
        os.makedirs(folder_path, exist_ok=True)


def prepare_inputs(cert_config, relative_folder, container_inputs_folder):
    for cert_input in cert_config["inputs"]:
        if "upload_method" not in cert_input or\
            not cert_input["upload_method"] or\
            cert_input["upload_method"] not in ["direct", "hf_url", "hf_cache", "url"]:
            print("-- Ignoring input due to missing upload method.")
            continue

        upload_method = cert_input["upload_method"]
        if upload_method == "direct":
            if "input_folder" not in cert_input or\
                not cert_input["input_folder"] or\
                cert_input["input_folder"] == "":
                continue
            input_folder = relative_folder + cert_input["input_folder"]
            # upload the necessary input files
            print(f"-- Copying necessary input files from folder: {input_folder}")
            input_path = pathlib.Path(input_folder)
            input_files = [str(file) for file in list(input_path.rglob("*")) if file.is_file()]
            for fname in input_files:
                base_fname = fname[len(input_folder):]
                
                if not input_folder.endswith("/"):
                    base_fname = base_fname[1:]

                print("--- Copying input: " + fname + " " + base_fname)
                if base_fname.rfind("/") != -1:
                    base_folder = base_fname[:base_fname.rfind("/")]
                    os.makedirs(container_inputs_folder + "/" + base_folder, exist_ok=True)

                shutil.copyfile(fname, container_inputs_folder + "/" + base_fname)

        elif upload_method in ["hf_url", "hf_cache"]:
            assert "asset_id" in cert_input and cert_input["asset_id"] and cert_input["asset_id"] != ""
            assert "asset_type" in cert_input and cert_input["asset_type"] in ["dataset", "model"]

            asset_id = cert_input["asset_id"]
            asset_type = cert_input["asset_type"]

            print(f"Handling {asset_type}: {asset_id}")

            input_filter_filename = None
            filters = []
            if "input_filter_filename" in cert_input and\
                cert_input["input_filter_filename"] != "":
                input_filter_filename = relative_folder + cert_input["input_filter_filename"]

                with open(input_filter_filename, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line == "" or line.startswith("#"):
                            continue
                        filters.append(line)
                    print("-- Using prefix filters: " + json.dumps(filters, indent=4))

            if upload_method == "hf_url":
                asset_urls = get_repo_urls(asset_id, asset_type, filters)
                for url in asset_urls:
                    base_fname = url["rfilename"]
                    asset_url = url["asset_url"]

                    if "local_folder" in cert_input and cert_input["local_folder"]:
                        local_folder = relative_folder + cert_input["local_folder"]
                    else:
                        local_folder = asset_id

                    local_name = local_folder + "/" + base_fname

                    print("-- Downloading input: " + asset_url + " " + local_name)
                    if local_name.rfind("/") != -1:
                        base_folder = local_name[:local_name.rfind("/")]
                        os.makedirs(container_inputs_folder + "/" + base_folder, exist_ok=True)

                    headers = {}
                    if "token_path" in cert_input:
                        with open(relative_folder + cert_input["token_path"], "r") as f:
                            token = f.read().strip()
                        headers = {"Authorization": "Bearer " + token}
                    download_file(asset_url, container_inputs_folder + "/" + local_name, headers=headers)

            elif upload_method == "hf_cache":
                base_cache_dir = container_inputs_folder + "/HF_CACHE"
                os.makedirs(base_cache_dir, exist_ok=True)

                my_env = os.environ.copy()
                my_env["HF_HOME"] = base_cache_dir
                if "token_path" in cert_input:
                    token_path = relative_folder + cert_input["token_path"]
                    my_env["HF_TOKEN_PATH"] = token_path
                
                if asset_type == "dataset":
                    if "configs" in cert_input:
                        my_env["DATASET_CONFIGS"] = ",".join(cert_input["configs"])

                    command = [
                        "python3", 
                        "hf_download_dataset.py",
                        asset_id
                    ]
                elif asset_type == "model":
                    command = [
                        "huggingface-cli",
                        "download",
                        "--repo-type", "model",
                        asset_id
                    ]

                # Execute the command
                subprocess.run(command, env=my_env, check=True)

            print("="*10)

        elif upload_method == "url":
            asset_url = cert_input["asset_url"]
            asset_id = cert_input["asset_id"]
            
            base_fname = asset_url[asset_url.rfind("/")+1:]
            
            if "local_folder" in cert_input and cert_input["local_folder"]:
                local_folder = relative_folder + cert_input["local_folder"]
            else:
                local_folder = asset_id

            local_name = local_folder + "/" + base_fname

            print("-- Downloading input: " + asset_url + " " + local_name)
            if local_name.rfind("/") != -1:
                base_folder = local_name[:local_name.rfind("/")]
                os.makedirs(container_inputs_folder + "/" + base_folder, exist_ok=True)

            headers = {}
            if "token_path" in cert_input:
                with open(relative_folder + cert_input["token_path"], "r") as f:
                    token = f.read().strip()
                headers = {"Authorization": "Bearer " + token}
            download_file(asset_url, container_inputs_folder + "/" + local_name, headers=headers)

def reset(tarinfo):
    tarinfo.mode = 0o644
    tarinfo.uid = tarinfo.gid = 0
    tarinfo.uname = tarinfo.gname = "root"
    tarinfo.mtime = 1
    return tarinfo

def prepare_container(code_folder, tag, code_build_args):
    print(code_folder)
    
    code_path = pathlib.Path(code_folder)
    code_files = [str(file) for file in list(code_path.rglob("*"))]
    code_files = sorted(code_files)

    code_filename = "test_temp/docker_test_code.tar"
    with tarfile.open(code_filename, "w", dereference=True) as tar:
        for fname in code_files:
            print("--- Adding file: " + fname + " " + fname[len(code_folder):])
            tar.add(fname, fname[len(code_folder):], filter=reset)
    tar.close()
    build_image2(code_filename, tag, code_build_args)

def run_container(container_folders, tag):
    try:
        container = client.containers.get(tag)
        container.remove()
    except Exception as exc:
        pass

    volume_map = {}
    volume_map[container_folders["inputs"]] = {"bind": "/tmp/inputs", "mode": "rw"}
    volume_map[container_folders["outputs"]] = {"bind": "/tmp/outputs", "mode": "rw"}
    print(volume_map)

    client.containers.run(tag, detach=True, name=tag, volumes=volume_map, network_disabled=True)

def build_and_run(cert_config, relative_folder):
    assert "name" in cert_config and cert_config["name"] and cert_config["name"] != ""
    assert "code_folder" in cert_config and cert_config["code_folder"] and cert_config["code_folder"] != ""

    code_build_args = {}
    code_build_args["http_proxy"] = HTTP_PROXY
    if "code_build_args" in cert_config:
        code_build_args.update(cert_config["code_build_args"])

    container_folders = {}
    container_folders["inputs"] = os.getcwd() + "/test_temp/tmp/inputs"
    container_folders["outputs"] = os.getcwd() + "/test_temp/tmp/outputs"

    prepare_folders(container_folders)

    prepare_inputs(cert_config, relative_folder, container_folders["inputs"])

    tag = "test-" + cert_config["name"]
    tag = tag.replace("/", "-").replace("_", "-").replace(" ", "-")
    tag = tag.lower()

    code_folder = relative_folder + cert_config["code_folder"]
    prepare_container(code_folder, tag, code_build_args)

    run_container(container_folders, tag)

    while True:
        container = client.containers.get(tag)
        status = container.status
        print(str(time.time()) + " " + status)
        time.sleep(2.0)
        if status == "exited":
            for line in container.logs(stream=True):
                print(line.decode().strip("\n"))
            break

def main(config_filename):
    relative_folder = "./"
    if config_filename.rfind("/") != -1:
        relative_folder = config_filename[:config_filename.rfind("/")+1]
    print(relative_folder)

    with open(config_filename, "r") as f:
        cert_config = json.load(f)

    print(json.dumps(cert_config, indent=4))
    build_and_run(cert_config, relative_folder)

if __name__ == "__main__":
    len_args = len(sys.argv)
    if len_args == 2:
        config_filename = sys.argv[1]
        main(config_filename)
