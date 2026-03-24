# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

FROM ubuntu:22.04

RUN mkdir -p /tmp/inputs
RUN mkdir -p /tmp/outputs

RUN apt-get update --fix-missing \
    && apt-get -y --no-install-recommends install \
    python3 \
    python3-pip

RUN mkdir /tmp/libprop
ADD libprop/* /tmp/libprop/

RUN /usr/bin/python3 -m pip install --upgrade pip \
    && /usr/bin/python3 -m pip install -r /tmp/libprop/requirements.txt

ADD requirements.txt /tmp/requirements.txt

RUN /usr/bin/python3 -m pip install -r /tmp/requirements.txt
ADD compute_dataset_property.py /tmp/

ENTRYPOINT ["python3", "/tmp/compute_dataset_property.py"]