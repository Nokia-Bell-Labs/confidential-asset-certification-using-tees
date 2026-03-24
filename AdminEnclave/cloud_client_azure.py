# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import base64
import json

from azure.identity import ManagedIdentityCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient

try:
    from .cloud_client import CloudClient
    from .cvm import ConfidentialVM
except Exception as _:
    from cloud_client import CloudClient
    from cvm import ConfidentialVM

class AzureClient(CloudClient):
    """
    The cloud client class that interacts with Microsoft Azure.
    """
    def __init__(self, config, ip_address, logger):
        super().__init__(config, ip_address, logger)

        self._credential = ManagedIdentityCredential(client_id=self._config["managed_identity_client_id"])
        self._network_client = NetworkManagementClient(self._credential, self._config["subscription_id"])
        self._compute_client = ComputeManagementClient(self._credential, self._config["subscription_id"])

    def _setup_vnet(self):
        """
        This function sets up a virtual network for the confidential VM in the service owner's
        resource group.
        """
        resource_group_name = self._config["resource_group_name"]
        vnet_name = self._config["vnet_name"]
        location = self._config["location"]

        poller = self._network_client.virtual_networks.begin_create_or_update(
            resource_group_name,
            vnet_name,
            {
                "location": location,
                "address_space": {"address_prefixes": ["10.0.0.0/16"]}
            }
        )

        vnet_result = poller.result()

        return vnet_result

    def _setup_subnet(self):
        """
        This function sets up a subnet for the confidential VM in the service owner's
        resource group.
        """
        resource_group_name = self._config["resource_group_name"]
        vnet_name = self._config["vnet_name"]
        subnet_name = self._config["subnet_name"]

        poller = self._network_client.subnets.begin_create_or_update(
            resource_group_name,
            vnet_name,
            subnet_name,
            {
                "address_prefix": "10.0.0.0/24"
            },
        )

        subnet_result = poller.result()

        return subnet_result

    def _setup_ip(self):
        """
        This function sets up an IP address for the confidential VM in the service owner's
        resource group.
        """
        resource_group_name = self._config["resource_group_name"]
        ip_name = self._config["ip_name"]
        location = self._config["location"]

        poller = self._network_client.public_ip_addresses.begin_create_or_update(
            resource_group_name,
            ip_name,
            {
                "location": location,
                "sku": {"name": "Standard"},
                "public_ip_allocation_method": "Static",
                "public_ip_address_version": "IPV4",
            },
        )

        ip_address_result = poller.result()
        self._logger.info(f"Provisioned public IP address {ip_address_result.name} with address {ip_address_result.ip_address}")

        return ip_address_result

    def _setup_nsg(self):
        """
        This function sets up a network security group for the confidential VM in the service owner's
        resource group.
        """
        resource_group_name = self._config["resource_group_name"]
        nsg_name = self._config["nsg_name"]
        location = self._config["location"]

        poller = self._network_client.network_security_groups.begin_create_or_update(
            resource_group_name,
            nsg_name,
            {
                "location": location,
            },
        )

        nsg_result = poller.result()
        self._logger.info(f"Provisioned network security group {nsg_result.name}")

        return nsg_result

    def _setup_nic(self, subnet_id, ip_id, nsg_id):
        """
        This function sets up a network interface card for the confidential VM in the service owner's
        resource group.
        """
        resource_group_name = self._config["resource_group_name"]
        nic_name = self._config["nic_name"]
        location = self._config["location"]
        ip_config_name = self._config["ip_config_name"]

        poller = self._network_client.network_interfaces.begin_create_or_update(
            resource_group_name,
            nic_name,
            {
                "location": location,
                "ip_configurations": [
                    {
                        "name": ip_config_name,
                        "subnet": {"id": subnet_id},
                        "public_ip_address": {"id": ip_id},
                    }
                ],
                "network_security_group": {
                    "id": nsg_id
                }
            }
        )

        nic_result = poller.result()
        self._logger.info(f"Provisioned network interface client {nic_result.name}")

        return nic_result

    def _setup_nsg_rule(self, dest_port, source_ip, priority):
        """
        This function sets up a firewall rule for the confidential VM in the service owner's
        resource group.
        """
        resource_group_name = self._config["resource_group_name"]
        nsg_name = self._config["nsg_name"]

        poller = self._network_client.security_rules.begin_create_or_update(
            resource_group_name,
            nsg_name,
            security_rule_name="allow-" + str(dest_port),
            security_rule_parameters={
                "properties": {
                    "access": "Allow",
                    "destinationAddressPrefix": "10.0.0.0/24",
                    "destinationPortRange": str(dest_port),
                    "direction": "Inbound",
                    "priority": priority,
                    "protocol": "*",
                    "sourceAddressPrefix": source_ip,
                    "sourcePortRange": "*",
                }
            },
        )

        nsg_rule_result = poller.result()

        return nsg_rule_result

    def _provision_cvm(self, serialized_public_key, nic_id):
        """
        This function provisions the confidential VM in the service owner's
        resource group.
        """
        resource_group_name = self._config["resource_group_name"]
        location = self._config["location"]
        vm_size = self._config["vm_size"]
        vm_name = self._config["vm_name"]
        vm_username = self._config["vm_username"]
        vm_image_tokens = self._config["vm_image_tokens"]

        parameters={
            "location": location,
            "properties": {
                "hardwareProfile": {
                    "vmSize": vm_size
                    },
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "id": nic_id,
                            "properties": {"primary": True},
                        }
                    ]
                },
                "osProfile": {
                    "adminUsername": vm_username,
                        "computerName": vm_name,
                        "linuxConfiguration": {
                            "disablePasswordAuthentication": True,
                            "ssh": {
                                "publicKeys": [
                                    {
                                        "keyData": serialized_public_key,
                                        "path": "/home/" + vm_username + "/.ssh/authorized_keys",
                                    }
                                ]
                            },
                        },
                    }
                },
                "securityProfile": {
                    "encryptionAtHost": True,
                    "securityType": "ConfidentialVM",
                    "uefiSettings": {
                        "secureBootEnabled": True,
                        "vTpmEnabled": True
                        },
                },
                "storageProfile": {
                    "imageReference": {
                        "publisher": vm_image_tokens[0],
                        "offer": vm_image_tokens[1],
                        "sku": vm_image_tokens[2],
                        "version": vm_image_tokens[3],
                    },
                    "osDisk": {
                        "createOption": "FromImage",
                        "diskSizeGB": 1024,
                        "caching": "ReadWrite",
                        "deleteOption": "Delete",
                        "managedDisk": {
                            "securityProfile": {
                                "securityEncryptionType": "DiskWithVMGuestState",
                            },
                            "storageAccountType": "StandardSSD_LRS",
                        },
                    },
                },
            }
        poller = self._compute_client.virtual_machines.begin_create_or_update(
            resource_group_name,
            vm_name,
            parameters
        )

        vm_result = poller.result()

        return vm_result

    def provision_resources(self, serialized_public_key):
        """
        This function provisions all necessary resources for a confidential VM in the service owner's
        resource group.
        """
        # Step 1: Provision the virtual network
        # If the virtual network already exists, it's fine.
        try:
            vnet_result = self._setup_vnet()
            self._logger.info(f"Provisioned virtual network {vnet_result.name} with address prefix {vnet_result.address_space.address_prefixes}")
        except Exception as _:
            pass

        # Step 2: Provision the subnet
        subnet_result = self._setup_subnet()
        self._logger.info(f"Provisioned virtual subnet {subnet_result.name} with address prefix {subnet_result.address_prefix}")

        # Step 3: Provision an IP address
        ip_address_result = self._setup_ip()

        ip_id = ip_address_result.id
        ip_address = ip_address_result.ip_address

        subnet_id = subnet_result.id

        # Step 4: Provision the network security group
        nsg_result = self._setup_nsg()
        nsg_id = nsg_result.id

        # Step 5: Provision the network interface client
        nic_result = self._setup_nic(subnet_id, ip_id, nsg_id)
        nic_id = nic_result.id

        # Step 6: Allow only controller IP address for ssh and service
        nsg_rule_result = self._setup_nsg_rule(22, self._ip_address, 300)
        self._logger.info(f"Set up network security group rule: {nsg_rule_result.name}.")
        nsg_rule_result2 = self._setup_nsg_rule(6038, self._ip_address, 301)
        self._logger.info(f"Set up network security group rule: {nsg_rule_result2.name}.")

        # Step 7: Provision the virtual machine
        vm_result = self._provision_cvm(serialized_public_key, nic_id)
        vm_username = self._config["vm_username"]
        self._logger.info(f"Provisioned virtual machine {vm_result.name} with username {vm_username}")

        cvm = ConfidentialVM(self._config, ip_address, serialized_public_key, self._logger)

        return cvm

    def delete_resources(self):
        """
        This function deletes a provisioned confidential VM and its resources in the service owner's
        resource group.
        """
        resource_group_name = self._config["resource_group_name"]
        vm_name = self._config["vm_name"]
        nic_name = self._config["nic_name"]
        ip_name = self._config["ip_name"]
        nsg_name = self._config["nsg_name"]

        self._logger.info(f"Deleting the VM: {vm_name}")
        self._compute_client.virtual_machines.begin_delete(resource_group_name, vm_name).result()

        self._logger.info(f"Deleting NIC: {nic_name}")
        self._network_client.network_interfaces.begin_delete(resource_group_name, nic_name).wait()

        self._logger.info(f"Deleting the IP: {ip_name}")
        self._network_client.public_ip_addresses.begin_delete(resource_group_name, ip_name)

        self._logger.info(f"Deleting the NSG: {nsg_name}")
        self._network_client.network_security_groups.begin_delete(resource_group_name, nsg_name).wait()

    def check_attestation(self, attestation_token_filename, nonce_filename):
        """
        This function checks the attestation report of the provisioned confidential VM
        with the random nonce that the duet controller generated when provisioning the
        confidential VM.
        """
        # TODO: improve the check of the attestation report of the CVM
        with open(attestation_token_filename, "r") as f_attestation_filename:
            report = f_attestation_filename.read()

        attestation_fields = report.split(".")

        while len(attestation_fields[0]) % 4 != 0:
            attestation_fields[0] += "="

        while len(attestation_fields[1]) % 4 != 0:
            attestation_fields[1] += "="

        field_0 = base64.b64decode(attestation_fields[0]).decode()
        field_0 = json.loads(field_0)

        field_1 = base64.b64decode(attestation_fields[1]).decode()
        field_1 = json.loads(field_1)

        try:
            assert "x-ms-isolation-tee" in field_1
            report_isolation_info = field_1["x-ms-isolation-tee"]
            assert "x-ms-attestation-type" in report_isolation_info
            assert report_isolation_info["x-ms-attestation-type"] == "sevsnpvm"
            assert "x-ms-runtime" in report_isolation_info and "vm-configuration" in report_isolation_info["x-ms-runtime"] and "secure-boot" in report_isolation_info["x-ms-runtime"]["vm-configuration"] and "tpm-enabled" in report_isolation_info["x-ms-runtime"]["vm-configuration"]
            assert report_isolation_info["x-ms-runtime"]["vm-configuration"]["secure-boot"]
            assert report_isolation_info["x-ms-runtime"]["vm-configuration"]["tpm-enabled"]
        except Exception as _:
            return False, None

        with open(nonce_filename, "r") as f_nonce:
            nonce = f_nonce.read()

        try:
            assert "x-ms-runtime" in field_1 and "client-payload" in field_1["x-ms-runtime"] and "nonce" in field_1["x-ms-runtime"]["client-payload"]
            report_nonce = base64.b64decode(field_1["x-ms-runtime"]["client-payload"]["nonce"]).decode()
            assert report_nonce == nonce
        except Exception as _:
            return False, None

        return True, {"field_0": field_0, "field_1": field_1}

    def _check_h100_attestation(self, h100_attestation_filename):
        """
        This function checks the NVIDIA H100 GPU's attestation report that is provisioned in the
        confidential VM.
        """
        # TODO: better check
        with open(h100_attestation_filename, "r", encoding="utf-8") as f_h100_attestation:
            report = f_h100_attestation.read()

        lines = report.split("\n")
        non_empty_lines = []
        for line in lines:
            line = line.strip()
            if line == "":
                continue
            non_empty_lines.append(line)

        last_3_lines = non_empty_lines[-3:]
        expected_last_3_lines = ["SecureBoot enabled", "CC status: ON", "CC Environment: PRODUCTION"]
        try:
            assert last_3_lines[-3:] == expected_last_3_lines
        except Exception as _:
            return False, None

        non_empty_lines = non_empty_lines[:-3]

        info_lines = []
        start_collecting = False
        for line in non_empty_lines:
            if start_collecting:
                info_lines.append(line)
            if line == "Entity Attestation Token:":
                start_collecting = True

        if not start_collecting:
            return False, None

        info_txt = "".join(info_lines)
        info = json.loads(info_txt)
        cgpu_info = {info[0][0]: info[0][1]}
        cgpu_info["GPU"] = info[1]

        return True, cgpu_info

    def check_gpu_attestation(self, gpu_attestation_filename):
        """
        This function checks the GPU TEE's attestation report that is provisioned in the
        confidential VM.
        """
        return self._check_h100_attestation(gpu_attestation_filename)
