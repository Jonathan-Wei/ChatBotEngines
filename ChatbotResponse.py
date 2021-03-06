#-*- coding=utf-8 -*-
from collections import OrderedDict
from ChatbotIntentFlow import *
from ChatbotHistoryInfo import *
from core.Slots import *

class ChatbotResponse:

    def __init__(self):
        self.INIT_TYPE = 0
        self.PRE_ASK_TYPE = 1
        self.POST_ASK_TYPE = 3
        self.SLOT_ASK_TYPE =2
        self.RULE_ASK_TYPE =4

        self.slots = OrderedDict()

        self.answer  = ""
        self.complete = False
        self.result_entities = {}
        self.actionJson = {}
        self.lastResponseJson = {}
        self.entities_question = OrderedDict()

        self.entities_types = {}  # slot提问类型
        self.lastEntities = {}
        self.entities = []  # 识别的entities
        self.status = {}
        self.responseJson = {}  # 响应信息
        self.currentQuestionType = 0  # 1-为前置询问，2-slot询问，3-后置询问，4-流程规则询问

        self.pre_question = None  # 上一次的问题信息
        self.curslot = None

        self.contentData = []
        self.historyInfo = ChatbotHistoryInfo()

        self.returnJson = {}
        self.existHistory = False

        self.intentFlowInfo = ChatbotIntentFlow()
