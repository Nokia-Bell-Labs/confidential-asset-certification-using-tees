# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

FROM ubuntu:22.04

ENV app_user=duet

RUN groupadd -o -g 1000 -r ${app_user} && useradd -d /home/${app_user} -u 1000 -m -r -g ${app_user} ${app_user}

RUN apt-get update --fix-missing \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    wget \
    iputils-ping \
    python3 \
    python3-pip \
    python-is-python3

# Python
RUN /usr/bin/python3 -m pip install --upgrade pip
ADD requirements.txt /tmp/
RUN /usr/bin/python3 -m pip install -r /tmp/requirements.txt

RUN apt-get clean

RUN mkdir -p /home/${app_user}/AdminEnclave
RUN mkdir -p /home/${app_user}/AdminEnclave/sealed
RUN mkdir -p /home/${app_user}/AdminEnclave/utils
RUN mkdir -p /home/${app_user}/AdminEnclave/geoloc
RUN mkdir -p /home/${app_user}/AdminEnclave/cvm_commands/azure
RUN mkdir -p /home/${app_user}/tmp
RUN mkdir -p /home/${app_user}/certs

ADD expected_hashes.json /home/${app_user}/AdminEnclave/
ADD cvm_commands/azure/* /home/${app_user}/AdminEnclave/cvm_commands/azure/

ADD *.py /home/${app_user}/AdminEnclave/
ADD utils/*.py /home/${app_user}/AdminEnclave/utils/
ADD geoloc/*.py /home/${app_user}/AdminEnclave/geoloc/

WORKDIR /home/${app_user}/AdminEnclave/geoloc/

RUN tar --sort=name \
      --mtime='1970-01-01 00:00Z' \
      --owner=0 --group=0 --numeric-owner \
      --pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime \
      --mode=a=rX,u+w \
      -cvf /home/${app_user}/AdminEnclave/geoloc.tar .

RUN rm -rf /home/${app_user}/.cache
RUN chown ${app_user}:${app_user} -R /home/${app_user}
USER ${app_user}

WORKDIR /

CMD ["python3", "-m", "home.duet.AdminEnclave.admin"]
