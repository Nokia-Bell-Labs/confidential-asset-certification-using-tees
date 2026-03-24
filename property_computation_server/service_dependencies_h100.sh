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

# Nvidia Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y nvidia-container-toolkit

# Nvidia currently having an issue with GPU disappear from docker
# Put temp mitigation based on: https://github.com/nvidia/nvidia-container-toolkit/issues/48
sudo echo "{ \"exec-opts\": [\"native.cgroupdriver=cgroupfs\"] }" \
    | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker