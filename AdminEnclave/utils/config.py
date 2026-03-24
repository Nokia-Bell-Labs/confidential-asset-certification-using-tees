# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
import random

def extend_configuration(config, cvm_type, cvm_num_cpus):
    if config["cloud_provider"] == "azure":
        config["vm_image_tokens"] = config["vm_image"].split(":")

        config["cvm_type"] = cvm_type
        if cvm_type == "snp-h100":
            config["vm_size"] = "Standard_NCC40ads_H100_v5"
        else:
            config["vm_size"] = "Standard_DC" + str(cvm_num_cpus)
            if cvm_type == "snp":
                config["vm_size"] += "a"
            config["vm_size"] += "ds_v5"

        config["vm_name"] = config["prefix"] + "-cvm-" + cvm_type + "-" + str(random.randint(1000, 3000))

        vm_name = config["vm_name"]
        config["nsg_name"] = vm_name + "-nsg"
        config["nic_name"] = vm_name + "-nic"
        config["ip_name"] = vm_name + "-ip"
        config["ip_config_name"] = vm_name + "-ip-config"
    
    else:
        print("[ERROR] Other cloud providers are not supported yet.")

    return config

def check_missing_parameters(params, required_params, empty_ok=True):
    for param in required_params:
        if param not in params:
            print("[ERROR] missing config parameter: " + param)
            return False
        elif not empty_ok:
            if params[param] is None or params[param] == "":
                print("[ERROR] empty config parameter: " + param)
                return False

    return True

def check_azure_configuration(config):
    required_params = ["subscription_id", "managed_identity_client_id", "location", "resource_group_name", "vnet_name", "subnet_name", "prefix", "vm_image"]
    return check_missing_parameters(config, required_params, empty_ok=False)

def load_configuration(config_filename):
    config = {}
    with open(config_filename, "r") as f:
        config = json.load(f)
    
    required_params = ["cloud_provider"]
    if not check_missing_parameters(config, required_params, empty_ok=False):
        return None
    
    if config["cloud_provider"] == "azure":
        if not check_azure_configuration(config):
            return None
    else:
        print("[ERROR] Other cloud providers are not supported yet.")
        return None
    
    return config

def read_commands_from_file(filename, vm_username):
    commands = []
    with open(filename, "r") as f:
        lines = f.readlines()
        for line in lines:
            line = line.strip()
            if line == "" or line.startswith("#"):
                continue
            line = line.replace("/home/duet/", "/home/" + vm_username + "/")
            commands.append(line)

    return commands

def load_expected_hashes(expected_hashes_filename):
    expected_hashes = {}
    with open(expected_hashes_filename, "r") as f:
        expected_hashes = json.load(f)
    
    return expected_hashes
