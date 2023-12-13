# Itslearning-DL Tool

The Itslearning-DL Tool is a Python-based utility for downloading resources from the Itslearning platform.

## Overview

This tool allows users to:

- **Download Itslearning Resources:** Fetch various resources from Itslearning, such as documents or media files.
- **Customize Download Options:** Specify download paths, provide credentials, and fetch specific resources.

## Features

- Download resources from Itslearning by providing your credentials.
- Customize the output path for downloaded resources.
- Fetch new resources or update all including existing ones.

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/unterdrueckt/itslearning-dl.git
    ```

2. Navigate to the project directory:

    ```bash
    cd itslearning-dl
    ```

3. Install itslearning-dl:

    ```bash
    python install.py
    ```

## Usage

1. Run the tool with your Itslearning credentials:

    ```bash
    itslearning-dl -u YOUR_USERNAME -p YOUR_PASSWORD
    ```

    or

    ```bash
    ildl -u YOUR_USERNAME -p YOUR_PASSWORD
    ```

**Running without Installation:**  
If you prefer not to install the tool globally, you can [use the Itslearning-DL Tool without installation](useWithoutInstall.md). This method allows you to run the tool directly from the cloned repository.

### Help Command

For additional information on available commands and options, use the `-h` or `--help` command:

```bash
itslearning-dl -h
```

This will display a help message with a list of available options and their descriptions.

## Configuration

- **Credentials:** You can provide your Itslearning username and password as command-line arguments or set environment variables: `ITSLEARNING_USERNAME` and `ITSLEARNING_PASSWORD`.
- **Output Path:** By default, the tool saves downloaded resources to the `/out` directory. You can specify a custom path using the `--path` argument.

