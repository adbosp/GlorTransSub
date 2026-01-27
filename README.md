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
