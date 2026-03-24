# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

FROM node:24-alpine

RUN mkdir -p /tmp/inputs
RUN mkdir -p /tmp/outputs

RUN npm install -g npm@latest
WORKDIR /tmp

RUN npm install terser -g

CMD ["terser", "/tmp/inputs/javascript/jquery/jquery-3.7.1.js", "--compress", "--mangle", "--source-map", "--output", "/tmp/outputs/jquery-3.7.1.min.js"]
