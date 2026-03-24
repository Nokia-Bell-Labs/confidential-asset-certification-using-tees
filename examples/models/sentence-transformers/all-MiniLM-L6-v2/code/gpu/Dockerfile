# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

FROM python:3.10-slim

RUN mkdir -p /tmp/inputs
RUN mkdir -p /tmp/outputs

ADD requirements.txt /tmp/requirements.txt
ADD requirements_base.txt /tmp/requirements_base.txt

RUN python -m pip install --upgrade pip  
RUN python -m pip install -r /tmp/requirements.txt
RUN python -m pip install -r /tmp/requirements_base.txt

ADD eval.py /tmp/

ENTRYPOINT ["python", "/tmp/eval.py"]