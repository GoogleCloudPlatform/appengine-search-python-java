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

"""Specifies product category information for the app.  In this sample, there
are two categories: books, and televisions.
"""
from google.appengine.api import search


televisions = {'name': 'hd televisions', 'children': []}
books = {'name': 'books', 'children': []}

ctree =  {'name': 'root', 'children': [books, televisions]}

# [The core fields that all products share are: product id, name, description,
# category, category name, and price]
# Define the non-'core' (differing) product fields for each category
# above, and their types.
product_dict =  {'hd televisions': {'size': search.NumberField,
                                 'brand': search.TextField,
                                 'tv_type': search.TextField},
                 'books': {'publisher': search.TextField,
                           'pages': search.NumberField,
                           'author': search.TextField,
                           'title': search.TextField,
                           'isbn': search.TextField}
                }
