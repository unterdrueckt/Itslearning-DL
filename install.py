import subprocess
import sys
import os

def generate_distribution_package():
    try:
        subprocess.check_call([sys.executable, "setup.py", "sdist"])
        print("Package distribution created successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Failed to create package distribution: {e}")
        sys.exit(1)

def install_package(package_path):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_path])
        print("Installation successful!")
    except subprocess.CalledProcessError as e:
        print(f"Installation failed: {e}")
        sys.exit(1)

def add_to_windows_path(script_path):
    try:
        subprocess.check_call(['setx', 'PATH', f'%PATH%;{script_path}'])
        print("Path added to system PATH!")
    except subprocess.CalledProcessError as e:
        print(f"Failed to add path to system PATH: {e}")
        sys.exit(1)

def add_to_linux_path(script_path):
    try:
        with open(os.path.expanduser("~/.bashrc"), "a") as bashrc:
            bashrc.write(f'export PATH=$PATH:{script_path}\n')
        print("Path added to system PATH!")
    except Exception as e:
        print(f"Failed to add path to system PATH: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Generate distribution package
    generate_distribution_package()

    # Find the generated package
    dist_folder = os.path.join(os.getcwd(), "dist")
    package_files = os.listdir(dist_folder)
    package_path = None

    for file in package_files:
        if file.endswith(".tar.gz"):
            package_path = os.path.join(dist_folder, file)
            break

    if not package_path:
        print("Package not found!")
        sys.exit(1)

    # Install the package
    install_package(package_path)

    # Add the directory to PATH based on the system
    if sys.platform.startswith('win'):
        add_to_windows_path(os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "Python", "Python311", "Scripts"))
    elif sys.platform.startswith('linux'):
        add_to_linux_path(os.path.join(os.path.expanduser("~"), ".local", "bin"))
    else:
        print("Unsupported platform. Couldn't add to PATH.")
