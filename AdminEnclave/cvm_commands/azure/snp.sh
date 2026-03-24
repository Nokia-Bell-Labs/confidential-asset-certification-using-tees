# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends --yes build-essential libcurl4-openssl-dev libjsoncpp-dev libboost-dev zlib1g-dev cmake libjsoncpp-dev nlohmann-json3-dev

wget https://packages.microsoft.com/repos/azurecore/pool/main/a/azguestattestation1/azguestattestation1_1.0.5_amd64.deb
sha256sum azguestattestation1_1.0.5_amd64.deb
sudo dpkg -i azguestattestation1_1.0.5_amd64.deb

git clone https://github.com/Azure/confidential-computing-cvm-guest-attestation.git

cd confidential-computing-cvm-guest-attestation/cvm-attestation-sample-app; git checkout c626949d429086fcd3211e0eabc86c24c014af38; cmake .; make;

cp confidential-computing-cvm-guest-attestation/cvm-attestation-sample-app/AttestationClient .

sudo /home/duet/./AttestationClient -o token -n $(cat ~/nonce) > /home/duet/attestation_token.txt
