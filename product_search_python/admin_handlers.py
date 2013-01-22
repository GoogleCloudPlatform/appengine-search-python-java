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

""" Contains the admin request handlers for the app (those that require
administrative access).
"""

import csv
import logging
import os
import urllib
import uuid

from base_handler import BaseHandler
import categories
import config
import docs
import errors
import models
import stores
import utils

from google.appengine.api import users
from google.appengine.ext.deferred import defer
from google.appengine.ext import ndb
from google.appengine.api import search


def reinitAll(sample_data=True):
  """
  Deletes all product entities and documents, essentially resetting the app
  state, then loads in static sample data if requested. Hardwired for the
  expected product types in the sample data.
  (Re)loads store location data from stores.py as well.
  This function is intended to be run 'offline' (e.g., via a Task Queue task).
  As an extension to this functionality, the channel ID could be used to notify
  when done."""

  # delete all the product and review entities
  review_keys = models.Review.query().fetch(keys_only=True)
  ndb.delete_multi(review_keys)
  prod_keys = models.Product.query().fetch(keys_only=True)
  ndb.delete_multi(prod_keys)
  # delete all the associated product documents in the doc and
  # store indexes
  docs.Product.deleteAllInProductIndex()
  docs.Store.deleteAllInIndex()
  # load in sample data if indicated
  if sample_data:
    logging.info('Loading product sample data')
    # Load from csv sample files.
    # The following are hardwired to the format of the sample data files
    # for the two example product types ('books' and 'hd televisions')-- see
    # categories.py
    datafile = os.path.join('data', config.SAMPLE_DATA_BOOKS)
    # books
    reader = csv.DictReader(
        open(datafile, 'r'),
        ['pid', 'name', 'category', 'price',
         'publisher', 'title', 'pages', 'author',
         'description', 'isbn'])
    importData(reader)
    datafile = os.path.join('data', config.SAMPLE_DATA_TVS)
    # tvs
    reader = csv.DictReader(
        open(datafile, 'r'),
        ['pid', 'name', 'category', 'price',
         'size', 'brand', 'tv_type',
         'description'])
    importData(reader)

    # next create docs from store location info
    loadStoreLocationData()

  logging.info('Re-initialization complete.')

def loadStoreLocationData():
    # create documents from store location info
    # currently logs but otherwise swallows search errors.
    slocs = stores.stores
    for s in slocs:
      logging.info("s: %s", s)
      geopoint = search.GeoPoint(s[3][0], s[3][1])
      fields = [search.TextField(name=docs.Store.STORE_NAME, value=s[1]),
                search.TextField(name=docs.Store.STORE_ADDRESS, value=s[2]),
                search.GeoField(name=docs.Store.STORE_LOCATION, value=geopoint)
              ]
      d = search.Document(doc_id=s[0], fields=fields)
      try:
        add_result = search.Index(config.STORE_INDEX_NAME).put(d)
      except search.Error:
        logging.exception("Error adding document:")


def importData(reader):
  """Import via the csv reader iterator using the specified batch size as set in
  the config file.  We want to ensure the batch is not too large-- we allow 100
  rows/products max per batch."""
  MAX_BATCH_SIZE = 100
  rows = []
  # index in batches
  # ensure the batch size in the config file is not over the max or < 1.
  batchsize = utils.intClamp(config.IMPORT_BATCH_SIZE, 1, MAX_BATCH_SIZE)
  logging.debug('batchsize: %s', batchsize)
  for row in reader:
    if len(rows) == batchsize:
      docs.Product.buildProductBatch(rows)
      rows = [row]
    else:
      rows.append(row)
  if rows:
    docs.Product.buildProductBatch(rows)


class AdminHandler(BaseHandler):
  """Displays the admin page."""

  def buildAdminPage(self, notification=None):
    # If necessary, build the app's product categories now.  This is done only
    # if there are no Category entities in the datastore.
    models.Category.buildAllCategories()
    tdict = {
        'sampleb': config.SAMPLE_DATA_BOOKS,
        'samplet': config.SAMPLE_DATA_TVS,
        'update_sample': config.DEMO_UPDATE_BOOKS_DATA}
    if notification:
      tdict['notification'] = notification
    self.render_template('admin.html', tdict)

  @BaseHandler.logged_in
  def get(self):
    action = self.request.get('action')
    if action == 'reinit':
      # reinitialise the app data to the sample data
      defer(reinitAll)
      self.buildAdminPage(notification="Reinitialization performed.")
    elif action == 'demo_update':
      # update the sample data, from (hardwired) book update
      # data. Demonstrates updating some existing products, and adding some new
      # ones.
      logging.info('Loading product sample update data')
      # The following is hardwired to the known format of the sample data file
      datafile = os.path.join('data', config.DEMO_UPDATE_BOOKS_DATA)
      reader = csv.DictReader(
          open(datafile, 'r'),
          ['pid', 'name', 'category', 'price',
           'publisher', 'title', 'pages', 'author',
           'description', 'isbn'])
      for row in reader:
        docs.Product.buildProduct(row)
      self.buildAdminPage(notification="Demo update performed.")

    elif action == 'update_ratings':
      self.update_ratings()
      self.buildAdminPage(notification="Ratings update performed.")
    else:
      self.buildAdminPage()

  def update_ratings(self):
    """Find the products that have had an average ratings change, and need their
    associated documents updated (re-indexed) to reflect that change; and
    re-index those docs in batch. There will only
    be such products if config.BATCH_RATINGS_UPDATE is True; otherwise the
    associated documents will be updated right away."""
    # get the pids of the products that need review info updated in their
    # associated documents.
    pkeys = models.Product.query(
        models.Product.needs_review_reindex == True).fetch(keys_only=True)
    # re-index these docs in batch
    models.Product.updateProdDocsWithNewRating(pkeys)


class DeleteProductHandler(BaseHandler):
  """Remove data for the product with the given pid, including that product's
  reviews and its associated indexed document."""

  @BaseHandler.logged_in
  def post(self):
    pid = self.request.get('pid')
    if not pid:  # this should not be reached
      msg = 'There was a problem: no product id given.'
      logging.error(msg)
      url = '/'
      linktext = 'Go to product search page.'
      self.render_template(
          'notification.html',
          {'title': 'Error', 'msg': msg,
           'goto_url': url, 'linktext': linktext})
      return

    # Delete the product entity within a transaction, and define transactional
    # tasks for deleting the product's reviews and its associated document.
    # These tasks will only be run if the transaction successfully commits.
    def _tx():
      prod = models.Product.get_by_id(pid)
      if prod:
        prod.key.delete()
        defer(models.Review.deleteReviews, prod.key.id(), _transactional=True)
        defer(
            docs.Product.removeProductDocByPid,
            prod.key.id(), _transactional=True)

    ndb.transaction(_tx)
    # indicate success
    msg = (
        'The product with product id %s has been ' +
        'successfully removed.') % (pid,)
    url = '/'
    linktext = 'Go to product search page.'
    self.render_template(
        'notification.html',
        {'title': 'Product Removed', 'msg': msg,
         'goto_url': url, 'linktext': linktext})


class CreateProductHandler(BaseHandler):
  """Handler to create a new product: this constitutes both a product entity
  and its associated indexed document."""

  def parseParams(self):
    """Filter the param set to the expected params."""

    pid = self.request.get('pid')
    doc = docs.Product.getDocFromPid(pid)
    params = {}
    if doc:  # populate default params from the doc
      fields = doc.fields
      for f in fields:
        params[f.name] = f.value
    else:
      # start with the 'core' fields
      params = {
          'pid': uuid.uuid4().hex,  # auto-generate default UID
          'name': '',
          'description': '',
          'category': '',
          'price': ''}
      pf = categories.product_dict
      # add the fields specific to the categories
      for _, cdict in pf.iteritems():
        temp = {}
        for elt in cdict.keys():
          temp[elt] = ''
        params.update(temp)

    for k, v in params.iteritems():
      # Process the request params. Possibly replace default values.
      params[k] = self.request.get(k, v)
    return params

  @BaseHandler.logged_in
  def get(self):
    params = self.parseParams()
    self.render_template('create_product.html', params)

  @BaseHandler.logged_in
  def post(self):
    self.createProduct(self.parseParams())

  def createProduct(self, params):
    """Create a product entity and associated document from the given params
    dict."""

    try:
      product = docs.Product.buildProduct(params)
      self.redirect(
          '/product?' + urllib.urlencode(
              {'pid': product.pid, 'pname': params['name'],
               'category': product.category
              }))
    except errors.Error as e:
      logging.exception('Error:')
      params['error_message'] = e.error_message
      self.render_template('create_product.html', params)


