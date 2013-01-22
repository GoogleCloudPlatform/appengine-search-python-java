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

""" Contains unit tests using search API.
"""

__author__ = 'tmatsuo@google.com (Takashi Matsuo), amyu@google.com (Amy Unruh)'

import os
import shutil
import tempfile
import unittest
import base64
import pickle

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import files
from google.appengine.api import queueinfo
from google.appengine.api import search
from google.appengine.api import users
from google.appengine.api.search import simple_search_stub
from google.appengine.api.taskqueue import taskqueue_stub
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.ext import testbed
from google.appengine.datastore import datastore_stub_util

import admin_handlers
import config
import docs
import errors
import models
import utils

PRODUCT_PARAMS = dict(
  pid='testproduct',
  name='The adventures of Sherlock Holmes',
  category='books',
  price=2000,
  publisher='Baker Books',
  title='The adventures of Sherlock Holmes',
  pages=200,
  author='Sir Arthur Conan Doyle',
  description='The adventures of Sherlock Holmes',
  isbn='123456')

def _add_mark(v, i):
  if isinstance(v, basestring):
    return '%s %s' % (v, i)
  else:
    return v + i

def create_test_data(n):
  """Create specified number of test data with marks added to its values."""
  ret = []
  for i in xrange(n):
    params = dict()
    for key in PRODUCT_PARAMS.keys():
      if key == 'category':
        # untouched
        params[key] = PRODUCT_PARAMS[key]
      else:
        params[key] = _add_mark(PRODUCT_PARAMS[key], i)
    ret.append(params)
  return ret


class FTSTestCase(unittest.TestCase):

  def setUp(self):
    # First, create an instance of the Testbed class.
    self.testbed = testbed.Testbed()
    # Then activate the testbed, which prepares the service stubs for use.
    self.testbed.activate()
    # Create a consistency policy that will simulate the High
    # Replication consistency model. It's easier to test with
    # probability 1.
    self.policy = \
      datastore_stub_util.PseudoRandomHRConsistencyPolicy(probability=1)
    # Initialize the datastore stub with this policy.
    self.testbed.init_datastore_v3_stub(consistency_policy=self.policy)
    self.testbed.init_memcache_stub()
    self.testbed.init_taskqueue_stub()

    # search stub is not available via testbed, so doing this by
    # myself.
    apiproxy_stub_map.apiproxy.RegisterStub(
      'search',
      simple_search_stub.SearchServiceStub())

  def tearDown(self):
    self.testbed.deactivate()

  def testBuildProduct(self):
    models.Category.buildAllCategories()
    self.assertRaises(errors.Error, docs.Product.buildProduct, {})

    product = docs.Product.buildProduct(PRODUCT_PARAMS)

    # make sure that a product entity is stored in Datastore
    self.assert_(product is not None)
    self.assertEqual(product.price, PRODUCT_PARAMS['price'])

    # make sure the search actually works
    sq = search.Query(query_string='Sir Arthur Conan Doyle')
    res = docs.Product.getIndex().search(sq)
    self.assertEqual(res.number_found, 1)
    for doc in res:
      self.assertEqual(doc.doc_id, product.doc_id)

  def testUpdateAverageRatingNonBatch1(self):
    "Test non-batch mode avg ratings updating."
    models.Category.buildAllCategories()
    product = docs.Product.buildProduct(PRODUCT_PARAMS)
    self.assertEqual(product.avg_rating, 0)
    config.BATCH_RATINGS_UPDATE = False

    # Create a review object and invoke updateAverageRating.
    review = models.Review(product_key=product.key,
                           username='bob',
                           rating=4,
                           comment='comment'
                           )
    review.put()
    utils.updateAverageRating(review.key)
    review = models.Review(product_key=product.key,
                           username='bob2',
                           rating=1,
                           comment='comment'
                           )
    review.put()
    utils.updateAverageRating(review.key)

    product = models.Product.get_by_id(product.pid)
    # check that the parent product rating average has been updated based on the
    # two reviews
    self.assertEqual(product.avg_rating, 2.5)
    # with BATCH_RATINGS_UPDATE = False, the product document's average rating
    # field ('ar') should be updated to match its associated product
    # entity.

    # run the task queue tasks
    taskq = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    tasks = taskq.GetTasks("default")
    taskq.FlushQueue("default")
    while tasks:
      for task in tasks:
        deferred.run(base64.b64decode(task["body"]))
      tasks = taskq.GetTasks("default")
      taskq.FlushQueue("default")

    sq = search.Query(query_string='ar:2.5')
    res = docs.Product.getIndex().search(sq)
    self.assertEqual(res.number_found, 1)
    for doc in res:
      self.assertEqual(doc.doc_id, product.doc_id)

  def testUpdateAverageRatingNonBatch2(self):
    "Check the number of tasks added to the queue when reviews are created."

    models.Category.buildAllCategories()
    product = docs.Product.buildProduct(PRODUCT_PARAMS)
    config.BATCH_RATINGS_UPDATE = False

    # Create a review object and invoke updateAverageRating.
    review = models.Review(product_key=product.key,
                           username='bob',
                           rating=4,
                           comment='comment'
                           )
    review.put()
    utils.updateAverageRating(review.key)
    review = models.Review(product_key=product.key,
                           username='bob2',
                           rating=1,
                           comment='comment'
                           )
    review.put()
    utils.updateAverageRating(review.key)

    # Check the number of tasks in the queue
    taskq = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    tasks = taskq.GetTasks("default")
    taskq.FlushQueue("default")
    self.assertEqual(len(tasks), 2)

  def testUpdateAverageRatingBatch(self):
    "Test batch mode avg ratings updating."
    models.Category.buildAllCategories()
    product = docs.Product.buildProduct(PRODUCT_PARAMS)
    config.BATCH_RATINGS_UPDATE = True

    # Create a review object and invoke updateAverageRating.
    review = models.Review(product_key=product.key,
                           username='bob',
                           rating=5,
                           comment='comment'
                           )
    review.put()
    utils.updateAverageRating(review.key)

    # there should not be any task queue tasks
    taskq = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    tasks = taskq.GetTasks("default")
    taskq.FlushQueue("default")
    self.assertEqual(len(tasks), 0)

    # with BATCH_RATINGS_UPDATE = True, the product document's average rating
    # field ('ar') should not yet be updated to match its associated product
    # entity.
    product = models.Product.get_by_id(product.pid)
    sq = search.Query(query_string='ar:5.0')
    res = docs.Product.getIndex().search(sq)
    self.assertEqual(res.number_found, 0)


if __name__ == '__main__':
  unittest.main()
