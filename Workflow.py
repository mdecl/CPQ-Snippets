import re

import Dictionary
import Interface_Swagger
import Object_Compare
import Workflow_Notifications

class WorkflowHelper:
    def __init__(self):
        self.InterfaceHelper = Interface_Swagger.SwaggerInterface()

    ## workflow item manipulation

    def changeCondition(self, _workflowItems, _newCondition):
        # type: (list[WorkflowItem], str) -> list[WorkflowItem]
        """Change the condition for all items in the provided list."""
        for Item in _workflowItems:
            for Action in Item.actions:
                Action.condition = _newCondition
        return _workflowItems

    def copyToDifferentStatus(self, 
                              _workflowItem, 
                              _newStartStatusName,
                              _newEndStatusName):
        # type: (WorkflowItem, str, str) -> WorkflowItem
        NewItem = WorkflowItem(**_workflowItem.copy())
        NewItem.startStatusName = _newStartStatusName
        NewItem.startStatusId = 0
        NewItem.endStatusName = _newEndStatusName
        NewItem.endStatusId = 0
        return NewItem

    def addPreActionToAll(self, _workflowItems, _preAction, _rankIndex=0):
        # type: (list[WorkflowItem], WorkflowItemPreAction, int) -> list[WorkflowItem] | None
        """Add a pre-action to all items in the provided list."""
        if not (_workflowItems and isinstance(_preAction, WorkflowItemPreAction)):
            return
        for Item in _workflowItems:
            for Action in Item.actions:
                Action.addPreAction(_preAction, _rankIndex)
        return _workflowItems

    def addPostActionToAll(self, _workflowItems, _postAction, _rankIndex=0):
        # type: (list[WorkflowItem], WorkflowItemPostAction, int) -> list[WorkflowItem] | None
        """Add a post-action to all items in the provided list."""
        if not (_workflowItems and isinstance(_postAction, WorkflowItemPostAction)):
            return
        for Item in _workflowItems:
            for Action in Item.actions:
                Action.addPostAction(_postAction, _rankIndex)
        return _workflowItems

    def changeQuoteType(self, _workflowItems, _newQuoteTypeId):
        # type: (list[WorkflowItem], int) -> list[WorkflowItem]
        """Change the quote type id for all items in the provided list."""
        for Item in _workflowItems:
            Item.quoteTypeId = _newQuoteTypeId
        return _workflowItems

    def upsertWorkflowItems(self, _workflowItems, _existingList=None,
                            _baseUrl=None):
        # type: (list[WorkflowItem], list[WorkflowItem] | None, str | None) -> list[WorkflowItem]
        """Insert or update workflow items into an existing workflow list."""
        if _existingList is None:
            ExistingWorkflow = self.getFullWorkflow(_baseUrl=_baseUrl)
        else:
            ExistingWorkflow = _existingList
        if not _workflowItems:
            return ExistingWorkflow

        # map action/notification names to ids (may differ between tenants)
        ActionIdsByName = {
            Action["name"]: Action["id"]
            for Action in self.InterfaceHelper.getActions(_baseUrl=_baseUrl)
        }
        NotificationIdsByName = {
            Notification["name"]: Notification["id"]
            for Notification in self.InterfaceHelper.getNotifications(_baseUrl=_baseUrl)
        }

        for Item in _workflowItems:
            ExistingWorkflow = self._upsertWorkflowItem(Item, ExistingWorkflow)
            Item.replaceActionIds(ActionIdsByName)
            Item.replaceNotificationIds(NotificationIdsByName)

        return ExistingWorkflow

    def _upsertWorkflowItem(self, _newItem, _workflowItems):
        # type: (WorkflowItem, list[WorkflowItem]) -> list[WorkflowItem]
        """Insert or update a single workflow item in a list."""
        try:
            Item = next(I for I in _workflowItems if I.isMatch(_newItem))
        except StopIteration:
            # new item -> no adjustment needed of existing items
            _workflowItems.append(_newItem)
            return _workflowItems

        # combine existing item with new item actions
        for NewAction in _newItem.actions:
            try:
                Index = next(
                    i for i, Action in enumerate(Item.actions)
                    if NewAction.actionName == Action.actionName
                )
            except StopIteration:
                Item.actions.append(NewAction)
            else:
                Item.actions[Index] = NewAction
        return _workflowItems

    ## workflow comparison / update

    def compareWorkflow(self, _workflowItems1, _workflowItems2):
        # type: (list[WorkflowItem], list[WorkflowItem]) -> dict
        """Compare two workflow item lists and return differences."""
        CompareFunctionsByType = {
            WorkflowItem: WorkflowItem.getHeader,
            WorkflowItemAction: WorkflowItemAction.getActionName,
            WorkflowItemPostAction: WorkflowItemSubAction.getActionName,
            WorkflowItemPreAction: WorkflowItemSubAction.getActionName,
            Workflow_Notifications.Notification: Workflow_Notifications.Notification.getName,
        }
        return Object_Compare.dictIterDiffByKey(
            _workflowItems1, _workflowItems2, CompareFunctionsByType
        )

    def compareWorkflowAcrossEnvironments(self, _baseUrl, _baseUrlToCompare):
        # type: (str, str) -> dict
        """Compare the full workflow between two CPQ tenants."""
        return self.compareWorkflow(
            self.getFullWorkflow(_baseUrl=_baseUrl),
            self.getFullWorkflow(_baseUrl=_baseUrlToCompare),
        )

    def updateWorkflow(self, _workflowItems, _baseUrl=None):
        # type: (list[WorkflowItem], str|None) -> tuple[str|None, bool]
        """Deletes the full workflow and replaces it with provided workflow.

        Warning: pass a full workflow, not a filtered subset!.
        """
        MIN_LEN = 150
        if not _workflowItems or len(_workflowItems) < MIN_LEN:
            raise ValueError("MIN_LEN condition not fulfilled")
        return self.InterfaceHelper.updateWorkflow(_workflowItems, _baseUrl=_baseUrl)

    def getFullWorkflow(self, _baseUrl=None):
        # type: (str|None) -> list[WorkflowItem]
        Raw = self.InterfaceHelper.getWorkflow("", _baseUrl=_baseUrl)
        return self.sortWorkflow([WorkflowItem(**Item) for Item in Raw])

    def getFilteredWorkflow(self, _filter, _baseUrl=None):
        # type: (str, str|None) -> list[WorkflowItem]
        Raw = self.InterfaceHelper.getWorkflow(_filter, _baseUrl=_baseUrl)
        return self.sortWorkflow([WorkflowItem(**Item) for Item in Raw])

    def sortWorkflow(self, _workflowItems):
        # type: (list[WorkflowItem]) -> list[WorkflowItem]
        return sorted(_workflowItems, key=WorkflowItem.getHeader)

    ## actions

    def getActionIdByName(self, _actionName, _baseUrl=None):
        # type: (str, str|None) -> int
        Filter = "name eq '{}'".format(_actionName)
        Actions = self.InterfaceHelper.getActions(Filter, _baseUrl=_baseUrl, _top="1")
        if not Actions:
            return 0
        return WorkflowAction(**Actions[0]).id

    def getAllActions(self, _baseUrl=None):
        Actions = self.InterfaceHelper.getActions(_baseUrl=_baseUrl)
        return self.sortActions([WorkflowAction(**Item) for Item in Actions])

    def sortActions(self, _actions):
        # type: (list[WorkflowAction]) -> list[WorkflowAction]
        return sorted(_actions, key=WorkflowAction.getActionName)

    def compareActionsAcrossEnvironments(self, _baseUrl, _baseUrlToCompare):
        """Compare all actions between two CPQ tenants."""
        CompareKeyFunctions = {WorkflowAction: WorkflowAction.getActionName}

        return Object_Compare.dictIterDiffByKey(
            self.getAllActions(_baseUrl=_baseUrl),
            self.getAllActions(_baseUrl=_baseUrlToCompare),
            CompareKeyFunctions
        )



### data classes ###

class WorkflowItemSubAction(Dictionary.ModeledMapping):
    customActionName = ""
    customActionId = 0
    rank = 0

    def getActionName(self):
        return self.customActionName


class WorkflowItemPreAction(WorkflowItemSubAction):
    def getRankFromIndex(self, _index):
        return -10 * (_index + 1)

    def setRankFromIndex(self, _index):
        self.rank = self.getRankFromIndex(_index)


class WorkflowItemPostAction(WorkflowItemSubAction):
    def getRankFromIndex(self, _index):
        return 10 * (_index + 1)

    def setRankFromIndex(self, _index):
        self.rank = self.getRankFromIndex(_index)


class WorkflowAction(Dictionary.ModeledMapping):
    id = 0
    actionType = 0
    modifiedOn = ""
    modifiedBy = ""
    modifiedById = ""
    translations = []
    globalFlag = ""
    name = ""
    systemId = ""
    sortOrder = "0"
    actionDisplayLevel = True
    image = ""
    defaultImage = False
    useDefaultImage = ""
    globalCondition = ""
    preActionCondition = ""
    postActionCondition = ""
    script = ""
    placement = "C"

    def getActionName(self):
        return self.name

    def __eq__(self, _other):
        if not isinstance(_other, WorkflowAction):
            return False
        return (
            self.name == _other.name and
            self.globalCondition == _other.globalCondition and
            self.preActionCondition == _other.preActionCondition and
            self.postActionCondition == _other.postActionCondition and
            _normalizeScript(self.script) == _normalizeScript(_other.script)
        )

def _normalizeScript(_script):
    # type: (str) -> str
    if not _script or not isinstance(_script, str):
        return ""

    Normalized = re.sub(r'\r\n+', '\n', _script)
    Normalized = re.sub(r'\n+', '\n', Normalized)
    Normalized = re.sub(r' +', ' ', Normalized)
    Normalized = Normalized.replace("\\t", " ").replace("\t", " ")
    Normalized = Normalized.strip()
    return Normalized


class WorkflowItem(Dictionary.ModeledMapping):
    quoteTypeName = ""
    quoteTypeId = 0
    startStatusName = ""
    startStatusId = 0
    endStatusName = ""
    endStatusId = 0
    actions = []  # type: list[WorkflowItemAction]

    @Dictionary.KeyValidator('actions')
    def _setActions(self, _actions):
        Actions = self.ensureIterableType(_actions, WorkflowItemAction)
        return sorted(Actions, key=WorkflowItemAction.getActionName)

    def isMatch(self, _other):
        """True if provided other WorkflowItem has the same header."""
        if not isinstance(_other, WorkflowItem):
            return False
        return self.getHeader() == _other.getHeader()

    def getHeader(self):
        return "{}".format((self.quoteTypeName, self.startStatusName, self.endStatusName))

    def replaceActionIds(self, _actionIdsByName):
        # type: (dict[str, int]) -> None
        for Action in self.actions:
            Action.actionId = _actionIdsByName.get(Action.actionName, Action.actionId)
            for PreAction in Action.preActions:
                PreAction.customActionId = _actionIdsByName.get(
                    PreAction.customActionName, PreAction.customActionId
                )
            for PostAction in Action.postActions:
                PostAction.customActionId = _actionIdsByName.get(
                    PostAction.customActionName, PostAction.customActionId
                )

    def replaceNotificationIds(self, _notificationIdByName):
        # type: (dict[str, int]) -> None
        for Action in self.actions:
            for Notification in Action.notifications:
                Notification.id = _notificationIdByName.get(
                    Notification.name, Notification.id
                )

class WorkflowItemAction(Dictionary.ModeledMapping):
    actionId = 0
    actionName = ""
    condition = ""
    reconfigure = False
    automaticallyUpgrade = False
    promptForUpgrade = False
    disableWhenIncomplete = False
    performOn = ""
    preActions = []  # type: list[WorkflowItemPreAction]
    postActions = []  # type: list[WorkflowItemPostAction]
    notifications = []  # type: list[Workflow_Notifications.Notification]

    def __eq__(self, _other):
        if not isinstance(_other, WorkflowItemAction):
            return False
        return (
            self.actionName == _other.actionName and
            self.condition == _other.condition and
            self.preActions == _other.preActions and
            self.postActions == _other.postActions and
            self.notifications == _other.notifications
        )

    def _addSubAction(self, _subAction, _rankIndex):
        if not isinstance(_subAction, (WorkflowItemPreAction, WorkflowItemPostAction)):
            raise ValueError

        if isinstance(_subAction, WorkflowItemPreAction):
            SubActions = self.preActions
        else:
            SubActions = self.postActions

        if _subAction.customActionName in (_ .customActionName for _ in SubActions):
            return

        if len(SubActions) <= _rankIndex:
            _subAction.setRankFromIndex(len(SubActions))
            SubActions.append(_subAction)
            return

        _subAction.setRankFromIndex(_rankIndex)
        for Existing in SubActions:
            if int(Existing.rank) <= _subAction.rank:
                Existing.rank = Existing.rank + _subAction.getRankFromIndex(0)
        SubActions.append(_subAction)

    def addPreAction(self, _preAction, _rankIndex=0):
        self._addSubAction(_preAction, _rankIndex)

    def addPostAction(self, _postAction, _rankIndex=0):
        self._addSubAction(_postAction, _rankIndex)

    def getActionName(self):
        return self.actionName

    @Dictionary.KeyValidator('preActions')
    def _setPreActions(self, _preActions):
        return [WorkflowItemPreAction(**Action) for Action in _preActions]

    @Dictionary.KeyValidator('postActions')
    def _setPostActions(self, _postActions):
        return [WorkflowItemPostAction(**Action) for Action in _postActions]

    @Dictionary.KeyValidator('notifications')
    def _setNotifications(self, _notifications):
        return [Workflow_Notifications.Notification(**N) for N in _notifications]
