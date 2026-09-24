#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2021 by The qTox Project Contributors
# Copyright © 2024-2025 The TokTok team
import argparse
import json
import subprocess  # nosec
import sys
from dataclasses import dataclass

QTOX_GIT_URL = "https://github.com/TokTok/qTox"


@dataclass
class Config:
    flathub_manifest: str
    output: str
    git_tag: str


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="""
    Point the qTox flathub descriptor to the local qTox sources.
    If the descriptor is already pointing at the local sources, do the inverse.
    """)
    parser.add_argument(
        "--flathub-manifest",
        help="Path to flathub manifest",
        required=True,
    )
    parser.add_argument(
        "--output",
        help="Output manifest path",
        required=True,
    )
    parser.add_argument(
        "--git-tag",
        help="Git tag to use for the qTox version",
        required=False,
        default=None,
    )
    return Config(**vars(parser.parse_args()))


def commit_from_tag(url: str, tag: str) -> str:
    git_output = subprocess.run(  # nosec
        ["git", "ls-remote", url, f"{tag}^{{}}"],
        check=True,
        stdout=subprocess.PIPE,
    )
    return git_output.stdout.split(b"\t")[0].decode()


def git_tag() -> str:
    git_output = subprocess.run(  # nosec
        ["git", "describe", "--tags", "--abbrev=0"],
        check=True,
        stdout=subprocess.PIPE,
    )
    return git_output.stdout.decode().strip()


def localize_flathub_descriptor(config: Config) -> None:
    with open(config.flathub_manifest) as f:
        flathub_descriptor = json.load(f)

    # Update the flathub descriptor for qTox to point sources at /qtox/.
    for module in flathub_descriptor["modules"]:
        if module["name"] == "qTox":
            if module["sources"][0]["type"] == "git":
                module["sources"] = [{
                    "type": "dir",
                    "path": "/qtox/",
                }]
            else:
                tag = config.git_tag or git_tag()
                commit = commit_from_tag(QTOX_GIT_URL, tag)
                # Reverse if we run the script twice.
                module["sources"] = [{
                    "type": "git",
                    "url": QTOX_GIT_URL,
                    "commit": commit,
                    "tag": tag,
                }]

    with open(config.output, "w") as f:
        json.dump(flathub_descriptor, f, indent=2)
        f.write("\n")


def main(config: Config) -> None:
    localize_flathub_descriptor(config)


if __name__ == "__main__":
    main(parse_args())
