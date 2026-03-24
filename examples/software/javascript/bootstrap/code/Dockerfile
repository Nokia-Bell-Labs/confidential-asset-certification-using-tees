# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

FROM node:24-alpine

RUN mkdir -p /tmp/inputs
RUN mkdir -p /tmp/outputs

RUN npm install -g npm@latest
WORKDIR /tmp

RUN apk update

RUN apk add --no-cache unzip
RUN apk add --no-cache wget

RUN wget https://github.com/twbs/bootstrap/archive/v5.3.8.zip -O /tmp/inputs/v5.3.8.zip
RUN echo "4f36c463a1079debab6b5e43e09e14253d3aa896939967b3e9f9098edc39e448  /tmp/inputs/v5.3.8.zip" | sha256sum -c -

RUN unzip /tmp/inputs/v5.3.8.zip -d /tmp/bootstrap

RUN cd /tmp/bootstrap/bootstrap-5.3.8/\
    && npm install

ADD copy_files.sh /tmp/
RUN chmod +x /tmp/copy_files.sh

CMD ["/tmp/./copy_files.sh"]