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
Method for calculating the cost for charging an EV.

Some notes on the meaning of important response fields from the API:
1. energyweekdayschedule
Array of arrays. The 12 top-level arrays correspond to a month of
the year. Each month array contains one integer per hour of the
weekday from 12am to 11pm, and the integer corresponds to the
index of a period in energyratestructure.
2. energyweekendschedule
Array of arrays. The 12 top-level arrays correspond to a month of
the year. Each month array contains one integer per hour of the
weekend from 12am to 11pm, and the integer corresponds to the index
of a period in energyratestructure.
3. energyratestructure
Tiered Energy Usage Charge Structure. Each element in the
top-level array corresponds to one rate period
(see energyweekdayschedule and energyweekendschedule)
and each array element within a period corresponds to one tier.
Indices are zero-based to correspond with energyweekdayschedule

"""


from auxiliary import check_if_monthly_tiers, \
    convert_monthly_to_daily, get_month_weekends, get_month_weekdays


def derive_params(record, month):
    """
    Calculate a few parameters for use elsewhere.
    :param record:
    :param month:
    :return:
    """
    weekday_rate_periods = set(record["energyweekdayschedule"][month - 1])
    weekend_rate_periods = set(record["energyweekendschedule"][month - 1])

    rate_periods = set(weekday_rate_periods | weekend_rate_periods)
    lowest_rate_period_n = min(rate_periods)

    number_of_tiers_by_rate_period = {
        rate_period: len(record["energyratestructure"][rate_period])
        for rate_period in rate_periods
    }

    max_num_tiers = max(
        len(record["energyratestructure"][rate_period])
        for rate_period in rate_periods
    )

    return rate_periods, lowest_rate_period_n, \
        number_of_tiers_by_rate_period, max_num_tiers


def check_tier_structure(record, month):
    """
    We need to check the tier structure, in particular whether consumption
    tier maximums are defined for the whole day or just the subset of hours
    for a rate period. We will infer that from whether tier maximums
    are the same for all rate periods present in a given month. If they are,
    we will assume tier maximums are for the whole day and will return a
    dictionary of the maximums indexed by tier.
    :param record:
    :param month:
    :return:
    """
    # Check that all rate_periods of a month have the same 'max' for the
    # same tier
    # This is necessary to ensure that we are interpreting the data
    # correctly: max value is given by rate_period, but it appears that --
    # and our assumption is -- that this is actually the maximum monthly (
    # or in some cases daily) consumption across rate_periods

    rate_periods, lowest_rate_period_n, \
        number_of_tiers_by_rate_period, max_num_tiers = \
        derive_params(record=record, month=month)

    # Check if all rate periods have the same number of tiers in the data
    # That's the case for the vast majority of records
    for rate_period in rate_periods:
        try:
            tier_content = \
                record["energyratestructure"][rate_period][max_num_tiers-1]
        except IndexError:
            return False

    # For records with the same number of tiers in each period, we'll check
    # that the max of each tier is the same in all periods
    for tier in range(max_num_tiers):
        rate_period_tier_max = dict()
        for rate_period in rate_periods:
            # If the period has only a single tier, there are no maxes to
            # compare and this record is fine
            if number_of_tiers_by_rate_period[rate_period] == 1:
                pass
            # If there is a max, add the number to a dictionary of tier
            # maxes for each rate period
            elif "max" \
                    in record["energyratestructure"][rate_period][tier].keys():
                rate_period_tier_max[rate_period] = \
                    record["energyratestructure"][rate_period][tier]["max"]
            else:
                pass

        # Check if all rate period max values are the same or matched to a
        # no max for this tier
        if not all(max_value == rate_period_tier_max[lowest_rate_period_n]
                   for max_value in rate_period_tier_max.values()):
            return False
        else:
            pass

    return True


def make_db_tables(
        record, db,
        baseline_weekday_profile, baseline_weekend_profile,
        charging_weekday_profile, charging_weekend_profile
):
    """
    Make database tables from the baseline and EV charging profiles.
    :param record:
    :param db:
    :param baseline_weekday_profile:
    :param baseline_weekend_profile:
    :param charging_weekday_profile:
    :param charging_weekend_profile:
    :return:
    """
    c = db.cursor()

    # ### Make tables of weekday/weekend rate_period by month/hour ### #
    for day_type in ["day", "end"]:
        c.execute(
            """DROP TABLE IF EXISTS week{}_profiles;""".format(day_type)
        )
        c.execute(
            """CREATE TABLE week{}_profiles (
            month_of_year INTEGER,
            hour_of_day INTEGER,
            number_week{}_days_in_month FLOAT,
            rate_period INTEGER,
            baseline_kw FLOAT,
            ev_charging_kw FLOAT,
            PRIMARY KEY (month_of_year, hour_of_day)
            );""".format(day_type, day_type)
        )

        for month in range(1, 13):
            month_index = month - 1  # index in energyweek*schedule
            for hour in range(0, 24):
                # index in energyratestructure
                if day_type == 'day':
                    rate_period_index = \
                        record["energyweekdayschedule"][month_index][hour]
                else:
                    rate_period_index = \
                        record["energyweekendschedule"][month_index][hour]
                c.execute(
                    """INSERT INTO week{}_profiles
                    (month_of_year, hour_of_day, number_week{}_days_in_month,
                    rate_period, baseline_kw, ev_charging_kw)
                    VALUES ({}, {}, {}, {}, {}, {});""".format(
                        day_type, day_type,
                        month, hour,
                        get_month_weekdays()[month] if day_type == 'day' else
                        get_month_weekends()[month],
                        rate_period_index,
                        baseline_weekday_profile[month][hour]
                        if day_type == 'day'
                        else baseline_weekend_profile[month][hour],
                        charging_weekday_profile[month][hour]
                        if day_type == 'day'
                        else charging_weekend_profile[month][hour]
                    )
                )

    # ### Aggregate to month-rate_period ### #
        c.execute(
            """DROP TABLE IF EXISTS 
            week{}_consumption_by_month_rate_period;""".format(day_type)
        )

        c.execute(
            """CREATE TABLE week{}_consumption_by_month_rate_period (
            month_of_year INTEGER,
            rate_period INTEGER,
            total_hours FLOAT,
            baseline_kwh FLOAT,
            ev_charging_kwh FLOAT,
            PRIMARY KEY (month_of_year, rate_period)
            );""".format(day_type)
        )

        c.execute(
            """INSERT INTO week{}_consumption_by_month_rate_period
            (month_of_year, rate_period, total_hours, baseline_kwh,
            ev_charging_kwh)
            SELECT month_of_year, rate_period, 
            sum(number_week{}_days_in_month),
            sum(baseline_kw*number_week{}_days_in_month), 
            sum(ev_charging_kw*number_week{}_days_in_month)
            FROM week{}_profiles
            GROUP BY month_of_year, rate_period;""".format(
                day_type, day_type, day_type, day_type, day_type
            )
        )

        db.commit()

    # ### Combine weekday and weekend consumption by rate_period ### #
    c.execute(
        """DROP TABLE IF EXISTS total_consumption_by_month_rate_period;"""
    )
    c.execute(
        """CREATE TABLE total_consumption_by_month_rate_period (
            month_of_year INTEGER,
            rate_period INTEGER,
            weekday_hours FLOAT,
            weekend_hours FLOAT,
            total_hours FLOAT,
            weekday_baseline_kwh FLOAT,
            weekend_baseline_kwh FLOAT,
            total_baseline_kwh FLOAT,
            weekday_ev_charging_kwh FLOAT,
            weekend_ev_charging_kwh FLOAT,
            total_ev_charging_kwh FLOAT,
            PRIMARY KEY (month_of_year, rate_period)
            );"""
    )

    # Add weekdays
    c.execute(
        """INSERT INTO total_consumption_by_month_rate_period
        (month_of_year, rate_period, weekday_hours, weekday_baseline_kwh, 
        weekday_ev_charging_kwh)
        SELECT month_of_year, rate_period, total_hours, baseline_kwh, 
        ev_charging_kwh
        FROM weekday_consumption_by_month_rate_period;"""
        )

    # Add weekends
    c.execute(
        """INSERT OR IGNORE INTO total_consumption_by_month_rate_period
        (month_of_year, rate_period)
        SELECT month_of_year, rate_period
        FROM weekend_consumption_by_month_rate_period;"""
    )
    db.commit()

    weekend_month_rate_period = c.execute(
        """SELECT month_of_year, rate_period
        FROM weekend_consumption_by_month_rate_period;"""
    ).fetchall()

    for m, rp in weekend_month_rate_period:
        h, b, e = c.execute(
            """SELECT total_hours, baseline_kwh, ev_charging_kwh
            FROM weekend_consumption_by_month_rate_period
            WHERE month_of_year = {}
            AND rate_period = {};""".format(m, rp)
        ).fetchall()[0]

        c.execute(
            """UPDATE total_consumption_by_month_rate_period
            SET weekend_hours = {},
            weekend_baseline_kwh = {},
            weekend_ev_charging_kwh = {}
            WHERE month_of_year = {}
            AND rate_period = {};""".format(
                h, b, e, m, rp
            )
        )
    db.commit()

    # NULLs to zeros
    for column in [
        "weekday_hours", "weekend_hours",
        "weekday_baseline_kwh", "weekend_baseline_kwh",
        "weekday_ev_charging_kwh", "weekend_ev_charging_kwh"
    ]:
        c.execute(
            """UPDATE total_consumption_by_month_rate_period
            SET {} = 0
            WHERE {} IS NULL;""".format(
                column, column
            )
        )

    # Get totals
    c.execute(
        """UPDATE total_consumption_by_month_rate_period
        SET total_hours = weekday_hours + weekend_hours,
        total_baseline_kwh = weekday_baseline_kwh + weekend_baseline_kwh,
        total_ev_charging_kwh = weekday_ev_charging_kwh + 
        weekend_ev_charging_kwh;"""
    )
    db.commit()


def calculate_monthly_cost(record, month, day_type, tier_maximums, db):
    """
    Calculate the cost to charge an EV based on pre-specified baseline and
    charging profiles in a given month and 'day type.' Day types can be
    'weekday,' 'weekend,' and 'total.' We use the 'total,' i.e. lumping
    weekdays and weekends together, if the units for the record are
    monthly 'kWh' because in that case we can't distinguish between weekdays
    and weekends. If the units are 'kWh daily,' we can apply our weekday and
    weekend profiles respectively.

    If the rate is EV-specific, we'll start with a baseline consumption of 0.

    To calculate the cost, we do the following:
    1. Get the total baseline and EV consumption for the month (by day type)
    and convert that to daily consumption
    2. Figure out how much of the EV consumption is in each period present
    in this month/day_type
    3. Loop through the tiers for this record; keep track of cost incurred
    in each tier and charging in each tier
        3.1. If there's a max for this tier, decide whether to apply rate for
        this tier or if we have consumed enough to move to the next tier:
            3.1.1. Check of baseline consumption plus EV charging that we have
            already done is more than the max
                3.1.1.1. If yes, move to the next tier
                3.1.1.2. If not, check if the remaining EV charging is less
                than the difference between the tier max and the baseline
                consumption
                    3.1.1.2.1. If yes, apply the tier rate to the remaining EV
                    charging (loop through periods, get charging in each
                    period, and apply tier rate for each period); no charging
                    is left to do
                    3.1.1.2.2. If not, apply the tier rate to the difference
                    between the tier max and the baseline consumption, and
                    subtract that amount from the remaining EV charging
        3.2. If the tier has no max, apply the tier rate (by period) to the
        remaining EV charging.
    :param record:
    :param month:
    :param day_type:
    :param tier_maximums:
    :param db:
    :return:
    """
    c = db.cursor()
    month_index = month - 1

    # Is this is an EV-specific rate
    ev_specific = \
        True if "EV" in record["name"] \
                or "electric vehicle" in record["name"].lower() \
        else False

    # Get the baseline and EV consumption for the month
    # If this is an EV-specific rate, the baseline consumption is 0
    monthly_baseline_kwh = c.execute(
        """SELECT sum({}_baseline_kwh)
        FROM total_consumption_by_month_rate_period
        WHERE month_of_year = {}
        GROUP BY month_of_year;""".format(
            day_type, month
        )
    ).fetchall()[0][0] if not ev_specific else 0

    monthly_ev_charging_kwh = c.execute(
        """SELECT sum({}_ev_charging_kwh)
        FROM total_consumption_by_month_rate_period
        WHERE month_of_year = {}
        GROUP BY month_of_year""".format(
            day_type, month
        )
    ).fetchall()[0][0]

    daily_baseline_kwh = \
        monthly_baseline_kwh * convert_monthly_to_daily(month, day_type)
    daily_ev_charging_kwh = \
        monthly_ev_charging_kwh * convert_monthly_to_daily(month, day_type)

    # Figure out which rate periods are in this month
    if day_type == 'weekday':
        rate_periods = record["energyweekdayschedule"][month_index]
    elif day_type == 'weekend':
        rate_periods = record["energyweekendschedule"][month_index]
    elif day_type == 'total':
        rate_periods = \
            record["energyweekdayschedule"][month_index] + \
            record["energyweekendschedule"][month_index]
    else:
        raise ValueError("Day types can be 'weekday,' 'weekend,' and 'total.'")

    # For each tier, we'll loop through the rate_periods to apply the
    # appropriate rate, so we need to know how much of the consumption in
    # the tier is in each period; we'll figure that out by getting the
    # relative EV consumption in each period: weights for each period that
    # sum up to 1 for the  month/day_type
    rate_period_weights = {}
    for rate_period in set(rate_periods):
        ev_charging_kwh_at_rate_period = c.execute(
            """SELECT sum({}_ev_charging_kwh)
                FROM total_consumption_by_month_rate_period
                WHERE month_of_year = {}
                AND rate_period = {}
                GROUP BY month_of_year;""".format(
                day_type, month, rate_period
            )
        ).fetchall()[0][0]
        rate_period_weights[rate_period] = \
            ev_charging_kwh_at_rate_period/monthly_ev_charging_kwh

    # ### CALCULATION LOOP ### #
    # Loop through tiers and rate periods for each tier to figure out charging
    # and cost in each tier

    # We'll need to track how many kWh we have left to charge
    # Start with the total daily charging consumption
    remaining_ev_charging_kwh = daily_ev_charging_kwh

    # Charging cost starts at 0
    daily_charging_cost = 0

    for tier in tier_maximums.keys():
        # If there's a max for this tier, figure out if we have consumed
        # enough to go to the next tier or if we need to calculate EV
        # charging cost in this tier
        if tier_maximums[tier] is not None:
            # We have checked that the tier maxes are the same for all rate
            # periods, so can just pick the first one here
            tier_max_unit = record["energyratestructure"][rate_periods[0]][
                    tier]["unit"].encode("utf-8")

            # # Convert monthly to daily if needed
            if tier_max_unit == 'kWh':
                tier_max_kwh_daily = \
                    tier_maximums[tier] \
                    * convert_monthly_to_daily(month, day_type)
            elif tier_max_unit == "kWh daily":
                tier_max_kwh_daily = \
                    tier_maximums[tier]
            else:
                raise ValueError(
                    "Can only allow 'kWh' and 'kWh daily' units. Check why "
                    "different units for record {}, month {} were not "
                    "filtered out.".format(record["label"], month)
                )
            # If the daily baseline consumption is
            # more than the max for this tier, we'll move to the next
            # tier without applying this tier's rate to any of the EV
            # charging kWh
            if daily_baseline_kwh > tier_max_kwh_daily:
                pass

            # If remaining EV charging kWh is less than the difference
            # between the daily max and and the baseline consumption,
            # this tier rate is applied to any remaining EV charging kWh
            # Loop through all the periods and apply the appropriate period
            # rate for this tier
            elif remaining_ev_charging_kwh < \
                    tier_max_kwh_daily - daily_baseline_kwh:
                for rate_period in set(rate_periods):
                    daily_charging_cost += \
                        remaining_ev_charging_kwh \
                        * rate_period_weights[rate_period] \
                        * record["energyratestructure"][rate_period][tier][
                            "rate"] \
                        + (record["energyratestructure"][rate_period][tier][
                               "adj"]
                            if "adj" in record["energyratestructure"][
                                rate_period][tier].keys() else 0)
                # No EV charging left to do
                remaining_ev_charging_kwh = 0

            # Otherwise, we'll apply this tier's rates to the remaining
            # kWh within this tier, subtract that from remaining EV
            # charging kWh, and move on to the next tier
            else:
                for rate_period in set(rate_periods):
                    daily_charging_cost += \
                        (tier_max_kwh_daily - daily_baseline_kwh) \
                        * rate_period_weights[rate_period] \
                        * record["energyratestructure"][rate_period][tier][
                            "rate"] \
                        + (record["energyratestructure"][rate_period][tier][
                               "adj"]
                            if "adj" in record["energyratestructure"][
                                rate_period][tier].keys() else 0)
                # Subtract the amount we charged in this tier from the
                # remaining charging
                remaining_ev_charging_kwh -= \
                    (tier_max_kwh_daily - daily_baseline_kwh)
        # If no max for the tier, apply the tier rate to any remaining
        # EV charging kWh
        else:
            for rate_period in set(rate_periods):
                daily_charging_cost += \
                    remaining_ev_charging_kwh \
                    * rate_period_weights[rate_period] \
                    * record["energyratestructure"][rate_period][tier][
                        "rate"] \
                    + (record["energyratestructure"][rate_period][tier]["adj"]
                        if "adj" in record["energyratestructure"][
                            rate_period][tier].keys() else 0)
            remaining_ev_charging_kwh = 0

    # Convert daily cost to monthly cost
    monthly_charging_cost = \
        daily_charging_cost \
        / convert_monthly_to_daily(day_type=day_type, month=month)

    return monthly_charging_cost


def process_record(
        record, db,
        baseline_weekday_profile, baseline_weekend_profile,
        charging_weekday_profile, charging_weekend_profile
):
    """

    :param record:
    :param db:
    :param baseline_weekday_profile:
    :param baseline_weekend_profile:
    :param charging_weekday_profile:
    :param charging_weekend_profile:
    :return:
    """
    make_db_tables(record=record, db=db,
                   baseline_weekday_profile=baseline_weekday_profile,
                   baseline_weekend_profile=baseline_weekend_profile,
                   charging_weekday_profile=charging_weekday_profile,
                   charging_weekend_profile=charging_weekend_profile
                   )

    # We'll use the totals if we have a monthly tier structure and separate
    # by weekday/weekend if we have a daily tier structure
    tier_max_is_monthly = check_if_monthly_tiers(record=record)
    day_types = ["total"] if tier_max_is_monthly else ["weekday", "weekend"]

    annual_charging_cost = 0
    for month in range(1, 13):
        lowest_rate_period_n, max_num_tiers = \
            derive_params(record=record, month=month)[1], \
            derive_params(record=record, month=month)[3]
        for day_type in day_types:
            tier_maximums = {
                tier_index:
                    record["energyratestructure"][lowest_rate_period_n][
                        tier_index]["max"]
                    if "max" in
                       record["energyratestructure"][lowest_rate_period_n][
                           tier_index].keys()
                    else None
                for tier_index in range(0, max_num_tiers)
            }

            annual_charging_cost += calculate_monthly_cost(
                record=record, month=month,
                day_type=day_type,
                tier_maximums=tier_maximums,
                db=db
            )
    return annual_charging_cost
