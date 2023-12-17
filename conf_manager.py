import yaml
import os, sys, subprocess

class ConfManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.conf = None
        self.status = self.load_conf()

    def load_conf(self):
        """Load a YAML configuration file."""
        try:
            with open(self.file_path, 'r') as f:
                self.conf = yaml.safe_load(f)
            return "loaded"
        except FileNotFoundError:
            return "missing"
        except yaml.YAMLError:
            return "corrupted"

    def get_status(self):
        """Get the status of the configuration file."""
        return self.status

    def get_param(self, param):
        """Get a parameter from the configuration."""
        if self.conf is not None:
            return self.conf.get(param)
        else:
            return None

    def clear_conf(self):
        """Clear a YAML configuration file."""
        with open(self.file_path, 'w') as f:
            f.write("")

    def open_conf(self, opt_file_path=None):
            """Open the configuration file with the default application."""
            file_path = opt_file_path or self.file_path
            if os.path.exists(file_path):
                # Use the default application to open the file
                if sys.platform == "win32":
                    os.startfile(file_path)
                else:
                    opener = "open" if sys.platform == "darwin" else "xdg-open"
                    subprocess.call([opener, file_path])
            else:
                print(f"Configuration file {file_path} does not exist.")

    def create_example_conf(self, open_conf):
        """Create an example YAML configuration file with comments."""
        with open(self.file_path, 'w') as f:
            f.write("# itslearning-dl config\n\n")
            f.write("# Your itslearning username\n")
            f.write("ITSLEARNING_USERNAME: ''\n\n")
            f.write("# Your itslearning password\n")
            f.write("ITSLEARNING_PASSWORD: ''\n\n")
            f.write("# Your itslearning instance\n")
            f.write("ITSLEARNING_INSTANCE: ''\n\n")
            f.write("# Output directory\n")
            f.write("# (leave empty to use the default /out)\n")
            f.write("#ITSLEARNINGDL_OUT: ''\n\n")
            f.write("# Enable or disable log file (default: true)\n")
            f.write("#ITSLEARNINGDL_LOGFILE: true\n\n")
            f.write("# Set number of worker processes to use for downloading (default: 20)\n")
            f.write("#WORKER_COUNT: 20\n\n")
            f.write("# Set true to refetch all elements every time and ignore the previous state (default: false)\n")
            f.write("# Note: This is not recommended as it will cause all data to be re-downloaded every time,\n")
            f.write("# which can be slow and inefficient. Please use this setting judiciously.\n")
            f.write("#IGNORE_STATE: true\n\n")
            f.write("# Set the log level for the log file and console out (default: info)\n")
            f.write("# Note: Setting the log level higher than 'info', such as 'debug', and enabling the log file\n")
            f.write("# could potentially save sensitive information like credentials or session details in the log file.\n")
            f.write("# Please ensure the security of the log file if you choose to enable this setting.\n")
            f.write("#LOGLVL: debug\n")

        if(open_conf):
            self.open_conf()
