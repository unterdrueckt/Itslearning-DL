# Using Itslearning-DL Tool without Installation

If you prefer not to install the Itslearning-DL Tool globally, you can run it directly from the cloned repository.

## Prerequisites

- Python 3.x installed on your system.
- Git installed on your system to clone the repository.

## Usage

1. Clone the Itslearning-DL repository:

    ```bash
    git clone https://github.com/unterdrueckt/itslearning-dl.git
    ```

2. Navigate to the project directory:

    ```bash
    cd itslearning-dl
    ```

3. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Run the Itslearning-DL Tool with your Itslearning credentials:

    ```bash
    python itslearning_dl.py -u YOUR_USERNAME -p YOUR_PASSWORD --install False --path /path/to/output
    ```

## Notes

- This method runs the tool directly from the cloned repository without installing it globally on your system and without creating itslearning-dl folder.
- Make sure to satisfy the prerequisites and install dependencies before using the tool.