#-*- coding=utf-8 -*-
from collections import OrderedDict

class ChatbotResponse:

    def __init__(self):
        self.answer  = ""
        self.complete = False
        self.result_entities = {}
        self.actionJson = {}
        self.lastResponseJson = {}
        self.entities_question = OrderedDict()

        self.entities_types = {}  # slot提问类型
        self.ruleContent = OrderedDict()  # 规则内容
        self.ruleComplete = True  # 规则是否完整执行
        self.lastEntities = {}
        self.entities = []  # 识别的entities
        self.status = {}
        self.responseJson = {}  # 响应信息
        self.currentQuestionType = 0

        self.pre_question = None  # 上一次的问题信息
        self.curslot = None
        self.history_details = []  # 历史详情，用于酒店-航班的选择匹配
        # 历史意图
        self.historyIntentsInfo = []  # 历史意图信息
        self.historyIntentsTag = []  # 历史意图输出标签信息
        self.historyAction = []

        self.returnJson = {}
        self.existHistory = False
