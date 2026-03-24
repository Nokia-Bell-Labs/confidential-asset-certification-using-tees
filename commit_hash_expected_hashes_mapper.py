# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

from argparse import ArgumentParser
from collections import OrderedDict
import json

from git import Repo


def _collect_commits():
    repo = Repo("./")
    value_commit_map = OrderedDict()

    previous_values = None
    for commit in repo.iter_commits():
        item = commit.tree["duet_expected_hashes.json"]
        val = item.data_stream.read().decode()
        values = json.loads(val)
        val = json.dumps(values)
        if previous_values != values:
            # print("*"*50)
            # print(json.dumps(values, indent=4))
            previous_values = values

        if val not in value_commit_map:
            value_commit_map[val] = []

        # print(commit, commit.committed_datetime, commit.authored_datetime, commit.message)
        c = {}
        c["commit_hash"] = str(commit)
        c["commit_authored_datetime"] = str(commit.authored_datetime)
        c["commit_commit_datetime"] = str(commit.committed_datetime)
        c["commit_message"] = commit.message
        c["commit_author"] = str(commit.author), str(commit.author.email)
        value_commit_map[val].append(c)

    print("="*50)
    
    return value_commit_map

def list_commits():
    value_commit_map = _collect_commits()

    for v in value_commit_map:
        commits = value_commit_map[v]
        v = json.loads(v)
        print("Contents of the 'duet_expected_hashes.json' file:")
        print("-"*10)
        print(json.dumps(v, indent=4))
        print("-"*20)
        print("In the following " + str(len(commits)) + " commit(s) of the repo:")
        print("-"*10)
        for c in commits:
            print(json.dumps(c, indent=4))
        print("*"*50)

def _find_string(values, search_string):
    for k, v in values.items():
        if isinstance(v, dict):
            return _find_string(v, search_string)
        elif v.find(search_string) != -1:
            return k, v

    return None, None

def search_hash(search_string):
    value_commit_map = _collect_commits()
    found_commits = None
    found_values = None
    
    for v in value_commit_map:
        values = json.loads(v)
        key, expected_hash = _find_string(values, search_string)
        if key and expected_hash:
            found_commits = value_commit_map[v]
            found_values = values
            break

    if found_values:
        # key = _find_corresponding_key(found_values, search_string)
        print("Found string: " + search_string)
        print("Corresponding key: " + key + ", hash: " + expected_hash)
        print(json.dumps(found_values, indent=4))
        print("Found in the following " + str(len(found_commits)) + " commit(s):")
        for c in found_commits:
            print(json.dumps(c, indent=4))
        
def parse_args():
    parser = ArgumentParser()
    parser.add_argument("-l", "--list", action='store_true', help="List commit id")
    parser.add_argument("-s", "--search-string", help="Search for an expected hash string.")
    args = parser.parse_args()
    return args

def check_valid_args(args):
    if args.list:
        return True

    if not args.search_string:
        print("Missing argument: search_string")
        return False

    return True

if __name__ == "__main__":
    args = parse_args()

    if check_valid_args(args):
        if args.list:
            list_commits()
        else:
            search_hash(args.search_string)