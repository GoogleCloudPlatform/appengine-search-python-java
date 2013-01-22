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


import logging

from google.appengine.api import search


def get_sort_options(expressions=None, match_scorer=None, limit=1000):
  """A function to handle the sort expression API differences in 1.6.4
  vs. 1.6.5+.

 An example of usage (NOTE: Do NOT put limit SortExpression or MatchScorer):

  expr_list = [
      search.SortExpression(expression='author', default_value='',
                            direction=search.SortExpression.DESCENDING)]
  sortopts = get_sort_options(expression=expr_list, limit=sort_limit)

  The returned value is used in constructing the query options:

  qoptions=search.QueryOptions(limit=doc_limit, sort_options=sortopts)

  Another example illustrating sorting on an expression based on a
  MatchScorer score:

  expr_list = [
      search.SortExpression(expression='_score + 0.001 * rating',
                            default_value='',
                            direction=search.SortExpression.DESCENDING)]
  sortopts = get_sort_options(expression=expr_list,
                              match_scorer=search.MatchScorer(),
                              limit=sort_limit)


  Args:
    expression: a list of search.SortExpression. Do not set limit parameter on
      SortExpression
    match_scorer: a search.MatchScorer or search.RescoringMatchScorer. Do not
      set limit parameter on either scorer
    limit: the scoring limit

  Returns: the sort options value, either list of SortOption (1.6.4) or
  SortOptions (1.6.5), to set the sort_options field in the QueryOptions object.
  """
  try:
    # using 1.6.5 or greater
    if search.SortOptions:
      logging.debug("search.SortOptions is defined.")
      return search.SortOptions(
          expressions=expressions, match_scorer=match_scorer, limit=limit)

  # SortOptions not available, so using 1.6.4
  except AttributeError:
    logging.debug("search.SortOptions is not defined.")
    expr_list = []
    # copy the sort expressions including the limit info
    if expressions:
      expr_list=[
          search.SortExpression(
              expression=e.expression, direction=e.direction,
              default_value=e.default_value, limit=limit)
          for e in expressions]
    # add the match scorer, if defined, to the expressions list.
    if isinstance(match_scorer, search.MatchScorer):
      expr_list.append(match_scorer.__class__(limit=limit))
    logging.info("sort expressions: %s", expr_list)
    return expr_list
