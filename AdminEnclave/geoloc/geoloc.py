# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
import os

import requests

try:
    from .geoip import GeoIpAPIChecker
    from .rtt_based_estimator import RTTBasedLocationEstimator
except Exception as _:
    from geoip import GeoIpAPIChecker
    from rtt_based_estimator import RTTBasedLocationEstimator

AZURE_METADATA_API_URL = "http://169.254.169.254/metadata/instance?api-version=2025-04-07&format=json"

def get_ip():
    """
    Obtain and return our current IP address.
    """
    try:
        resp = requests.get("https://ipecho.net/plain")
        ip_address = resp.text
    except Exception as _:
        raise

    return ip_address

def get_cloud_provider_result(cloud_provider):
    """
    Obtain and return the metadata information provided by a cloud service.

    Note that currently only Azure is supported.
    """
    report = {}
    if cloud_provider == "azure":
        url = AZURE_METADATA_API_URL
    else:
        url = None

    if url:
        try:
            resp = requests.get(url, headers={"Metadata": "True"}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if cloud_provider == "azure":
                    assert "compute" in data and "azEnvironment" in data["compute"] and "location" in data["compute"]
                    for key in ["azEnvironment", "location"]:
                        report[key] = data["compute"][key]
                    # print(json.dumps(data, indent=4))
        except Exception as _:
            raise

    return report

def get_geoip_api_result(ip_address):
    """
    Obtain and return the GeoIP location information from various online API services.
    """
    geoip_checker = GeoIpAPIChecker()

    return geoip_checker.get_geo_info(ip_address)

def get_estimation_result(area_type, n, weight_method):
    """
    Obtain and return the RTT-based estimation of current location.
    """
    rtt_based_estimator = RTTBasedLocationEstimator()

    return rtt_based_estimator.get_estimated_location(area_type, n, weight_method)

def main(ip_address):
    """
    Compile and return various pieces of information for reporting the current location.
    1. Cloud provider metadata
    2. GeoIP API lookup
    3. RTT-based estimation
    """
    area_type = os.getenv("ESTIMATION_AREA_TYPE", "city")
    n = int(os.getenv("ESTIMATION_NUM_CLOSEST_AREAS_TO_USE", "20"))
    weight_method = os.getenv("ESTIMATION_WEIGHT_METHOD", "inverse_squared")
    cloud_provider = os.getenv("CLOUD_PROVIDER", "azure")

    result = {}
    result["cloud_provider_metadata_result"] = get_cloud_provider_result(cloud_provider)
    result["geoip_api_lookup_result"] = get_geoip_api_result(ip_address)
    result["rtt_based_estimation_result"] = get_estimation_result(area_type, n, weight_method)

    print("-" * 50)
    print(json.dumps(result, indent=4))

if __name__ == "__main__":
    ip_address = get_ip()

    main(ip_address)
