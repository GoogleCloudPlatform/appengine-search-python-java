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

"""Contains the non-admin ('user-facing') request handlers for the app."""


import logging
import urllib
import wsgiref

from base_handler import BaseHandler
import config
import docs
import models
import utils

from google.appengine.api import search
from google.appengine.api import users
from google.appengine.ext.deferred import defer
from google.appengine.ext import ndb


class IndexHandler(BaseHandler):
  """Displays the 'home' page."""

  def get(self):
    cat_info = models.Category.getCategoryInfo()
    sort_info = docs.Product.getSortMenu()
    template_values = {
        'cat_info': cat_info,
        'sort_info': sort_info,
    }
    self.render_template('index.html', template_values)


class ShowProductHandler(BaseHandler):
  """Display product details."""

  def parseParams(self):
    """Filter the param set to the expected params."""
    # The dict can be modified to add any defined defaults.

    params = {
        'pid': '',
        'pname': '',
        'comment': '',
        'rating': '',
        'category': ''
    }
    for k, v in params.iteritems():
      # Possibly replace default values.
      params[k] = self.request.get(k, v)
    return params

  def get(self):
    """Do a document search for the given product id,
    and display the retrieved document fields."""

    params = self.parseParams()

    pid = params['pid']
    if not pid:
      # we should not reach this
      msg = 'Error: do not have product id.'
      url = '/'
      linktext = 'Go to product search page.'
      self.render_template(
          'notification.html',
          {'title': 'Error', 'msg': msg,
           'goto_url': url, 'linktext': linktext})
      return
    doc = docs.Product.getDocFromPid(pid)
    if not doc:
      error_message = ('Document not found for pid %s.' % pid)
      return self.abort(404, error_message)
      logging.error(error_message)
    pdoc = docs.Product(doc)
    pname = pdoc.getName()
    app_url = wsgiref.util.application_uri(self.request.environ)
    rlink = '/reviews?' + urllib.urlencode({'pid': pid, 'pname': pname})
    template_values = {
        'app_url': app_url,
        'pid': pid,
        'pname': pname,
        'review_link': rlink,
        'comment': params['comment'],
        'rating': params['rating'],
        'category': pdoc.getCategory(),
        'prod_doc': doc,
        # for this demo, 'admin' status simply equates to being logged in
        'user_is_admin': users.get_current_user()}
    self.render_template('product.html', template_values)


class CreateReviewHandler(BaseHandler):
  """Process the submission of a new review."""

  def parseParams(self):
    """Filter the param set to the expected params."""

    params = {
        'pid': '',
        'pname': '',
        'comment': 'this is a great product',
        'rating': '5',
        'category': ''
    }
    for k, v in params.iteritems():
      # Possibly replace default values.
      params[k] = self.request.get(k, v)
    return params

  def post(self):
    """Create a new review entity from the submitted information."""
    self.createReview(self.parseParams())

  def createReview(self, params):
    """Create a new review entity from the information in the params dict."""

    author = users.get_current_user()
    comment = params['comment']
    pid = params['pid']
    pname = params['pname']
    if not pid:
      msg = 'Could not get pid; aborting creation of review.'
      logging.error(msg)
      url = '/'
      linktext = 'Go to product search page.'
      self.render_template(
          'notification.html',
          {'title': 'Error', 'msg': msg,
           'goto_url': url, 'linktext': linktext})
      return
    if not comment:
      logging.info('comment not provided')
      self.redirect('/product?' + urllib.urlencode(params))
      return
    rstring = params['rating']
    # confirm that the rating is an int in the allowed range.
    try:
      rating = int(rstring)
      if rating < config.RATING_MIN or rating > config.RATING_MAX:
        logging.warn('Rating %s out of allowed range', rating)
        params['rating'] = ''
        self.redirect('/product?' + urllib.urlencode(params))
        return
    except ValueError:
      logging.error('bad rating: %s', rstring)
      params['rating'] = ''
      self.redirect('/product?' + urllib.urlencode(params))
      return
    review = self.createAndAddReview(pid, author, rating, comment)
    prod_url = '/product?' + urllib.urlencode({'pid': pid, 'pname': pname})
    if not review:
      msg = 'Error creating review.'
      logging.error(msg)
      self.render_template(
          'notification.html',
          {'title': 'Error', 'msg': msg,
           'goto_url': prod_url, 'linktext': 'Back to product.'})
      return
    rparams = {'prod_url': prod_url, 'pname': pname, 'review': review}
    self.render_template('review.html', rparams)

  def createAndAddReview(self, pid, user, rating, comment):
    """Given review information, create the new review entity, pointing via key
    to the associated 'parent' product entity.  """

    # get the account info of the user submitting the review. If the
    # client is not logged in (which is okay), just make them 'anonymous'.
    if user:
      username = user.nickname().split('@')[0]
    else:
      username = 'anonymous'

    prod = models.Product.get_by_id(pid)
    if not prod:
      error_message = 'could not get product for pid %s' % pid
      logging.error(error_message)
      return self.abort(404, error_message)

    rid = models.Review.allocate_ids(size=1)[0]
    key = ndb.Key(models.Review._get_kind(), rid)

    def _tx():
      review = models.Review(
          key=key,
          product_key=prod.key,
          username=username, rating=rating,
          comment=comment)
      review.put()
      # in a transactional task, update the parent product's average
      # rating to include this review's rating, and flag the review as
      # processed.
      defer(utils.updateAverageRating, key, _transactional=True)
      return review
    return ndb.transaction(_tx)


class ProductSearchHandler(BaseHandler):
  """The handler for doing a product search."""

  _DEFAULT_DOC_LIMIT = 3  #default number of search results to display per page.
  _OFFSET_LIMIT = 1000

  def parseParams(self):
    """Filter the param set to the expected params."""
    params = {
        'qtype': '',
        'query': '',
        'category': '',
        'sort': '',
        'rating': '',
        'offset': '0'
    }
    for k, v in params.iteritems():
      # Possibly replace default values.
      params[k] = self.request.get(k, v)
    return params

  def post(self):
    params = self.parseParams()
    self.redirect('/psearch?' + urllib.urlencode(
        dict([k, v.encode('utf-8')] for k, v in params.items())))

  def _getDocLimit(self):
    """if the doc limit is not set in the config file, use the default."""
    doc_limit = self._DEFAULT_DOC_LIMIT
    try:
      doc_limit = int(config.DOC_LIMIT)
    except ValueError:
      logging.error('DOC_LIMIT not properly set in config file; using default.')
    return doc_limit

  def get(self):
    """Handle a product search request."""

    params = self.parseParams()
    self.doProductSearch(params)

  def doProductSearch(self, params):
    """Perform a product search and display the results."""

    # the defined product categories
    cat_info = models.Category.getCategoryInfo()
    # the product fields that we can sort on from the UI, and their mappings to
    # search.SortExpression parameters
    sort_info = docs.Product.getSortMenu()
    sort_dict = docs.Product.getSortDict()
    query = params.get('query', '')
    user_query = query
    doc_limit = self._getDocLimit()

    categoryq = params.get('category')
    if categoryq:
      # add specification of the category to the query
      # Because the category field is atomic, put the category string
      # in quotes for the search.
      query += ' %s:"%s"' % (docs.Product.CATEGORY, categoryq)

    sortq = params.get('sort')
    try:
      offsetval = int(params.get('offset', 0))
    except ValueError:
      offsetval = 0

    # Check to see if the query parameters include a ratings filter, and
    # add that to the final query string if so.  At the same time, generate
    # 'ratings bucket' counts and links-- based on the query prior to addition
    # of the ratings filter-- for sidebar display.
    query, rlinks = self._generateRatingsInfo(
        params, query, user_query, sortq, categoryq)
    logging.debug('query: %s', query.strip())

    try:
      # build the query and perform the search
      search_query = self._buildQuery(
          query, sortq, sort_dict, doc_limit, offsetval)
      search_results = docs.Product.getIndex().search(search_query)
      returned_count = len(search_results.results)

    except search.Error:
      logging.exception("Search error:")  # log the exception stack trace
      msg = 'There was a search error (see logs).'
      url = '/'
      linktext = 'Go to product search page.'
      self.render_template(
          'notification.html',
          {'title': 'Error', 'msg': msg,
           'goto_url': url, 'linktext': linktext})
      return

    # cat_name = models.Category.getCategoryName(categoryq)
    psearch_response = []
    # For each document returned from the search
    for doc in search_results:
      # logging.info("doc: %s ", doc)
      pdoc = docs.Product(doc)
      # use the description field as the default description snippet, since
      # snippeting is not supported on the dev app server.
      description_snippet = pdoc.getDescription()
      price = pdoc.getPrice()
      # on the dev app server, the doc.expressions property won't be populated.
      for expr in doc.expressions:
        if expr.name == docs.Product.DESCRIPTION:
          description_snippet = expr.value
        # uncomment to use 'adjusted price', which should be
        # defined in returned_expressions in _buildQuery() below, as the
        # displayed price.
        # elif expr.name == 'adjusted_price':
          # price = expr.value

      # get field information from the returned doc
      pid = pdoc.getPID()
      cat = catname = pdoc.getCategory()
      pname = pdoc.getName()
      avg_rating = pdoc.getAvgRating()
      # for this result, generate a result array of selected doc fields, to
      # pass to the template renderer
      psearch_response.append(
          [doc, urllib.quote_plus(pid), cat,
           description_snippet, price, pname, catname, avg_rating])
    if not query:
      print_query = 'All'
    else:
      print_query = query

    # Build the next/previous pagination links for the result set.
    (prev_link, next_link) = self._generatePaginationLinks(
        offsetval, returned_count,
        search_results.number_found, params)

    logging.debug('returned_count: %s', returned_count)
    # construct the template values
    template_values = {
        'base_pquery': user_query, 'next_link': next_link,
        'prev_link': prev_link, 'qtype': 'product',
        'query': query, 'print_query': print_query,
        'pcategory': categoryq, 'sort_order': sortq, 'category_name': categoryq,
        'first_res': offsetval + 1, 'last_res': offsetval + returned_count,
        'returned_count': returned_count,
        'number_found': search_results.number_found,
        'search_response': psearch_response,
        'cat_info': cat_info, 'sort_info': sort_info,
        'ratings_links': rlinks}
    # render the result page.
    self.render_template('index.html', template_values)

  def _buildQuery(self, query, sortq, sort_dict, doc_limit, offsetval):
    """Build and return a search query object."""

    # computed and returned fields examples.  Their use is not required
    # for the application to function correctly.
    computed_expr = search.FieldExpression(name='adjusted_price',
        expression='price * 1.08')
    returned_fields = [docs.Product.PID, docs.Product.DESCRIPTION,
                docs.Product.CATEGORY, docs.Product.AVG_RATING,
                docs.Product.PRICE, docs.Product.PRODUCT_NAME]

    if sortq == 'relevance':
      # If sorting on 'relevance', use the Match scorer.
      sortopts = search.SortOptions(match_scorer=search.MatchScorer())
      search_query = search.Query(
          query_string=query.strip(),
          options=search.QueryOptions(
              limit=doc_limit,
              offset=offsetval,
              sort_options=sortopts,
              snippeted_fields=[docs.Product.DESCRIPTION],
              returned_expressions=[computed_expr],
              returned_fields=returned_fields
              ))
    else:
      # Otherwise (not sorting on relevance), use the selected field as the
      # first dimension of the sort expression, and the average rating as the
      # second dimension, unless we're sorting on rating, in which case price
      # is the second sort dimension.
      # We get the sort direction and default from the 'sort_dict' var.
      if sortq == docs.Product.AVG_RATING:
        expr_list = [sort_dict.get(sortq), sort_dict.get(docs.Product.PRICE)]
      else:
        expr_list = [sort_dict.get(sortq), sort_dict.get(
              docs.Product.AVG_RATING)]
      sortopts = search.SortOptions(expressions=expr_list)
      # logging.info("sortopts: %s", sortopts)
      search_query = search.Query(
          query_string=query.strip(),
          options=search.QueryOptions(
              limit=doc_limit,
              offset=offsetval,
              sort_options=sortopts,
              snippeted_fields=[docs.Product.DESCRIPTION],
              returned_expressions=[computed_expr],
              returned_fields=returned_fields
              ))
    return search_query

  def _generateRatingsInfo(self, params, query, user_query, sort, category):
    """Add a ratings filter to the query as necessary, and build the
    sidebar ratings buckets content."""

    orig_query = query
    try:
      n = int(params.get('rating', 0))
      # check that rating is not out of range
      if n < config.RATING_MIN or n > config.RATING_MAX:
        n = None
    except ValueError:
      n = None
    if n:
      if n < config.RATING_MAX:
        query += ' %s >= %s %s < %s' % (docs.Product.AVG_RATING, n,
                                        docs.Product.AVG_RATING, n+1)
      else:  # max rating
        query += ' %s:%s' % (docs.Product.AVG_RATING, n)
    query_info = {'query': user_query.encode('utf-8'), 'sort': sort,
             'category': category}
    rlinks = docs.Product.generateRatingsLinks(orig_query, query_info)
    return (query, rlinks)

  def _generatePaginationLinks(
        self, offsetval, returned_count, number_found, params):
    """Generate the next/prev pagination links for the query.  Detect when we're
    out of results in a given direction and don't generate the link in that
    case."""

    doc_limit = self._getDocLimit()
    pcopy = params.copy()
    if offsetval - doc_limit >= 0:
      pcopy['offset'] = offsetval - doc_limit
      prev_link = '/psearch?' + urllib.urlencode(pcopy)
    else:
      prev_link = None
    if ((offsetval + doc_limit <= self._OFFSET_LIMIT)
        and (returned_count == doc_limit)
        and (offsetval + returned_count < number_found)):
      pcopy['offset'] = offsetval + doc_limit
      next_link = '/psearch?' + urllib.urlencode(pcopy)
    else:
      next_link = None
    return (prev_link, next_link)


class ShowReviewsHandler(BaseHandler):
  """Show the reviews for a given product.  This information is pulled from the
  datastore Review entities."""

  def get(self):
    """Show a list of reviews for the product indicated by the 'pid' request
    parameter."""

    pid = self.request.get('pid')
    pname = self.request.get('pname')
    if pid:
      # find the product entity corresponding to that pid
      prod = models.Product.get_by_id(pid)
      if prod:
        # get the product's average rating, over all its reviews
        # get the list of review entities for the product
        avg_rating = prod.avg_rating
        reviews = prod.reviews()
        logging.debug('reviews: %s', reviews)
      else:
        error_message = 'could not get product for pid %s' % pid
        logging.error(error_message)
        return self.abort(404, error_message)
      rlist = [[r.username, r.rating, str(r.comment)] for r in reviews]

      # build a template dict with the review and product information
      prod_url = '/product?' + urllib.urlencode({'pid': pid, 'pname': pname})
      template_values = {
          'rlist': rlist,
          'prod_url': prod_url,
          'pname': pname,
          'avg_rating': avg_rating}
      # render the template.
      self.render_template('reviews.html', template_values)


class StoreLocationHandler(BaseHandler):
  """Show the reviews for a given product.  This information is pulled from the
  datastore Review entities."""

  def get(self):
    """Show a list of reviews for the product indicated by the 'pid' request
    parameter."""

    query = self.request.get('location_query')
    lat = self.request.get('latitude')
    lon = self.request.get('longitude')
    # the location query from the client will have this form:
    # distance(store_location, geopoint(37.7899528, -122.3908226)) < 40000
    # logging.info('location query: %s, lat %s, lon %s', query, lat, lon)
    try:
      index = search.Index(config.STORE_INDEX_NAME)
      # search using simply the query string:
      # results = index.search(query)
      # alternately: sort results by distance
      loc_expr = 'distance(store_location, geopoint(%s, %s))' % (lat, lon)
      sortexpr = search.SortExpression(
            expression=loc_expr,
            direction=search.SortExpression.ASCENDING, default_value=0)
      sortopts = search.SortOptions(expressions=[sortexpr])
      search_query = search.Query(
          query_string=query.strip(),
          options=search.QueryOptions(
              sort_options=sortopts,
              ))
      results = index.search(search_query)
    except search.Error:
      logging.exception("There was a search error:")
      self.render_json([])
      return
    # logging.info("geo search results: %s", results)
    response_obj2 = []
    for res in results:
      gdoc = docs.Store(res)
      geopoint = gdoc.getFieldVal(gdoc.STORE_LOCATION)
      resp = {'addr': gdoc.getFieldVal(gdoc.STORE_ADDRESS),
              'storename': gdoc.getFieldVal(gdoc.STORE_NAME),
              'lat': geopoint.latitude, 'lon': geopoint.longitude}
      response_obj2.append(resp)
    logging.info("resp: %s", response_obj2)
    self.render_json(response_obj2)
