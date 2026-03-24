# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

FROM ubuntu:22.04

ENV app_user=duet

RUN groupadd -o -g 1000 -r ${app_user} && useradd -d /home/${app_user} -u 1000 -m -r -g ${app_user} ${app_user}

RUN apt-get update --fix-missing \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    python3 \
    python3-pip

ADD requirements.txt /tmp/requirements.txt

RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install -r /tmp/requirements.txt

RUN mkdir -p /tmp/HF_CACHE
ENV HF_HOME=/tmp/HF_CACHE

ADD hf_download.py /tmp/

RUN chown ${app_user}:${app_user} -R /home/${app_user}
USER ${app_user}

ENTRYPOINT ["python3", "/tmp/hf_download.py"]