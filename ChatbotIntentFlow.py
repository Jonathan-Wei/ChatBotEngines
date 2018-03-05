#-*- coding=utf-8 -*-
from collections import OrderedDict

class ChatbotIntentFlow:

    def __init__(self,intentFlowContent=OrderedDict(),intentFlowComplete = True, comfirmAction=None,negativeAction=None,ask=None):
        self.intentFlowContent = intentFlowContent # 规则内容
        self.intentFlowComplete = intentFlowComplete # 规则是否完整执行
        self.comfirmAction = comfirmAction  # 问题确认执行action
        self.negativeAction = negativeAction  # 问题否定执行action
        self.ask = ask  #规则询问

    # 获取流程询问以及对应的操作
    def getIntentFlowInfo(self):
        return {"ask":self.ask,"action":self.comfirmAction}

