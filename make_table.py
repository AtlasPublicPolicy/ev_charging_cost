#!/usr/bin/env python

# Copyright 2017 International Council on Clean Transportation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Create the EV charging cost table and record the rates that have been
filtered out.

"""
import csv
from collections import OrderedDict
import os.path
import sqlite3

from download import request_records
from filter import filter_record
from calculate import process_record


def get_request_params():
    """
    Get the parameters for the download request.
    :return:
    """
    params = dict()
    with open(os.path.join(os.getcwd(), "settings", "request_params.csv"),
              "r") as request_params_file:
        reader = csv.reader(request_params_file, delimiter=",")
        for row in reader:
            params[row[0]] = row[1]
    try:
        params["api_key"] = \
            open(os.path.join(os.getcwd(), "settings", "api_key.txt"),
                 "r").readline().splitlines()  # read one line, remove '/n'
    except IOError:
        raise IOError(
            "You need an API key: get it at "
            "https://openei.org/services/api/signup/ and include it in a file "
            "called 'api_key.txt' in the 'settings' subdirectory.")

    return params


def get_profile_inputs():
    """
    Get the baseline and EV charging input files.
    :return:
    """
    baseline_weekday = OrderedDict()
    baseline_weekend = OrderedDict()
    charging_weekday = OrderedDict()
    charging_weekend = OrderedDict()

    with open(
            os.path.join(os.getcwd(), 'inputs', 'baseline_profile.csv'),
            'r') as baseline_profile_file:
        reader = csv.reader(baseline_profile_file)
        reader.next()  # skip header
        for row in reader:
            if int(row[0]) not in baseline_weekday.keys():
                baseline_weekday[int(row[0])] = OrderedDict()
                baseline_weekend[int(row[0])] = OrderedDict()

            baseline_weekday[int(row[0])][int(row[1])] = float(row[2])
            baseline_weekend[int(row[0])][int(row[1])] = float(row[3])

    with open(
            os.path.join(os.getcwd(), 'inputs', 'charging_profile.csv'),
            'r') as charging_profile_file:
        reader = csv.reader(charging_profile_file)
        reader.next()  # skip header
        for row in reader:
            if int(row[0]) not in charging_weekday.keys():
                charging_weekday[int(row[0])] = OrderedDict()
                charging_weekend[int(row[0])] = OrderedDict()

            charging_weekday[int(row[0])][int(row[1])] = float(row[2])
            charging_weekend[int(row[0])][int(row[1])] = float(row[3])

    return baseline_weekday, baseline_weekend, \
        charging_weekday, charging_weekend


def write_results_files_headers():
    """
    Write the headers of the EV charging cost and filtered records results
    files.
    :return:
    """
    with open(os.path.join(
            os.getcwd(), "results", "ev_charging_cost_by_utility_rate.csv"
    ), "wb") as results_file:
        charging_cost_writer = csv.writer(results_file, delimiter=",")
        # Write header
        charging_cost_writer.writerow(
            ["label", "utility", "eia_id",
             "rate_name", "rate_description", "rate_end_date",
             "source_url", "openei_url",
             "fixed_charge_first_meter", "ev_annual_charging_cost"]
        )

    with open(os.path.join(
            os.getcwd(), "results", "filtered_records.csv"
    ), "wb") as results_file:
        filter_writer = csv.writer(results_file, delimiter=",")
        # Write header
        filter_writer.writerow(
            ["label", "utility", "eia_id", "rate_name",  "rate_description",
             "rate_end_date", "source_url", "openei_url", "reason"]
        )


def write_charging_cost_results(
        record, calculated_annual_charging_cost, csv_writer
):
    """
    Write the charging cost results for a record.
    :param record:
    :param calculated_annual_charging_cost:
    :param csv_writer:
    :return:
    """
    csv_writer.writerow([
        record["label"].encode("utf-8"),
        record["utility"].encode("utf-8"),
        record["eiaid"] if "eiaid" in record.keys() else None,
        record["name"].encode("utf-8"),
        record["description"].encode("utf-8")
        if "description" in record.keys() else None,
        record["enddate"] if "enddate" in record.keys() else None,
        record["source"].encode("utf-8")
        if "source" in record.keys() else None,
        record["uri"].encode("utf-8"),
        record["fixedmonthlycharge"]
        if "fixedmonthlycharge" in record.keys() else None,
        calculated_annual_charging_cost
    ]
    )


def write_filter_results(record, csv_writer, why):
    """
    Write the reason for filtering out a record.
    :param record:
    :param csv_writer:
    :param why:
    :return:
    """
    csv_writer.writerow([
        record["label"].encode("utf-8"),
        record["utility"].encode("utf-8"),
        record["eiaid"] if "eiaid" in record.keys() else None,
        record["name"].encode("utf-8"),
        record["description"].encode("utf-8")
        if "description" in record.keys() else None,
        record["enddate"] if "enddate" in record.keys() else None,
        record["source"].encode("utf-8")
        if "source" in record.keys() else None,
        record["uri"].encode("utf-8"),
        why
    ]
    )


if __name__ == "__main__":
    # Create an in-memory database where we'll load the input files
    db = sqlite3.connect(":memory:")

    # Get the params for the download request
    request_params = get_request_params()

    # Get profile inputs
    baseline_weekday_profile, baseline_weekend_profile, \
        charging_weekday_profile, charging_weekend_profile = \
        get_profile_inputs()

    # Start with no offset (first record)
    offset = 0
    remaining_records = True

    # Create the results directory if it doesn't exist
    if not os.path.exists(os.path.join(os.getcwd(), "results")):
        os.makedirs(os.path.join(os.getcwd(), "results"))

    # Write results files headers
    write_results_files_headers()

    # Download record, calculate cost, and write to results file
    while remaining_records is True:
        request_params["offset"] = offset
        requested_records = request_records(request_params=request_params)

        remaining_records = \
            False if len(requested_records["items"]) == 0 else True

        if remaining_records is True:
            print("Processing records {}-{} of ~10,200...".format(
                offset + 1, offset + len(requested_records["items"]))
            )
            for r in requested_records["items"]:
                if filter_record(record=r)[0]:

                    reason = filter_record(record=r)[1]
                    with open(os.path.join(
                            os.getcwd(), "results", "filtered_records.csv"
                    ), "ab") as filter_results_file:
                        writer = csv.writer(filter_results_file, delimiter=",")
                        write_filter_results(
                            record=r,
                            csv_writer=writer,
                            why=reason
                        )
                else:
                    annual_charging_cost = process_record(
                        record=r, db=db,
                        baseline_weekday_profile=baseline_weekday_profile,
                        baseline_weekend_profile=baseline_weekend_profile,
                        charging_weekday_profile=charging_weekday_profile,
                        charging_weekend_profile=charging_weekend_profile
                    )
                    with open(os.path.join(
                            os.getcwd(), "results",
                            "ev_charging_cost_by_utility_rate.csv"
                    ), "ab") as charging_results_file:
                        writer = csv.writer(
                            charging_results_file, delimiter=","
                        )
                        write_charging_cost_results(
                            record=r,
                            calculated_annual_charging_cost=
                            annual_charging_cost,
                            csv_writer=writer
                        )
        offset += len(requested_records["items"])

    print("Done.")
