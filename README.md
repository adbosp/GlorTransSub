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

## Features

- Background application with system tray integration  
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


The application runs in the background and may display a system tray icon depending on the current implementation.

Build Windows Executable (Optional)
pyinstaller --onefile --noconsole main.py


The generated executable will be located in:

dist/

Notes

The virtual environment directory (.venv) is intentionally excluded from the repository

Always activate the virtual environment before running or building the project

If you encounter missing module errors, ensure all dependencies are installed inside the active virtual environment
