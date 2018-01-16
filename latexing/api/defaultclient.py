import urllib.parse
import urllib.request

from .. import logger
from .. import tools

log = logger.getLogger(__name__)


class DefaultClient():

    def __init__(self, headers={}, data=None):
        self.headers = headers
        self.data = urllib.parse.urlencode(data).encode('utf-8') if data else None

    def request(self, url, http_basic_auth_handler=None):
        log.trace("%s %s", url, self.headers)

        # Load proxy settings for Package Control
        settings = tools.load_settings("Package Control", http_proxy="", https_proxy="", proxy_username="", proxy_password="")

        # Set http or https proxy
        if settings["http_proxy"] or settings["https_proxy"]:
            proxies = {}

            # http proxy settings
            if settings["http_proxy"]:
                proxies["http"] = settings["http_proxy"]
                log.debug("http_proxy %s", settings["http_proxy"])

            # https proxy settings
            if settings["https_proxy"]:
                proxies["https"] = settings["https_proxy"]
                log.debug("https_proxy %s", settings["https_proxy"])

            # Combine http and https proxy handler
            proxy_handler = urllib.request.ProxyHandler(proxies)
        else:
            proxy_handler = urllib.request.ProxyHandler()

        handlers = [http_basic_auth_handler, proxy_handler] if http_basic_auth_handler else [proxy_handler]

        # Set proxy username and password
        password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        if settings["proxy_username"] and settings["proxy_password"]:
            if settings["http_proxy"]:
                password_manager.add_password(None, settings["http_proxy"], settings["proxy_username"], settings["proxy_password"])
            if settings["https_proxy"]:
                password_manager.add_password(None, settings["https_proxy"], settings["proxy_username"], settings["proxy_password"])

            # Debug
            log.debug("proxy_username %s proxy_password %s", settings["proxy_username"], settings["proxy_password"])

            handlers += [urllib.request.ProxyBasicAuthHandler(password_manager)]
            handlers += [urllib.request.ProxyDigestAuthHandler(password_manager)]

        opener = urllib.request.build_opener(*handlers)
        return opener.open(urllib.request.Request(url, data=self.data, headers=self.headers)).read().decode("utf-8")
