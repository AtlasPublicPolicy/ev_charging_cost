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
Various auxiliary methods.
"""

from collections import OrderedDict


def get_month_weekdays():
    """
    Number of weekdays in each month.
    :return:
    """
    month_weekdays = OrderedDict(
        [(1, 22.14285714),
         (2, 20.17857143),
         (3, 22.14285714),
         (4, 21.42857143),
         (5, 22.14285714),
         (6, 21.42857143),
         (7, 22.14285714),
         (8, 22.14285714),
         (9, 21.42857143),
         (10, 22.14285714),
         (11, 21.42857143),
         (12, 22.14285714)]
    )

    return month_weekdays


def get_month_weekends():
    """
    Number of weekend days in each month.
    :return:
    """
    month_weekends = OrderedDict(
        [(1, 8.857142857),
         (2, 8.071428571),
         (3, 8.857142857),
         (4, 8.571428571),
         (5, 8.857142857),
         (6, 8.571428571),
         (7, 8.857142857),
         (8, 8.857142857),
         (9, 8.571428571),
         (10, 8.857142857),
         (11, 8.571428571),
         (12, 8.857142857)]
    )

    return month_weekends


def get_units(record):
    """
    Determine units used in a record's energyratestructure.
    :param record:
    :return:
    """
    units = list()
    for rate_period in record["energyratestructure"]:
        for tier in rate_period:
            if "max" in tier.keys() and "unit" in tier.keys():
                units.append(tier["unit"].encode("utf-8"))
            elif "max" in tier.keys() and "unit" not in tier.keys():
                units.append("no units specified!")

    return units


def check_if_monthly_tiers(record):
    """
    Determine whether the tier maximum is defined in 'kWh' (monthly) or
    'kWh daily' units.
    :param record:
    :return:
    """
    units = get_units(record=record)

    if all(u == 'kWh' for u in units):
        return True
    elif all(u == 'kWh daily' for u in units):
        return False
    else:
        raise ValueError(
            "Can only allow 'kWh' and 'kWh daily' units. Check why "
            "different units for record {} were not "
            "filtered out.".format(record["label"])
        )


def convert_monthly_to_daily(month, day_type):
    """
    Calculate a daily value from a monthly number depending on the month and
    the day type.
    :param month:
    :param day_type:
    :return:
    """

    # Convert monthly to daily values
    if day_type == 'weekday':
        month_to_day_conversion_factor = 1/get_month_weekdays()[month]
    elif day_type == "weekend":
        month_to_day_conversion_factor = 1/get_month_weekends()[month]
    else:
        month_to_day_conversion_factor = \
            1/(get_month_weekdays()[month] + get_month_weekends()[month])

    return month_to_day_conversion_factor
