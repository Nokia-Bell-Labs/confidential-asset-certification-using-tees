# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

from huggingface_hub import HfApi, hf_hub_url

import yaml

global HF_API
HF_API = HfApi()

def convert_info_to_json(obj):
    info = {}
    for attr in obj.__dataclass_fields__:
        value = str(obj.__getattribute__(attr))
        if attr == "card_data":
            value = yaml.safe_load(value)
        info[attr] = value

    return info

def convert_sibling_to_json(sibling):
    info = {}
    sibling = sibling[sibling.find("(")+1:sibling.rfind(")")]
    tokens = sibling.split(",")
    for token in tokens:
        tokens2 = token.split("=")
        if len(tokens2) < 2:
            continue
        t0 = tokens2[0].strip().lstrip()
        t1 = tokens2[1].strip().lstrip()
        if t0 == "rfilename" or t0 == "sha256":
            info[t0] = t1[1:-1]

    return info

def get_repo_urls(asset_id, asset_type, filters):
    files = []
    repo_info = HF_API.repo_info(asset_id, repo_type=asset_type, files_metadata=True)
    repo_info = convert_info_to_json(repo_info)
    siblings = repo_info["siblings"].split("RepoSibling")
    for sibling in siblings:
        info = convert_sibling_to_json(sibling)
        if info:
            base_fname = info["rfilename"]
            if filters:
                for filter in filters:
                    if base_fname.startswith(filter):
                        info["asset_url"] = hf_hub_url(repo_id=asset_id, filename=base_fname, repo_type=asset_type)
                        files.append(info)
            else:
                info["asset_url"] = hf_hub_url(repo_id=asset_id, filename=base_fname, repo_type=asset_type)
                files.append(info)

    return files
