#-*- coding=utf-8 -*-

class ChatbotHistoryInfo:

    def __init__(self,historyIntentsInfo = {},historyIntentsTag = [],historyDetails = [],historyActions = {}):
        self.historyIntentsInfo = historyIntentsInfo
        self.historyIntentsTag = historyIntentsTag
        self.historyDetails = historyDetails
        self.historyActions = historyActions

    def getHistoryIntents(self):
        return self.historyIntentsInfo

    #获取历史意图标记
    def getHistoryIntentTag(self):
        # 返回历史意图标记数组
        return self.historyIntentsTag

    def getHistoryIntent(self):
        return self.historyIntentsInfo

    def setHistoryIntent(self,historyIntents):
        self.historyIntentsTag = historyIntents


    def addHistoryIntent(self,intent,tag,responseJson):
        item = {
            "intent":intent,
            "tag":tag,
            "responseJson":responseJson
        }
        # 添加历史意图
        self.historyIntentsInfo[intent] = item

        # 更新历史意图标记
        if tag is not None:
            tags = tag.split(",")
            for item in tags:
                self.historyIntentsTag.append(int(item))


    #查询是否匹配存在下级意图
    def matchHistoryIntent(self,tag):
        if tag in self.historyIntentsTag:
            return True
        else:
            return False

    def getHistorySlots(self):
        params = {}
        for (k,intent) in self.historyIntentsInfo.items():
            entities = intent['responseJson']['action']['parameters']
            for entity in entities:
                params[entity['entity']] = entity['value']

        return params

    # 匹配历史详情，查询是否存在对应的酒店/机票信息
    def matchHistoryDetails(self, query, slot):
        if len(self.historyDetails) > 0:
            for details in self.historyDetails:
                if details is None:
                    continue

                for detail in details:
                    for (k, v) in detail.items():
                        if k == slot and (query.upper() in v):
                            return True
                            break
        else:
            return False