#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2025 The TokTok team
import argparse
import asyncio
import hashlib
import itertools
import json
import os
import re
import subprocess  # nosec
from dataclasses import dataclass
from typing import Any
from typing import AsyncGenerator
from typing import Generator
from typing import Iterable
from typing import Optional
from typing import TypeVar

T = TypeVar("T")


@dataclass
class Config:
    cache_file: str
    root_path: str
    compile_commands_dir: str
    fatal_errors: bool
    wait: bool


def _parse_args() -> Config:
    parser = argparse.ArgumentParser(description="""
    Run clangd on the project and print diagnostics.
    """)
    root_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    parser.add_argument(
        "--cache-file",
        help="Path to the lsp_tidy cache file",
        default=os.path.join(root_path, ".lsp_tidy_cache"),
    )
    parser.add_argument(
        "--root-path",
        help="Root path of the project",
        default=root_path,
    )
    parser.add_argument(
        "--compile-commands-dir",
        help="Directory containing compile_commands.json",
        default=os.path.join(root_path, "_build-release"),
    )
    parser.add_argument(
        "--fatal-errors",
        help="Exit on error diagnostics (default is to continue)",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--wait",
        help="Wait for clangd to exit",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    return Config(**vars(parser.parse_args()))


@dataclass
class File:
    root: str
    path: str

    def __init__(self, config: Config, path: str) -> None:
        self.root = config.root_path
        self.path = os.path.relpath(path, config.root_path)

    @staticmethod
    def from_uri(config: Config, uri: str) -> "File":
        if not uri.startswith("file://"):
            raise ValueError(f"Invalid URI: {uri}")
        return File(config, uri[len("file://"):])

    def __hash__(self) -> int:
        return hash(self.fullpath)

    @property
    def fullpath(self) -> str:
        return os.path.join(self.root, self.path)

    @property
    def uri(self) -> str:
        return f"file://{self.fullpath}"


class Preprocessor:
    # Hashes of the preprocessed files
    _hashes: dict[str, str]
    # List of all source files (not in _build)
    _sources: tuple[File, ...]

    def __init__(self, config: Config) -> None:
        # Walk config.root_path, find all .cpp, .h, .mm files and load them.
        loaded_files: dict[str, str] = {}
        sources: list[File] = []
        print("Loading files...", flush=True)
        for root, _, files in os.walk(config.root_path):
            for filename in files:
                if "third_party" in root:
                    continue
                if filename.endswith((".cpp", ".h", ".mm", ".moc")):
                    if filename.startswith("qrc_") or filename in (
                            "moc_predefs.h",
                            "mocs_compilation.cpp",
                    ):
                        continue
                    if filename in loaded_files:
                        raise ValueError("Duplicate file: "
                                         f"{filename} ({root})")
                    if "_build" not in root:
                        sources.append(
                            File(config, os.path.join(root, filename)))
                    with open(os.path.join(root, filename), "r") as f:
                        loaded_files[filename] = f.read()
        self._sources = tuple(set(sources))
        print(f"Preprocessing {len(loaded_files)} files...", flush=True)
        # Map from filename to list of #include base-names.
        includes: dict[str, list[str]] = {}
        for filename, content in loaded_files.items():
            includes[filename] = []
            for line in content.split("\n"):
                if match := re.match(r"#\s*include\s*\"(.+)\"", line):
                    includes[filename].append(os.path.basename(match.group(1)))
        # Preprocess all files.
        self._hashes = {}
        for filename in loaded_files.keys():
            self._hashes[filename] = self._sha256(loaded_files, includes,
                                                  filename)

    def _sha256(
        self,
        loaded_files: dict[str, str],
        includes: dict[str, list[str]],
        filename: str,
    ) -> str:
        """Recursively resolve all includes, hash the result."""
        if filename not in includes:
            raise ValueError(f"File not found: {filename}")
        hashable = [loaded_files[filename]]
        hashable.extend(
            self._sha256(loaded_files, includes, include)
            for include in includes[filename])
        return hashlib.sha256("".join(hashable).encode()).hexdigest()

    def sha256(self, file: File) -> str:
        return self._hashes[os.path.basename(file.path)]

    def identifier(self, file: File) -> str:
        return f"{file.path}@{self.sha256(file)}"

    @property
    def sources(self) -> tuple[File, ...]:
        return self._sources


@dataclass
class Diagnostic:
    severity: int
    message: str
    line_start: int
    line_end: int
    column_start: int
    column_end: int

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Diagnostic":
        return Diagnostic(
            severity=int(data["severity"]),
            message=data["message"],
            line_start=data["range"]["start"]["line"],
            line_end=data["range"]["end"]["line"],
            column_start=data["range"]["start"]["character"],
            column_end=data["range"]["end"]["character"],
        )

    def to_dict(self) -> dict[str, str | int | dict[str, dict[str, int]]]:
        return {
            "severity": self.severity,
            "message": self.message,
            "range": {
                "start": {
                    "line": self.line_start,
                    "character": self.column_start,
                },
                "end": {
                    "line": self.line_end,
                    "character": self.column_end,
                },
            },
        }


@dataclass
class Clangd:
    _config: Config
    _rpc_id: Generator[int, None, None]
    _process: asyncio.subprocess.Process

    @staticmethod
    async def create(config: Config) -> "Clangd":
        return Clangd(
            config,
            (n for n in itertools.count(start=1)),
            await asyncio.create_subprocess_exec(
                "clangd",
                f"--compile-commands-dir={config.compile_commands_dir}",
                "--background-index",
                "--clang-tidy",
                "--log=error",
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
            ),
        )

    async def wait(self) -> int:
        return await self._process.wait()

    def __enter__(self) -> "Clangd":
        return self

    def __exit__(self, exc_type: object, exc_value: object,
                 traceback: object) -> None:
        self._process.terminate()

    def _rpc(self, rpc_id: Optional[int], method: str,
             params: dict[str, Any]) -> None:
        # Send a request to clangd
        content = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            **({
                "id": rpc_id
            } if rpc_id is not None else {}),
        }).encode()
        if not self._process.stdin:
            raise RuntimeError("Process has no stdin")
        self._process.stdin.write(
            f"Content-Length: {len(content)}\r\n\r\n".encode())
        self._process.stdin.write(content)

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._rpc(None, method, params)

    async def _receive(self) -> dict[str, Any]:
        if not self._process.stdout:
            raise RuntimeError("Process has no stdout")
        line = await self._process.stdout.readline()
        while not line.startswith(b"Content-Length: "):
            if self._process.returncode is not None:
                return {}
            line = await self._process.stdout.readline()
        content_length = int(line[len(b"Content-Length: "):])
        await self._process.stdout.readline()
        content = await self._process.stdout.read(content_length)
        response: dict[str, Any] = json.loads(content.decode())
        return response

    async def _invoke(
        self,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        self._rpc(next(self._rpc_id), method, params)
        # Receive the response
        result: dict[str, Any] = (await self._receive())["result"]
        return result

    async def initialize(self) -> dict[str, Any]:
        result = await self._invoke(
            "initialize",
            {
                "processId":
                os.getpid(),
                "rootUri":
                f"file://{self._config.root_path}",
                "capabilities": {
                    "textDocument": {
                        "publishDiagnostics": {
                            "relatedInformation": True,
                            "versionSupport": True,
                            "codeDescriptionSupport": True,
                            "dataSupport": True,
                        },
                    },
                },
                "clientInfo": {
                    "name": "lsp_tidy",
                    "version": "0.1",
                },
                "workspaceFolders": [{
                    "uri": f"file://{self._config.root_path}",
                    "name": "workspace"
                }],
            },
        )
        capabilities: dict[str, Any] = result["capabilities"]
        return capabilities

    def open(self, file: File) -> None:
        with open(file.fullpath, "r") as f:
            self._notify(
                "textDocument/didOpen",
                {
                    "textDocument": {
                        "uri": file.uri,
                        "languageId": "cpp",
                        "version": 1,
                        "text": f.read(),
                    },
                },
            )

    def _close(self, uri: str) -> None:
        self._notify(
            "textDocument/didClose",
            {
                "textDocument": {
                    "uri": uri,
                },
            },
        )

    async def receive_diagnostics(
        self, ) -> AsyncGenerator[tuple[str, list[Diagnostic]], None]:
        while self._process.returncode is None:
            response = await self._receive()
            if not response:
                break
            if response["method"] == "textDocument/publishDiagnostics":
                uri = response["params"]["uri"]
                diags = [
                    Diagnostic.from_dict(diag)
                    for diag in response["params"]["diagnostics"]
                ]
                yield uri, diags


async def _read_into_queue(
    task: AsyncGenerator[T, None],
    queue: asyncio.Queue[T],
    done: asyncio.Semaphore,
) -> None:
    async for item in task:
        await queue.put(item)
    # All items from this task are in the queue, decrease semaphore by one.
    await done.acquire()


async def _join(
        *generators: AsyncGenerator[T, None]) -> AsyncGenerator[T, None]:
    queue: asyncio.Queue[T] = asyncio.Queue()
    done_semaphore = asyncio.Semaphore(len(generators))

    # Read from each given generator into the shared queue.
    produce_tasks = [
        asyncio.create_task(_read_into_queue(task, queue, done_semaphore))
        for task in generators
    ]

    # Read items off the queue until it is empty and the semaphore value is down to zero.
    while not done_semaphore.locked() or not queue.empty():
        try:
            yield await asyncio.wait_for(queue.get(), 0.001)
        except TimeoutError:
            continue

    # Not strictly needed, but usually a good idea to await tasks, they are already finished here.
    try:
        await asyncio.wait_for(asyncio.gather(*produce_tasks), 0)
    except TimeoutError:
        raise NotImplementedError(
            "Impossible state: expected all tasks to be exhausted")


class CachingClangd:
    sem: asyncio.Semaphore
    _cache_path: str
    _cache: dict[str, list[Diagnostic]]
    _clangd: Clangd
    _pp: Preprocessor

    def __init__(self, config: Config, clangd: Clangd,
                 pp: Preprocessor) -> None:
        self._sem = asyncio.Semaphore(os.cpu_count() or 4)
        self._cache_path = config.cache_file
        self._clangd = clangd
        self._pp = pp
        if os.path.exists(self._cache_path):
            with open(self._cache_path, "r") as f:
                self._cache = {
                    sha: [Diagnostic.from_dict(diag) for diag in diags]
                    for sha, diags in json.load(f).items()
                }
        else:
            self._cache = {}

    def _save(self) -> None:
        with open(self._cache_path + ".new", "w") as f:
            json.dump(
                {
                    sha: [diag.to_dict() for diag in diags]
                    for sha, diags in self._cache.items()
                },
                f,
                indent=2,
            )
        os.rename(self._cache_path + ".new", self._cache_path)

    async def _diagnostics_for(
            self,
            file: File) -> AsyncGenerator[tuple[File, list[Diagnostic]], None]:
        async with self._sem:
            sha = self._pp.identifier(file)
            if sha not in self._cache:
                print(f"Analyzing {file.path}", flush=True)
                self._clangd.open(file)
            else:
                yield file, self._cache[sha]

    async def _receive_diagnostics(
        self, todo: dict[str, File]
    ) -> AsyncGenerator[tuple[File, list[Diagnostic]], None]:
        async for uri, diags in self._clangd.receive_diagnostics():
            file = todo.get(uri, None)
            if not file:
                continue
            self._cache[self._pp.identifier(file)] = diags
            self._save()
            yield file, diags

    async def diagnostics(
        self, files: tuple[File, ...]
    ) -> AsyncGenerator[tuple[File, list[Diagnostic]], None]:
        todo = {file.uri: file for file in files}
        results = _join(
            *(self._diagnostics_for(file) for file in files),
            self._receive_diagnostics(todo),
        )
        async for result in results:
            if result is not None:
                file, diags = result
                yield file, diags
                del todo[file.uri]
                if not todo:
                    break


def _color(severity: int, msg: str) -> str:
    if severity == 1:
        # Red
        return f"\033[91m{msg}\033[0m"
    if severity == 2:
        # Yellow
        return f"\033[93m{msg}\033[0m"
    if severity == 3:
        # Light blue
        return f"\033[94m{msg}\033[0m"
    if severity == 4:
        # Grey
        return f"\033[90m{msg}\033[0m"
    return msg


def _bold(msg: str) -> str:
    return f"\033[1m{msg}\033[0m"


def _severity(diag: Diagnostic) -> str:
    if diag.severity == 1:
        return _color(diag.severity, "error")
    if diag.severity == 2:
        return _color(diag.severity, "warning")
    if diag.severity == 3:
        return _color(diag.severity, "information")
    if diag.severity == 4:
        return _color(diag.severity, "hint")
    return f"severity {diag.severity}"


def _print_diagnostic(file: File, diagnostics: Iterable[Diagnostic]) -> None:
    with open(file.fullpath, "r") as f:
        lines = f.readlines()
        for diag in diagnostics:
            severity = _severity(diag)
            line_start = diag.line_start
            column_start = diag.column_start
            column_end = diag.column_end
            location = f"{file.path}:{line_start + 1}:{column_start + 1}:"
            message = [f"{_bold(location)} {severity}: {diag.message}"]
            if line_start > len(lines):
                raise ValueError(f"Invalid line number {line_start}: "
                                 f"{file.path} only has {len(lines)} lines")
            if line_start < len(lines):
                message.append(lines[line_start].rstrip())
                message.append(" " * column_start + "^" *
                               (column_end - column_start))
            print("\n".join(message), flush=True)


async def main(config: Config) -> None:
    preprocessor = Preprocessor(config)
    with await Clangd.create(config) as clangd:
        await clangd.initialize()

        cache = CachingClangd(config, clangd, preprocessor)

        has_errors = False
        # Print diagnostics as they come in
        async for file, diags in cache.diagnostics(preprocessor.sources):
            _print_diagnostic(file, diags)
            has_errors |= any(diag.severity == 1 for diag in diags)
            if config.fatal_errors and has_errors:
                exit(1)
        if has_errors:
            exit(1)

    if config.wait:
        # Wait for at most 5 minutes for clangd to exit
        await asyncio.wait_for(clangd.wait(), 300)


if __name__ == "__main__":
    asyncio.run(main(_parse_args()))
