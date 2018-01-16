import re

from . import logger
from . import tools

log = logger.getLogger(__name__)

FIELDS = ["address", "annote", "author", "collaborator", "booktitle", "chapter", "crossref", "edition", "editor", "howpublished", "institution", "isbn", "journal", "key", "month", "note", "number", "organization", "pages", "publisher", "school", "series", "title", "type", "url", "volume", "year"]
CITE_FIELDS = ["author", "journal", "title", "year"]


class BibItem:

    def __init__(self, key, origin, entrytype, fields, tags=[], folders=[]):
        self.key = key
        self.origin = origin
        self.entrytype = entrytype
        self.fields = fields
        self.tags = tags
        self.folders = folders

    def string(self, plain=False, panel_format=False):
        if panel_format:
            settings = tools.load_settings("LaTeXing", cite_panel_format=["{key}: {title}", "#{type} by {author}"])
            item = [s.format(
                    key=self.key,
                    type=self.entrytype,
                    author=self.fields["author"].strip(" ,") if "author" in self.fields else "None",
                    sauthor=(re.split(r",", self.fields["author"], 1)[0] + " et al." if self.fields["author"].count("and") > 1 else self.fields["author"].strip(" ,")) if "author" in self.fields else "None",
                    journal = self.fields["journal"] if "journal" in self.fields else "None",
                    title = self.fields["title"] if "title" in self.fields else "None",
                    stitle = re.split(r"[.!\?]", self.fields["title"], 1)[0] if "title" in self.fields else "None",
                    year = self.fields["year"] if "year" in self.fields else "None",
                    origin = self.origin
                    ) for s in settings["cite_panel_format"]]
        else:
            item = "\n@%s{%s" % (self.entrytype.lower(), self.key)
            for key, value in sorted(self.fields.items(), key=lambda x: x[0]):
                value = self.fields[key]
                if value.isdigit():
                    item += ",\n\t%s = %s" % (key, value)
                else:
                    item += ",\n\t%s = {%s}" % (key, value)
            item += "\n}\n"
        return re.sub(r"[\t\n\s]*", "", item) if plain else item
