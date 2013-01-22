#!/usr/bin/env python
#
# Copyright 2011 Google Inc.
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

"""Defines the routing for the app's non-admin handlers.
"""


from handlers import *
import webapp2

application = webapp2.WSGIApplication(
    [('/', IndexHandler),
     ('/psearch', ProductSearchHandler),
     ('/product', ShowProductHandler),
     ('/reviews', ShowReviewsHandler),
     ('/create_review', CreateReviewHandler),
     ('/get_store_locations', StoreLocationHandler)
    ],
    debug=True)


