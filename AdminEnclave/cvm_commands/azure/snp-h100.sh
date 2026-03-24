# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

wget https://github.com/Azure/az-cgpu-onboarding/releases/download/V4.1.5/cgpu-onboarding-package.tar.gz
sha256sum cgpu-onboarding-package.tar.gz
tar -xvf cgpu-onboarding-package.tar.gz

# will reboot
cd cgpu-onboarding-package; sudo bash step-0-prepare-kernel.sh

cd cgpu-onboarding-package; sudo bash step-1-install-gpu-driver.sh

cd cgpu-onboarding-package; sudo bash step-2-attestation.sh > /home/duet/h100_attestation.txt

# expected: "SecureBoot enabled"
mokutil --sb-state >> /home/duet/h100_attestation.txt

# expected: "CC status: ON"
nvidia-smi conf-compute -f >> /home/duet/h100_attestation.txt

# expected: "CC Environment: PRODUCTION"
nvidia-smi conf-compute -e >> /home/duet/h100_attestation.txt
