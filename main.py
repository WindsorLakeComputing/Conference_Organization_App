#!/usr/bin/env python

"""
main.py -- Udacity conference server-side Python App Engine
    HTTP controller handlers for memcache & task queue access

$Id$

created by wesc on 2014 may 24

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

import webapp2
from google.appengine.api import app_identity
from google.appengine.api import mail
from conference import ConferenceApi
from google.appengine.api import memcache
from sets import Set
from models import Session
from google.appengine.ext import ndb

max_seses_alwd = 50

class SetAnnouncementHandler(webapp2.RequestHandler):
    def get(self):
        """Set Announcement in Memcache."""
        ConferenceApi._cacheAnnouncement()
        self.response.set_status(204)


class SendConfirmationEmailHandler(webapp2.RequestHandler):
    def post(self):
        """Send email confirming Conference creation."""
        mail.send_mail(
            'noreply@%s.appspotmail.com' % (
                app_identity.get_application_id()),     # from
            self.request.get('email'),                  # to
            'You created a new Conference!',            # subj
            'Hi, you have created a following '         # body
            'conference:\r\n\r\n%s' % self.request.get(
                'conferenceInfo')
        )

class CheckSpeakerSessionsHandler(webapp2.RequestHandler):
    def post(self):
        """ If there is more than one session by this speaker at this conference, add a new Memcache entry"""
        conf_key = ndb.Key(urlsafe=self.request.get('conf_key')).get().key
        seses_keys = Session.query(ancestor=conf_key, filters=ndb.AND(Session.speaker == self.request.get('speakerName'))).fetch(max_seses_alwd,keys_only=True)
        if len(seses_keys) > 1:
            sessions = ndb.get_multi(seses_keys)
            for ses in sessions:
                if memcache.get(self.request.get('speakerName')):
                    ses_names = memcache.get(self.request.get('speakerName'))
                    ses_names.add(ses.name)
                    memcache.set(self.request.get('speakerName'), ses_names, time=60)
                else:
                    ses_names = Set([ses.name])
                    memcache.set(self.request.get('speakerName'), ses_names, time=60)
            featuredSpeaker = self.request.get('speakerName') + ":" + repr(ses_names)
            memcache.set("featuredSpeaker", featuredSpeaker, time=3600)

app = webapp2.WSGIApplication([
    ('/crons/set_announcement', SetAnnouncementHandler),
    ('/tasks/send_confirmation_email', SendConfirmationEmailHandler),
    ('/tasks/check_speaker_sessions', CheckSpeakerSessionsHandler)
], debug=True)
