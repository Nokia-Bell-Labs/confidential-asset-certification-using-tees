# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

PYTHONDONTWRITEBYTECODE=1 gramine-sgx-sign \
      --key $1 \
      --manifest $2 \
      --output $3