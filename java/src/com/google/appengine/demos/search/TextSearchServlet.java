// Copyright 2011 Google Inc. All Rights Reserved.

package com.google.appengine.demos.search;

import com.google.appengine.api.search.Document;
import com.google.appengine.api.search.Field;
import com.google.appengine.api.search.Index;
import com.google.appengine.api.search.IndexSpec;
import com.google.appengine.api.search.OperationResult;
import com.google.appengine.api.search.Query;
import com.google.appengine.api.search.QueryOptions;
import com.google.appengine.api.search.Results;
import com.google.appengine.api.search.DeleteException;
import com.google.appengine.api.search.ScoredDocument;
import com.google.appengine.api.search.SearchServiceFactory;
import com.google.appengine.api.search.StatusCode;
import com.google.appengine.api.users.User;
import com.google.appengine.api.users.UserService;
import com.google.appengine.api.users.UserServiceFactory;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.Iterator;
import java.util.List;
import java.util.StringTokenizer;
import java.util.logging.Level;
import java.util.logging.Logger;

import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

/**
 * A demo servlet showing basic text search capabilities. This servlet
 * has a single index shared between all users. It illustrates how to
 * add, search for and remove documents from the shared index.
 *
 */
public class TextSearchServlet extends HttpServlet {

  private static final long serialVersionUID = 1L;

  private static final String VOID_REMOVE =
      "Remove failed due to a null doc ID";

  private static final String VOID_ADD =
      "Document not added due to empty content";

  /**
   * The index used by this application. Since we only have one index
   * we create one instance only. We build an index with the default
   * consistency, which is Consistency.PER_DOCUMENT. These types of
   * indexes are most suitable for streams and feeds, and can cope with
   * a high rate of updates.
   */
  private static final Index INDEX = SearchServiceFactory.getSearchService()
      .getIndex(IndexSpec.newBuilder().setName("shared_index"));

  enum Action {
    ADD, REMOVE, DEFAULT;
  }

  private static final Logger LOG = Logger.getLogger(
      TextSearchServlet.class.getName());

  @Override
  public void doGet(HttpServletRequest req, HttpServletResponse resp)
      throws IOException, ServletException {
    User currentUser = setupUser(req);
    String outcome = null;
    switch (getAction(req)) {
      case ADD:
        outcome = add(req, currentUser);
        break;
      case REMOVE:
        outcome = remove(req);
        break;
      // On DEFAULT we fall through and just execute search below.
    }
    String searchOutcome = search(req);
    if (outcome == null) {
      outcome = searchOutcome;
    }
    req.setAttribute("outcome", outcome);
    req.getRequestDispatcher("index.jsp").forward(req, resp);
  }

  private User setupUser(HttpServletRequest req) {
    UserService userService = UserServiceFactory.getUserService();
    User currentUser = userService.getCurrentUser();
    if (currentUser != null) {
      req.setAttribute("authAction", "sign out");
      req.setAttribute("authUrl",
          userService.createLogoutURL(req.getRequestURI()));
    } else {
      currentUser = new User("nobody@example.com", "example.com");
      req.setAttribute("authAction", "sign in");
      req.setAttribute("authUrl",
          userService.createLoginURL(req.getRequestURI()));
    }
    req.setAttribute("nickname", currentUser.getNickname());
    return currentUser;
  }

  /**
   * Indexes a document built from the current request on behalf of the
   * specified user. Each document has three fields in it. The content
   * field stores used entered text. The email, and domain are extracted
   * from the current user.
   */
  private String add(HttpServletRequest req, User currentUser) {
    String content = req.getParameter("doc");
    if (content == null || content.isEmpty()) {
      LOG.warning(VOID_ADD);
      return VOID_ADD;
    }
    String ratingStr = req.getParameter("rating");
    int rating = 1;
    if (ratingStr != null) {
      rating = Integer.parseInt(ratingStr);
    }
    Document.Builder docBuilder = Document.newBuilder()
        .addField(Field.newBuilder().setName("content").setText(content))
        .addField(Field.newBuilder().setName("email")
            .setText(currentUser.getEmail()))
        .addField(Field.newBuilder().setName("domain")
            .setText(currentUser.getAuthDomain()))
        .addField(Field.newBuilder().setName("published").setDate(
            Field.date(new Date())))
        .addField(Field.newBuilder().setName("rating")
            .setNumber(rating));
    String tagStr = req.getParameter("tags");
    if (tagStr != null) {
      StringTokenizer tokenizer = new StringTokenizer(tagStr, ",");
      while (tokenizer.hasMoreTokens()) {
        docBuilder.addField(Field.newBuilder().setName("tag")
            .setAtom(tokenizer.nextToken()));
      }
    }
    Document doc = docBuilder.build();
    LOG.info("Adding document:\n" + doc.toString());
    try {
      INDEX.put(doc);
      return "Document added";
    } catch (RuntimeException e) {
      LOG.log(Level.SEVERE, "Failed to add " + doc, e);
      return "Document not added due to an error " + e.getMessage();
    }
  }

  private String getOnlyField(Document doc, String fieldName, String defaultValue) {
    if (doc.getFieldCount(fieldName) == 1) {
      return doc.getOnlyField(fieldName).getText();
    }
    LOG.severe("Field " + fieldName + " present " + doc.getFieldCount(fieldName));
    return defaultValue;
  }

  /**
   * Searches the index for matching documents. If the query is not specified
   * in the request, we search for any documents.
   */
  private String search(HttpServletRequest req) {
    String queryStr = req.getParameter("query");
    if (queryStr == null) {
      queryStr = "";
    }
    String limitStr = req.getParameter("limit");
    int limit = 10;
    if (limitStr != null) {
      try {
        limit = Integer.parseInt(limitStr);
      } catch (NumberFormatException e) {
        LOG.severe("Failed to parse " + limitStr);
      }
    }
    List<Document> found = new ArrayList<Document>();
    String outcome = null;
    try {
      // Rather than just using a query we build a search request.
      // This allows us to specify other attributes, such as the
      // number of documents to be returned by search.
      Query query = Query.newBuilder()
          .setOptions(QueryOptions.newBuilder()
              .setLimit(limit).
              // for deployed apps, uncomment the line below to demo snippeting.
              // This will not work on the dev_appserver.
              // setFieldsToSnippet("content").
              build())
          .build(queryStr);
      LOG.info("Sending query " + query);
      Results<ScoredDocument> results = INDEX.search(query);
      for (ScoredDocument scoredDoc : results) {
        User author = new User(
            getOnlyField(scoredDoc, "email", "user"),
            getOnlyField(scoredDoc, "domain", "example.com"));
        // Rather than presenting the original document to the
        // user, we build a derived one that holds author's nickname.
        List<Field> expressions = scoredDoc.getExpressions();
        String content = null;
        if (expressions != null) {
          for (Field field : expressions) {
            if ("content".equals(field.getName())) {
              content = field.getHTML();
              break;
            }
          }
        }
        if (content == null) {
          content = getOnlyField(scoredDoc, "content", "");
        }
        Document derived = Document.newBuilder()
            .setId(scoredDoc.getId())
            .addField(Field.newBuilder().setName("content").setText(content))
            .addField(Field.newBuilder().setName("nickname").setText(
                author.getNickname()))
            .addField(Field.newBuilder().setName("published").setDate(
                scoredDoc.getOnlyField("published").getDate()))
            .build();
        found.add(derived);
      }
    } catch (RuntimeException e) {
      LOG.log(Level.SEVERE, "Search with query '" + queryStr + "' failed", e);
      outcome = "Search failed due to an error: " + e.getMessage();
    }
    req.setAttribute("found", found);
    return outcome;
  }

  /**
   * Removes documents with IDs specified in the given request. In the demo
   * application we do not perform any authorization checks, thus no user
   * information is necessary.
   */
  private String remove(HttpServletRequest req) {
    String[] docIds = req.getParameterValues("docid");
    if (docIds == null) {
      LOG.warning(VOID_REMOVE);
      return VOID_REMOVE;
    }
    List<String> docIdList = Arrays.asList(docIds);
    try {
      INDEX.delete(docIdList);
      return "Documents " + docIdList + " removed";
    } catch (DeleteException e) {
      List<String> failedIds = findFailedIds(docIdList, e.getResults());
      LOG.log(Level.SEVERE, "Failed to remove documents " + failedIds, e);
      return "Remove failed for " + failedIds;
    }
  }

  /**
   * A convenience method that correlates document status to the document ID.
   */
  private List<String> findFailedIds(List<String> docIdList,
      List<OperationResult> results) {
    List<String> failedIds = new ArrayList<String>();
    Iterator<OperationResult> opIter = results.iterator();
    Iterator<String> idIter = docIdList.iterator();
    while (opIter.hasNext() && idIter.hasNext()) {
      OperationResult result = opIter.next();
      String docId = idIter.next();
      if (!StatusCode.OK.equals(result.getCode())) {
        failedIds.add(docId);
      }
    }
    return failedIds;
  }

  /**
   * Extracts the type of action stored in the request. We have only three
   * types of actions: ADD, REMOVE and DEFAULT. The DEFAULT is included
   * to indicate action other than ADD or REMOVE. We do not have a special
   * acton for search, as we always execute search. This way we show documents
   * that match terms entered in the search box, regardless of the operation.
   *
   * @param HTTP request received by the servlet
   * @return the requested user action, as inferred from the request
   */
  private Action getAction(HttpServletRequest req) {
    if (req.getParameter("index") != null) {
      return Action.ADD;
    }
    if (req.getParameter("delete") != null) {
      return Action.REMOVE;
    }
    return Action.DEFAULT;
  }
}
