import os.path

from . import cache
from . import logger
from . import tools

log = logger.getLogger(__name__)


def check_linked_bib_files(tex_path):
    log.trace(tex_path)

    # Load Settings
    prefs = tools.load_settings("LaTeXing", default_bib_extension=".bib", check_source=["local_bibliography", "remote_bibliography"])

    warnings = []

    if "local_bibliography" not in prefs["check_source"]:
        return warnings

    tex_file = cache.TeXFile(tex_path)
    tex_file.run()

    root_file = tex_file.root_file()
    root_file.run()

    tex_dir, tex_name = os.path.split(root_file.file_path)

    for file_path, item in root_file.get("bibliography"):
        arguments = [argument for argument in item["arguments"] if argument.split(":", 1)[0] == "{"]
        if arguments:
            for arg in arguments[0].split(":", 1)[1].split(","):
                if not os.path.exists(os.path.normpath(os.path.join(tex_dir, tools.add_extension(arg, prefs["default_bib_extension"])))):
                    warnings.append("W: %s:%i File `%s` not found. %s" % (file_path, item["line"], arg, item["tag"]))
    return warnings


def check_remote_bibfile(tex_path):
    log.trace(tex_path)

    # Load Settings
    settings = tools.load_settings("LaTeXing", bibname="Remote.bib", check_source=["local_bibliography", "remote_bibliography"])

    warnings = []

    if "remote_bibliography" not in settings["check_source"]:
        return warnings

    tex_file = cache.TeXFile(tex_path)
    tex_file.run()

    root_file = tex_file.root_file()
    root_file.run()

    tex_dir, tex_name = os.path.split(root_file.file_path)

    remote_bibliography = os.path.join(tex_dir, settings["bibname"])
    if remote_bibliography not in tex_file.bibliography() and os.path.exists(remote_bibliography):
        warnings = ["W: %s:0 File `%s` available but not included." % (tex_path, settings["bibname"])]

    return warnings
