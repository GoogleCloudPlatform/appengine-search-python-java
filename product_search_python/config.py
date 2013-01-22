#!/usr/bin/env python
#
# Copyright 2012 Google Inc.
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

""" Holds configuration settings.
"""


PRODUCT_INDEX_NAME = 'productsearch1'  # The document index name.
    # An index name must be a visible printable
    # ASCII string not starting with '!'. Whitespace characters are
    # excluded.

STORE_INDEX_NAME = 'stores1'

# set BATCH_RATINGS_UPDATE to False to update documents with changed ratings
# info right away.  If True, updates will only occur when triggered by
# an admin request or a cron job.  See cron.yaml for an example.
BATCH_RATINGS_UPDATE = False
# BATCH_RATINGS_UPDATE = True

# The max and min (integer) ratings values allowed.
RATING_MIN = 1
RATING_MAX = 5

# the number of search results to display per page
DOC_LIMIT = 3

SAMPLE_DATA_BOOKS = 'sample_data_books.csv'
SAMPLE_DATA_TVS = 'sample_data_tvs.csv'
DEMO_UPDATE_BOOKS_DATA = 'sample_data_books_update.csv'

# the size of the import batches, when reading from the csv file.  Must not
# exceed 100.
IMPORT_BATCH_SIZE = 5
