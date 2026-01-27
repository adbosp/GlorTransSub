GlorTransSub (Experimental)

GlorTransSub is an experimental Windows application designed to capture on-screen content and support text processing and translation workflows in real time.
The project is intended for scenarios such as subtitle translation, game text assistance, and other screen-based language support tools.

This repository represents an early-stage prototype, focusing on validating the core concept, system interaction, and future extensibility.

Features

Background application with system tray integration
The application runs in the background and can be controlled via a system tray icon.

Mouse and screen interaction handling
Supports capturing mouse events and screen-related triggers for text processing workflows.

Text processing pipeline (early stage)
Provides a foundation for:

extracting on-screen text,

preprocessing textual data,

integrating translation or analysis engines in future versions.

Modular and extensible design
The codebase is structured to allow easy integration of additional components such as OCR engines, translation APIs, or AI-based processing.

Windows executable build support
The project can be packaged into a standalone Windows executable (.exe) without requiring a Python runtime on the target machine.

Project Status

Important Notice: This is an experimental / prototype version.

The application is under active development.

Features may be incomplete, unstable, or subject to change.

Performance and long-term stability have not yet been optimized.

This project is not recommended for production use at this stage.

Planned Improvements

Integration of OCR for on-screen text recognition.

Automatic multi-language translation support.

Improved user interface and configuration options.

Better background stability and resource management.

Official installer and distribution workflow for Windows.

Technologies Used

Python

Virtual environments (venv)

Third-party libraries listed in requirements.txt

PyInstaller for building Windows executables

Notes

The repository does not include any virtual environment directories (.venv).

Dependencies must be installed manually using:

pip install -r requirements.txt

Installation (Development Setup)

This project uses a Python virtual environment (venv) to manage dependencies.
Please follow the steps below to set up the development environment locally.

Prerequisites

Python 3.9+ (recommended)

Windows operating system

Git

Make sure Python is available in your system path:

python --version

Setup Virtual Environment

Clone the repository:

git clone https://github.com/adbosp/GlorTransSub.git
cd GlorTransSub


Create a virtual environment:

python -m venv .venv


Activate the virtual environment (Windows):

.venv\Scripts\activate


After activation, your terminal should show:

(.venv)

Install Dependencies

Install all required dependencies using requirements.txt:

pip install -r requirements.txt


If pip is outdated, upgrade it first:

python -m pip install --upgrade pip

Running the Application

Run the application using:

python main.py


The application will start in the background and may display a system tray icon depending on the current implementation.

Build Windows Executable (Optional)

To build a standalone Windows executable:

pyinstaller --onefile --noconsole main.py


The generated executable will be located in:

dist/

Notes

The virtual environment directory (.venv) is intentionally excluded from the repository.

Always activate the virtual environment before running or building the project.

If you encounter missing module errors, ensure all dependencies are installed correctly inside the active virtual environment.
