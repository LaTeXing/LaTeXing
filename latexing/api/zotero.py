import sublime

import re
import sys
import urllib.parse
import webbrowser
import xml.etree.ElementTree

from . import oauth1client
from .. import logger
from .. import terminal
from .. import tools

log = logger.getLogger(__name__)


class ZoteroClient():

    def __init__(self, client_key, client_secret, user_key=None, user_id=None):
        self.baseurl = "https://api.zotero.org"
        self.client_key = client_key
        self.client_secret = client_secret
        self.user_key = user_key
        self.user_id = user_id

    def request_token(self, callback="oob"):
        url = 'https://www.zotero.org/oauth/request/'
        client = oauth1client.OAuth1Client(self.client_key, self.client_secret, {"Zotero-API-Version": 2})
        response = client.request(url, callback_uri=callback)
        token = urllib.parse.parse_qs(response)
        return {"oauth_token": token["oauth_token"][0], "oauth_token_secret": token["oauth_token_secret"][0]}

    def authorize_url(self, request_token):
        url = "https://www.zotero.org/oauth/authorize/?oauth_token=%s"
        return url % request_token["oauth_token"]

    def access_token(self, request_token, verifier):
        url = "https://www.zotero.org/oauth/access/"
        client = oauth1client.OAuth1Client(self.client_key, self.client_secret, {"Zotero-API-Version": 2})
        response = client.request(url, **{"resource_owner_key": request_token["oauth_token"], "resource_owner_secret": request_token["oauth_token_secret"], "verifier": verifier})
        token = urllib.parse.parse_qs(response)
        return {"user_key": token["oauth_token"][0], "user_id": token["userID"][0]}

    def get(self, url):
        client = oauth1client.OAuth1Client(self.client_key, self.client_secret, {"Zotero-API-Version": 2})
        response = client.request(self.baseurl + ("/users/%s" % self.user_id) + url + ("&" if "?" in url else "?") + ("key=%s" % self.user_key))
        if not response and "ssl" not in sys.modules and terminal.find_executable("curl", command_line_tool=True, error=True):
            response = terminal.communicate(["curl", "-H", "Zotero-API-Version:2", self.baseurl + ("/users/%s" % self.user_id) + url + ("&" if "?" in url else "?") + ("key=%s" % self.user_key)])
        return response


class Zotero():

    def __init__(self):
        self.client_key = "40af22476e380eadfef5"
        self.client_secret = "ec5cfba3fb9fb063d0d4"

        self.settings = tools.load_settings("LaTeXing",
                                            zotero_user_key="",
                                            zotero_user_id="",
                                            zotero_cite_key_pattern="{Author}{year}"
                                            )

        # Load map
        self.map = sublime.decode_value(sublime.load_resource("Packages/LaTeXing/latexing/api/zotero.map"))

        # bibtex: zotero type
        self.type_map = self.map["types"]

        # bibtex: zotero field
        self.field_map = self.map["fields"]

        # Check for user maps
        try:
            self.user_map = sublime.decode_value(sublime.load_resource("Packages/User/LaTeXing/zotero.map"))
            self.type_map.update(self.user_map["types"] if "types" in self.user_map else {})
            self.field_map.update(self.user_map["fields"] if "fields" in self.user_map else {})
        except:
            pass

        self.status = "Ok"
        self.items = []
        self.items_no_key = {}

    def build_string(self, creator_type, item_list):
        return " and ".join(["%s" % item["name"] if "name" in item else ("%s, %s" % (item["lastName"], item["firstName"])) for item in item_list if item["creatorType"] in creator_type])

    def build_year(self, date_string):
        try:
            return re.search(r"\d{4}", date_string).group()
        except:
            return None

    def library(self):
        client = ZoteroClient(self.client_key, self.client_secret, self.settings["zotero_user_key"], self.settings["zotero_user_id"])
        url = "/items?format=versions&itemType=-attachment&&-note"
        return sublime.decode_value(client.get(url))

    def folders(self):
        client = ZoteroClient(self.client_key, self.client_secret, self.settings["zotero_user_key"], self.settings["zotero_user_id"])
        url = "/collections?content=json"
        x = xml.etree.ElementTree.fromstring(client.get(url))
        json_folders = []
        for folder in x.findall("{http://www.w3.org/2005/Atom}entry/{http://www.w3.org/2005/Atom}content"):
            json_folders += [sublime.decode_value((folder.text))]

        def build_folder_path(folder):
            path = [folder["name"]]
            if not folder["parentCollection"]:
                return path
            else:
                for item in json_folders:
                    if folder["parentCollection"] == item["collectionKey"]:
                        path = build_folder_path(item) + path
                return path

        folders = {}
        for folder in json_folders:
            folders[folder["collectionKey"]] = "/".join(build_folder_path(folder))
        return folders

    def documents(self, document_ids):
        client = ZoteroClient(self.client_key, self.client_secret, self.settings["zotero_user_key"], self.settings["zotero_user_id"])
        url = "/items?itemKey=%s&content=json"
        documents = {}
        i = 0
        for document_id in [document_ids[n:n + 50] for n in range(0, len(document_ids), 50)]:
            i += len(document_id) if isinstance(document_id, list) else 1
            x = xml.etree.ElementTree.fromstring(client.get(url % ",".join(document_id)))
            # Output
            log.info("%s/%d" % (str(i).zfill(len(str(len(document_ids)))), len(document_ids)))
            # Save documents
            for document in x.findall("{http://www.w3.org/2005/Atom}entry/{http://www.w3.org/2005/Atom}content"):
                json_document = sublime.decode_value((document.text))
                documents[json_document["itemKey"]] = json_document
        return documents

    def build_fields(self, json_document):
        fields = {}
        #
        f = self.field_map[json_document["itemType"]]
        for target_key, key in f.items():
            source_key = key.split(":")[0]
            # Skip non existing keys in json_document
            if not source_key in json_document or not json_document[source_key]:
                continue

            # Start matching fields
            if source_key == "creators":
                field = self.build_string(key.split(":")[1].split("|"), json_document[source_key])
            elif target_key == "year":
                field = self.build_year(json_document[source_key])
            else:
                field = json_document[source_key]

            # Validate Field, remove multiple spaces (need escape TeX commands)
            field = tools.validate_field(field)

            # Just to avoid empty fields
            if field:
                fields[target_key] = field
        return fields

    def run(self, cites={}, cites_no_key={}):
        try:
            if self.settings["zotero_user_key"] and self.settings["zotero_user_id"]:
                # User Library
                library_documents = self.library()

                # Folders
                library_folders = self.folders()
                # Keys
                library_keys = []

                document_ids = []
                for document_id, version in library_documents.items():
                    # check for cached cite
                    item = cites[document_id] if document_id in cites else None
                    if item and item["version"] == version:
                        self.items += [item]
                        library_keys += [item["key"]]
                        continue

                    # checked for cached cite without a key
                    item = cites_no_key[document_id] if document_id in cites_no_key else None
                    if item and item == version:
                        self.items_no_key[document_id] = version
                        continue

                    document_ids += [document_id]

                log.info("load %d of %d", len(document_ids), len(library_documents))

                for document_id, json_document in self.documents(document_ids).items():
                    # Debug infos
                    log.trace(json_document)

                    # Skip attachments and notes
                    if json_document["itemType"] in ["attachment", "note"]:
                        continue

                    try:
                        # Save Tags
                        tags = [tag["tag"] for tag in json_document["tags"]] if "tags" in json_document else []

                        # Save Folders
                        folders = [library_folders[folder] for folder in json_document["collections"] if folder in library_folders] if "collections" in json_document else []

                        # Save Fields
                        fields = self.build_fields(json_document)

                        # Save Citation Type
                        citation_type = self.type_map[json_document["itemType"]] if json_document["itemType"] in self.type_map else None
                        if not citation_type:
                            log.error("skip citation_type (%s)", json_document)
                            continue

                        self.items += [{"id": document_id, "version": json_document["itemVersion"], "key": None, "type": citation_type, "fields": fields, "tags": tags, "folders": folders}]

                    except Exception as e:
                        log.error(e)
                        log.error("invalid response (%s)", json_document)
                self.status = "Ok"

            else:
                self.status = "Waiting"

                # ZoteroClient
                client = ZoteroClient(self.client_key, self.client_secret)
                request_token = client.request_token()
                authorize_url = client.authorize_url(request_token)
                webbrowser.open(authorize_url)

                def on_done(s):
                    access_token = client.access_token(request_token, s)
                    tools.save_settings("LaTeXing", **{"zotero_user_key": access_token["user_key"], "zotero_user_id": access_token["user_id"]})
                    sublime.status_message("Zotero.com successfully configured!")
                    sublime.run_command("ltx_sync_data", {"mode": "zotero"})

                sublime.set_timeout(lambda: sublime.active_window().show_input_panel("Please enter your verification code:", authorize_url, on_done, None, None), 250)

        except Exception as e:
            log.error(e)
            self.status = "Error"
            if "global name 'oauthlib' is not defined" in str(e):
                sublime.error_message("Cannot access Zotero.org, please install the oauthlib package from the package control and restart Sublime Text.")
            elif "'oauth_token'" in str(e) and "ssl" not in sys.modules:
                url = "https://www.zotero.org/settings/keys"
                webbrowser.open(url)
                sublime.error_message("Your system do not have the ssl module, please obtain your zotero_user_key and zotero_user_id from Zotero.org.")
            else:
                sublime.error_message("Cannot access Zotero.org, please check docs.latexing.com for more details")
