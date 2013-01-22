

# Full-Text Search Demo App: Product Search

## Introduction

This Python App Engine application illustrates the use of the [Full-Text Search
API](https://developers.google.com/appengine/docs/python/search) in a "Product
Search" domain with two categories of sample products: *books* and
*hd televisions*.  This README assumes that you are already familiar with how to
configure and deploy an App Engine app. If not, first see the App Engine
[documentation](https://developers.google.com/appengine/docs/python/overview)
and  [Getting Started guide](https://developers.google.com/appengine/docs/python/gettingstarted).

This demo app allows users to search product information using full-text search,
and to add reviews with ratings to the products.  Search results can be sorted
according to several criteria. In conjunction with listed search results, a
sidebar allows the user to further filter the search results on product rating.
(A product's rating is the average of its reviews, so if a product has no
reviews yet, its rating will be 0).

A user does not need to be logged in to search the products, or to add reviews.
A user must be logged in **as an admin of the app to add or modify product
data**. The sidebar admin links are not displayed for non-admin users.

## Configuration

Before you deploy the application, edit `app.yaml` to specify your own app id and version.

In `templates/product.html`, the Google Maps API is accessed.  It does not require an API key, but you are encouraged to use one to monitor your maps usage.  In the <head> element, look for:

	src="https://maps.googleapis.com/maps/api/js?sensor=false"

and replace it with something like the following, where `replaceWithYourAPIKey` is your own API key:

      src="https://maps.googleapis.com/maps/api/js?sensor=false&amp;key=replaceWithYourAPIKey"

as described [here](https://developers.google.com/maps/documentation/javascript/tutorial#api_key).

## Information About Running the App Locally

Log in as an app admin to add and modify the app's product data.

The app uses XG (cross-group) transactions, which requires the dev_appserver to
be run with the `--high_replication` flag.  E.g., to start up the dev_appserver
from the command line in the project directory (this directory), assuming the
GAE SDK is in your path, do:

    dev_appserver.py --high_replication .

The app is configured to use Python 2.7. On some platforms, it may also be
necessary to have Python 2.7 installed locally when running the dev_appserver.
The app's unit tests also require Python 2.7.

When running the app locally, not all features of the search API are supported.
So, not all search queries may give the same results during local testing as
when run with the deployed app.
Be sure to test on a deployed version of your app as well as locally.

## Administering the deployed app

You will need to be logged in as an administrator of the app to add and modify
product data, though not to search products or add reviews.  If you want to
remove this restriction, you can edit the `login: admin` specification in
`app.yaml`, and remove the `@BaseHandler.admin` decorators in 
`admin_handlers.py`.

## Loading Sample Data

When you first start up your app, you will want to add sample data to it.

Sample product data can be added in two ways. First, sample product data in CSV
format can be added in batch via a link on the app's admin page. Batch indexing
of documents is more efficient than adding the documents one at a time. For consistency,
**the batch addition of sample data first removes all
existing index and datastore product data**.

The second way to add sample data is via the admin's "Create new product" link
in the sidebar, which lets an admin add sample products (either "books" or
"hd televisions") one at a time.


## Updating product documents with a new average rating

When a user creates a new review, the average rating for that product is
updated in the datastore.  The app may be configured to update the associated
product `search.Document` at the same time (the default), or do this at a
later time in batch (which is more efficient).  See `cron.yaml` for an example
of how to do this update periodically in batch.

## Searches

Any valid queries can be typed into the search box.  This includes simple word
and phrase queries, but you may also submit queries that include references to
specific document fields and use numeric comparators on numeric fields.  See the
Search API's
[documentation](https://developers.google.com/appengine/docs/python/search) for
a description of the query syntax.  

Thus, for explanatory purposes, the "product details" show all actual
field names of the given product document; you can use this information to
construct queries against those fields. In the same spirit, the raw
query string used for the query is displayed with the search results.

Only product information is searched; product review text is not included in the 
search.

### Some example searches

Below are some example product queries, which assume the sample data has been loaded.
As discussed above, not all of these queries are supported by the dev_appserver.

`stories price < 10`  
`price > 10 price < 15`  
`publisher:Vintage`  
`Mega TVs`   
`name:tv1`    
`size > 30`

## Geosearch

This application includes an example of using the Search API to perform
location-based queries.  Sample store location data is defined in `stores.py`,
and is loaded along with the product data.  The product details page for a
product allows a search for stores within a given radius of the user's current
location. The user's location is obtained from the browser.
