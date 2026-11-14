# Third-party notices

Meeting Report is licensed under the GNU Affero General Public License v3.0
(AGPL-3.0-only, see [LICENSE](LICENSE)).

This repository does not include third-party code. `install.sh` downloads the
packages below from PyPI and Homebrew, and the app downloads a speech model on
the first run. Each component keeps its own license. The license text of each
Python package is in its folder under `.venv/lib/python3.*/site-packages/`
after installation.

The versions below are the versions that were installed when this file was
written. Newer versions can have different terms. Check them before you
redistribute a build.

## Speech models

The app downloads one of these models from Hugging Face on the first
speech-to-text run. The models are not part of this repository.

| Model | Source | License |
|---|---|---|
| Whisper large-v3-turbo ("Fast") | OpenAI, converted to MLX by `mlx-community` | MIT |
| Whisper large-v3 ("Accurate") | OpenAI, `mlx-community/whisper-large-v3-mlx` | MIT |

Whisper is a name of OpenAI. Meeting Report is not affiliated with or endorsed
by OpenAI.

## System tools

These tools are installed separately with Homebrew. They are not bundled.

| Tool | Use | License |
|---|---|---|
| [ffmpeg](https://ffmpeg.org) | Decode audio and video, remove silences | LGPL-2.1-or-later; the Homebrew build includes GPL parts (GPL-2.0-or-later) |
| [uv](https://github.com/astral-sh/uv) | Create the Python environment | MIT OR Apache-2.0 |

If you distribute a build that bundles ffmpeg, you must also follow the
ffmpeg license and include its source or a written offer for it.

## Direct Python dependencies

From `app/requirements.txt`.

| Package | Version | License |
|---|---|---|
| mlx-whisper | 0.4.3 | MIT |
| anthropic | 2.7.0 | Apache-2.0 |
| python-docx | 1.2.0 | MIT |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| huggingface_hub | 2.4.0 | Apache-2.0 |
| fastapi | 0.162.2 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| pywebview | 6.2.1 | BSD-3-Clause |

## Indirect Python dependencies

Packages that the direct dependencies install.

| Package | Version | License |
|---|---|---|
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.16.0 | MIT |
| bottle | 0.13.4 | MIT |
| certifi | 2026.10.23 | MPL-2.0 |
| charset-normalizer | 3.5.2 | MIT |
| click | 8.5.1 | BSD-3-Clause |
| docstring_parser | 0.18.0 | MIT |
| filelock | 4.2.10 | MIT |
| fsspec | 2026.9.0 | BSD-3-Clause |
| h11 | 0.16.0 | MIT |
| hf-xet | 1.8.0 | Apache-2.0 |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpcore2 | 2.16.0 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| httpx2 | 2.16.0 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| Jinja2 | 3.1.6 | BSD-3-Clause |
| jiter | 0.19.0 | MIT |
| llvmlite | 0.50.0 | BSD-2-Clause AND Apache-2.0 WITH LLVM-exception |
| lxml | 6.1.3 | BSD-3-Clause |
| MarkupSafe | 3.0.4 | BSD-3-Clause |
| mlx | 0.32.4 | MIT |
| mlx-metal | 0.32.4 | MIT |
| more-itertools | 11.2.1 | MIT |
| mpmath | 1.3.0 | BSD-3-Clause |
| networkx | 3.7 | BSD-3-Clause |
| numba | 0.68.1 | BSD-2-Clause |
| opentelemetry-api | 1.45.2 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| proxy_tools | 0.1.0 | MIT |
| pydantic | 2.14.3 | MIT |
| pydantic_core | 2.50.4 | MIT |
| pyobjc-core | 13.0 | MIT |
| pyobjc-framework-Cocoa | 13.0 | MIT |
| pyobjc-framework-Quartz | 13.0 | MIT |
| pyobjc-framework-Security | 13.0 | MIT |
| pyobjc-framework-UniformTypeIdentifiers | 13.0 | MIT |
| pyobjc-framework-WebKit | 13.0 | MIT |
| PyYAML | 6.0.3 | MIT |
| regex | 2026.11.9 | Apache-2.0 AND CNRI-Python |
| requests | 2.34.2 | Apache-2.0 |
| scipy | 1.18.1 | BSD-3-Clause |
| setuptools | 84.2.1 | MIT |
| sniffio | 1.3.1 | MIT OR Apache-2.0 |
| starlette | 1.10.0 | BSD-3-Clause |
| sympy | 1.14.0 | BSD-3-Clause |
| tiktoken | 0.14.0 | MIT |
| torch | 2.15.0 | BSD-3-Clause, with parts under Apache-2.0, BSD-2-Clause, BSL-1.0, ISC, MIT and Zlib |
| tqdm | 4.70.1 | MPL-2.0 AND MIT |
| truststore | 0.10.5 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| typing-inspection | 0.4.5 | MIT |
| urllib3 | 2.8.0 | MIT |

## Development dependencies

From `requirements-dev.txt`. Only used to run the tests.

| Package | Version | License |
|---|---|---|
| pytest | 9.2.0 | MIT |
| iniconfig | 2.3.1 | MIT |
| pluggy | 1.7.0 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
