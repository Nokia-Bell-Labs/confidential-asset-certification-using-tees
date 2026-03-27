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

The output would look like this:

```
{
  "systemAssignedIdentity": "",
  "userAssignedIdentities": {
    "/subscriptions/<subscription-id>/resourceGroups/<resource-group-name>/providers/Microsoft.ManagedIdentity/userAssignedIdentities/<managed-identity-name>": {
      "clientId": "<some-id>",
      "principalId": "<some-id>"
    }
  }
}
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

### Service Provider Setup

1. Some operations in the controller are privileged operations. They are only supposed to be invoked by the service provider. To authenticate the service provider, we use the service provider's public key and verify the signature on the operations requested by the client.

The service provider public key needs to be available to the controller. This public key is used to register the service in the controller.

To generate the public/private key and store it, do the following:

```
python3 generate_private_key.py
```

This will produce `service_owner_private_key` and `service_owner_public_key`.

When the client interacts with the controller for service deployment, it reads the private key, extracts the public key and sends it along with the registration request. Any subsequent requests requiring privileges (e.g., starting/stopping CVMs, deploying the service) are signed by the provider's private key and checked with the registered public key in the controller.

#### Running The Controller with SGX

1. Build the gramine image that will help creating duet's controller in a graminized container.

```
make -C graminize gramine-image
```

2. Then build the controller.

```
make -C AdminEnclave graminize
```

3. Afterwards, one can instantiate the controller as

```
make -C AdminEnclave run-sgx
```

4. Then, you can run deploy the CACTEE service.

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

Once you have done that, you can deploy the asset certification service as the service provider.

First, deploy at least one CVM backend via the following script:
```
# repeat if needed more
python3 test_duet_service_owner.py start-cvm snp-h100
```

For ML model scenarios, it is suggested to use `snp-h100`. Other example scenarios can also be used with `snp`.

This script will print out the steps that are happening:

First, the service provider's public key will be registered.
Second, the service provider will supply the cloud config file (e.g., `azure_config.json`).
Finally, the script will call the `start_cvm()` API to interact with the controller.
It will come to an end when the CVM is deployed, attested (with GPU attestation also if needed) 
and geolocation measurements performed. The `start_cvm()` call will return the CVM's id and its location.

Afterwards, the property computation service can be deployed through the controller.

```
# then start the service on those backends
python3 test_duet_service_owner.py start snp-h100
```

This script will also print out the steps that are happening:

First, the property computation server's code and the code for the tools are archived.
Then, the runtime dependencies are read through the `service_dependencies_h100.sh` (or `service_dependencies.sh` if `snp`).
All these pieces are used to call the `start_service()` API to interact with the controller.
Once the service is successfully deployed, the script print the service metadata:
the secure hashes of the service code archive, the tools and the service dependencies as well as the service's location.

The controller, as it proxies requests to an available CVM, implements a simple sticky session approach
by letting the property computation service embed the handling CVM id into the responses.
The client then embeds the same CVM id in its requests, so that the requests belonging to the same certification
end up in the same backend CVM.

5. Once you are done with generation of certificates, you can also shut down the service:

```
python3 test_duet_service_owner.py stop
```

This will stop the property computation service and the CVMs it was launched on.

One can also shut down individual CVMs by supplying its <cvm_id> that was returned when it was started.

```
python3 test_duet_service_owner.py stop-cvm <cvm_id>
```


### Asset Owner Setup

1. After the service is deployed, you can run an example script.

```
python3 test_asset_certification.py <example_config.json>
```

Again here, the script will print out the steps:

First, the config file will be read.
Accordingly, the relevant API calls are made to upload inputs and code.
Once all pieces are uploaded, the script will call `prepare()` API to let the property computation service build the container image.
The script will loop until the status of the image is ready.
Afterwards, the client will call `start()` API and loop until the result is ready.
Once the request is finished, the asset certificate as well as any output files that were certified will be downloaded to `test_results/certifications/` folder.

Sample runs of this script can be found in [examples/systex_eval_logs/](examples/systex_eval_logs/).

### Third-party Verifier

1. Once the certificate has been downloaded, it can also be verified with the config
for finding relevant inputs, code and build args as well as the output folder
where the asset certificate and computation output is stored (e.g., `test_results/certifications/<example_name>` or `examples/certificates/<example_name>`).

```
python3 test_asset_certificate_verification.py <example_config.json> <output_folder>
```

One can pass the `ATTESTATION_SERVICE_URL` environment variable to use a different MAA endpoint (default value: `https://sharedneu.neu.attest.azure.net/`).

```
ATTESTATION_SERVICE_URL=https://sharedweu.weu.attest.azure.net/ python3 test_asset_certificate_verification.py <example_config.json> <output_folder>
```


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

## Known Issues
### Limitations of Quote Verification

The client uses Microsoft Azure Attestation (MAA) service for quote verifications 
(i.e., for interacting with the controller, for verifying certificates).

If the client is running on the same Azure VM as the controller or in another Azure VM, 
no additional configuration is required.

If not, Azure requires the caller to authenticate, which is 
why Azure credentials must be available in the client's environment.
The additional configuration for that environment can be set up as follows:

1. Create an Azure service principal using Azure CLI:

	```bash
	az ad sp create-for-rbac --name "duet-client"
	```
	
	Example output:
	```json
	{
	  "appId": "xxxxxx",
	  "displayName": "duet-client",
	  "password": "xxxxxx",
	  "tenant": "xxxxxx"
	}
	```

	Note the `appId` (-> `AZURE_CLIENT_ID`) and `tenant` (-> `AZURE_TENANT_ID`) from the output. Discard the generated `password` — the next step replaces it with a certificate credential.

3. Create a certificate credential:

	```bash
	# Generate a self-signed certificate
	openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
	  -subj "/CN=duet-client"
    
	# Combine into a single PEM file for teh client (required by the Azure SDK)
	cat cert.pem key.pem > client-cert.pem

	# Upload the public certificate to the service principal
	az ad app credential reset \
      --id <appId> \
	  --cert @cert.pem \
	  --append
	```

4. Deliver credentials to the client and export variables three variables on the client:

	```bash
	export AZURE_CLIENT_ID=<clientId>
	export AZURE_TENANT_ID=<tenantId>
	export AZURE_CLIENT_CERTIFICATE_PATH=/path/to/client-cert.pem
	```

### Inconsistent MRENCLAVE Value for the Controller

When the controller enclave is built using gramine libOS in a new machine,
the controller's MRENCLAVE value may change.
This is due to the duet/gramine image that is used to graminize the controller
not being fully reproducible.
We are working on it to fix it.

As a workaround on a single machine, the error messages can be fixed by updating the `duet_expected_hashes.json` file with the current MRENCLAVE value for the controller. 

### InsecureRequestWarning

Alongside the attestation warnings you may see:

```
InsecureRequestWarning: Unverified HTTPS request is being made to host '...'.
```

This is expected. The initial connection to the controller via the SDK is done
with TLS verification disabled
because the controller uses a self-signed certificate
that cannot be verified via standard CA chains.
The quote verification step with the expected MRENCLAVE value is what establishes
the security guarantee.

Afterwards, the client SDK uses the self-signed certificate of the controller
to establish secure communications with it.

### Dropped Managed Identity from Controller VM

Sometimes, the managed identity assigned to the controller's VM vanishes.
It is not clear why this happens.
As a result, the controller fails performing some provisioning operations for the CVM and throws an error.
Please check again if the VM has still the necessary identity as described above in the [Pre-requisites](#pre-requisites) and assign it again.

Afterwards, retry the commands from the client side.

### Troubleshooting

Currently, there is not much fault tolerance and error propagation.
When there is an error at the client, the reason usually is an error not propagated from the server.
To see what went wrong, one can get the server logs via `docker logs duetadmin-enclave`, which usually contain the error message from Azure.
