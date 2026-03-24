# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

ls -1 /linux_build/*.deb | grep -v "dbg_" | xargs -I {} cp {} /tmp/outputs/
