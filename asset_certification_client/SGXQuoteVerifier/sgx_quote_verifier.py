# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import base64
import json

from azure.identity import DefaultAzureCredential
from azure.security.attestation import AttestationClient

from cryptography.hazmat.primitives import hashes

class SGXQuoteVerifier():
    def __init__(self, attestation_service_url):
        self._attestation_service_url = attestation_service_url

    def _verify_public_key_hash(self, key_hash_recvd, enclave_key):
        if not isinstance(enclave_key, bytes):
            enclave_key = bytes(enclave_key, "utf-8")

        key_hash_calc = hashes.Hash(hashes.SHA256())
        key_hash_calc.update(enclave_key)
        calculated_hash_digest = key_hash_calc.finalize().hex()

        if calculated_hash_digest == key_hash_recvd:
            return True

        return False

    def _verify_expected_mrenclave(self, mrenclave_received, mrenclave_expected):
        print("Expecting MRENCLAVE: " + mrenclave_expected)
        print("Found MRENCLAVE: " + mrenclave_received)
        if mrenclave_received == mrenclave_expected:
            return True

        return False

    def verify_remote_enclave(self, remote_quote, remote_public_key, expected_mrenclave):
        if not isinstance(remote_quote, bytes):
            remote_quote = bytes(remote_quote, "utf-8")

        if not isinstance(remote_public_key, bytes):
            remote_public_key = bytes(remote_public_key, "utf-8")

        if not self._verify_quote(remote_quote, remote_public_key):
            return False

        if not self._verify_public_key_hash(remote_quote[368:400].hex(), remote_public_key):
            return False

        # TODO: check attributes, mrsigner, isvprodid, isvsvn
        # check mrenclave
        if not self._verify_expected_mrenclave(remote_quote[112:144].hex(), expected_mrenclave):
            return False

        return True


class AzureSGXQuoteVerifier(SGXQuoteVerifier):
    def __init__(self, attestation_service_url):
        super().__init__(attestation_service_url)

    def _verify_quote(self, quote, enclave_key):
        # Check the quote via remote attestation
        # use the internal checks to validate the token's properties
        # if the quote is not valid, there will be an exception
        try:
            attest_client = AttestationClient(
                endpoint=self._attestation_service_url,
                credential=DefaultAzureCredential(),
                validate_token=True,
                validate_signature=True,
                validate_issuer=True,
                issuer=self._attestation_service_url,
                validate_expiration=True,
                #validation_callback=validate_token
                )

            attest_result, token = attest_client.attest_sgx_enclave(quote, runtime_data=enclave_key)

            # print(attest_result.enclave_held_data)
            # print(attest_result.nonce)
            # print(attest_result.mr_enclave)
            # print(attest_result.mr_signer)
            # print("---------------------------")
            # token = json.loads(token.body_bytes.decode())
            # print(json.dumps(token, indent=4))

        except Exception as exc:
            print(exc)
            return False

        return True
