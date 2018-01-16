import sublime
import sublime_plugin

from . import defaultclient
from .. import logger
from .. import tools

log = logger.getLogger(__name__)


class CiteulikeClient():

    def __init__(self, username):
        self.baseurl = 'http://www.citeulike.org/json/user/%s' % username
        self.username = username

    def get(self, url):
        client = defaultclient.DefaultClient({'User-Agent': 'LaTeXing/info@latexing.com LaTeXing/1.0'})
        resonce = client.request(self.baseurl + url)
        return resonce


class Citeulike():

    def __init__(self):
        self.settings = tools.load_settings("LaTeXing", citeulike_username="")

        # Load map
        self.map = sublime.decode_value(sublime.load_resource("Packages/LaTeXing/latexing/api/citeulike.map"))

        # bibtex: citeulike type
        self.type_map = self.map["types"]

        # bibtex: citeulike field
        self.field_map = self.map["fields"]

        # Check for user maps
        try:
            self.user_map = sublime.decode_value(sublime.load_resource("Packages/User/LaTeXing/citeulike.map"))
            self.type_map.update(self.user_map["types"] if "types" in self.user_map else {})
            self.field_map.update(self.user_map["fields"] if "fields" in self.user_map else {})
        except:
            pass

        self.status = "Ok"
        self.items = []

    def build_string(self, item_list):
        return " and ".join([item for item in item_list])

    def documents(self):
        client = CiteulikeClient(self.settings["citeulike_username"])
        documents = []
        # Read maximum
        i = 0
        while True:
            i += 1
            json_library = sublime.decode_value(client.get("?page=%d&per_page=50" % i))
            if not json_library:
                break
            # Output
            log.info("%d", i)

            # Save documents
            documents += json_library
        return documents

    def build_fields(self, json_document):
        fields = {}
        #
        for target_key, source_key in self.field_map.items():
            # Skip non existing keys in json_document or empty
            if not source_key in json_document or not json_document[source_key]:
                continue

            # Start matching fields
            if source_key == "authors" or source_key == "editors":
                field = self.build_string(json_document[source_key])
            elif source_key == "published":
                field = json_document[source_key][0]
            elif source_key == "start_page":
                field = json_document["start_page"]
                if "end_page" in json_document and json_document["end_page"]:
                    field += "--" + json_document["end_page"]
            else:
                field = json_document[source_key]

            # Validate Field, remove multiple spaces (need escape TeX commands)
            field = tools.validate_field(field)

            # Just to avoid empty fields
            if field:
                fields[target_key] = field
        return fields

    def run(self):
        try:
            if self.settings["citeulike_username"]:

                # Document Details
                for json_document in self.documents():
                    # Debug infos
                    log.trace(json_document)
                    try:
                        # Save Tags
                        tags = [tag for tag in json_document["tags"]] if "tags" in json_document else []

                        # Save Fields
                        fields = self.build_fields(json_document)

                        # Save Citation Type
                        citation_type = self.type_map[json_document["type"]] if json_document["type"] in self.type_map else None
                        if not citation_type:
                            log.error("skip citation_type (%s)", json_document)
                            continue

                        # Save Citation Key
                        citation_key = json_document["citation_keys"][2].replace(" ", "") if json_document["citation_keys"][2] else json_document["citation_keys"][1].replace(" ", "")
                        self.items += [{"key": citation_key, "type": citation_type, "fields": fields, "tags": tags}]
                    except Exception as e:
                        log.error("invalid response (%s)", json_document)

                self.status = "Ok"

            else:
                self.status = "Waiting"

                def on_done(s):
                    username = s
                    tools.save_settings("LaTeXing", **{"citeulike_username": username})
                    sublime.status_message("Citeulike.org successfully configured!")
                    sublime.run_command("ltx_sync_data", {"mode": "citeulike"})

                sublime.active_window().show_input_panel("Please enter your username:", "", on_done, None, None)
        except Exception as e:
            log.error(e)
            self.status = "Error"
            sublime.error_message("Cannot access Citeulike.org, please check your username.")
