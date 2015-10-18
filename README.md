Task 1: Add Sessions to a Conference
Explain your design choices

Inside of the models.py class I created a session class with the same attributes listed in the grading rubric. The name field is required – as it is in the Conference class. The highlights field allows for multiple entries because a session can have multiple highlights. The SessionForm class, like the ConferenceForm class, allows fields to be transported between the web application front end and the database. 
I created a session as a child of the conference because it’s easy to get all sessions associated with a conference with the following query: Session.query(ancestor=conference_key).fetch(). Because the session class has the field speaker it’s easy to implement the getSessionsBySpeaker(speaker) as thus: seses = Session.query(Session.speaker == request.websafeSpeakerName).

Task 3: Work on indexes and queries
Come up with 2 additional queries

Inside of conference.py please see the code for the following methods: getConferenceStats(self, request) and getConferenceBySessionName(self, request). 
Solve the following query related problem

In order to handle a query for all non-workshop sessions before 7 pm I would create a query that returns all sessions that aren’t of type “workshop.” I would then further filter the sessions by running a query against the just returned sessions that filtered out sessions that have a start time of 7 pm or greater. The problem of implementing this query is that it is composed of 2 variables – session type and start time – rather than just 1. I solved it by diving it into 2 separate queries.


## Products
- [App Engine][1]

## Language
- [Python][2]

## APIs
- [Google Cloud Endpoints][3]

## Setup Instructions
1. Update the value of `application` in `app.yaml` to the app ID you
   have registered in the App Engine admin console and would like to use to host
   your instance of this sample.
1. Update the values at the top of `settings.py` to
   reflect the respective client IDs you have registered in the
   [Developer Console][4].
1. Update the value of CLIENT_ID in `static/js/app.js` to the Web client ID
1. (Optional) Mark the configuration files as unchanged as follows:
   `$ git update-index --assume-unchanged app.yaml settings.py static/js/app.js`
1. Run the app with the devserver using `dev_appserver.py DIR`, and ensure it's running by visiting your local server's address (by default [localhost:8080][5].)
1. (Optional) Generate your client library(ies) with [the endpoints tool][6].
1. Deploy your application.


[1]: https://developers.google.com/appengine
[2]: http://python.org
[3]: https://developers.google.com/appengine/docs/python/endpoints/
[4]: https://console.developers.google.com/
[5]: https://localhost:8080/
[6]: https://developers.google.com/appengine/docs/python/endpoints/endpoints_tool
