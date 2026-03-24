# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import requests

GEOIP_API_URLS = [
    "https://ipinfo.io/" + "<IP_ADDRESS>",
    "https://apip.cc/json",
    "http://ip-api.com/json/" + "<IP_ADDRESS>",
    "https://api.ipwho.org/ip/" + "<IP_ADDRESS>",
    "https://free.freeipapi.com/api/json/" + "<IP_ADDRESS>",
    "https://reallyfreegeoip.org/json/" + "<IP_ADDRESS>",
    "https://geoapi.info/api/geo",
]

GEO_IP_KEYS = ["country", "city", "lon", "lat", "loc"]

def _find_key(key, data, found):
    """
    Internally used function to recursively search for a key
    that is a substring of the keys of a dictionary.
    """
    for k, val in data.items():
        if isinstance(val, dict):
            _find_key(key, val, found)
        elif isinstance(val, str) or isinstance(val, float) or isinstance(val, int):
            if k.lower().find(key.lower()) != -1:
                found[k] = val

class GeoIpAPI():
    """
    The class that deals with a GeoIP location database service API.
    """
    def __init__(self, api_url, key_list):
        self._api_url = api_url
        self._key_list = key_list

    def get_geo_info(self, ip_address, short=True):
        """
        Obtains the lookup result and returns it.
        If requested in short format, it recursively searches and finds
        the relevant information in the result and records it.
        The relevant information includes the coordinates, city and country.
        Each API service may return the same information with a slightly different
        set of key names; thus, a helper function `_find_key()' is used to obtain
        the matching key.
        """
        info = {}
        url = self._api_url.replace("<IP_ADDRESS>", ip_address)

        try:
            response = requests.get(url)
            if response.status_code == 200:
                result = response.json()
                # print(json.dumps(result, indent=4))
                if short:
                    for key in self._key_list:
                        found = {}
                        _find_key(key, result, found)
                        info.update(found)
                else:
                    info = result
        except Exception as _:
            pass

        return info

class GeoIpAPIChecker():
    """
    The class that instantiates and returns the lookup results from various
    online GeoIP location databases via an API call.
    """
    def __init__(self):
        pass

    def get_geo_info(self, ip_address):
        """
        Obtain and collect the GeoIP location information from various online
        API services.
        """
        result = {}
        for geoip_api_url in GEOIP_API_URLS:
            geoip_db = GeoIpAPI(geoip_api_url, GEO_IP_KEYS)
            info = geoip_db.get_geo_info(ip_address)
            result[geoip_api_url.replace("<IP_ADDRESS>", "")] = info

        return result
