import sublime

import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

import re
import webbrowser

from requests_oauthlib import OAuth2Session

from .. import logger
from .. import tools

log = logger.getLogger(__name__)


class MendeleyClient():

    def __init__(self, refresh_token=None):
        self.baseurl = "https://api.mendeley.com"

        self.client_id = "141"
        self.client_secret = "4*ic:5WfF;LxE534"
        self.redirect_uri = "http://www.latexing.com/mendeley.html"

        self.access_token = None
        self.refresh_token = refresh_token

    def authorization_url(self):
        oauth = OAuth2Session(client_id=self.client_id, scope=["all"])
        authorization_url, self.state = oauth.authorization_url("https://api.mendeley.com/oauth/authorize")
        return authorization_url

    def get_access_token(self):
        oauth = OAuth2Session(client_id=self.client_id, token={"refresh_token": self.refresh_token})
        token = oauth.refresh_token("https://api.mendeley.com/oauth/token", client_id=self.client_id, client_secret=self.client_secret)

        self.access_token = token["access_token"]

    def get_refresh_token(self, code):
        oauth = OAuth2Session(client_id=self.client_id, redirect_uri=self.redirect_uri, state=self.state)
        token = oauth.fetch_token("https://api.mendeley.com/oauth/token", authorization_response=self.redirect_uri + "?state=%s&code=%s" % (self.state, code), client_secret=self.client_secret, scope=['all'])

        self.refresh_token = token["refresh_token"]
        return token["refresh_token"]

    def get(self, url):
        oauth = OAuth2Session(client_id=self.client_id, token={"access_token": self.access_token})
        r = oauth.get(self.baseurl + url)
        return r.text


class Mendeley():

    def __init__(self):
        self.client_id = "141"
        self.client_secret = "4*ic:5WfF;LxE534"

        self.settings = tools.load_settings("LaTeXing", mendeley_oauth_token="", mendeley_internal_cite_key=False, mendeley_cite_key_pattern="{Author}{year}")

        # Load map
        self.map = sublime.decode_value(sublime.load_resource("Packages/LaTeXing/latexing/api/mendeley.map"))

        # bibtex: zotero type
        self.type_map = self.map["types"]

        # bibtex: zotero field
        self.field_map = self.map["fields"]

        # Check for user maps
        try:
            self.user_map = sublime.decode_value(sublime.load_resource("Packages/User/LaTeXing/mendeley.map"))
            self.type_map.update(self.user_map["types"] if "types" in self.user_map else {})
            self.field_map.update(self.user_map["fields"] if "fields" in self.user_map else {})
        except:
            pass

        self.status = "Ok"
        self.items = []
        self.items_no_key = {}

    def build_string(self, item_list):
        # add curely braket in case if no forename in Mendeley given, needs to be checked, not 100% sure
        return " and ".join([("%s, %s" % (item["last_name"], item["first_name"])) if ("first_name" in item and item["first_name"]) else (("ltx:1%sltx:2" if " " in item["last_name"] else "%s") % item["last_name"]) for item in item_list])

    def library(self):
        url = "/documents?limit=500&reverse=false&order=asc&view=all"
        json_documents = sublime.decode_value(self.client.get(url))

        documents = json_documents
        while len(json_documents) == 500:
            json_documents = sublime.decode_value(self.client.get(url + "&marker=" + json_documents[-1]['id']))
            documents += json_documents

        return documents

    def folders(self):
        url = "/folders"
        json_folders = sublime.decode_value(self.client.get(url))

        def build_folder_path(folder):
            path = [folder["name"]]
            if "parent_id" not in folder:
                return path
            else:
                for item in json_folders:
                    if folder["parent_id"] == item["id"]:
                        path = build_folder_path(item) + path
                return path

        folders = {}
        for folder in json_folders:
            folders[folder["id"]] = "/".join(build_folder_path(folder))
        return folders

    def documents(self, document_ids):
        url = "/documents/%s/"
        documents = {}
        i = 0
        n = len(str(len(document_ids)))
        for document_id in document_ids:
            json_document = sublime.decode_value(self.client.get(url % document_id))
            # Debug
            i += 1
            log.debug("%s/%d" % (str(i).zfill(n), len(document_ids)))
            documents[document_id] = json_document
        return documents

    def build_fields(self, json_document):
        fields = {}

        for target_key, key in self.field_map.items():
            source_key = key.split(":")[0]
            # Skip non existing keys in json_document or empty
            if source_key not in json_document or not json_document[source_key]:
                continue

            if source_key in ["authors", "editors", "translators"]:
                field = self.build_string(json_document[source_key])
            elif source_key == "identifiers":
                if source_key not in json_document or target_key not in json_document[source_key]:
                    continue
                field = json_document[source_key][target_key]
            elif source_key == "keywords" or source_key == "websites":
                field = ",".join(json_document[source_key])
            elif source_key == "last_modified":
                if re.search(r"(\d{2})[/-](\d{2})[/-](\d{4})", json_document[source_key]):
                    field = re.sub(r"(\d{2})[/-](\d{2})[/-](\d{4})", r"\3-\2-\1", json_document[source_key])
                elif re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})", json_document[source_key]):
                    field = re.sub(r"(\d{4})[/-](\d{2})[/-](\d{2})", r"\1-\2-\3", json_document[source_key])
            else:
                field = str(json_document[source_key])

            # Validate Field, remove multiple spaces (need escape TeX commands)
            field = tools.validate_field(field) if target_key != "url" else field

            # Just to avoid empty fields
            if field:
                fields[target_key] = field

        return fields

    def run(self, cites={}, cites_no_key={}):
        try:
            if self.settings["mendeley_oauth_token"]:
                self.client = MendeleyClient(self.settings["mendeley_oauth_token"])
                self.client.get_access_token()

                # User Library
                library_documents = self.library()

                # Folders
                library_folders = self.folders()

                # Document Details
                for json_document in library_documents:
                    # Debug infos
                    print(json_document)
                    log.trace(json_document)
                    try:
                        # Save Tags
                        tags = json_document["tags"] if "tags" in json_document else []

                        # Save Folders
                        folders = [library_folders[folder] for folder in json_document["folders_ids"]] if "folders_ids" in json_document else []

                        # Save Fields
                        fields = self.build_fields(json_document)

                        # Save Citation Type
                        citation_type = self.type_map[json_document["type"]] if json_document["type"] in self.type_map else None
                        if not citation_type:
                            log.error("skip citation_type (%s)" % json_document)
                            continue

                        # Save Citation Key
                        citation_key = json_document["citation_key"] if "citation_key" in json_document else None
                        self.items += [{"id": json_document["id"], "version": json_document["last_modified"], "key": citation_key, "type": citation_type, "fields": fields, "tags": tags, "folders": folders}]

                    except Exception as e:
                        log.error(e)
                        log.error("invalid response (%s)" % json_document)
                self.status = "Ok"

            else:
                self.status = "Waiting"

                # MendeleyClient
                client = MendeleyClient()
                url = client.authorization_url()
                webbrowser.open(url)

                def on_done(s):
                    token = client.get_refresh_token(s)
                    tools.save_settings("LaTeXing", **{"mendeley_oauth_token": token})
                    sublime.status_message("Mendeley.com successfully configured!")
                    sublime.run_command("ltx_sync_data", {"mode": "mendeley"})

                sublime.set_timeout(lambda: sublime.active_window().show_input_panel("Please enter your verification code:", url, on_done, None, None), 250)

        except Exception as e:
            raise e
