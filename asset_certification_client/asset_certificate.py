# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

class AssetCertificate():
    """
    Data structure to hold an asset certificate content

    The quote is the SGX quote of the duet controller.
    It also includes the ephemeral public key of the controller.

    The service result contains the service info
    as well as what the asset certification service returns.

    The controller signature covers the service result and can be verified
    with the public key of the controller.

    The attestation service URL will be used to query the authenticity of the
    duet controller's quote.
    """

    def __init__(self):
        self._controller_quote = None
        self._service_result = None
        self._controller_signature = None
        self._attestation_service_url = None

    def set_controller_quote(self, quote):
        self._controller_quote = quote

    def set_attestation_service_url(self, attestation_service_url):
        self._attestation_service_url = attestation_service_url

    def set_controller_signature(self, signature):
        self._controller_signature = signature

    def set_service_result(self, result):
        self._service_result = result

    def get_asset_certificate(self):
        content = {}
        content["duet_admin_quote"] = self._controller_quote
        content["duet_admin_attestation_service_url"] = self._attestation_service_url
        content["duet_service_result"] = self._service_result
        content["duet_admin_signature"] = self._controller_signature

        return content
