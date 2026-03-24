# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

FROM ubuntu:22.04

RUN mkdir -p /tmp/inputs
RUN mkdir -p /tmp/outputs

RUN apt-get update --fix-missing \
    && apt-get -y --no-install-recommends install \
    ca-certificates \
    curl

# Define environment variables
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG IMAGE_NAME
ARG TRIVY_VERSION

ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV IMAGE_NAME=${IMAGE_NAME}
ENV TRIVY_VERSION=${TRIVY_VERSION}

# install trivy
RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin ${TRIVY_VERSION}

# install syft
RUN curl -sSfL https://get.anchore.io/syft | sh -s -- -b /usr/local/bin

# install grype
RUN curl -sSfL https://get.anchore.io/grype | sh -s -- -b /usr/local/bin

RUN trivy clean --all

RUN trivy image --download-db-only

RUN grype db update

ADD run.sh /
RUN chmod +x /run.sh
RUN ./run.sh

ADD copy-files.sh /
RUN chmod +x copy-files.sh

CMD ["./copy-files.sh"]