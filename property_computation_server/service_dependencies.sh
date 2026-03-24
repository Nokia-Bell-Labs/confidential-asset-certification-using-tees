# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

# docker repos
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
# install dependencies: docker, python
sudo DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends --yes docker-ce docker-ce-cli containerd.io docker-buildx-plugin python3-pip
sudo usermod -aG docker duet
sudo python3 -m pip install --ignore-installed cryptography==45.0.7 docker==7.1.0 flask==3.1.2 requests==2.32.3 codecarbon==3.2.0 --break-system-packages