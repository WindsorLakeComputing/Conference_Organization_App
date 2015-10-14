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
        print "Inside of CheckSpeakerSessions()"
        print "The conference key is ", self.request.get('conf_key')
        print "The speaker name is ", self.request.get('speakerName')
        conf = ConferenceApi.getConferenceFromKey(self.request.get('conf_key'))
        print "The conf is ", conf.name
        seses = ConferenceApi.getSessionsByConfKey(self.request.get('conf_key'), True)
        for ses in seses:
            if ses.speaker == self.request.get('speakerName'):
                if memcache.get(self.request.get('speakerName')):
                    ses_names = memcache.get(self.request.get('speakerName'))
                    print "inside of memcache.get(self.request.get('speakerName')) ... ses_names == ", ses_names
                    ses_names.add(ses.name)
                    memcache.set(self.request.get('speakerName'), ses_names, time=60)
                else:
                    ses_names = Set([ses.name])
                    memcache.set(self.request.get('speakerName'), ses_names, time=60)
                #memcache.set(self.request.get('speakerName'), ses.name, time=1800)
                print "THERE IS A MATCH WITH THIS NAME == ", self.request.get('speakerName')
                print memcache.get_stats()
        print "Out of loop"
        print "memcache.get(\"Jeb\") ", memcache.get("Jeb"), "length == ", len(memcache.get("Jeb"))


app = webapp2.WSGIApplication([
    ('/crons/set_announcement', SetAnnouncementHandler),
    ('/tasks/send_confirmation_email', SendConfirmationEmailHandler),
    ('/tasks/check_speaker_sessions', CheckSpeakerSessionsHandler)
], debug=True)
