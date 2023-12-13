import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote, quote_plus, quote
import re
from pathlib import Path
import traceback
import os
import signal
import sys
import json
import datetime
import time
import logging
import argparse
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from dotenv import load_dotenv

sys_path = Path.home() / "Documents" / "itslearning-dl"
state_path = os.path.join(sys_path, 'state.json')
env_path = os.path.join(sys_path, '.env')
env_loaded = load_dotenv(env_path)
output_folder = Path(os.getenv("ITSLEARNINGDL_OUT") or os.path.join(sys_path, 'out'))

# Create the parser
parser = argparse.ArgumentParser(description="ItsLearning-DL TOOL.")

# Add the arguments with improved help texts
parser.add_argument('-u', '--username', type=str, default=os.getenv("ITSLEARNING_USERNAME"), help='Set your Itslearning username (default: value from environment variable ITSLEARNING_USERNAME)')
parser.add_argument('-p', '--password', type=str, default=os.getenv("ITSLEARNING_PASSWORD"), help='Set your Itslearning password (default: value from environment variable ITSLEARNING_PASSWORD)')
parser.add_argument('-o', '--path', type=str, default=output_folder, help=f'Set the output folder for downloaded resources (default (/out or env): {output_folder})')
parser.add_argument('-a', '--all', default=False, action='store_true', help='Force refetch of all elements')
parser.add_argument('-e', '--env', default=False, action='store_true', help='Open .env config file')
parser.add_argument('-i', '--install', default=True, action='store_true', help='Create conf folder')
parser.add_argument('--instance', type=str, default=os.getenv("ITSLEARNING_INSTANCE"), help='Set the Itslearning API instance (default: value from environment variable ITSLEARNING_INSTANCE)')
parser.add_argument("--loglvl", choices=["debug", "info", "warning", "error", "critical"], default="info", help="Set the logging level (default: info)")

# Parse the arguments
args = parser.parse_args()

# Set up logging with colored output
LOG_COLORS = {
    'debug': '\033[94m',  # Blue
    'info': '\033[92m',   # Green
    'warning': '\033[93m',  # Yellow
    'error': '\033[91m',   # Red
    'critical': '\033[95m'  # Purple
}

log_format = f"%(levelname)s: %(message)s"
logging.basicConfig(level=logging.getLevelName(args.loglvl.upper()), format=log_format)

class ColoredFormatter(logging.Formatter):
    def format(self, record):
        levelname = record.levelname
        colored_levelname = f"{LOG_COLORS[levelname.lower()]}{levelname}\033[0m"
        record.levelname = colored_levelname
        return super().format(record)

console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter(log_format))

logger = logging.getLogger()
logger.handlers = []
logger.addHandler(console_handler)

username = args.username
password = args.password
output_folder = args.path
refetch = args.all
open_env = args.env
install_sys = args.install
itslearning_instance = args.instance
user_agent = "com.itslearning.itslearningintapp 3.7.1 (HONOR BLN-L21 / Android 9)"

headers = {
    "User-Agent": user_agent
}

def signal_handler(sig, frame):
    logging.critical("The process was interrupted. The current state might be corrupted or inaccurate.")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def remove_state_file():
    logging.info("Remove state.json to download all elements")
    os.remove(state_path)

def create_env_file(env_path, open_file=True):
    try:
        # Ensure the directory exists
        os.makedirs(env_path, exist_ok=True)

        # Construct the full path to the .env file
        env_file_path = os.path.join(env_path, '.env')

        # Check if the .env file already exists
        if not os.path.isfile(env_file_path):
            logging.info(f"Create .env")
            with open(env_file_path, 'w') as f:
                f.write('ITSLEARNING_USERNAME=\n')
                f.write('ITSLEARNING_PASSWORD=\n')
                f.write('ITSLEARNING_INSTANCE=\n')
                f.write('# leave empty to use the default out folder\n')
                f.write('ITSLEARNINGDL_OUT=\n')
            open_env_file()
        else:
            logging.debug(f".env file already exists at {env_file_path}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

def open_env_file(env_path):
    try:
        # Construct the full path to the .env file
        env_file_path = os.path.join(env_path, '.env')

        # Check if the .env file already exists
        if os.path.isfile(env_file_path):
            logging.info(f"Open .env file")
            os.startfile(env_file_path)
        else:
            logging.warning(f".env file does not exist at {env_file_path} and cannot be opened")
    except Exception as e:
        logging.error(f"An error occurred: {e}")


def extract_filename(response):  # Decodes "Content-Disposition" header to get filename
    filename = ""
    disposition = response.headers.get('Content-Disposition')
    if disposition:
        filename_regex = re.compile(
            r'filename[^;=\n]*=(([\'"]).*?\2|[^\;\n]*)')
        matches = filename_regex.search(disposition)
        if matches and matches.group(1):
            filename = matches.group(1).replace("'", "").replace('"', '')
    return unquote(filename)


def sanitize_path(raw):  # Turn " / Example path" to "/Example Path"
    return re.sub(r'\s*?/\s*', "/", raw)

# Downloads a binary file from a requests response
def download_response(response, dest_path):
    local_filename = extract_filename(response)
    dest_path = dest_path.lstrip('/')
    full_dir_path = os.path.join(output_folder, dest_path)
    full_file_path = os.path.join(full_dir_path, local_filename)
    Path(full_dir_path).mkdir(parents=True, exist_ok=True)
    logging.debug(f"-> DL Element - status: {response.status_code}; filepath: {full_file_path}")
    if response.status_code == 200:
        with open(full_file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)


# Login with username and password to get an authtoken
def get_access_token(username, password):
    url = itslearning_instance + "/restapi/oauth2/token"
    payload = f"client_id=10ae9d30-1853-48ff-81cb-47b58a325685&grant_type=password&username={quote_plus(username)}&password={quote_plus(password)}"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": user_agent
    }

    try:
        response = requests.post(url, data=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            return None
    except requests.RequestException as e:
        logging.error(f"Login request exception: {e}")
        return None
    


# Fetch and download a file element
def download_element(element_id, dest_path, access_token):
    # Request the SSO redirect url
    url = itslearning_instance + "/restapi/personal/sso/url/v1"
    querystring = {
        "access_token": access_token,
        "url": itslearning_instance + "/LearningToolElement/ViewLearningToolElement.aspx?LearningToolElementId=" + str(element_id)
    }

    response = requests.request(
        "GET", url, headers=headers, params=querystring, timeout=5)
    sso_url = response.json()["Url"]

    logging.debug("-> SSO")

    session = requests.Session()
    # Make a request to that url to get the iframe url
    response = session.request("GET", sso_url, headers=headers, timeout=5)

    logging.debug("-> Iframe")

    # Get the iframe url
    soup = BeautifulSoup(response.text, 'html.parser')
    iframe_src = soup.find("iframe").get("src")

    # Make a request to the iframe url to get redirected and have
    # a url with the LearningObjectId and LearningObjectInstanceId params
    response2 = session.request("GET", iframe_src, headers=headers, timeout=5)

    logging.debug("-> Redirect")

    # Check if the element is a list of files ("filesblock"?)
    soup2 = BeautifulSoup(response2.text, "html.parser")
    link_elements = soup2.select(".ilw-filesblock-li a")
    if link_elements:
        # Download all files from the page
        for element in link_elements:
            url = "https://page.itslearning.com" + element.get("href")

            file_response = session.request("GET", url, headers=headers, timeout=5)
            logging.debug("-> DL File")
            download_response(file_response, dest_path)

    # Or a single file element
    else:
        # Parse the url and get the query parameters
        url = urlparse(response2.url)
        qs = parse_qs(url.query)
        params = {
            "LearningObjectId": qs["LearningObjectId"],
            "LearningObjectInstanceId": qs["LearningObjectInstanceId"]
        }

        # Call the DownloadRedirect endpoint to get the file
        url = "https://resource.itslearning.com/Proxy/DownloadRedirect.ashx"
        file_response = session.request(
            "GET", url, headers=headers, params=params, timeout=5)
        download_response(file_response, dest_path)


def query_course_list(access_token):  # Get user enrolled courses
    url = itslearning_instance + "/restapi/personal/courses/v2"
    querystring = {"access_token": access_token,
                   "pageIndex": "0", "pageSize": "9999", "filter": "1"}
    response = requests.request(
        "GET", url, headers=headers, params=querystring)
    return response.json()["EntityArray"]


# Fetch the resource list of a course
def query_course_resources(course_id, access_token):
    url = itslearning_instance + \
        f"/restapi/personal/courses/{course_id}/resources/v1"
    querystring = {"access_token": access_token,
                   "pageIndex": "0", "pageSize": "9999"}
    response = requests.request(
        "GET", url, headers=headers, params=querystring)
    return response.json()["Resources"]["EntityArray"]


# Fetch the resource list of a subfolder
def query_folder_resources(course_id, folder_element_id, access_token):
    url = itslearning_instance + \
        f"/restapi/personal/courses/{course_id}/folders/{folder_element_id}/resources/v1"
    querystring = {"access_token": access_token,
                   "pageIndex": "0", "pageSize": "9999"}
    response = requests.request(
        "GET", url, headers=headers, params=querystring)
    return response.json()["Resources"]["EntityArray"]


def download_file_resource(resource, access_token):
    sanitized_path = sanitize_path(resource["Path"])
    file_path = os.path.join(sanitized_path, resource["Title"])
    try:
        # Fetch the file
        download_element(resource["ElementId"], sanitized_path, access_token)
        # download_element(resource["ElementId"], file_path, access_token)
    except Exception as e:
        logging.error(f"Failed downloading: {resource['Title']}")
        logging.debug(e)
    else:
        logging.info(f"Downloaded resource '{resource['Title']}")


def download_folder_recursive(course_id, folder_resource, access_token):
    try:
        sanitized_path = sanitize_path(folder_resource["Path"])
        # Use os.path.join to handle spaces in folder names
        folder_path = os.path.join(output_folder, sanitized_path, folder_resource["Title"])
        # Use quote to handle special characters in folder names
        folder_path = quote(folder_path)
        # Path(folder_path).mkdir(parents=True, exist_ok=True)

        folder = query_folder_resources(course_id, folder_resource["ElementId"], access_token)
        if folder:
            logging.info(f" -> Download sub folder: {folder_resource['Title']}")
            for resource in tqdm(folder, desc="Files in folder", leave=False):
                if resource["ElementType"] == "Folder":
                    # Pass the updated folder_path to the recursive call
                    download_folder_recursive(course_id, resource, access_token)
                elif resource["ElementType"] == "LearningToolElement":
                    download_file_resource(resource, access_token)
    except Exception as e:
        logging.error(f"An error occurred: {e}")



def main():
    sys_path_exist = Path(sys_path).exists()
    logging.debug(f"install_sys: {install_sys}")
    logging.debug(f"sys_path: {sys_path}")
    logging.debug(f"sys_path_exist: {sys_path_exist}")
    logging.debug(f"env_loaded: {env_loaded}")
    logging.debug(f"open_env: {env_loaded}")
    
    if not sys_path_exist and install_sys:
        logging.info(f"Create itslearning-dl folder: {sys_path}")
        Path(sys_path).mkdir(parents=True, exist_ok=True)

    # if no .env exist create example file
    if not env_loaded and install_sys:
        create_env_file(sys_path)
    elif open_env:
        open_env_file(sys_path)
        logging.critical("Opening .env resulted in a process exit!")
        os._exit(1)

    if not username or not password:
        logging.critical("Env variables or username and password missing!")
        os._exit(1)

    if(refetch):
        remove_state_file()

    logging.info(f"Output path: {output_folder}")

    # Login
    access_token = get_access_token(username, password)
    if(not access_token):
        logging.critical("Login failed. Please check your username, password, or use '--loglvl debug' for more details.")
        os._exit(1)
    
    logging.info(f"-> Login: {username}")

    # Make sure the state file exists
    if not os.path.exists(state_path):
        f = open(state_path, "w")
        f.write("{}")
        f.close()

    # Load the current state
    f = open(state_path, "r")
    try:
        state = json.loads(f.read())
    except:
        traceback.print_exc()
        logging.warning("State file corrupt! The tool may not behave as intended.")
        state = {}
    f.close()

    if not 'course' in state:
        state["course"] = {}

    # Loop through all enrolled courses
    with logging_redirect_tqdm():
        for course in tqdm(query_course_list(access_token), desc="Courses"):
            courseId = str(course["CourseId"])
            if not courseId in state["course"]:
                state["course"][courseId] = {"lastUpdated": 0}

            # If the course was not updated since the last request, skip downloading
            last_updated_date = datetime.datetime.strptime(
                course["LastUpdatedUtc"], "%Y-%m-%dT%H:%M:%SZ")
            if state["course"][courseId]["lastUpdated"] >= last_updated_date.timestamp():
                continue
            state["course"][courseId]["lastUpdated"] = last_updated_date.timestamp()

            logging.info(f"-> Start downloading course {course['Title']}")

            # Download all resources (since we don't have any indication of which resource has changed)
            for resource in tqdm(query_course_resources(courseId, access_token), desc="Resources", leave=False):
                if resource["ElementType"] == "Folder":
                    download_folder_recursive(courseId, resource, access_token)

                if resource["ElementType"] != "LearningToolElement":
                    continue

                download_file_resource(resource, access_token)

            logging.info(f"-> Course {course['Title']} finished")

            # Persist the state
            f = open(state_path, "w")
            f.write(json.dumps(state))

if __name__ == "__main__":
    main()