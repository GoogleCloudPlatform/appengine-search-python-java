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

"""Defines the routing for the app's admin request handlers
(those that require administrative access)."""

from admin_handlers import *

import webapp2

application = webapp2.WSGIApplication(
    [
        ('/admin/manage', AdminHandler),
        ('/admin/create_product', CreateProductHandler),
        ('/admin/delete_product', DeleteProductHandler)
    ],
    debug=True)

