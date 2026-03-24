# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

from argparse import ArgumentParser
import logging
from logging.config import dictConfig
import os
import sys
import signal
import subprocess

from flask import Flask, request

try:
    from .property_computation_server import PropertyComputationServer
except Exception as _:
    from property_computation_server import PropertyComputationServer

dictConfig({
    "version": 1,
    "formatters": {"default": {
        "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
    }},
    "handlers": {"wsgi": {
        "class": "logging.StreamHandler",
        "formatter": "default"
    }},
    "root": {
        "level": "INFO",
        "handlers": ["wsgi"]
    }
})

app = Flask(__name__)

def check_missing_parameters(params, required_params, empty_ok=True):
    """
    This function checks whether all required request parameters are present.
    """
    for param in required_params:
        if param not in params:
            app.logger.error("Missing request parameter: " + param)
            return False

        if not empty_ok:
            if params[param] is None or params[param] == "":
                app.logger.error("Empty request parameter: " + param)
                return False

    return True

def check_gpu():
    """
    This function determines whether the current machine has a GPU.
    If so, the computation for the request will be launched
    with access to the GPU.
    """
    command = ["nvidia-smi"]

    try:
        _ = subprocess.run(command, check=True)
    except Exception as _:
        return False

    return True

@app.route("/", methods=["POST"])
def handle_property_computation_request():
    """
    The main function to handle and route property computation related requests.
    """
    global PROPERTY_COMPUTATION_SERVER

    data = request.get_json()

    if "action" in data and data["action"] in ["new", "upload", "prepare", "start", "status", "result", "download"]:
        action = data["action"]

        if action == "new":
            result = PROPERTY_COMPUTATION_SERVER.create_request()

        elif action in ["upload", "prepare", "start", "status", "result", "download"]:
            # First, check whether all required request parameters are present.
            required_params = ["request_id", "request_token"]
            if action == "upload":
                required_params.extend(["input_type", "upload_method", "upload_name", "upload_data"])
            elif action == "download":
                required_params.extend(["output_name"])

            if check_missing_parameters(data, required_params, empty_ok=True):
                rid = data["request_id"]
                rt = data["request_token"]

                req, msg = PROPERTY_COMPUTATION_SERVER.get_request(rid, rt)
                if req:
                    if action == "upload":
                        result = PROPERTY_COMPUTATION_SERVER.upload(data, req)

                    elif action == "prepare":
                        result = PROPERTY_COMPUTATION_SERVER.prepare_computation(req)

                    elif action == "start":
                        result = PROPERTY_COMPUTATION_SERVER.start_computation(req)

                    elif action == "status":
                        result = PROPERTY_COMPUTATION_SERVER.check_status(req)

                    elif action == "result":
                        result = PROPERTY_COMPUTATION_SERVER.get_service_result(req)

                    elif action == "download":
                        result = PROPERTY_COMPUTATION_SERVER.download_output(data["output_name"], req)
                else:
                    # no such request or invalid token
                    result = {"error": msg}
            else:
                result = {"error": "Missing parameter(s)."}
    else:
        result = {"error": "Missing parameter(s) or no such action."}

    response = result

    return response

# Register a signal handler for SIGINT
def handle_sigint(signal, frame):
    app.logger.info("SIGINT received. Stopping DuetAdmin...")
    sys.exit()

def parse_args():
    """
    Parse the arguments to start the server.
    """
    parser = ArgumentParser()
    parser.add_argument("-p", "--port", default=6038, help="Server port")
    parser.add_argument("-i", "--cvm-id-filename", default="/home/duet/cvm_id.txt", help="CVM id")
    parser.add_argument("-k", "--key_filename", default="/home/duet/certs/key.pem", help="Server private key filename")
    parser.add_argument("-c", "--cert_filename", default="/home/duet/certs/cert.pem", help="Server TLS certificate")
    args = parser.parse_args()
    return args

def main():
    """
    Main function to initialize the property computation server.
    """
    app.logger.setLevel(logging.INFO)

    # Attach the signal handler to SIGINT
    signal.signal(signal.SIGINT, handle_sigint)

    args = parse_args()
    port = args.port
    cvm_id_filename = args.cvm_id_filename
    key_filename = args.key_filename
    cert_filename = args.cert_filename

    # ensure we have all necessary configuration files
    if not cvm_id_filename or not key_filename or not cert_filename:
        app.logger.error("Missing parameter(s).")
        return

    if not os.path.exists(cvm_id_filename) or not os.path.exists(key_filename) or not os.path.exists(cert_filename):
        app.logger.error("Missing configuration file(s).")
        return

    # The cvm_id is used to implement a crude sticky session for requests.
    # It will be embedded into responses, so that subsequent actions related to this
    # request will be coming to the same CVM running this service instance.
    with open(cvm_id_filename, "r", encoding="utf-8") as f:
        cvm_id = f.read().strip()

    global PROPERTY_COMPUTATION_SERVER
    PROPERTY_COMPUTATION_SERVER = PropertyComputationServer(cvm_id, "/tmp/PropertyComputationService/", check_gpu())

    try:
        app.logger.info("*"*50)
        app.logger.info(f"[Property Computation Server] Starting server on {port}...")
        app.logger.info("*"*50)
        app.run(host="0.0.0.0", threaded=True, debug=False, port=port, ssl_context=(cert_filename, key_filename))
    except KeyboardInterrupt:
        app.logger.info("[Property Computation Server] Shutting down...")

    app.logger.info("[Property Computation Server] Done.")

if __name__ == "__main__":
    main()
