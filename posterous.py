import base64
import urllib, urllib2
from xml.dom import minidom
from google.appengine.api import urlfetch
import logging

'''
Created on Oct 29, 2009

@author: Greg Tracy
'''

def getText(nodelist):
    rc = ""
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
           rc = rc + node.data
    return rc

APITESTING_SITE_ID = '575337'
FAMILY_SITE_ID = '500859'
GREG_SITE_ID = '7963'
MADFIBER_SITE_ID = '1139921'

class Posterous(object):

    
    user = 'guest'
    password = 'empty'
    baseURL = "http://posterous.com/api/"
    sitesURL = "http://posterous.com/api/getsites" 
    postURL = "http://posterous.com/api/newpost" 

    auth = 'undef'

    def __init__(self, userID, userPassword):
        '''
        Constructor
        '''
        logging.debug("posterous init: user %s" % userID)
        self.user = userID
        self.password = userPassword
        logging.debug("encoding password...")
        self.auth = "Basic %s" % base64.encodestring(userID + ":" + userPassword)[:-1]
    ## end __init__
        
    def _parse(self, xml):
        dom = minidom.parseString(xml)
        conditions = dom.getElementsByTagName('condition')[0]
        location = dom.getElementsByTagName('location')[0]
        return {
            'location': '%s, %s' % (location.getAttribute('city'),
                location.getAttribute('region')),
            'conditions': conditions.getAttribute('text'),
            'temp': conditions.getAttribute('temp')
        }
    ## end _parse()

    def getSites(self, userHostname):
        xml = None
        
        logging.debug("getting sites... looking for %s" % userHostname)
        
        # create a password manager
        req = urllib2.Request(self.sitesURL,None,{"Authorization":self.auth})        
        try: 
            h = urllib2.urlopen(req)
            xml = h.read()
            logging.info("Get sites:")
            logging.info(xml)
            
            if not xml:
                return None
            else:
                # start interrogating the xml
                dom = minidom.parseString(xml)
                sites = dom.getElementsByTagName('site')
                for s in sites:
                    # find and return the requested posterous for
                    # this user.
                    hostname = s.getElementsByTagName('hostname')[0]
                    value = getText(hostname.childNodes)
                    logging.info("hostname: %s" % value)
                    if value == userHostname:
                        id = s.getElementsByTagName('id')[0]
                        name = s.getElementsByTagName('name')[0]
                        url = s.getElementsByTagName('url')[0]
                        return {'id':getText(id.childNodes),
                                'name':getText(name.childNodes),
                                'url':getText(url.childNodes),                                
                               }

        except urllib2.HTTPError:
            logging.error('Failed to open: ', req)     
        
        return None
    
    ## end getSites()
    
    def postBlog(self,siteID,postTitle,postBody,private):
   
        ## override for testing ---> siteID = APITESTING_SITE_ID
        logging.info("Posterous: posting to %s" % siteID)
        
        privateBit = 0
        if private == "on":
            privateBit = 1
            
        post_details = urllib.urlencode({"site_id":siteID,
                                         "private":privateBit,
                                         "title":postTitle,
                                         "body":postBody,
                                         "source":"<a href=http://www.ringerous.com>Ringerous</a>"
                                        })
        req = urllib2.Request(self.postURL,
                              post_details,
                              {"Authorization":self.auth}
                              )
        
        try:
          h = urllib2.urlopen(req)
          xml = h.read()
          logging.debug("postBlog %s" % postTitle)
          logging.debug(xml)

          # extract the post.ly link from the post
          dom = minidom.parseString(xml)
          sites = dom.getElementsByTagName('post')
          for s in sites:
              # find and return the post.ly URL
              primary = s.getElementsByTagName('url')[0]
              value = getText(primary.childNodes)
              return value

        except urlfetch.DownloadError:
            logging.error("Another urlfetch error for %s! Assuming the post worked, however..." % siteID)
            return "Error"
    
        
        return "this should never happen"
        ## end of postBlog    

    def findSite(self,siteName):
        getSites()
    ## end findSite())
    
    
