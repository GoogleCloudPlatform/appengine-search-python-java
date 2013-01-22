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

""" The base request handler class.
"""


import webapp2
from webapp2_extras import jinja2
import json

from google.appengine.api import users


class BaseHandler(webapp2.RequestHandler):
  """The other handlers inherit from this class.  Provides some helper methods
  for rendering a template and generating template links."""

  @classmethod
  def logged_in(cls, handler_method):
    """
    This decorator requires a logged-in user, and returns 403 otherwise.
    """
    def auth_required(self, *args, **kwargs):
      if (users.get_current_user() or
          self.request.headers.get('X-AppEngine-Cron')):
        handler_method(self, *args, **kwargs)
      else:
        self.error(403)
    return auth_required

  @webapp2.cached_property
  def jinja2(self):
    return jinja2.get_jinja2(app=self.app)

  def render_template(self, filename, template_args):
    template_args.update(self.generateSidebarLinksDict())
    self.response.write(self.jinja2.render_template(filename, **template_args))

  def render_json(self, response):
    self.response.write("%s(%s);" % (self.request.GET['callback'],
                                     json.dumps(response)))

  def getLoginLink(self):
    """Generate login or logout link and text, depending upon the logged-in
    status of the client."""
    if users.get_current_user():
      url = users.create_logout_url(self.request.uri)
      url_linktext = 'Logout'
    else:
      url = users.create_login_url(self.request.uri)
      url_linktext = 'Login'
    return (url, url_linktext)

  def getAdminManageLink(self):
    """Build link to the admin management page, if the user is logged in."""
    if users.get_current_user():
      admin_url = '/admin/manage'
      return (admin_url, 'Admin/Add sample data')
    else:
      return (None, None)

  def createProductAdminLink(self):
    if users.get_current_user():
      admin_create_url = '/admin/create_product'
      return (admin_create_url, 'Create new product (admin)')
    else:
      return (None, None)

  def generateSidebarLinksDict(self):
    """Build a dict containing login/logout and admin links, which will be
    included in the sidebar for all app pages."""

    url, url_linktext = self.getLoginLink()
    admin_create_url, admin_create_text = self.createProductAdminLink()
    admin_url, admin_text = self.getAdminManageLink()
    return {
        'admin_create_url': admin_create_url,
        'admin_create_text': admin_create_text,
        'admin_url': admin_url,
        'admin_text': admin_text,
        'url': url,
        'url_linktext': url_linktext
        }

