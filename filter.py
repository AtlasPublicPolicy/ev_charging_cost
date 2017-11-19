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
Functions for excluding records based on various criteria.
"""

import csv
import datetime
import os.path

from auxiliary import get_units
from calculate import check_tier_structure


def filter_by_energy_structure(record):
    """
    Include only records that have an 'energyratestructure' field defined.
    True: filter out
    False: keep
    :param record:
    :return:
    """
    if "energyratestructure" not in record.keys():
        return True
    else:
        return False


def filter_by_end_date(record):
    """
    Filter out records with an end date before 'now.'
    True: filter out
    False: keep
    :param record:
    :return:
    """
    if "enddate" in record.keys():
        if datetime.datetime.fromtimestamp(record["enddate"]) \
                < datetime.datetime.now():
            return True
        else:
            return False
    else:
        return False


def filter_by_keyword(record):
    """
    Exclude records containing certain keywords in the name.
    True: filter out
    False: keep
    :param record:
    :return:
    """
    name = record["name"].encode("utf-8")

    keyword_list = list()
    with open(os.path.join(os.getcwd(), "settings",
                           "keywords_for_filtering.csv"
                           ), 'r') as f:
        reader = csv.reader(f)
        for item in reader:
            keyword_list += item

        if any(keyword.lower() in name.lower() for
               keyword
               in keyword_list):  # case insensitive
            return True
        else:
            return False


def filter_by_units(record):
    """
    Filter out records with units that are not 'kWh' or 'kWh' daily
    True: filter out
    False: keep
    :param record:
    :return:
    """
    units = get_units(record=record)
    if all(u == 'kWh' or u == 'kWh daily' for u in units):
        return False
    else:
        return True


def filter_for_missing_rates(record):
    """
    Exclude records that are missing a value in a rate field.
    :param record:
    :return:
    """
    for period in record["energyratestructure"]:
        for tier in period:
            if "rate" not in tier.keys():
                return True

    return False


def filter_for_non_conforming_tier_structure(record):
    """
    Exclude records that have a tier structure that does not conform to the
    expected structure.
    :param record:
    :return:
    """
    if any(check_tier_structure(record=record, month=month) is False
           for month in range(1, 13)
           ):
        return True
    else:
        return False


def filter_record(record):
    """
    Decide whether to keep a record (and calculate EV charging cost) or to
    filter it out; if filtering out, return the reason for filtering out to
    eventually write to an output file.
    :param record:
    :return:
    """
    if filter_by_energy_structure(record=record):
        return True, "missing energy structure"
    elif filter_by_end_date(record=record):
        return True, "end date"
    elif filter_by_keyword(record=record):
        return True, "keyword"
    elif filter_by_units(record=record):
        return True, "units"
    elif filter_for_missing_rates(record=record):
        return True, "missing rate"
    elif filter_for_non_conforming_tier_structure(record=record):
        return True, "non-conforming tier structure"
    else:
        return False, None
