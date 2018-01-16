import sublime
import sublime_plugin

import re
import urllib.request
import xml.etree.ElementTree
import webbrowser

from . import defaultclient
from .. import logger
from .. import tools

log = logger.getLogger(__name__)


class BibsonomyClient():

    def __init__(self, username, apikey):
        self.baseurl = 'http://www.bibsonomy.org/api'
        self.username = username
        self.apikey = apikey

        self.auth_handler = urllib.request.HTTPBasicAuthHandler()
        self.auth_handler.add_password('BibSonomyWebService', self.baseurl, self.username, self.apikey)

    def get(self, url):
        client = defaultclient.DefaultClient()
        response = client.request(url if url.startswith(self.baseurl) else self.baseurl + url, self.auth_handler)
        return response


class Bibsonomy():

    def __init__(self):
        self.settings = tools.load_settings("LaTeXing", bibsonomy_username="", bibsonomy_apikey="")

        # Load map
        self.map = sublime.decode_value(sublime.load_resource("Packages/LaTeXing/latexing/api/bibsonomy.map"))

        # bibtex: citeulike type
        self.type_map = self.map["types"]

        # bibtex: citeulike field
        self.field_map = self.map["fields"]

        # Check for user maps
        try:
            self.user_map = sublime.decode_value(sublime.load_resource("Packages/User/LaTeXing/bibsonomy.map"))
            self.type_map.update(self.user_map["types"] if "types" in self.user_map else {})
            self.field_map.update(self.user_map["fields"] if "fields" in self.user_map else {})
        except:
            pass

        self.status = "Ok"
        self.items = []

    def decode_value(self, string):
        json_data = {"url": None, "documents": []}
        x = xml.etree.ElementTree.fromstring(string)
        json_data["url"] = x.find("posts").get("next")
        for post in x.findall('posts/post'):
            bibtex = post.find("bibtex")
            data = {"tags": [tag.get("name") for tag in post.findall('tag')]}
            for key, value in bibtex.attrib.items():
                data[key] = value
            json_data["documents"] += [data]
        return json_data

    def documents(self):
        client = BibsonomyClient(self.settings["bibsonomy_username"], self.settings["bibsonomy_apikey"])
        documents = []

        # Build first url
        url = "/users/%s/posts?resourcetype=publication" % self.settings["bibsonomy_username"]
        json_library = self.decode_value(client.get(url))
        documents = json_library["documents"]

        # Fetch all the other pages
        while(json_library["url"]):
            # Output
            log.info("%d" % (int(re.search(r"(?<=start=)\d+", json_library["url"]).group()) / 20))
            json_library = self.decode_value(client.get(json_library["url"]))

            # Save documents
            documents += json_library["documents"]
        return documents

    def build_fields(self, json_document):
        fields = {}
        #
        for target_key, source_key in self.field_map.items():
            # Skip non existing keys in json_document or empty
            if not source_key in json_document or not json_document[source_key]:
                continue

            field = json_document[source_key]

            # Validate Field, remove multiple spaces (need escape TeX commands)
            field = tools.validate_field(field)

            # Just to avoid empty fields
            if field:
                fields[target_key] = field

        return fields

    def run(self):
        try:
            if self.settings["bibsonomy_username"] and self.settings["bibsonomy_apikey"]:

                # Document Details
                for json_document in self.documents():
                    # Debug infos
                    log.trace(json_document)
                    try:
                        # Save Tags
                        tags = json_document["tags"]

                        # Save Fields
                        fields = self.build_fields(json_document)

                        # Save Citation Type
                        citation_type = self.type_map[json_document["entrytype"]] if json_document["entrytype"] in self.type_map else None
                        if not citation_type:
                            log.error("skip citation_type (%s)" % json_document)
                            continue

                        # Save Citation Key
                        citation_key = json_document["bibtexKey"] if "bibtexKey" in json_document else None
                        self.items += [{"key": citation_key, "type": json_document["entrytype"], "fields": fields, "tags": tags}]
                    except Exception as e:
                        log.error("invalid response (%s)" % json_document)
                self.status = "Ok"

            else:
                self.status = "Waiting"

                url = "http://www.bibsonomy.org/settings?selTab=1"
                webbrowser.open(url)

                def on_done(s):
                    username, apikey = s.split(" ", 1)
                    tools.save_settings("LaTeXing", **{"bibsonomy_username": username, "bibsonomy_apikey": apikey})
                    sublime.status_message("Bibsonomy.com successfully configured!")
                    sublime.run_command("ltx_sync_data", {"mode": "bibsonomy"})

                sublime.active_window().show_input_panel("Please enter your username and apikey:", url, on_done, None, None)
        except Exception as e:
            log.error(e)
            self.status = "Error"
            sublime.error_message("Cannot access Bibsonomy.org, please check your username and apikey.")
