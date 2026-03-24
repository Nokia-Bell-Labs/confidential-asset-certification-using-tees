# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

set -x

OUTPUT_FOLDER=/tmp/results

mkdir -p $OUTPUT_FOLDER

trivy image --scanners license,vuln,secret --format spdx-json -f json --output $OUTPUT_FOLDER/results_trivy.spdx $IMAGE_NAME

syft $IMAGE_NAME -o spdx-json=$OUTPUT_FOLDER/results_syft.spdx

grype $IMAGE_NAME -o json=$OUTPUT_FOLDER/results_grype.json

grype $IMAGE_NAME -o cyclonedx-json=$OUTPUT_FOLDER/results_grype.cdx.json
