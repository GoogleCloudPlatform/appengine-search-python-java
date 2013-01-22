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

"""Contains utility functions."""

import logging

import config
import docs
import models

from google.appengine.ext.deferred import defer
from google.appengine.ext import ndb


def intClamp(v, low, high):
  """Clamps a value to the integer range [low, high] (inclusive).

  Args:
    v: Number to be clamped.
    low: Lower bound.
    high: Upper bound.

  Returns:
    An integer closest to v in the range [low, high].
  """
  return max(int(low), min(int(v), int(high)))

def updateAverageRating(review_key):
  """Helper function for updating the average rating of a product when new
  review(s) are added."""

  def _tx():
    review = review_key.get()
    product = review.product_key.get()
    if not review.rating_added:
      review.rating_added = True
      product.num_reviews += 1
      product.avg_rating = (product.avg_rating +
          (review.rating - product.avg_rating)/float(product.num_reviews))
      # signal that we need to reindex the doc with the new ratings info.
      product.needs_review_reindex = True
      ndb.put_multi([product, review])
      # We need to update the ratings associated document at some point as well.
      # If the app is configured to have BATCH_RATINGS_UPDATE set to True, don't
      # do this re-indexing now.  (Instead, all the out-of-date documents can be
      # be later handled in batch -- see cron.yaml).  If BATCH_RATINGS_UPDATE is
      # False, go ahead and reindex now in a transational task.
      if not config.BATCH_RATINGS_UPDATE:
        defer(
            models.Product.updateProdDocWithNewRating,
            product.key.id(), _transactional=True)
    return (product, review)

  try:
    # use an XG transaction in order to update both entities at once
    ndb.transaction(_tx, xg=True)
  except AttributeError:
    # swallow this error and log it; it's not recoverable.
    logging.exception('The function updateAverageRating failed. Either review '
                      + 'or product entity does not exist.')



