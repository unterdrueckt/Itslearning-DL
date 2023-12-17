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
from multiprocessing import Pool, Queue
import time
from conf_manager import ConfManager

# Define paths
sys_path = Path.home() / "Documents" / "itslearning-dl"
state_path = sys_path / 'state.json'
conf_path = sys_path / 'itslearning-dl.conf'
output_folder = Path(ConfManager(conf_path).get_param("ITSLEARNINGDL_OUT") or sys_path / 'out')
logging_path = sys_path / 'log'

# Define parser
parser = argparse.ArgumentParser(description="ItsLearning-DL TOOL.")
conf = ConfManager(conf_path)

# Define arguments
parser.add_argument('-u', '--username', type=str, default=conf.get_param("ITSLEARNING_USERNAME"), help='Set your Itslearning username (default: Config > ITSLEARNING_USERNAME)')
parser.add_argument('-p', '--password', type=str, default=conf.get_param("ITSLEARNING_PASSWORD"), help='Set your Itslearning password (default: Config > ITSLEARNING_PASSWORD)')
parser.add_argument('-o', '--path', type=str, default=output_folder, help=f'Set the output folder for downloaded resources (default: Config > ITSLEARNINGDL_OUT): {output_folder})')
default_ignore_state = conf.get_param("IGNORE_STATE") or False
parser.add_argument('-a', '--ignorestate', default=default_ignore_state, const=True, action='store_const', help='Force refetch of all elements (IGNORE_STATE)')
parser.add_argument('-conf', '--config', default=False, action='store_true', help='Open config file')
parser.add_argument('--state', default=False, action='store_true', help='Open state file')
parser.add_argument('-ni', '--noinstall', default=False, const=True, action='store_const', help='Create itslearning-dl folder in Documents')
default_logfile_bool = conf.get_param("ITSLEARNINGDL_LOGFILE") or True
parser.add_argument('-lf', '--logfile', default=default_logfile_bool, const=True, action='store_const', help=f'Create log file (default: {default_logfile_bool})')
default_worker_count = conf.get_param("WORKER_COUNT") or 20
parser.add_argument('-w', '--worker', type=int, default=default_worker_count, help=f'Number of worker processes to use for downloading (default: {default_worker_count})')
parser.add_argument('--instance', type=str, default=conf.get_param("ITSLEARNING_INSTANCE"), help='Set the Itslearning API instance (default: Config > ITSLEARNING_INSTANCE)')
default_log_level = conf.get_param("LOGLVL") or "info"
parser.add_argument("--loglvl", choices=["debug", "info", "warning", "error", "critical"], default=default_log_level, help="Set the logging level (default: info)")

# Parse the arguments
args = parser.parse_args()

# Other variables
access_token = ""
resources = []  # Create a resources "queue"

# Set up logging with colored output
LOG_COLORS = {
    'debug': '\033[94m',  # Blue
    'info': '\033[92m',   # Green
    'warning': '\033[93m',  # Yellow
    'error': '\033[91m',   # Red
    'critical': '\033[95m'  # Purple
}

class ColoredFormatter(logging.Formatter):
    def format(self, record):
        levelname = record.levelname
        colored_levelname = f"{LOG_COLORS[levelname.lower()]}{levelname}\033[0m"
        record.levelname = colored_levelname
        return super().format(record)

# Create a logger
logger = logging.getLogger()

start_time_string = datetime.datetime.now().strftime("%d-%m-%Y %H_%M_%S")

username = args.username
password = args.password
output_folder = args.path
refetch = args.ignorestate
open_conf = args.config
open_state = args.state
install_sys = not args.noinstall
logfile_bool = args.logfile
worker_count = args.worker
itslearning_instance = args.instance
user_agent = "com.itslearning.itslearningintapp 3.7.1 (HONOR BLN-L21 / Android 9)"

headers = {
    "User-Agent": user_agent
}

# Global variable for the Pool
pool = None

def signal_handler(sig, frame):
    global pool, resources
    logging.critical("The process was interrupted. The current state might be corrupted or inaccurate.")
    resources = []
    if pool is not None:
        logging.warning("Try stopping download processes.")
        pool.terminate()
    logging.warning("Exit process")
    sys.exit()

def remove_state_file():
    logging.info("Remove state.json to download all elements")
    os.remove(state_path)

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

def extract_filename(response):
    filename = ""
    disposition = response.headers.get('Content-Disposition')
    if disposition:
        filename_regex = re.compile(r'filename[^;=\n]*=(([\'"]).*?\2|[^\;\n]*)')
        matches = filename_regex.search(disposition)
        if matches and matches.group(1):
            filename = matches.group(1).replace("'", "").replace('"', '')
    return unquote(filename)

def sanitize_path(raw):
    return re.sub(r'\s*?/\s*', "/", raw)

def download_response(response, dest_path, filename):
    if response.status_code != 200:
        raise Exception(f"DL - failed. Status code: {response.status_code}; File: {filename}")
    try:
        dest_path = dest_path.lstrip('/')
        full_dir_path = os.path.join(output_folder, dest_path)
        full_file_path = os.path.join(full_dir_path, filename)
        Path(full_dir_path).mkdir(parents=True, exist_ok=True)
        logging.debug("-> DL File")
        logging.debug(f" > status: {response.status_code}")
        logging.debug(f" > filename: {filename}")
        logging.debug(f" > full_dir_path: {full_dir_path}")
        logging.debug(f" > full_file_path: {full_file_path}")

        if response.status_code == 200:
            with open(full_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
    except Exception as e:
        logging.error(f"Error: {e}")
        raise Exception(f" -> An error occurred while downloading the file: {filename}")

def download_element(element_id, dest_path, filename, access_token):
    url = itslearning_instance + "/restapi/personal/sso/url/v1"
    querystring = {
        "access_token": access_token,
        "url": itslearning_instance + "/LearningToolElement/ViewLearningToolElement.aspx?LearningToolElementId=" + str(element_id)
    }

    response = requests.request("GET", url, headers=headers, params=querystring, timeout=5)

    logging.debug(response)

    if 'Url' in response.json():
        sso_url = response.json()["Url"]
    else:
        raise Exception('Url not found in the response')

    logging.debug("-> SSO")
    session = requests.Session()

    response = session.request("GET", sso_url, headers=headers, timeout=5)

    logging.debug("-> Iframe")

    soup = BeautifulSoup(response.text, 'html.parser')
    iframe_src = soup.find("iframe").get("src")

    response2 = session.request("GET", iframe_src, headers=headers, timeout=5)

    logging.debug("-> Redirect")

    soup2 = BeautifulSoup(response2.text, "html.parser")
    link_elements = soup2.select(".ilw-filesblock-li a")
    if link_elements:
        logging.debug(" > link_elements: true")
        for element in link_elements:
            url = "https://page.itslearning.com" + element.get("href")

            file_response = session.request("GET", url, headers=headers, timeout=5)
            download_response(file_response, dest_path, filename)

    else:
        logging.debug(" > link_elements: false")
        url = urlparse(response2.url)
        qs = parse_qs(url.query)
        params = {
            "LearningObjectId": qs["LearningObjectId"],
            "LearningObjectInstanceId": qs["LearningObjectInstanceId"]
        }

        url = "https://resource.itslearning.com/Proxy/DownloadRedirect.ashx"
        file_response = session.request("GET", url, headers=headers, params=params, timeout=5)
        download_response(file_response, dest_path, filename)

def query_course_list():
    try:
        url = itslearning_instance + "/restapi/personal/courses/v2"
        querystring = {
            "access_token": access_token,
            "pageIndex": "0",
            "pageSize": "9999",
            "filter": "1"
        }
        response = requests.get(url, headers=headers, params=querystring)

        # Check for HTTP errors
        response.raise_for_status()

        return response.json()["EntityArray"]

    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
    except KeyError as ke:
        logger.error(f"KeyError: {ke}. Check the JSON structure for 'EntityArray'")
        # You can add more specific error handling for different exceptions if needed

    return None  # Return None or any other default value to signify failure

# Fetch the resource list of a course
def query_course_resources(course_id):
    url = itslearning_instance + \
        f"/restapi/personal/courses/{course_id}/resources/v1"
    querystring = {"access_token": access_token,
                   "pageIndex": "0", "pageSize": "9999"}
    response = requests.request(
        "GET", url, headers=headers, params=querystring)
    return response.json()["Resources"]["EntityArray"]

# Fetch the resource list of a subfolder
def query_folder_resources(course_id, folder_element_id):
    url = itslearning_instance + \
        f"/restapi/personal/courses/{course_id}/folders/{folder_element_id}/resources/v1"
    querystring = {"access_token": access_token,
                   "pageIndex": "0", "pageSize": "9999"}
    response = requests.request(
        "GET", url, headers=headers, params=querystring)
    return response.json()["Resources"]["EntityArray"]

def download_file_resource(resource, access_token):
    sanitized_path = sanitize_path(resource["Path"])
    try:
        # Fetch the file
        download_element(resource["ElementId"], sanitized_path, resource["Title"], access_token)
    except Exception as e:
        logging.error(f"Failed downloading: {resource['Title']} error: {e}")
    else:
        logging.info(f"Downloaded resource '{resource['Title']}")

def start_download_file_resource(resource):
    try:
        # Add download resource
        resources.append({ 'ElementId': resource['ElementId'], 'Title': resource['Title'], 'Path': resource['Path']})
    except Exception as e:
        logging.error(f"Failed adding downloading: {resource['Title']}")
        logging.debug(e)


def download_folder_recursive(course_id, folder_resource):
    try:
        sanitized_path = sanitize_path(folder_resource["Path"])
        # Use os.path.join to handle spaces in folder names
        folder_path = os.path.join(output_folder, sanitized_path, folder_resource["Title"])
        # Use quote to handle special characters in folder names
        folder_path = quote(folder_path)
        # Path(folder_path).mkdir(parents=True, exist_ok=True)

        folder = query_folder_resources(course_id, folder_resource["ElementId"])
        if folder:
            logging.info(f" -> add sub folder: {folder_resource['Title']}")
            for resource in tqdm(folder, desc="Files", leave=False):
                if resource["ElementType"] == "Folder":
                    # Pass the updated folder_path to the recursive call
                    download_folder_recursive(course_id, resource)
                elif resource["ElementType"] == "LearningToolElement":
                    start_download_file_resource(resource)
    except Exception as e:
        logging.error(f"An error occurred: {e}")

def worker(resource, access_token):
    download_file_resource(resource, access_token)

def format_time(seconds):
    """Format time in seconds to a string in seconds or minutes."""
    return "{:.2f} min".format(seconds / 60) if seconds > 60 else "{:.2f}s".format(seconds)

def log_statistics(logger, total_elements, download_time, total_time):
    """Log download and total time statistics."""
    logger.info(f"Total downloads processed: {total_elements}")
    if total_elements > 0:
        logger.info(f"Download time taken: {format_time(download_time)}")
    logger.info(f"Total time taken: {format_time(total_time)}")

def main():
    global access_token, pool

    main_start_time = time.time()
    sys_path_exist = Path(sys_path).exists()
    logging_path_exist = Path(logging_path).exists()

    # Remove all handlers from the root logger
    while logger.hasHandlers():
        logger.removeHandler(logger.handlers[0])

    logger.setLevel(logging.getLevelName(args.loglvl.upper()))

    if not sys_path_exist and install_sys:
        Path(sys_path).mkdir(parents=True, exist_ok=True)
    
    if not logging_path_exist and install_sys:
        Path(logging_path).mkdir(parents=True, exist_ok=True)

    if(logfile_bool and (logging_path_exist or install_sys)):
        # Create a logfile handler
        logfile_name = f'{start_time_string}.log'
        logfile_path = os.path.join(logging_path, logfile_name)
        logfile_handler = logging.FileHandler(logfile_path)
        logfile_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s'))
        logger.addHandler(logfile_handler)

    # Create a console handler with color codes
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter('%(levelname)s: %(message)s'))
    logger.addHandler(console_handler)

    logging.debug(f"install_sys: {install_sys}")
    logging.debug(f"sys_path: {sys_path}")
    logging.debug(f"sys_path_exist: {sys_path_exist}")
    logging.debug(f"conf status: {conf.get_status()}")
    logging.debug(f"logfile_bool: {logfile_bool}")
    

    if not sys_path_exist and install_sys:
        logging.info(f"Create itslearning-dl folder: {sys_path}")

    # if no config file exist create example file
    if conf.get_status() == 'missing' and install_sys:
        conf.create_example_conf(True)
        logging.critical("Creating and opening config resulted in a process exit!")
        os._exit(1)

    if open_conf:
        conf.open_conf()
        logging.critical("Opening config resulted in a process exit!")
        os._exit(1)
    
    if open_state:
        conf.open_conf(state_path)
        logging.critical("Opening state file resulted in a process exit!")
        os._exit(1)

    if not username or not password or not itslearning_instance:
        logging.critical("Username, password or instance url missing! (use --config to open the config)")
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
    if not os.path.exists(state_path) and install_sys:
        f = open(state_path, "w")
        f.write("{}")
        f.close()

    # Load the current state
    if install_sys:
        f = open(state_path, "r")
        try:
            state = json.loads(f.read())
        except:
            traceback.print_exc()
            logging.warning("State file corrupt! The tool may not behave as intended.")
            state = {}
        f.close()
    else:
        state = {}
        
    if not 'course' in state:
        state["course"] = {}

    logger.info(f"Collect all elements in courses...")

    # Loop through all enrolled courses
    with logging_redirect_tqdm():
        for course in tqdm(query_course_list(), desc="Courses"):
            courseId = str(course["CourseId"])
            if not courseId in state["course"]:
                state["course"][courseId] = {"lastUpdated": 0}

            # If the course was not updated since the last request, skip downloading
            last_updated_date = datetime.datetime.strptime(
                course["LastUpdatedUtc"], "%Y-%m-%dT%H:%M:%SZ")
            if state["course"][courseId]["lastUpdated"] >= last_updated_date.timestamp():
                continue
            state["course"][courseId]["lastUpdated"] = last_updated_date.timestamp()

            logging.info(f"-> add course {course['Title']}")

            # Download all resources (since we don't have any indication of which resource has changed)
            for resource in tqdm(query_course_resources(courseId), desc="Resources", leave=False):
                if resource["ElementType"] == "Folder":
                    download_folder_recursive(courseId, resource)

                if resource["ElementType"] != "LearningToolElement":
                    continue

                start_download_file_resource(resource)

            # Persist the state
            if install_sys:
                f = open(state_path, "w")
                f.write(json.dumps(state))

    total_elements = len(resources)
    try:
        if total_elements > 0:
            logger.info(f"Download {total_elements} elements with {min(worker_count, total_elements)} worker...")
            pool = Pool(worker_count)
            for resource in resources:
                pool.apply_async(worker, (resource, access_token))
            pool.close()
            pool.join()
        else:
            logger.info("No new elements found!")
    except InterruptedError or KeyboardInterrupt:
        logging.critical("The process was interrupted. The current state might be corrupted or inaccurate.")
        if pool is not None:
            pool.terminate()
        sys.exit(0)

    end_time = time.time()
    download_time = end_time - main_start_time
    total_time = end_time - main_start_time

    log_statistics(logger, total_elements, download_time, total_time)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    main()