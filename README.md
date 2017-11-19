This software calculates the cost for charging an electric vehicle by utility
and rate.

Rates are from the OpenEI.org U.S. Utilities Rate Database (USURDB) available
at https://openei.org/apps/USURDB/.

The API documentation is at https://openei.org/services/doc/rest/util_rates/.
You will need an API key, which you can obtain at
https://openei.org/services/api/signup/. Include this key in a file named
'api_key.txt' in the 'settings' subdirectory. You can change the request
parameters in the the 'request_params.csv' file in the 'settings' subdirectory.

To make a table with the EV charging cost by utility rate, navigate to the
directory where you downloaded this code and run the 'make_table.py' script:

>> python make_table.py

This will download the database records and filter them based on several
criteria including:
1. Missing energy structure -- record has not 'energyratestructure' defined
2. Rate end date in the past
3. Missing rate
4. Unexpected units
5. Non-conforming tier structure -- we expect all periods to have the same tier
 structure
6. Keywords -- we exclude rates that include certain keywords in the rate name;
 the keywords are included in the 'keywords_for_filtering.csv' file in the
 'settings' subdirectory. You can edit this file to add or remove keywords.

All filtered records and the reason for filtering will be included in a file
called 'filtered_records.csv' in the 'results' subdirectory.

For the remaining records, the script will calculate the cost to charge an EV
based on the USURDB data and two input files ('baseline_profile.csv' and
'charging_profile.csv'), which you must include in the 'inputs' subdirectory.
These files contain average profiles by month, hour, and day type (i.e.
weekday or weekend) for the 'baseline' (i.e. pre-EV) consumption and for the
EV charging. The included sample profiles are based on supplementary data from:
M. Muratori, "Impact of uncoordinated plug-in electric vehicle charging on
residential power demand." Forthcoming.

The EV charging cost results are saved in a file named
'ev_charging_cost_by_utility_rate.csv' in the 'results' directory.