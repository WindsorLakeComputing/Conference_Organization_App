#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'


from datetime import datetime

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache 
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import ConflictException
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import BooleanMessage
from models import Conference
from models import ConferenceStats
from models import ConferenceForm
from models import ConferenceForms
from models import Session
from models import SessionForm
from models import SessionForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import TeeShirtSize

from utils import getUserId

import json


from settings import WEB_CLIENT_ID

from google.appengine.api import memcache

from models import StringMessage
from google.appengine.api import taskqueue

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": [ "Default", "Topic" ],
}

S_DEFAULTS = {
    "speaker": "Mister Bush",
    "sessionType": "INFO",
    "highlights": [ "Big", "Fun" ],
}
    

OPERATORS = {
            'EQ':   '=',
            'GT':   '>',
            'GTEQ': '>=',
            'LT':   '<',
            'LTEQ': '<=',
            'NE':   '!='
            }

FIELDS =    {
            'CITY': 'city',
            'TOPIC': 'topics',
            'MONTH': 'month',
            'MAX_ATTENDEES': 'maxAttendees',
            }

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

SES_GET_TYPE_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    typeOfSession=messages.StringField(2),
)

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1),
)

SES_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSessionKey=messages.StringField(1),
)

SES_GET_SPKR_NAME_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSpeakerName=messages.StringField(1),
)

SES_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSessionKey=messages.StringField(1),
)

SES_GET_NAME_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSessionName=messages.StringField(1),
)

SES_POST_REQUEST = endpoints.ResourceContainer(
    SessionForm,
    websafeConferenceKey=messages.StringField(1),
)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@endpoints.api(name='conference', version='v1',
    allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID],
    scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

# - - - Conference objects - - - - - - - - - - - - - - - - -

    def _copyConferenceToForm(self, conf, displayName="Anonymous"):
        """Copy relevant fields from Conference to ConferenceForm."""
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if displayName:
            setattr(cf, 'organizerDisplayName', displayName)
        cf.check_initialized()
        return cf


    def _createConferenceObject(self, request):
        """Create or update Conference object, returning ConferenceForm/request."""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException("Conference 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        print "The data[websafekey] is ", data['websafeKey']
        del data['websafeKey']
        del data['organizerDisplayName']

        # add default values for those missing (both data model & outbound Message)
        for df in DEFAULTS:
            if data[df] in (None, []):
                data[df] = DEFAULTS[df]
                setattr(request, df, DEFAULTS[df])

        # convert dates from strings to Date objects; set month based on start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(data['startDate'][:10], "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(data['endDate'][:10], "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
        # generate Profile Key based on user ID and Conference
        # ID based on Profile key get Conference key from ID
        p_key = ndb.Key(Profile, user_id)
        print "The p_key is ", p_key
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key
        data['organizerUserId'] = request.organizerUserId = user_id

        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        # TODO 2: add confirmation email sending task to queue
        print "Before Session(**data).put() ... data == ", data
        Conference(**data).put()
        taskqueue.add(params={'email': user.email(),
            'conferenceInfo': repr(request)},
            url='/tasks/send_confirmation_email'
        )

        return request

    def _copySessionToForm(self, ses):
        """Copy relevant fields from Conference to ConferenceForm."""
        print "the parameter passed in is ", ses.name
        sf = SessionForm()
        for field in sf.all_fields():
            if hasattr(ses, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(sf, field.name, str(getattr(ses, field.name)))
                else:
                    setattr(sf, field.name, getattr(ses, field.name))
            elif field.name == "websafeKey":
                setattr(sf, field.name, ses.key.urlsafe())

        sf.check_initialized()
        print "inside of _copySessionToForm ... ses.name == ", ses.name
        return sf


    def createSessionObject(self, request):
        """Create or update Session object, returning SessionForm/request."""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException("Session 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        print "The data[websafekey] is ", data['websafeKey']
        del data['websafeKey']
        del data['websafeConferenceKey']


        #del data['organizerDisplayName']

        # add default values for those missing (both data model & outbound Message)
        for df in S_DEFAULTS:
            if data[df] in (None, []):
                data[df] = S_DEFAULTS[df]
                setattr(request, df, S_DEFAULTS[df])
        print "The data is ", data

        # update existing conference
        #conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        conf = ConferenceApi.getConferenceFromKey(request.websafeConferenceKey)
        print "conf.name == ", conf.name
        print "conf key == ", conf.key
        #if not conf:
        #    raise endpoints.NotFoundException(
        #        'No conference found with key: %s' % request.websafeConferenceKey)


        s_id = Session.allocate_ids(size=1, parent=conf.key)[0]
        s_key = ndb.Key(Session, s_id, parent=conf.key)
        data['key'] = s_key

        print "Before Session(**data).put() ... data == ", data

        print "Before  taskqueue.add(params={'conf_key': conf.key, "
        print "conf.key == ", conf.key.urlsafe()
        print "speakerName == ", data['speaker']

        taskqueue.add(params={'conf_key': conf.key.urlsafe(),
            'speakerName': data['speaker']},
            url='/tasks/check_speaker_sessions'
        )


        #self.checkSpeaker(conf.key, data['speaker'])


        Session(**data).put()
        # check that conference exists
        
        # check that user is owner
        #if user_id != conf.organizerUserId:
        #    raise endpoints.ForbiddenException(
        #        'Only the owner can update the conference.')
        print "THe conference key is ", conf.key



        ses = s_key.get()
      
        return self._copySessionToForm(ses)

    def checkSpeaker(self, conf_key, speaker):

        seses = ConferenceApi.getSessionsByConfKey(conf_key)
        print "inside of getSessions ... the conf_key is",conf_key," the speaker is ", speaker
        print "the seses are: "

        for ses in seses:
            print ses.name

    @staticmethod
    def getConferenceFromKey(conf_key):
        #conf = Session.query(ancestor=conf_key)
        print "INSIDE OF ... getConferenceFromKey"
        print "The key is ", conf_key
        conf = ndb.Key(urlsafe=conf_key).get()
        #conf = key.get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % conf_key)
       
        return conf


    @staticmethod
    def getSessionsByConfKey(conf_key, urlsafe=False):
        conf_keys = Conference.query().fetch(50,keys_only=True)
        conferences = ndb.get_multi(conf_keys)

        if urlsafe:
            #seses = Session.query(ancestor=conf_key)
            conf_key = ndb.Key(urlsafe=conf_key).get().key

        seses_keys = Session.query(ancestor=conf_key).fetch(50,keys_only=True)

        if not seses_keys:
            raise endpoints.NotFoundException(
                'Not a single session found with conference key: %s' % conf_key)

        seses = ndb.get_multi(seses_keys)
        return seses
            
        

    @ndb.transactional()
    def _updateConferenceObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}

        # update existing conference
        #conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        conf = ConferenceApi.getConferenceFromKey(request.websafeConferenceKey)
        

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
            http_method='POST', name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)

    @endpoints.method(SES_POST_REQUEST, SessionForm, 
            path='conference/{websafeConferenceKey}/session',
            http_method='POST', name='createSession')
    def createSession(self, request):
        """Create new session."""
        return self.createSessionObject(request)


    @endpoints.method(CONF_POST_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='PUT', name='updateConference')
    def updateConference(self, request):
        """Update conference w/provided fields & return w/updated info."""
        return self._updateConferenceObject(request)

    @endpoints.method(message_types.VoidMessage, ConferenceStats,
            path='conferenceStats',
            http_method='GET', name='getConferenceStats')
    def getConferenceStats(self, request):
        stats = {}

        conf_keys = Conference.query().fetch(50,keys_only=True)
        conferences = ndb.get_multi(conf_keys)

        for conf in conferences:
            print "Building a conference"
            c = {}
            c['name'] = conf.name
            c['topics'] = conf.topics
            c['city'] = conf.city
            c['startDate'] = conf.startDate
            print "name of new conference is ", c['name']
            key = conf.key
            #sesses = Session.query(ancestor=key)
            seses = ConferenceApi.getSessionsByConfKey(key)
            if seses:
                for ses in seses:
                    s = {}
                    s['name'] = ses.name
                    s['speaker'] = ses.speaker
                    s['sessionType'] = ses.sessionType
                    print "The session name is ", s['name']
                    c[ses.name + "-Session"] = s

            stats[conf.name + "-Conference"] = c

        for k, v in stats.iteritems():
            print "{0} : {1}".format(k, v)

        return ConferenceStats(some_dict=json.dumps(stats, ensure_ascii=True))
        #return ConferenceStats(some_dict=json.dumps(stats, default=json_util.default))


    @endpoints.method(CONF_GET_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='GET', name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""
        # get Conference object from request; bail if not found
        print "request.websafeConferenceKey == ", request.websafeConferenceKey
        #conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()

        conf = ConferenceApi.getConferenceFromKey(request.websafeConferenceKey)
        
        prof = conf.key.parent().get()
        # return ConferenceForm
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))
        
    @endpoints.method(SES_GET_SPKR_NAME_REQUEST, SessionForms, #SessionForm,
            path='sessionsBySpeaker/{websafeSpeakerName}',
            http_method='GET', name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        print "The speaker is ", request.websafeSpeakerName

        seses = Session.query(Session.speaker == request.websafeSpeakerName)
        if not seses:
            raise endpoints.NotFoundException(
                'Not a single session found with a speaker by the name of : %s' % request.websafeSpeakerName)

        for ses in seses:
            print "The ses name is ", ses.name
        #    print "The ses key is", ses.key
        #    key = ses.key
        #    print "the ses id is ", key.id()
        #    print "the key's parent is ", key.parent()
          
        #    confs = Conference.query(ancestor=key.parent())
        #   for conf in confs:
        #       print "the name of the conf is ", conf.name
           

        return SessionForms(
            items=[self._copySessionToForm(ses) for ses in seses]
        )

    @endpoints.method(SES_GET_NAME_REQUEST, ConferenceForm, 
            path='conferenceBySessionName/{websafeSessionName}',
            http_method='GET', name='getConferenceBySessionName')
    def getConferenceBySessionName(self, request): 

        ses = Session.query(Session.name == request.websafeSessionName)
        if not ses:
            raise endpoints.NotFoundException(
                'Not a single session found by the name of : %s' % request.websafeSessionName)
        key = ses.get().key
        conf = Conference.query(ancestor=key.parent())

        return self._copyConferenceToForm(conf.get())


    @endpoints.method(SES_GET_TYPE_REQUEST, SessionForms, #SessionForm,
            path='sessionsByType/{websafeConferenceKey}/{typeOfSession}',
            http_method='GET', name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        print "The websafeConferenceKey is ", request.websafeConferenceKey
        #conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        conf = ConferenceApi.getConferenceFromKey(request.websafeConferenceKey)
        
        key = conf.key
        print "The type is", request.typeOfSession


        seses = ConferenceApi.getSessionsByConfKey(key)
        #seses = Session.query(ancestor=key)
        #if not seses:
        #    raise endpoints.NotFoundException(
        #        'This conference doesnt have any sessions : %s' % request.websafeConferenceKey)
        

        return SessionForms(
            items=[self._copySessionToForm(ses) for ses in seses if ses.sessionType == request.typeOfSession]
        )


    @endpoints.method(CONF_GET_REQUEST, SessionForms, #SessionForm,
            path='conferenceSessions/{websafeConferenceKey}',
            http_method='GET', name='getConferenceSessions')
    def getConferenceSessions(self, request):
        #conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        conf_key = request.websafeConferenceKey
        print "inside of getConferenceSessions(), the conf_key is ", conf_key

        conf = ConferenceApi.getConferenceFromKey(conf_key)
       
        key = conf.key

        seses = ConferenceApi.getSessionsByConfKey(key)

        #seses = Session.query(ancestor=key)
        #if not seses:
        #    raise endpoints.NotFoundException(
        #        'Not a single session found with conference key: %s' % request.websafeConferenceKey)

        return SessionForms(
            items=[self._copySessionToForm(ses) for ses in seses]
        )

    @endpoints.method(message_types.VoidMessage, SessionForms,
            path='getSessionsInWishlist',
            http_method='GET', name='getSessionsInWishlist')
    def getSessionsInWishlist(self, request):
        prof = self._getProfileFromUser() # get user Profile
        ses_keys = [ndb.Key(urlsafe=wssk) for wssk in prof.sessionKeysWishList]
        sesses = ndb.get_multi(ses_keys)



        # return set of ConferenceForm objects per Conference
        return SessionForms(
            items=[self._copySessionToForm(ses) for ses in sesses]
        )


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='getConferencesCreated',
            http_method='POST', name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id =  getUserId(user)
        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        if not confs:
            raise endpoints.NotFoundException(
                'Not a single conference was created by: %s' % user.nickname())

        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, getattr(prof, 'displayName')) for conf in confs]
        )


    def _getQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Conference.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)

        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q


    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name) for field in f.all_fields()}

            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException("Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous filters
                # disallow the filter if inequality was performed on a different field before
                # track the field on which the inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException("Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)


    @endpoints.method(ConferenceQueryForms, ConferenceForms,
            path='queryConferences',
            http_method='POST',
            name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        conferences = self._getQuery(request)

        # need to fetch organiser displayName from profiles
        # get all keys and use get_multi for speed
        organisers = [(ndb.Key(Profile, conf.organizerUserId)) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return individual ConferenceForm object per Conference
        return ConferenceForms(
                items=[self._copyConferenceToForm(conf, names[conf.organizerUserId]) for conf in \
                conferences]
        )


# - - - Profile objects - - - - - - - - - - - - - - - - - - -

    def _copyProfileToForm(self, prof):
        """Copy relevant fields from Profile to ProfileForm."""
        # copy relevant fields from Profile to ProfileForm
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name, getattr(TeeShirtSize, getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf


    def _getProfileFromUser(self):
        """Return user Profile from datastore, creating new one if non-existent."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Profile from datastore
        user_id = getUserId(user)
        p_key = ndb.Key(Profile, user_id)
        profile = p_key.get()
        # create new Profile if not there
        if not profile:
            profile = Profile(
                key = p_key,
                displayName = user.nickname(),
                mainEmail= user.email(),
                teeShirtSize = str(TeeShirtSize.NOT_SPECIFIED),
            )
            profile.put()

        return profile      # return Profile


    def _doProfile(self, save_request=None):
        """Get user Profile and return to user, possibly updating it first."""
        # get user Profile
        prof = self._getProfileFromUser()

        # if saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
                        #if field == 'teeShirtSize':
                        #    setattr(prof, field, str(val).upper())
                        #else:
                        #    setattr(prof, field, val)
            prof.put()

        # return ProfileForm
        return self._copyProfileToForm(prof)


    @endpoints.method(message_types.VoidMessage, ProfileForm,
            path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return self._doProfile()


    @endpoints.method(ProfileMiniForm, ProfileForm,
            path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        """Update & return user profile."""
        return self._doProfile(request)


# - - - Registration - - - - - - - - - - - - - - - - - - - -

    @ndb.transactional(xg=True)
    def _addSessionToWishlist(self, request):
        retval = None
        prof = self._getProfileFromUser() # get user Profile
        wssk = request.websafeSessionKey
        ses = ndb.Key(urlsafe=wssk).get()
        if not ses:
            raise endpoints.NotFoundException(
                'No session found with key: %s' % wssk)

        if wssk in prof.sessionKeysWishList:
            raise ConflictException(
                    "You have already added this session to your wish list")
        prof.sessionKeysWishList.append(wssk)
        retval = True
        prof.put()
        return BooleanMessage(data=retval)

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        retval = None
        prof = self._getProfileFromUser() # get user Profile

        # check if conf exists given websafeConfKey
        # get conference; check that it exists
        #wsck = request.websafeConferenceKey
        #conf = ndb.Key(urlsafe=wsck).get()
        conf = ConferenceApi.getConferenceFromKey(request.websafeConferenceKey)
        #if not conf:
        #    raise endpoints.NotFoundException(
        #        'No conference found with key: %s' % wsck)

        # register
        if reg:
            # check if user already registered otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")

            # register user, take away one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            retval = True

        # unregister
        else:
            # check if user already registered
            if wsck in prof.conferenceKeysToAttend:

                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)

    @endpoints.method(SES_GET_REQUEST, BooleanMessage,
            path='session/{websafeSessionKey}',
            http_method='POST', name='addSessionToWishlist')
    def addSessionToWishlist(self, request):       
        return self._addSessionToWishlist(request)


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='conferences/attending',
            http_method='GET', name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""
        prof = self._getProfileFromUser() # get user Profile
        conf_keys = [ndb.Key(urlsafe=wsck) for wsck in prof.conferenceKeysToAttend]
        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[self._copyConferenceToForm(conf, names[conf.organizerUserId])\
         for conf in conferences]
        )


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='POST', name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='DELETE', name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference."""
        return self._conferenceRegistration(request, reg=False)


# - - - Announcements - - - - - - - - - - - - - - - - - - - -

# TODO 1
# - - - Announcements - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheAnnouncement():
        """Create Announcement & assign to memcache; used by
        memcache cron job & putAnnouncement().
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])

        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = '%s %s' % (
                'Last chance to attend! The following conferences '
                'are nearly sold out:',
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

        return announcement


    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='conference/announcement/get',
            http_method='GET', name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""

        # TODO 1
        # return an existing announcement from Memcache or an empty string.
        return StringMessage(data=memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY) or "")

api = endpoints.api_server([ConferenceApi]) # register API
