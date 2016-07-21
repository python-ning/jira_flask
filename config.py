# encoding=utf-8
import json
import requests
from api.connection_nexus import *

HOSTNAME = 'http://localhost:8081'
HEADERS = {"Content-Type": "application/json"}
AUTH = ("root", "123456")
get_firld_url = '%s/rest/api/2/field' % HOSTNAME

jira_fields = json.loads(requests.session().get(get_firld_url, auth=AUTH, headers=HEADERS).content)
field_config = [u"datacenter", u"tags", u"size", u"csname", u"hostname", u"root_password", u"image", u"cpu", u"memory", u"disk", u"comments", u"network", u"datacenter", u"bandwidth", u'tags', u'size', u'status']

params = {}
for jira in jira_fields:
    if jira['name'] in field_config:
        params[jira['name']] = str(jira['id'])

api_obj = CloudAPIConnection()
token = api_obj.login("machao", "machao").get('token')
api_obj = CloudAPIConnection(token)
