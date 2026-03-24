# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

FROM nvidia/cuda:13.1.1-cudnn-devel-ubuntu22.04

RUN mkdir -p /tmp/inputs
RUN mkdir -p /tmp/outputs

# Set environment variables for CUDA
#ENV CUDA_HOME=/usr/local/cuda
ENV PATH="/usr/local/cuda/bin:${PATH}"
ENV LD_LIBRARY_PATH="/usr/local/cuda/lib64:${LD_LIBRARY_PATH}"
# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive  

# Install necessary system dependencies and Python 3.11
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get update && apt-get install -y \
    python3.11 python3.11-venv python3.11-dev python3-pip git wget curl \
    && rm -rf /var/lib/apt/lists/*


ADD requirements_base.txt /tmp/requirements_base.txt
ADD requirements.txt /tmp/requirements.txt
 
RUN /usr/bin/python3 -m pip install --upgrade pip  
RUN /usr/bin/python3 -m pip install -r /tmp/requirements_base.txt
RUN /usr/bin/python3 -m pip install -r /tmp/requirements.txt

ADD eval.py /tmp/
 
CMD ["python3", "/tmp/eval.py", "cuda"]
