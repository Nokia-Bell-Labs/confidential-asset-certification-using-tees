# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

from collections import Counter
from pathlib import Path
import json
import math
import re
import sys
import time
from typing import TypedDict

import pandas as pd

import langid

# Load the model
LANGUAGE_IDENTIFIER = langid.LanguageIdentifier.from_modelstring(
    langid.model, norm_probs=True
)


def is_missing(value: any) -> bool:
    """Check if `value` is empty (depending on the type)."""
    if value is None:
        return True
    if isinstance(value, str) and value == "":
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def process_files(data_path: str, glob: str) -> dict:
    """Process all files in a directory."""
    output = {}

    data_dir = Path(data_path)
    paths = list(data_dir.glob(glob))

    output["filenames"] = [str(path.relative_to(data_dir)) for path in paths]

    n = len(paths)
    for i, path in enumerate(paths):
        print(f"Processing {path} ({i+1}/{n})")
        (lang, results) = process_file(path)
        if lang not in output:
            output[lang] = []
        output[lang].append(results)

    return output


# For a bunch of common licenses, strings we can use to detect them.
LICENSES = {
    "Apache-2.0": ["Apache-2.0", "Apache License", "Apache 2.0"],
    "MIT": ["MIT"],
    "GPL-3.0": [
        "GPL-3",
        "GPL 3",
        "General Public License v3",
        "General Public License 3",
    ],
    "GPL-2.0": [
        "GPL-2",
        "GPL 2",
        "General Public License v2",
        "General Public License 2",
    ],
    "LGPL-3.0": [
        "LGPL-3",
        "LGPL 3",
        "Lesser General Public License v3",
        "Lesser General Public License 3",
    ],
    "LGPL-2.1": [
        "LGPL-2.1",
        "LGPL 2.1",
        "Lesser General Public License v2.1",
        "Lesser General Public License 2.1",
    ],
    "AGPL-3.0": [
        "AGPL-3",
        "AGPL 3",
        "Affero General Public License v3",
        "Affero General Public License 3",
    ],
    "BSD-3-Clause": ["BSD-3", "BSD 3"],
    "BSD-2-Clause": ["BSD-2", "BSD 2"],
    "MPL-2.0": [
        "MPL-2",
        "MPL 2",
        "Mozilla Public License v2",
        "Mozilla Public License 2",
    ],
    "CC-BY-4.0": ["CC-BY-4.0", "CC BY 4.0", "Creative Commons Attribution 4.0"],
    "CC-BY-SA-4.0": [
        "CC-BY-SA-4.0",
        "CC BY-SA 4.0",
        "Creative Commons Attribution Share Alike 4.0",
    ],
    "CC-BY-NC-4.0": [
        "CC-BY-NC-4.0",
        "CC BY-NC 4.0",
        "Creative Commons Attribution Non Commercial 4.0",
    ],
    "CC-BY-NC-SA-4.0": [
        "CC-BY-NC-SA-4.0",
        "CC BY-NC-SA 4.0",
        "Creative Commons Attribution Non Commercial Share Alike 4.0",
    ],
}


def extract_license(content):
    """Try to extract a license from a file."""
    lines = content.split("\n")
    header = lines[:10]
    header = [line.strip() for line in header]
    # Option 1: it contains "SPDX-License-Identifier" in one of the first 10 lines
    for line in header:
        if "SPDX-License-Identifier" in line:
            m = re.search(r"SPDX-License-Identifier:\s*(\S+)", line)
            if m and m.group(1):
                license = m.group(1)
                # print(f"Found license {license} (option 1)")
                return license
    # Option 2: it contains the name of a license in the first 10 lines
    for line in header:
        for license, strings in LICENSES.items():
            for string in strings:
                if string.lower() in line.lower():
                    # print(f"Found license {license} (option 2)")
                    return license
    # Option 3: it contains "license:" in the first 10 lines
    for line in header:
        if "license" in line.lower():
            m = re.search(r"license:\s*(.+)", line.lower())
            if m and m.group(1):
                license = m.group(1)
                print(f"Found license {license} (option 3)")
                return license
    return None


class ColumnInfoDict(TypedDict):
    cell_types: dict[str, int]
    cell_missing: int


def extract_generic_properties(df: pd.DataFrame) -> dict[str, ColumnInfoDict]:
    """Extract generic properties from a DataFrame."""
    column_info = {}
    for col_name in df.columns:
        types = {}
        null_count = 0
        for cell in df[col_name]:
            type_ = str(type(cell))

            if is_missing(cell):
                null_count += 1
                continue

            if type_ not in types:
                types[type_] = 1
            else:
                types[type_] += 1

        column_info[col_name] = {"cell_types": types, "cell_missing": null_count}
    return column_info


class LicenseDict(TypedDict):
    unique_licenses: list[str]
    count_per_license: dict[str, int]
    multiple_licenses: int


def count_licenses(df: pd.DataFrame) -> LicenseDict:
    """Count the number of unique licenses and the number of entries per license."""
    # Cells in df["max_stars_repo_licenses"] looks like:
    #   [ "Apache-2.0" ]
    # -> this is already a list
    count_per_licenses = {"none": 0}
    multiple_licenses = 0
    for licenses in df["max_stars_repo_licenses"]:
        if licenses is None:
            count_per_licenses["none"] += 1
        for l in licenses:
            if l in count_per_licenses:
                count_per_licenses[l] += 1
            else:
                count_per_licenses[l] = 1
        if len(licenses) > 1:
            multiple_licenses += 1

    unique_licenses = list(count_per_licenses.keys())
    # Remove none if it does not actually appear
    # (All others are only added if they appear at least once)
    if count_per_licenses["none"] == 0:
        unique_licenses.remove("none")

    return {
        "unique_licenses": unique_licenses,
        "count_per_license": count_per_licenses,
        "multiple_licenses": multiple_licenses,
    }


def check_license_mismatch(df: pd.DataFrame) -> int:
    """Check if the license in the content matches the license in the metadata."""
    selected_cols = df[["hexsha", "content", "max_stars_repo_licenses"]]
    license_mismatch = 0
    for hexsha, content, licenses in selected_cols.itertuples(index=False):
        if content is None:
            continue
        if licenses is None:
            continue
        licenses = [l.lower() for l in licenses]

        content_license = extract_license(content)
        if content_license is None:
            continue

        if content_license.lower() not in licenses:
            license_mismatch += 1
            repo_name, repo_path = df[df["hexsha"] == hexsha][
                ["max_stars_repo_name", "max_stars_repo_path"]
            ].values[0]
            print(
                f"Content license {content_license} does not match license "
                f"{licenses} for commit {hexsha} in {repo_name} at {repo_path}"
            )

    return license_mismatch


# There are 358 programming languages in the dataset, but we only consider a few
# of them here. We define regular expressions to match comments in these languages.
COMMENT_MATCHERS = {
    "c": [
        re.compile(r"//.*"),  # C comments
        re.compile(r"/\*.*?\*/", re.DOTALL),  # C multiline comments
    ],
    "c-sharp": [
        re.compile(r"//.*"),  # C# comments
        re.compile(r"/\*.*?\*/", re.DOTALL),  # C# multiline comments
    ],
    "clojure": [
        re.compile(r";.*"),  # Clojure comments
    ],
    "common-lisp": [
        re.compile(r";.*"),  # Common Lisp comments
    ],
    "cpp": [
        re.compile(r"//.*"),  # C++ comments
        re.compile(r"/\*.*?\*/", re.DOTALL),  # C++ multiline comments
    ],
    "css": [
        re.compile(r"/\*.*?\*/", re.DOTALL),  # CSS multiline comments
    ],
    "dockerfile": [
        re.compile(r"#.*"),  # Dockerfile comments
    ],
    "go": [
        re.compile(r"//.*"),  # Go comments
        re.compile(r"/\*.*?\*/", re.DOTALL),  # Go multiline comments
    ],
    "haskell": [
        re.compile(r"--.*"),  # Haskell comments
        re.compile(r"{-.*-}", re.DOTALL),  # Haskell multiline comments
    ],
    "html": [
        re.compile(r"<!--.*?-->", re.DOTALL),  # HTML comments
    ],
    "java": [
        re.compile(r"//.*"),  # Java comments
        re.compile(r"/\*.*?\*/", re.DOTALL),  # Java multiline comments
    ],
    "javascript": [
        re.compile(r"//.*"),  # JavaScript comments
        re.compile(r"/\*.*?\*/", re.DOTALL),  # JavaScript multiline comments
    ],
    "json": [
        re.compile(r"//.*"),  # JSON comments
        re.compile(r"/\*.*?\*/", re.DOTALL),  # JSON multiline comments
    ],
    "makefile": [
        re.compile(r"#.*"),  # Makefile comments
    ],
    "markdown": [
        re.compile(r".*"),  # Anything is text
    ],
    "perl": [
        re.compile(r"#.*"),  # Perl comments
        re.compile(r"=pod.*?=cut", re.DOTALL),  # Perl pod
    ],
    "php": [
        re.compile(r"//.*"),  # PHP comments
        re.compile(r"/\*.*?\*/", re.DOTALL),  # PHP multiline comments
    ],
    "prolog": [
        re.compile(r"%.*"),  # Prolog comments
    ],
    "python": [
        re.compile(r"#.*"),  # Python comments
        re.compile(r'""".*?"""', re.DOTALL),  # Python docstrings
        re.compile(r"'''.*?'''", re.DOTALL),  # Python docstrings
    ],
    "r": [
        re.compile(r"#.*"),  # R comments
    ],
    "ruby": [
        re.compile(r"#.*"),  # Ruby comments
    ],
    "rust": [
        re.compile(r"//.*"),  # Rust comments
        re.compile(r"/\*.*?\*/", re.DOTALL),  # Rust multiline comments
    ],
    "scala": [
        re.compile(r"//.*"),  # Scala comments
        re.compile(r"/\*.*?\*/", re.DOTALL),  # Scala multiline comments
    ],
    "scheme": [
        re.compile(r";.*"),  # Scheme comments
    ],
    "shell": [
        re.compile(r"#.*"),  # Shell comments
    ],
    "smalltalk": [
        re.compile(r"\".*"),  # Smalltalk comments
    ],
    "sparql": [
        re.compile(r"#.*"),  # SPARQL comments
    ],
    "sql": [
        re.compile(r"--.*"),  # SQL comments
        re.compile(r"/\*.*?\*/", re.DOTALL),  # SQL multiline comments
    ],
    "swift": [
        re.compile(r"//.*"),  # Swift comments
        re.compile(r"/\*.*?\*/", re.DOTALL),  # Swift multiline comments
    ],
    "tex": [
        re.compile(r"%.*"),  # TeX comments
    ],
    "text": [
        re.compile(r".*"),  # Anything is text
    ],
    "text": [
        re.compile(r".*"),  # Anything is text
    ],
    "textile": [
        re.compile(r".*"),  # Anything is text
    ],
    "toml": [
        re.compile(r"#.*"),  # TOML comments
    ],
    "typescript": [
        re.compile(r"//.*"),  # TypeScript comments
        re.compile(r"/\*.*?\*/", re.DOTALL),  # TypeScript multiline comments
    ],
    "visual-basic": [
        re.compile(r"'.*"),  # Visual Basic comments
    ],
    "webassembly": [
        re.compile(r";;.*"),  # WebAssembly comments
    ],
    "xml": [
        re.compile(r"<!--.*?-->", re.DOTALL),  # XML comments
    ],
    "yaml": [
        re.compile(r"#.*"),  # YAML comments
    ],
}


def determine_natural_languages(code: str, prog_lang: str) -> list[str]:
    """
    Extract a list of natural languages that appear in comments and docstrings
    in a code snippet. `prog_lang` should be the programming language used in
    the code snippet.

    The README of this dataset states:
    > The following natural languages appear in the comments and docstrings from files
    > in the dataset: EN, ZH, FR, PT, ES, RU, DE, KO, JA, UZ, IT, ID, RO, AR, FA, CA,
    > HU, ML, NL, TR, TE, EL, EO, BN, LV, GL, PL, GU, CEB, IA, KN, SH, MK, UR, SV, LA,
    > JKA, MY, SU, CS, MN. This kind of data is essential for applications such as
    > documentation generation and natural-language-to-code translation.

    We try to verify this claim.
    """

    # Extract all comments from the code
    comments = []
    if prog_lang in COMMENT_MATCHERS:
        for matcher in COMMENT_MATCHERS[prog_lang]:
            comments += matcher.findall(code)
    all_comments = "\n".join(comments)

    # Try to identify the natural languages in the comments
    languages_and_probabilities = LANGUAGE_IDENTIFIER.rank(all_comments)
    # Filter out languages with probability > 0.01
    languages = [lang for lang, prob in languages_and_probabilities if prob > 0.01]
    return languages


def count_natural_languages(df: pd.DataFrame, prog_lang: str) -> dict[str, int]:
    """Count natural languages from a DataFrame."""
    language_counter = Counter()
    for code in df["content"]:
        if code is None:
            continue
        langs = determine_natural_languages(code, prog_lang)
        language_counter.update(langs)
    return dict(language_counter)


class ResultDict(TypedDict):
    column_info: dict[str, ColumnInfoDict]
    licenses: LicenseDict
    license_mismatch: int
    number_of_items: int
    timestamp: float


def process_file(path: Path) -> tuple[str, ResultDict]:
    """Process one file.

    Returns `(language, output)`, where `language` is the programming language
    of all data in the file, and `output` is a dictionary with the results of
    the processing.
    """

    # path looks like "../datasets/the-stack-dedup/data/c/data-00000-of-00126.parquet"
    # We extract the programming language from the path, e.g. `c`
    lang = path.parts[-2]

    df = pd.read_parquet(path)

    output = {
        "column_info": extract_generic_properties(df),
        "licenses": count_licenses(df),
        "license_mismatch": check_license_mismatch(df),
        "natural_languages": count_natural_languages(df, lang),
        "number_of_items": len(df),
        "timestamp": time.time(),
    }

    return (lang, output)


if __name__ == "__main__":
    in_container = True

    if len(sys.argv) > 1:
        data_path = sys.argv[1]
        glob = sys.argv[2]
        filetype = sys.argv[3]
        glob = "**/" + glob + "*." + filetype
        in_container = False
    else:
        data_path = "/tmp/inputs"
        data_dir = Path(data_path)
        filetype = "parquet"
        glob = "**/*." + filetype

    print(data_path, glob)

    output = process_files(data_path, glob)

    if in_container:
        with open("/tmp/outputs/computation_result.json", "w") as f:
            json.dump(output, f, indent=4, sort_keys=True)
    else:
        print(json.dumps(output, indent=4, sort_keys=True))
