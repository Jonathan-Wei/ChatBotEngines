#-*- coding=utf-8 -*-
from collections import OrderedDict

class ChatbotIntentFlow:

    def __init__(self,intentFlow=None,comfirmAction=None,negativeAction=None,ask=None):
        self.intentFlow = intentFlow
        self.comfirmAction = comfirmAction
        self.negativeAction = negativeAction
        self.ask = ask

    def getIntentFlowInfo(self):
        return {"ask":self.ask,"action":self.comfirmAction}

