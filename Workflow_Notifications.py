import Interface_Swagger
import Dictionary


class NotificationHelper:

    def __init__(self):
        self.InterfaceHelper = Interface_Swagger.SwaggerInterface()

    def getAllNotifications(self, _baseUrl=None):
        # type: (str|None) -> list[Notification]
        Notifications = self.InterfaceHelper.getNotifications('', _baseUrl)
        Notifications = [Notification(**N) for N in Notifications]
        return self.sortNotifications(Notifications)

    def updateInBulk(self, _notifications, _baseUrl=None):
        # type: (list[Notification], str|None) -> tuple[str|None, bool]
        """Updates only the provided notifications in bulk."""
        return self.InterfaceHelper.updateNotifications(_notifications, _baseUrl)

    def updateContentsInBulk(self, _notificationContents, _baseUrl=None):
        # type: (list[NotificationContent], str|None) -> tuple[str|None, bool]
        """Updates only the provided contents in bulk."""
        return self.InterfaceHelper.updateNotificationContents(_notificationContents, _baseUrl)

    def getFilteredNotifications(self, _filter, _baseUrl=None):
        # type: (str, str|None) -> list[Notification]
        Notifications = self.InterfaceHelper.getNotifications(_filter, _baseUrl)
        Notifications = [Notification(**N) for N in Notifications]
        return self.sortNotifications(Notifications)

    def getFilteredNotificationsExpanded(self, _filter, _baseUrl=None):
        # type: (str, str|None) -> list[NotificationExpanded]
        Notifications = self.InterfaceHelper.getNotifications(
            _filter, _baseUrl, _expand="notificationcontents"
        )
        Notifications = [NotificationExpanded(**N) for N in Notifications]
        return self.sortNotifications(Notifications)

    def getAllContentsByNotificationId(self, _notificationId, _baseUrl=None):
        # type: (int, str|None) -> list[NotificationContent]
        Contents = self.InterfaceHelper.getNotificationContents(_notificationId, _baseUrl)
        Contents = [NotificationContent(**Content) for Content in Contents]
        return self.sortNotificationContents(Contents)

    def getNotificationIdByName(self, _name, _baseUrl=None):
        # type: (str, str|None) -> int
        Filter = "name eq '{}'".format(_name)
        Top = "1"
        Raw = self.InterfaceHelper.getNotifications(Filter, _baseUrl=_baseUrl, _top=Top)
        if not Raw:
            return 0
        return Notification(**Raw[0]).id

    def sortNotifications(self, _notifications):
        # type: (list[Notification]) -> list[Notification]
        return sorted(_notifications, key=Notification.getName)

    def sortNotificationContents(self, _contents):
        # type: (list[NotificationContent]) -> list[NotificationContent]
        return sorted(_contents, key=NotificationContent.getSubject)


class Notification(Dictionary.ModeledMapping):
    id = 0
    name = ''

    def getName(self):
        return self.name


class SimpleNotificationContent(Dictionary.ModeledMapping):
    id = 0
    subject = ''

    def getSubject(self):
        return self.subject


class NotificationExpanded(Notification):
    notificationContents = []  # type: list[SimpleNotificationContent]

    @Dictionary.KeyValidator('notificationContents')
    def setContents(self, _contents):
        Contents = self.ensureIterableType(_contents, SimpleNotificationContent)
        return sorted(Contents, key=SimpleNotificationContent.getSubject)


class NotificationContent(SimpleNotificationContent):
    id = 0
    subject = ''
    notificationId = 0
    condition = ''
    text = ''
    type = 0
    emailLists = []  # type: list[NotificationEmailList | NotificationEmailListExpanded]
    attachments = []  # type: list[NotificationAttachment]

    @Dictionary.KeyValidator('emailLists')
    def setEmailLists(self, _emailLists):
        return self.ensureIterableType(_emailLists, NotificationEmailListExpanded)

    @Dictionary.KeyValidator('attachments')
    def setAttachments(self, _attachments):
        return self.ensureIterableType(_attachments, NotificationAttachment)


class NotificationEmailList(Dictionary.ModeledMapping):
    emailListId = 0


class NotificationEmailListExpanded(Dictionary.ModeledMapping):
    emailListId = 0
    name = ''


class NotificationAttachment(Dictionary.ModeledMapping):
    fileName = ''
    parse = False
