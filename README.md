# GlorTransSub

![Platform](https://img.shields.io/badge/platform-Windows-blue)
![Status](https://img.shields.io/badge/status-experimental-orange)
![Python](https://img.shields.io/badge/python-3.9%2B-brightgreen)

---

## Overview

**GlorTransSub** is an experimental Windows application for capturing on-screen content and supporting real-time text processing and translation workflows.

It is intended for use cases such as subtitle translation, game text assistance, and other screen-based language support tools.

This repository represents an early-stage prototype focused on validating the core concept, system interaction, and future extensibility.

---

[Translation model review and offline OPUS-MT setup](docs/translation-models.md)

## Features

- Background application with system tray integration  
- Multi-monitor OCR, subtitle overlays, and Mouse Subtitle support
- Mouse-only mode with an independent Main Subtitle switch
- F8 pauses all OCR, translation API calls, and pending Voice playback
- Mouse and screen interaction handling  
- Early-stage text processing pipeline  
- Modular and extensible architecture  
- Standalone Windows executable (.exe) build support  

---

## Project Status

> **Warning**  
> This project is experimental and under active development.  
> Features may be incomplete, unstable, or subject to change.  
> This project is not recommended for production use.

---

## Planned Improvements

- OCR integration for on-screen text recognition  
- Automatic multi-language translation  
- Improved user interface and configuration options  
- Better background stability and resource management  
- Official Windows installer workflow  

---

## Technologies Used

| Item | Description |
|----|----|
| Language | Python |
| Environment | venv |
| Build Tool | PyInstaller |
| Platform | Windows |

---

## Windows Release (No installation required)

1. Download `GloSub-v1.1.2-Windows-x64.zip` from GitHub Releases.
2. Extract the entire ZIP to a normal writable folder.
3. Open `GloSub.exe`. Keep the `_internal` folder next to the EXE.

Python, pip, PyTorch, EasyOCR, Voice, and API client dependencies are already
included. OCR language models are downloaded automatically by EasyOCR the first
time a language is used; no manual installation command is required. User
settings and encrypted API credentials are stored under `%LOCALAPPDATA%\GloSub`.

The portable folder uses a bundled CPU PyTorch runtime so it works on Windows
PCs with or without a discrete GPU.

## Installation (Development Setup)

### Prerequisites

- Python **3.9+**
- Windows OS
- Git

Verify Python installation:
```bash
python --version

GlorTransSub (Experimental)

GlorTransSub is an experimental Windows application for capturing on-screen content and supporting real-time text processing and translation workflows.
It is intended for use cases such as subtitle translation, game text assistance, and other screen-based language support tools.

This repository represents an early-stage prototype focused on validating the core concept, system interaction, and future extensibility.

Features

Runs as a background application with system tray integration

Handles mouse and screen interaction events

Early-stage text processing pipeline for future OCR and translation integration

Modular and extensible architecture

Can be built as a standalone Windows executable (.exe) without requiring Python on the target machine

Project Status

Warning
This project is experimental and under active development.

Features may be incomplete or unstable

Behavior and structure may change without notice

Performance and long-term stability are not yet optimized

Not recommended for production use at this stage

Planned Improvements

OCR integration for on-screen text recognition

Automatic multi-language translation

Improved user interface and configuration options

Better background stability and resource management

Official Windows installer workflow

Technologies Used

Python

Virtual environments (venv)

Dependencies listed in requirements.txt

PyInstaller for building Windows executables

Installation (Development Setup)
Prerequisites

Python 3.9 or newer

Windows OS

Git

Verify Python installation:

python --version

Setup Virtual Environment

Clone the repository:

git clone https://github.com/adbosp/GlorTransSub.git
cd GlorTransSub


Create a virtual environment:

python -m venv .venv


Activate the virtual environment:

.venv\Scripts\activate


The terminal should display:

(.venv)

Install Dependencies
pip install -r requirements.txt


If needed, upgrade pip first:

python -m pip install --upgrade pip

Running the Application
python main.py

AI Translation

In Settings > General > Language & Translation, GloSub supports Google
Translate plus ChatGPT (OpenAI), Gemini, DeepSeek, Claude, and xAI (Grok).
Choose a provider, enter its API key, select or type a model, then use
Test AI Connection before saving. API keys saved in subtitle_config.json are
encrypted for the current Windows user with DPAPI; they are not stored as
plain text. If an AI request fails during translation, GloSub automatically
falls back to Google Translate for that subtitle.

AI Text-to-Speech

The Voice card supports Microsoft Edge TTS, OpenAI TTS, ElevenLabs,
Google Cloud Text-to-Speech, Microsoft Azure Speech, and Amazon Polly.
Each provider has its own editable model/engine, voice ID, region, and
credential fields. Use Test TTS Connection before enabling Voice. Secret
values (API keys, service-account JSON, and AWS credentials) are protected
with Windows DPAPI. Smart, Queue, Latest, audio caching, and language sync
continue to work with every provider.


Automatic GPU Acceleration

Before importing PyTorch, GloSub checks the computer automatically. On a
Windows PC with a supported NVIDIA GPU, it installs the pinned CUDA runtime
from requirements-gpu.txt and then opens the app. A small one-time progress
window is shown; the user does not need to run a pip command.

Computers without NVIDIA CUDA skip the GPU download and continue with CPU.
If installation fails while offline, GloSub continues on CPU, writes details
to %LOCALAPPDATA%\GloSub\gpu-setup.log, and retries later.


The application runs in the background and may display a system tray icon depending on the current implementation.

Build Windows Executable (Optional)
pyinstaller --onefile --noconsole main.py


The generated executable will be located in:

dist/

Notes

The virtual environment directory (.venv) is intentionally excluded from the repository

Always activate the virtual environment before running or building the project

If you encounter missing module errors, ensure all dependencies are installed inside the active virtual environment
# Vietnamese game/video dubbing

Settings → **Speech → Vietnamese** adds local Tiny ASR → OPUS-MT → Piper speech.
OCR pauses while dubbing. See [setup, output routing and limits](docs/speech-translation.md).
