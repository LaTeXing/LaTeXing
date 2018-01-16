import urllib.request

try:
    import oauthlib.oauth2
except:
    pass

from .. import logger
from .. import tools

log = logger.getLogger(__name__)


class OAuth2Client():

    def __init__(self, client_id, headers={}):
        self.client_id = client_id
        self.headers = headers

    def request(self, url, **args):
        client = oauthlib.oauth2.Client(self.client_id, **args)
        uri, headers, body = client.add_token(url)
        headers.update(self.headers)

        log.trace("%s %s", url, headers)

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

        handlers = [proxy_handler]

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
        return opener.open(urllib.request.Request(url, headers=headers)).read().decode("utf-8")
