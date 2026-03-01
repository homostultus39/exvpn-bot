from py3xui import Api


class XrayPanelClient:
    def __init__(self, endoint: str, username: str, password: str):
        self.api = Api(endpoint=endoint, username=username, password=password)
        self.api.login()

    def get_inbounds_list(self):
        return self.api.inbound.get_list()
