## Deployment

The Asset Certification Service (CACTEE) can be deployed on Azure.

### Pre-requisites

1. Create an SGX-capable VM in Azure: Ubuntu 22.04 LTS, Standard_DC2s_v3 (e.g., with name duet-vm) with username (e.g., `duet`)

2. The resource hosting the controller needs to have a role for creation of resources (i.e., Contributor).
In the below examples, the managed identity (i.e., test-man2) has Contributor role.

You can assign the role to the VM with Azure CLI (installable with `sudo apt install azure-cli` on your local machine) or over the web portal.

```
az vm identity assign --resource-group <your-resource-group-name> --name duet-vm --identities test-man2
```

You can check whether the VM has been correctly assigned the identity via:
```
az vm identity show --resource-group <your-resource-group-name> --name duet-vm
```

3. Then copy the repo to the VM and ssh into it.

4. The following script configures dependencies and installs necessary packages.

```
chmod +x install_vm_dependencies.sh
./install_vm_dependencies.sh
```
Note the above script adds the user `duet` to docker group. If you have a different username, please modify the script to match it.

### Setup

Some operations in the controller are privileged operations. They are only supposed to be invoked by the service owner. To authenticate the service owner, we use the service owner's public key and verify the signature on the operations requested by the client.

The service owner public key needs to be available to the controller. This public key is used to register a service in the controller.

To generate the public/private key and store it, do the following:

```
python3 generate_private_key.py
```

This will produce `service_owner_private_key` and `service_owner_public_key`.

When the client interacts with the controller for service deployment, it reads the private key, extracts the public key and sends it along with the registration request. Any subsequent requests requiring privileges (e.g., starting/stopping CVMs, deploying the service) are signed by the provider's private key and checked with the registered public key in the controller.

### Running with SGX

1. Build the gramine image that will help creating duet's controller in a graminized container.

```
make -C graminize gramine-image
```

2. Copy `AdminEnclave/azure_config.env.template` as `AdminEnclave/azure_config.env` and modify its contents to enter your Azure related information.

Note that any changes to this file will require re-building the controller docker image and the sub-sequent graminized version.

3. Then build the controller.

```
make -C AdminEnclave graminize
```

4. Afterwards, one can instantiate the controller as

```
make -C AdminEnclave run-sgx
```

5. Then, you can run deploy the asset certification service.

First, make sure that the requirements for the asset certification service SDK and test scripts are installed:

```
python3 -m pip install -r asset_certification_client/requirements.txt
python3 -m pip install -r requirements.txt
```

Second, make sure you have made a copy of `azure_config.json.template` as `azure_config.json`:

```
cp azure_config.json.template azure_config.json
```

Afterwards, fill out the details of your (i.e., CACTEE provider's) cloud configuration
in the `azure_config.json` file.
Supporting further cloud providers and local CVM deployments is future work.

Once you have done that, you can deploy the asset certification service as the service provider:

```
# first deploy at least one CVM backend; repeat if needed more
python3 test_duet_service_owner.py start-cvm snp-h100

# then start the service on those backends
python3 test_duet_service_owner.py start snp-h100
```

For ML model scenarios, it is suggested to use `snp-h100`. Other example scenarios can also be used with `snp`.

The controller, as it proxies requests to an available CVM, implements a simple sticky session approach
by letting the property computation service embed the handling CVM id into the responses.
The client then embeds the same CVM id in its requests, so that the requests belonging to the same certification
end up in the same backend CVM.

6. After the service is deployed, you can run an example script.

```
python3 test_asset_certification.py <example_config.json>
```

Once the request is finished, the asset certificate as well as any output files certified will be downloaded to `test_results/certifications/` folder.

7. Once the certificate has been downloaded, it can also be verified with the config
for finding relevant inputs, code and build args as well as the output folder
where the asset certificate and computation output is stored (e.g., `test_results/certifications/<example_name>` or `examples/certificates/<example_name>`).

```
python3 test_asset_certificate_verification.py <example_config.json> <output_folder>
```

8. Once you are done with generation of certificates, you can also shut down the service:

```
python3 test_duet_service_owner.py stop
```

This will stop the property computation service and the CVMs it was launched on.

One can also shut down individual CVMs by supplying its <cvm_id> that was returned when it was started.

```
python3 test_duet_service_owner.py stop-cvm <cvm_id>
```

### Troubleshooting

Currently, there is not much fault tolerance and error propagation. Please refer to the following steps for debugging any issues.

1. Sometimes, the managed identity is removed from the Azure VM. It is not clear why this happens.
As a result, the controller fails performing some provisioning operations for the CVM and throws an error.
Please retry the commands from the client side.

2. When there is an error at the client, the reason usually is an error not propagated from the server.
To see what went wrong, one can get the server logs via `docker logs duetadmin-enclave`, which usually contain the error message from Azure.

### Run direct mode

Alternatively, one can also run the controller without the SGX. This is useful for debugging/developing the controller code.
First, install the dependencies:

```
pip3 install -r AdminEnclave/requirements.txt
```

Then run the controller:

```
python3 -m AdminEnclave.admin -t direct
```

The client will work normally; however, it will print a warning message that the quote was not valid.

The controller will also dump the `ephemeral_private_key` used for ssh access to the CVM,
so that one can debug the property computation server that is deployed if necessary.

Note that during the SGX mode, this key is never exposed outside the enclave.

### Controller details for Azure

1. The controller provisions Azure resources to set up the CVM.

Currently, one can launch an AMD SEV-SNP or an AMD SEV-SNP machine with H100.

```
python3 test_duet_service_owner.py start-cvm snp
python3 test_duet_service_owner.py start-cvm snp-h100
```

2. For an SEV-SNP, the controller provisions a Standard_DC2ads_v5 machine with 32 vCPUs.
For an SEV-SNP with H100, the controller provisions a Standard_NCC40ads_H100_v5 with 40 vCPUs, which is fixed with this size.

Therefore, quotas in the resource group should be increased if necessary.

3. As a basis for the CVM, the standard Ubuntu 24.04 image designated for confidential computing is used ("Canonical:ubuntu-24_04-lts:cvm:latest" in [azure_config.json.template](azure_config.json.template)).

4. The controller launches the CVM with the following security profile (see `AzureClient:_provision_cvm() function in AdminEnclave/cloud_client_azure.py`):

```
"securityProfile": {
                    "encryptionAtHost": True,
                    "securityType": "ConfidentialVM",
                    "uefiSettings": {
                        "secureBootEnabled": True,
                        "vTpmEnabled": True
                        },
                },
```

For these reasons, the Azure environment needs to be configured to allow these requests.

5. The controller creates a separate virtual network and a default subnet in that virtual network for the CVM being launched.

6. Note that not all locations may have CVM-capable machines.
We tested the launch of the controller and the CVMs in location `westeurope`, in which both types of VMs were available.
It is also suggested to use the same location for the controller and the CVM (i.e., as defined in [azure_config.json.template](azure_config.json.template)).

## Limitations of client verification

Currently, Microsoft Azure Attestation (MAA) service requires quote verifications 
(i.e., for interacting with the controller, for verifying certificates) 
to have an Azure account if not run from inside the Azure infrastructure.
Thus, the client requires additional Azure configuration.

If the client is running on the same Azure VM as the controller or in another Azure VM, 
the quote verification request to MAA works successfully without additional configuration.

## Contact

Istemi Ekin Akkus (istemi_ekin.akkus@nokia-bell-labs.com)

Ivica Rimac (ivica.rimac@nokia-bell-labs.com)
