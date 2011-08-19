import os
import wsgiref.handlers
import logging
import base64

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api import mail
from google.appengine.api.labs.taskqueue import Task
from google.appengine.runtime import apiproxy_errors

import posterous
import twilio

ACCOUNT_SID = "XXXX"
ACCOUNT_TOKEN = "XXXX"
SALT_KEY = '2J86APQ0JIE81FA2NVMC48JXQS3F6VNC'

APPENGINE_ID = "XXXX"
MY_EMAIL = "XXX@XXX.XXX"


class User(db.Model):
  user = db.StringProperty()
  password = db.TextProperty()
  posterous = db.StringProperty()
  posterousID = db.StringProperty()
  posterousURL = db.StringProperty()
  name = db.StringProperty()
  phone = db.StringProperty()
  pin = db.StringProperty()
  private = db.StringProperty()
  postTitle = db.StringProperty()
  
  def __string__(self):
      return ('<p>%s<p>%s<p>%s<p>%s<p>%s<p>%s<p>%s<p>%s' % 
               (self.user, self.password, 
                self.posterous, self.posterousID, self.posterousURL, 
                self.name, self.phone, self.pin))
  
## end users
    
class PhoneLog(db.Model):
  phone = db.StringProperty()
  link = db.StringProperty()
  user = db.StringProperty()
  posterous = db.StringProperty()
  posterousID = db.StringProperty()
  date = db.DateTimeProperty(auto_now_add=True)
  duration = db.StringProperty()
  caller_city = db.StringProperty()
  caller_state = db.StringProperty()
  caller_zip = db.StringProperty()
## end phoneLog


class ConfigurationHandler(webapp.RequestHandler):
    
    def post(self):
        html = None
        error = False
        
        username = self.request.get('username')
        password_clear = self.request.get('password')
        posterousName = self.request.get('posterous')
        defaultTitle = self.request.get('postTitle')
        private = self.request.get('private')

        # the phone number comes in three parts. stitch them together
        callerOne = self.request.get('caller1')
        callerTwo = self.request.get('caller2')
        callerThree = self.request.get('caller3')
        
        if (len(callerOne) == 0 or
           len(callerTwo) == 0 or
           len(callerThree) == 0 or
           len(username) == 0 or
           len(password_clear) == 0 or
           len(posterousName) == 0):
            html = errorOutput('Oops. Configuration problem.',
                               "It looks as though you've left out some required fields")
            self.response.out.write(html)
            return

                    
        # verify the length of the phone number
        caller = callerOne + callerTwo + callerThree
        logging.info("phone number is %s" % caller)
        if len(caller) != 10:
            html = errorOutput('Oops. Configuration problem.',
                               'The phone number you entered does not appear to be valid (%s). Please type a ten digit number without any special characters'%caller)
            error = True
        else:    
            # verify that we don't already have this phone
            # number registered
            q = db.GqlQuery("SELECT * FROM User WHERE phone = :1", caller)
            if q.count(1) > 0:
              logging.debug('Checking for duplicates... found %s',q.count(1))
              html = errorOutput('Oops. Configuration problem.',
                                 'This phone number is already registered!')
              error = True
        
        # validate the posterous credentials
        if not error:
          p = posterous.Posterous(userID=username,userPassword=password_clear)
          site = p.getSites(posterousName)    

          # validate the posterous credentials and posterous ID
          if site is None:
              html = errorOutput('Oops. Configuration problem.',
                               'Unable to verify your Posterous configuration!')
              error = True
         
        if not error:
            # encrypt the password and shove the user
            # information in the database
            obj = AES.new(SALT_KEY, AES.MODE_CFB)
            cipher = base64.encodestring(obj.encrypt(password_clear))
            #cipher = base64.urlsafe_b64encode(obj.encrypt(password_clear))

            u = User()
            u.user = username
            u.password = cipher
            u.phone = caller
            u.posterous = posterousName
            u.posterousID = site['id']
            u.posterousURL = site['url']
            u.name = site['name']
            u.pin = '123'
            u.private = private
            u.postTitle = defaultTitle
            u.put()

            html = errorOutput('Configuration complete!', "We're ready to take your call - 415.367.3142")
            emailBody = "<html><body><p>This email confirms your Ringerous registration...<ul><li>Username: %s</li><li>Phone: %s</li><li>Posterous: %s</li></ul><p>Thanks for using Ringerous!<br><a href=http://www.ringerous.com>http://www.ringerous.com</a></body></html>" % (u.user, u.phone, u.posterous)
            task = Task(url='/emailqueue', params={'email':u.user,'body':emailBody})
            task.add('emailqueue')
        
        self.response.out.write(html)
        
## end ConfigurationHandler

class MainHandler(webapp.RequestHandler):

  def post(self):
      # this is the initial call...
      caller = self.request.get('Caller')
      
      # validate it is in fact coming from twilio
      if ACCOUNT_SID == self.request.get('AccountSid'):
        logging.info("was confirmed to have come from Twilio (%s)." % caller)
      else:
        logging.info("was NOT VALID.  It might have been spoofed (%s)!" % caller)
        self.response.out.write(errorResponse("Illegal caller"))
        return
      
      # not everyone gets the same recording length...
      recordLength = 720
          
      # verify the phone number as a known user
      q = db.GqlQuery("SELECT * FROM User WHERE phone = :1", caller)
      if q.count(1) == 0:
            self.response.out.write(errorResponse("I don't know you"))
            return
        
      # setup the response to get the recording from the caller
      r = twilio.Response()
      r.append(twilio.Say("Leave your posterous message after the beep", 
                          voice=twilio.Say.MAN,
                          language=twilio.Say.ENGLISH, 
                          loop=1))
      callbackURL = "http://%s.appspot.com/recording" % APPENGINE_ID
      r.append(twilio.Record(callbackURL, twilio.Record.GET, maxLength=recordLength))
      logging.info("now asking the caller to record their message...")
      self.response.out.write(r)

  def get(self):
      self.post()
      
      
## end MainHandler()

class RecordingHandler(webapp.RequestHandler):

  def post(self):
      self.get()
      
  def get(self):

      #logging.debug("The request from Twilio %s" % self.request)
      # validate it is in fact coming from twilio
      if ACCOUNT_SID == self.request.get('AccountSid'):
        logging.info("was confirmed to have come from Twilio.")
      else:
        logging.info("was NOT VALID.  It might have been spoofed!")
        self.response.out.write(errorResponse("Illegal caller"))
        return

      # verify the phone number as a known user
      call_duration = self.request.get('Duration')
      caller = self.request.get('Caller')
      q = db.GqlQuery("SELECT * FROM User WHERE phone = :1", caller)
      if q.count(1) == 0:
          self.response.out.write(errorResponse("I don't know you"))
          return
      else:
          user = q.get()
          logging.info('recording received. registered user... id: %s, posterous: %s, phone: %s, duration: %s' % 
                       (user.user, user.posterous, user.phone, call_duration))

      # special handline for my own blogs...
      if user.user == MY_EMAIL:
          logging.info("Sweet! Greg's calling... Looks like a post for the family site.")
          digit = self.request.get('Digits')
          if digit == "1":
              logging.info("Nope. He's posting to his PERSONAL site")
              user.posterousID = posterous.GREG_SITE_ID
              user.posterous = "gregtracy"
          elif digit == "7":
              logging.info("Nope. He's posting to his API TESTING site")
              user.posterousID = posterous.APITESTING_SITE_ID
              user.posterous = "apitesting"
              
      # decrypt the password
      obj = AES.new(SALT_KEY, AES.MODE_CFB)
      password_clear = obj.decrypt(base64.decodestring(user.password))
      #password_clear = obj.decrypt(base64.urlsafe_b64decode(user.password))
      
      # post to the blog      
      blogTitle = user.postTitle
      blogBody = "%s.mp3" % self.request.get('RecordingUrl')
      blog = posterous.Posterous(user.user, password_clear)
      postly = blog.postBlog(user.posterousID, blogTitle, blogBody, user.private)
      
      # log this event...
      log = PhoneLog()
      log.phone = user.phone
      log.link = blogBody
      log.user = user.user
      log.posterous = user.posterous
      log.posterousID = user.posterousID
      log.duration = call_duration
      log.caller_city = self.request.get('CallerCity')
      log.caller_state = self.request.get('CallerState')
      log.caller_zip = self.request.get('CallerZip') 
      log.put()
      
      if postly == "Error":
          postly = "http://%s.posterous.com" % user.posterous
      
      emailBody = "<html><body><p>Your posterous has been updated with your recorded message!<p>The message details are as follows...<ul><li>Phone: %s</li><li>Posterous: %s</li><li>Call duration: %s sec.</li><li>Your new post: <a href=%s>%s</a></li></ul><p>Thanks for using Ringerous!<br><a href=http://www.ringerous.com>http://www.ringerous.com</a></body></html>" % (user.phone, user.posterous, call_duration, postly, postly)
      task = Task(url='/emailqueue', params={'email':user.user,'body':emailBody})
      task.add('emailqueue')


      # setup the response to get the recording from the caller
      r = twilio.Response()
      v = twilio.Verb()
      r.append(twilio.Hangup())
      self.response.out.write(r)

## end RecordingHandler

class HistoryHandler(webapp.RequestHandler):

  def get(self):
      account = twilio.Account(ACCOUNT_SID, ACCOUNT_TOKEN)

      #d = { 'Status':2, }
      #self.response.out.write(account.request('/%s/Accounts/%s/Calls' % ('2008-08-01', ACCOUNT_SID), 'GET', d))

      d = { 'CallSid':'CA9d80c61fae9b82826245ba8e384e6cf1', }
      self.response.out.write(account.request('/%s/Accounts/%s/Recordings' % ('2008-08-01', ACCOUNT_SID), 'GET', d))

## end HistoryHandler

class EmailWorker(webapp.RequestHandler):
    def post(self):
        
        try:
            email = self.request.get('email')
            body = self.request.get('body')
            logging.debug("email task running for %s" % email)
        
            # send email 
            message = mail.EmailMessage()                                      
            message.subject = "Posterous Confirmation"
            message.sender = MY_EMAIL
            message.html = body
            message.bcc = MY_EMAIL
            message.to = email      
            message.send()

        except apiproxy_errors.DeadlineExceededError:
            logging.info("DeadlineExceededError exception!?! Try to set status and return normally")
            self.response.clear()
            self.response.set_status(200)
            self.response.out.write("Task took to long for %s - BAIL!" % email)

## end EmailWorker

def errorResponse(message):
    say = "Oops. There is an error." + message
    # setup the response to get the recording from the caller
    r = twilio.Response()
    r.append(twilio.Say(say, voice=twilio.Say.MAN,language=twilio.Say.ENGLISH, loop=1))
    return r
## end errorResponse()

def errorOutput(title, content):
    template_values = { 'title':title,'content':content }
    path = os.path.join(os.path.dirname(__file__), 'confirm.html')
    return template.render(path,template_values)

def main():
  logging.getLogger().setLevel(logging.DEBUG)
  application = webapp.WSGIApplication([('/call', MainHandler),
                                        ('/configure', ConfigurationHandler),
                                        ('/recording', RecordingHandler),
                                        ('/emailqueue', EmailWorker),
                                        ('/history', HistoryHandler)
                                        ],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
