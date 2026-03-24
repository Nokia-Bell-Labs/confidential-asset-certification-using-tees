# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import concurrent.futures
import random
import subprocess
import unicodedata

import requests

TIMEOUT = 10

# anchor related constants
RIPE_ATLAS_API_URL = "https://atlas.ripe.net/api/v2/anchors/"
ANCHOR_INFO_KEYS = sorted(["id", "ip_v4", "city", "country", "geometry"])

# rtt memasurement parameters
NUM_PINGS = 20
MAX_THREADS = 25

# estimation parameters
GEOIP_API_URL = "http://ip-api.com/json/"
REVERSE_GEOCODING_URL = "https://api.bigdatacloud.net/data/reverse-geocode-client"

class AtlasAnchorCollector():
    """
    The class that deals with RIPE Atlas anchors.
    """
    def __init__(self):
        self._anchor_city_map = None
        self._anchor_country_map = None

    def get_anchors(self):
        """
        Obtains enabled anchor information including its id, IP address, coordinates,
        city and country, and groups them according to the city and country.
        It normalizes city names to ASCII format,
        so that international entries referring to the same city are merged.
        """
        anchor_city_map = {}
        anchor_country_map = {}
        next_page = RIPE_ATLAS_API_URL
        total_processed = 0
        total_enabled = 0
        while True:
            try:
                response = requests.get(next_page, timeout=TIMEOUT)
                if response.status_code == 200:
                    data = response.json()
                    assert "results" in data and "next" in data and "count" in data
                    next_page = data["next"]
                    # print("Total number of anchors: " + str(data["count"]))
                    for anchor_info in data["results"]:
                        if not anchor_info["is_disabled"]:
                            total_enabled += 1
                            info = {}
                            for key in ANCHOR_INFO_KEYS:
                                info[key] = anchor_info[key]

                            city = info["city"]
                            city = city.replace("-", " ")
                            city = unicodedata.normalize("NFKD", city).encode("ascii", "ignore").decode()
                            tokens = city.split(" ")
                            tokens = [t.capitalize() for t in tokens]
                            city = ' '.join(tokens)
                            info["city"] = city

                            country = info["country"]
                            if country not in anchor_country_map:
                                anchor_country_map[country] = []
                            anchor_country_map[country].append(info)

                            if city not in anchor_city_map:
                                anchor_city_map[city] = []
                            anchor_city_map[city].append(info)

                        total_processed += 1
                    print(f"Processed anchors: {total_processed}/{data['count']} ({total_enabled} enabled in {len(anchor_city_map)} cities and in {len(anchor_country_map)} countries.)")
                    if total_processed == data["count"]:
                        break
            except Exception as _:
                pass

        self._anchor_city_map = anchor_city_map
        self._anchor_country_map = anchor_country_map

    def get_anchor_map(self, area_type):
        """
        Return the anchor information grouped by city name.
        """
        anchor_map = None

        if area_type == "city":
            anchor_map = self._anchor_city_map
        elif area_type == "country":
            anchor_map = self._anchor_country_map

        return anchor_map

class RTTMeasurementCollector():
    """
    The class to perform and collect RTT measurements to the given areas.
    """
    def __init__(self):
        self._rtt_measurement_map = None

    def _get_min_rtt_anchor(self, anchor):
        """
        Internal function to measure the RTT to a given anchor
        by pinging it `NUM_PINGS' times in successive order (i.e., `-A' option).
        Afterwards, the minimum RTT value is taken,
        because measurement values might change due to congestion,
        but physical distances do not.
        We use minimum RTT value as the best-case delay
        (i.e., representative of the pure physical distance).
        """
        anchor_ip = anchor["ip_v4"]
        command = ["ping", "-q", "-c", str(NUM_PINGS), "-A", "-i", "0.05", "-W", "1", anchor_ip]
        result = subprocess.run(command, capture_output=True, text=True)
        output = ''.join(result.stdout)

        if output.find("Name or service not known") != -1:
            return None

        if output.find("100% packet loss") != -1:
            return None

        output = output.split("\n")
        lines = []
        for line in output:
            if line.strip() == "":
                continue
            lines.append(line)
        last = lines[-1]
        tokens = last.split(" ")
        # min rtt
        tokens = tokens[3].split("/")

        return float(tokens[0])

    def _measure_rtt_area(self, area, anchor_map):
        """
        Internal function to measure the RTT value to an area
        by selecting and trying an anchor from the list of anchors
        in that area.
        If an anchor is unavailable, another is selected.
        If all anchors in an area are tried and are unavailable,
        the area is excluded from the measurement results
        (i.e., by setting its RTT value as `None').
        """
        anchors = anchor_map[area]
        # 2.1 pick an anchor from the area and measure rtt
        rtt = None
        success = False
        tried_all = False
        already_tried = {}
        # 2.2 try another anchor from the area for failed measurements
        while not success and not tried_all:
            cur_id = random.randint(0, len(anchors)-1)
            if cur_id not in already_tried:
                picked_anchor = anchors[cur_id]
                # 2.3 pick min value for area rtt
                # measurement values might change due to congestion, but physical distances do not
                # use minimum rtt as the best-case delay (i.e., pure distance-related)
                rtt = self._get_min_rtt_anchor(picked_anchor)
                if rtt:
                    success = True
                already_tried[cur_id] = True
            else:
                if len(already_tried) == len(anchors):
                    tried_all = True

        return (area, picked_anchor, rtt)

    def measure_rtts(self, anchor_map):
        """
        Measures the RTT values to each area in concurrent threads.
        """
        self._rtt_measurement_map = {}
        # 1. pick some areas
        area_list = anchor_map.keys()

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = [
                executor.submit(self._measure_rtt_area, area, anchor_map)
                for area in area_list
            ]
            i = 0
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                i += 1
                if res:
                    area = res[0]
                    picked_anchor = res[1]
                    rtt = res[2]
                    if rtt:
                        self._rtt_measurement_map[area] = (picked_anchor, rtt)
                        print(f"[+] ({i}/{len(area_list)}) {picked_anchor['ip_v4']} {picked_anchor['city']}, {picked_anchor['country']} -> min rtt: {rtt} ms", flush=True)
                    else:
                        print(f"[-] ({i}/{len(area_list)}) {picked_anchor['ip_v4']} {picked_anchor['city']}, {picked_anchor['country']} -> min rtt: {rtt} ms", flush=True)

    def get_rtt_measurement_map(self):
        """
        Return the measured RTT values to the areas.
        """
        return self._rtt_measurement_map

class RTTBasedLocationEstimator():
    """
    RTT-based location estimation class.

    This class utilizes RIPE ATLAS measurement anchors as landmarks,
    and collects RTT measurements (via ECHO requests using `ping') from these landmarks.

    The landmarks are grouped together according to their area names.
    From each area, an anchor is selected to estimate the RTT to that area from
    the current VM.
    If that measurement fails, another anchor from the same area is selected.
    This process continues until an RTT can be measured, or the area does not
    have any more anchors to select from.
    In the latter case, this area is not used for estimation.

    Instead of converting the RTT measurements to physical distances and triangulate
    the intersections, we directly utilize the measurement values
    for an estimation.
    The logic is as follows: if another area has a small RTT value, it must be closer
    to our current location than another area with a larger RTT value.

    After the measurements are taken to as many areas as possible via
    at least one available anchor in that area, they are sorted with increasing
    RTT values.
    As a heuristic, `n' closest areas (i.e., with the least RTT values) are selected.
    To estimate the coordinates of our current location, we take a potentially weighted
    averaging of the coordinates of each anchor from the closest respective area.

    These estimated coordinates are then used via a reverse geocoding API service
    to obtain a human-readable location (i.e., a city and country).

    The estimated coordinates, the reverse-geocoded city and country as well as the `n'
    closest areas with their respective RTT values in milliseconds are reported
    in the estimated location.

    Using the estimated coordinates in the returned value, one can perform their own
    reverse geocoding lookup for the human-readable location information.
    """
    def __init__(self):
        self._anchor_collector = AtlasAnchorCollector()
        self._rtt_measurement_collector = RTTMeasurementCollector()

    def _get_n_closest(self, rtt_measurement_map, n):
        """
        Internal function to obtain the closest `n' areas according to their
        RTT values.
        """
        top_n = []

        # 1. sort measurements according to their rtt
        sorted_rtt_measurement_map = dict(sorted(rtt_measurement_map.items(), key=lambda item: float(item[1][1])))

        # 2. pick n
        for a in sorted_rtt_measurement_map:
            top_n.append(sorted_rtt_measurement_map[a])
            if len(top_n) == n:
                break

        return top_n

    def _sum_rtt(self, top_n_closest):
        """
        Internal function to compute the total of RTT values of the closest
        anchors, so that we can adjust the weights accordingly
        when we compute the middle of their coordinates and estimate
        the possible country according to their country information.
        """
        sum_rtt = 0
        for m in top_n_closest:
            rtt = m[1]
            sum_rtt += rtt

        return sum_rtt

    def _compute_middle(self, top_n_closest, weight_method):
        """
        Internal function to compute the weighted average of the coordinates
        of the anchors used to determine the RTT values of the areas
        as well as estimate the possible country via closest anchors'
        country information.
        The weights are computed according to the `weight_method':
        For "none", there is no weighting, so it is a simple average.
        For "inverse", the weight is inversely proportional to the RTT values,
        so that closer areas are given more weight. The weight is computed
        by computing the sum of RTT values and dividing the sum by a given RTT.
        For "inverse_squared", the weight computed with "inverse" is squared.
        """
        middle = {}
        possible_countries = {}

        if weight_method in ["inverse_squared", "inverse"]:
            sum_rtt = self._sum_rtt(top_n_closest)

        sum_lon = 0
        sum_lat = 0
        total_weights = 0
        for m in top_n_closest:
            anchor = m[0]
            anchor_country = anchor["country"]
            if anchor_country not in possible_countries:
                possible_countries[anchor_country] = 0.0

            rtt = m[1]
            if weight_method == "inverse_squared":
                weight = (sum_rtt / rtt)**2
            elif weight_method == "inverse":
                weight = sum_rtt / rtt
            else:
                weight = 1

            total_weights += weight

            sum_lon += float(anchor["geometry"]["coordinates"][0]) * weight
            sum_lat += float(anchor["geometry"]["coordinates"][1]) * weight

            possible_countries[anchor_country] += weight

        middle["longitude"] = sum_lon / total_weights
        middle["latitude"] = sum_lat / total_weights

        for country in possible_countries:
            possible_countries[country] /= total_weights

        possible_countries = dict(sorted(possible_countries.items(), key=lambda item: float(item[1]), reverse=True))

        return middle, possible_countries

    def _reverse_geocoding_api_lookup(self, lat, lon):
        """
        Internal function to lookup the human-readable location information
        of the given coordinates.
        """
        location = {}
        url = REVERSE_GEOCODING_URL + "?"
        url += "latitude=" + str(lat) + "&"
        url += "longitude=" + str(lon)
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                # for key in ["longitude", "latitude", "city", "countryName", "countryCode", "continent", "continentCode"]:
                for key in ["city", "countryName", "countryCode"]:
                    if key in data:
                        location[key] = data[key]

        except Exception as _:
            pass

        return location

    def _get_estimation(self, area_type, n, weight_method):
        """
        Internal function to obtain the estimated location.

        It first obtains the anchor information grouped by their areas.
        Then it measures the RTT values to one available anchor from each area
        if possible.
        Then it picks the closest `n' areas according to their measured RTT values.
        The estimated coordinates are calculated by a weighted averaging of the
        coordinates of the anchors in the closest areas.
        Finally, a reverse geocoding lookup is performed for a human-readable
        city and country information.
        """
        self._anchor_collector.get_anchors()
        anchor_map = self._anchor_collector.get_anchor_map(area_type)

        self._rtt_measurement_collector.measure_rtts(anchor_map)
        rtt_measurement_map = self._rtt_measurement_collector.get_rtt_measurement_map()

        # 3. sort measurements and pick top n areas with smallest rtt
        top_n_closest = self._get_n_closest(rtt_measurement_map, n)

        closest_areas = {}
        for m in top_n_closest:
            anchor = m[0]
            rtt = m[1]
            print(f"{anchor['city']}, {anchor['country']} -> {rtt} ms")
            closest_areas[anchor["city"] + ", " + anchor["country"]] = rtt

        # 4. get middle of coordinates of those areas
        middle, possible_countries = self._compute_middle(top_n_closest, weight_method)
        estimated_location = self._reverse_geocoding_api_lookup(middle["latitude"], middle["longitude"])

        estimate = {}
        estimate["estimated_coordinates"] = middle
        estimate["estimated_possible_countries"] = possible_countries
        estimate["reverse_geocode_lookup"] = {}
        estimate["reverse_geocode_lookup"][REVERSE_GEOCODING_URL] = estimated_location
        estimate["closest_areas_rtt_ms"] = closest_areas

        return estimate

    def get_estimated_location(self, area_type, n, weight_method):
        """
        Estimate and return the estimated location.
        """
        estimated_location = self._get_estimation(area_type, n, weight_method)

        return estimated_location
