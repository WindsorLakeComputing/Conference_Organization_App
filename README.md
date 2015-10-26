Task 1: Add Sessions to a Conference
Explain your design choices

Inside of the models.py class I created a session class with the same attributes listed in the grading rubric. The name field is required – as it is in the Conference class. The highlights field allows for multiple entries because a session can have multiple highlights.  Inside of the Conference class all the fields are strings except: startDate, endDate, maxAttendees, and seatsAvailable. startDate and endDate are both a Date; maxAttendees, seatsAvailable, and month are all Integers. I chose to make them Integers because by making them Integers I can easily sort them, either ascending or descending, in a query. 

The SessionForm class, like the ConferenceForm class, allows fields to be transported between the web application front end and the database. 
I created a session as a child of the conference because it’s easy to get all sessions associated with a conference with the following query: Session.query(ancestor=conference_key).fetch(). Because the session class has the field speaker it’s easy to implement the getSessionsBySpeaker(speaker) as thus: seses = Session.query(Session.speaker == request.websafeSpeakerName). All of the attributes inside of the Session class are of type String except for: duration, date, and startTime. Duration is an Integer because I want to easily sort different sessions based off of their duration - i.e. the session with the shortest duration. startTime is of type Time because a session needs to be able to be expressed with a startTime that includes both the hour and minute. 


Task 3: Work on indexes and queries
Come up with 2 additional queries

Inside of conference.py please see the code for the following methods: getConferenceStats(self, request) and getConferenceBySessionName(self, request). 

The purpose of getConferenceStats() is to retrieve all created Conferences and every Session associated with it. This information is useful for comparing different conferences. The endpoint works by retrieving all the conferences from the datastore. The conferences are then iterated over with every field being stored in a Python dictionary. All the Sessions associated with a conference are obtained by running an ancestor query with the conference’s key as a parameter. Once the sessions are obtained their fields are also captured in a dictionary. This dictionary is then added to the conference dictionary.  The endpoint returns JSON that represents a dictionary of all the just created conferences.
The purpose of getConferenceBySessionName() is to retrieve a conference based off a session’s name. This is useful when a user remembers the name of a session but not any of the details describing the conference that is hosting it. The endpoint requires the exact name of a created session. It works by running a filter query that obtains a session that has the same name as the passed in parameter. Once the session is obtain an ancestor query is run that uses the session’s key as a parameter. The endpoint returns a conferenceForm that represents the conference that is hosting the session. 

Solve the following query related problem

The problem for implementing the query “for all non-workshop sessions before 7 pm” is that it contains inequality filters on two properties: sessionType and startTime. This won’t work because the docs state that “the Datastore rejects queries using inequality filtering on more than one property.” In order to solve this problem I would have a query containing one inequality: all sessions with a start time < 7 pm. I would then iterate through the sessions and check for a type that isn’t “workshop.” For the ones that aren’t I would add them to a Python dictionary. I would return this dictionary after iterating through all the sessions. 


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
