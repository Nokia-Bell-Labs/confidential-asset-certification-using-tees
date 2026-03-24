# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import os

import docker

def build_additional_tools():
    docker_api_client = docker.APIClient(base_url='unix://var/run/docker.sock')

    tool_list = [t for t in os.listdir("./") if os.path.isfile("./" + t)]
    for tool_name in tool_list:
        if tool_name.find("build_tools.py") != -1:
            continue
        print("Building computation tool: " + tool_name)
        try:
            with open(tool_name, "rb") as tool_file:
                build_log = docker_api_client.build(fileobj=tool_file, custom_context=True, decode=True, tag="computation-tool-" + tool_name[14:-4])
                for output in build_log:
                    if "stream" in output:
                        lines = output["stream"].split("\n")
                        for line in lines:
                            if line != "":
                                print(line)
        except Exception as exc:
            print("[ERROR]: Cannot build certification tool: " + str(exc))
            print("*"*20)

    docker_api_client.close()

if __name__ == "__main__":
    build_additional_tools()