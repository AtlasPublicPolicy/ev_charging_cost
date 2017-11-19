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
Method for requesting utility rate records from the U.S. Utility
Rates Database (USURDB) on OpenEI.org.

API documentation is here:
https://openei.org/services/doc/rest/util_rates/

You'll need an API key, which you can obtain at here:
https://openei.org/services/api/signup/

Include your API key in a file named 'api_key.txt' in the 'settings' directory.
"""

import requests
import json


def request_records(request_params):
    """
    Download utility rate records from USURDB given a set of request
    parameters.
    :param request_params: dictionary with request parameter names as
    keys and the parameter values
    :return:
    """
    records = requests.get(
        "https://api.openei.org/utility_rates?", params=request_params
    )
    request_content = records.content

    # strict=False prevents an error (control characters are allowed inside
    # strings)
    json_records = json.loads(request_content, strict=False)

    return json_records
