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

""" Contains unit tests for exceptions."""

__author__ = 'tmatsuo@google.com (Takashi Matsuo)'


import unittest

import errors


class ErrorTestCase(unittest.TestCase):

  def setUp(self):
    pass

  def tearDown(self):
    pass

  def testException(self):
    error_message = 'It is for test.'
    try:
      raise errors.NotFoundError(error_message)
    except errors.Error as e:
      self.assertEqual(error_message, e.error_message)
    try:
      raise errors.OperationFailedError(error_message)
    except errors.Error as e:
      self.assertEqual(error_message, e.error_message)


if __name__ == '__main__':
  unittest.main()
