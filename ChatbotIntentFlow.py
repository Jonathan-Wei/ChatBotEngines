#-*- coding=utf-8 -*-
from collections import OrderedDict

class ChatbotIntentFlow:

    def __init__(self,intentFlowContent=OrderedDict(),intentFlowComplete = True, comfirmAction=None,negativeAction=None,ask=None):
        self.intentFlowContent = intentFlowContent
        self.intentFlowComplete = intentFlowComplete
        self.comfirmAction = comfirmAction
        self.negativeAction = negativeAction
        self.ask = ask

    # 获取流程询问以及对应的操作
    def getIntentFlowInfo(self):
        return {"ask":self.ask,"action":self.comfirmAction}

