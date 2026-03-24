# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

FROM nvidia/cuda:13.1.1-cudnn-runtime-ubuntu22.04

RUN mkdir -p /tmp/inputs
RUN mkdir -p /tmp/outputs

RUN apt-get update --fix-missing \
    && apt-get -y --no-install-recommends install \
    git \
    python3 \
    python3-pip

ADD requirements.txt /tmp/requirements.txt

RUN /usr/bin/python3 -m pip install --upgrade pip \
    && /usr/bin/python3 -m pip install -r /tmp/requirements.txt

ADD compute_model_property.py /tmp/

RUN git clone https://github.com/huggingface/evaluate.git /tmp/evaluate-metrics/

RUN cd /tmp/evaluate-metrics/; git checkout 5aa3982a9a8c86e506860e381d428a64b0cce73b

ENTRYPOINT ["python3", "/tmp/compute_model_property.py"]
