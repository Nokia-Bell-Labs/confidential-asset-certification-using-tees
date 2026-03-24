# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
import sys

try:
    from .asset_certification_client.asset_certificate_verifier import AssetCertificateVerifier
except Exception as _:
    from asset_certification_client.asset_certificate_verifier import AssetCertificateVerifier

def main(config_filename, output_folder):
    relative_folder = "./"
    if config_filename.rfind("/") != -1:
        relative_folder = config_filename[:config_filename.rfind("/")+1]

    # get the expected measurement values
    with open("duet_expected_hashes.json", "r") as f:
        duet_manifest = json.load(f)

    # obtain the relevant values to find where the certification related
    # code and input files (optionally)
    with open(config_filename, "r") as f:
        cert_config = json.load(f)

    print("[INFO]: " + json.dumps(cert_config, indent=4))

    # certificate_filename, input_folder, code_folder, output_folder
    # output_folder = "test_results/certifications/" + cert_config["name"]
    certificate_filename = output_folder + "/asset_certificate.json"
    code_folder = relative_folder + cert_config["code_folder"]
    code_build_args = None
    if "code_build_args" in cert_config:
        code_build_args = cert_config["code_build_args"]
    
    input_folders = []
    for cert_input in cert_config["inputs"]:
        if cert_input["upload_method"] == "direct":
            input_folders.append(relative_folder + cert_input["input_folder"])

    # instantiate a verifier with the relevant folders paths
    cv = AssetCertificateVerifier(certificate_filename, code_folder, output_folder, input_folders, code_build_args, duet_manifest)

    # verify the certificate and obtain the detailed verification steps
    result, result_verification_steps = cv.verify_certificate(duet_admin_sgx_quote_provider="azure")
    
    print("*" * 50)
    if result:
        print("[OK] Valid asset certificate.")
    else:
        print("[ERROR] Invalid asset certificate.")
    
    print("*" * 20)
    print("Detailed steps of asset certification verification:")
    print(json.dumps(result_verification_steps, indent=4, sort_keys=True))
    print("*" * 50)

def usage():
    print("Usage: python3 test_asset_certificate_verification.py <config_filename>")

if __name__ == "__main__":
    len_args = len(sys.argv)
    if len_args == 3:
        config_filename = sys.argv[1]
        output_folder = sys.argv[2]
        main(config_filename, output_folder)
    else:
        usage()
