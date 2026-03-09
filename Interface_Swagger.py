import Baltimore_Interface_Helper
# TODO: replace import with existing Interface_Helper
ContentType = Baltimore_Interface_Helper.ContentType

# see documentation on Swagger REST API
# base url + '/webapihelp/index' e.g. https://baltimoreaircoil-dev.cpq.cloud.sap/webapihelp/index


class SwaggerInterfaceBase:

    BASE_URL_DEV = ''
    BASE_URL_TST = ''
    BASE_URL_UAT = ''
    BASE_URL_PRD = ''
    BASE_URL = ''
    CREDENTIAL = ''

    API_TOKEN = '/oauth2/token'

    API_WORKFLOW = '/api/workflow/v1/workflow'
    API_WORKFLOW_BULK = '/api/workflow/v1/workflow/bulk'

    API_ACTIONS = '/api/workflow/v1/actions'

    API_NOTIFICATIONS = '/api/workflow/v1/notifications'
    API_NOTIFICATION_CONTENT = '/api/workflow/v1/notifications/{notificationId}/content'
    API_NOTIFICATIONS_CONTENT_BULK = '/api/workflow/v1/notifications/content/bulk'
    API_NOTIFICATIONS_BULK = '/api/workflow/v1/notifications/bulk'

    API_ATTRIBUTE_VALUES = '/api/products/v1/attributes/{id}/values'

    def __init__(self):
        self.RestClient = Baltimore_Interface_Helper.InterfaceRestClient()
        self._setBaseUrl()

    def _setBaseUrl(self):
        Host = RequestContext.Url.Host
        self.BASE_URL = 'https://{}'.format(Host)

    def getBearerToken(self):
        # type: () -> str
        Url = self.BASE_URL + self.API_TOKEN
        Response = AuthorizedRestClient.GetPasswordGrantOAuthToken(
            self.CREDENTIAL, Url
        )
        Token = str(getattr(Response, 'access_token', ''))
        return Token

    def getHeaders(self):
        return {'Authorization': 'Bearer {}'.format(self.getBearerToken())}

    def getWorkflow(self, _filterQuery, _top='1000', _baseUrl=None):
        # type: (str, str, str|None) -> list
        if _baseUrl:
            self.BASE_URL = _baseUrl

        Params = {'$top': _top}
        if _filterQuery:
            Params['$filter'] = _filterQuery
        Url = self.BASE_URL + self.API_WORKFLOW
        Response = self.RestClient.Get(Url, ContentType.STR, self.getHeaders(), Params)
        if Response is None or not self.RestClient.wasSuccessfull():
            return []

        Response = JsonHelper.Deserialize(Response)
        return Response['pagedRecords']

    def getActions(self, _filterQuery=None, _baseUrl=None, _top='1000'):
        # type: (str|None, str|None, str) -> list
        if _baseUrl:
            self.BASE_URL = _baseUrl

        if _filterQuery is None:
            _filterQuery = "actionType eq '1'"

        Params = {'$filter': _filterQuery, '$top': _top}
        Url = self.BASE_URL + self.API_ACTIONS
        Response = self.RestClient.Get(Url, ContentType.STR, self.getHeaders(), Params)
        if Response is None or not self.RestClient.wasSuccessfull():
            return []

        Response = JsonHelper.Deserialize(Response)
        return Response['pagedRecords']

    def getNotifications(self, _filterQuery=None, _baseUrl=None, _top='1000', _expand=None):
        # type: (str|None, str|None, str, str|None) -> list
        if _baseUrl:
            self.BASE_URL = _baseUrl

        Params = {'$top': _top, '$orderby': 'name'}
        if _filterQuery:
            Params['$filter'] = _filterQuery
        if _expand:
            Params['$expand'] = _expand
        Url = self.BASE_URL + self.API_NOTIFICATIONS
        Response = self.RestClient.Get(Url, ContentType.STR, self.getHeaders(), Params)

        if not self.RestClient.wasSuccessfull():
            return []

        Response = JsonHelper.Deserialize(Response)
        return Response['pagedRecords']

    def getNotificationContents(self, _notificationId, _baseUrl=None):
        # type: (int, str|None) -> list
        # 1 content = 1 message with subject, body, ...
        if _baseUrl:
            self.BASE_URL = _baseUrl

        Params = {'$top': '1000', '$expand': 'emaillists', '$orderby': 'subject'}
        Url = self.BASE_URL + self.API_NOTIFICATION_CONTENT.format(
            notificationId=_notificationId
        )
        Response = self.RestClient.Get(Url, ContentType.STR, self.getHeaders(), Params)

        if not self.RestClient.wasSuccessfull():
            return []

        Response = JsonHelper.Deserialize(Response)
        return Response['pagedRecords']

    def updateWorkflow(self, _workflowItems, _baseUrl=None):
        # type: (list, str|None) -> tuple[str|None, bool]
        # WARNING: workflow will be deleted and replaced with input list!
        # Upsert needs to be done before using this API.
        if _baseUrl:
            self.BASE_URL = _baseUrl

        Params = {}
        Url = self.BASE_URL + self.API_WORKFLOW_BULK
        Response = self.RestClient.Post(
            Url,
            ContentType.STR,
            ContentType.JSON,
            self.getHeaders(),
            Params,
            JsonHelper.Serialize(_workflowItems),
        )
        return Response, self.RestClient.wasSuccessfull()

    def updateNotifications(self, _notifications, _baseUrl=None):
        # type: (list, str|None) -> tuple[str|None, bool]
        # Upserts the provided notifications without modifying others
        if _baseUrl:
            self.BASE_URL = _baseUrl

        Params = {}
        Url = self.BASE_URL + self.API_NOTIFICATIONS_BULK
        Response = self.RestClient.Post(
            Url,
            ContentType.STR,
            ContentType.JSON,
            self.getHeaders(),
            Params,
            JsonHelper.Serialize(_notifications),
        )
        return Response, self.RestClient.wasSuccessfull()

    def updateNotificationContents(self, _notificationContents, _baseUrl=None):
        # type: (list, str|None) -> tuple[str|None, bool]
        # Upserts the provided notification contents without modifying others
        if _baseUrl:
            self.BASE_URL = _baseUrl

        Params = {}
        Url = self.BASE_URL + self.API_NOTIFICATIONS_CONTENT_BULK
        Response = self.RestClient.Post(
            Url,
            ContentType.STR,
            ContentType.JSON,
            self.getHeaders(),
            Params,
            JsonHelper.Serialize(_notificationContents),
        )
        return Response, self.RestClient.wasSuccessfull()

    def getAttributeValues(self, _attributeId, _baseUrl=None):
        # type: (int, str|None) -> list
        if _baseUrl:
            self.BASE_URL = _baseUrl

        Params = {}
        Url = self.BASE_URL + self.API_ATTRIBUTE_VALUES.format(id=_attributeId)
        Response = self.RestClient.Get(Url, ContentType.STR, self.getHeaders(), Params)

        if not self.RestClient.wasSuccessfull():
            return []

        Response = JsonHelper.Deserialize(Response)
        return Response


class SwaggerInterface(SwaggerInterfaceBase):
    # TODO: fill in your tenants
    BASE_URL_DEV = "https://baltimoreaircoil-dev.cpq.cloud.sap"
    BASE_URL_TST = "https://baltimoreaircoil-tst.cpq.cloud.sap"
    BASE_URL_UAT = "https://baltimoreaircoil-uat.cpq.cloud.sap"
    BASE_URL_PRD = "https://baltimoreaircoil.cpq.cloud.sap"
    CREDENTIAL = "INTEGRATION_USER"
