#coding=utf-8
import requests
import json
from ChatbotMySQL import *
import pysolr


# 需要添加slot问题顺序、

class ChatbotEngines:
    lastResponseJson = {}
    complete = False
    answer = ""
    result_entities = []


    # 安全回答
    global_answer = "不好意思，您的回答不详细！"

    def __init__(self, sessionId, agentId):
        self.sessionId = sessionId
        self.agentId = agentId
        self.entities_question={}
        self.intents = []
        self.history_intents = []
        self.n = ChatbotMySQL('127.0.0.1', 'root', '123456', 3306)

        self.n.selectDb('chatbot')
        self.n.query("""select intent from tbl_intent""")
        r = self.n.fetchAll()

        for result in r:
            self.intents.append(result['intent'])

    def request(self, question):
        r = requests.get('http://localhost:5000/parse?q=' + question)  # ,params=payload)
        data = json.loads(r.text)

        return json.dumps(self.action(data, question))

    def getSlotQuestions(self,intent):
        self.n.query('select slot,slot_question from tbl_slot where intent_id in (select id from tbl_intent where intent =\''+intent+'\')')
        r = self.n.fetchAll()

        for result in r:
           self.entities_question[result['slot']] = result['slot_question']

        print(self.entities_question)

    def action(self, data, query):
        global lastResponseJson, actionJson, responseJson, history_intents
        # 获取实体列表
        entities = data['entities']

        if data['intent']['confidence'] > 0.4 and data['intent']['name'] in self.intents:
            print('意图识别成功！')
            status = {"code": 200, "error_type": "意图识别成功"}
        else:
            print('意图识别失败')
            status = {"code": 500, "error_type": "意图识别失败"}
            answer = ChatbotEngines.global_answer
            if lastResponseJson['status']['code'] == 200:
                lastResponseJson['status'] = status
                lastResponseJson['answer'] = answer + lastResponseJson['answer']

            print("last response is :", responseJson)
            return lastResponseJson

        if len(self.entities_question) == 0 :
            self.getSlotQuestions(data['intent']['name'])

        if status['code'] == 200:
            if len(entities) == 0:
                answer = self.entities_question.items[-1]
            else:
                if len(self.entities_question) == len(entities):
                    complete = True
                    answer = "action complete"
                else:
                    for (k, v) in self.entities_question.items():
                        isMatch = False
                        for entity in entities:
                            if entity['entity'] == k:
                                isMatch = True
                                self.result_entities.append(entity)
                                break

                        if isMatch == False:
                            for r_entities in self.result_entities:
                                if r_entities['entity'] == k:
                                    isMatch = True
                                    break

                            if isMatch == False:
                                answer = self.entities_question[k]
                                complete = False

                    if len(self.result_entities) == len(self.entities_question):
                        complete = True
                        answer = "action complete"

            parametersJson = []
            for r_entity in self.result_entities:
                parametersJson.append({"entity": r_entity['entity'], "value": r_entity['value']})

            actionJson = {"name": "", "complete": complete, "parameters": parametersJson}

        # 如果complete=True，则调用solr查询具体信息，填充answer属性
        if complete == True:
            question = ''
            # 组装问题
            slots = actionJson['parameters']
            for slot in slots:
                question += slot['value']

            answer = self.querySolr(query)
        # 检查是否有数据权限

        responseJson = {
            "sessionId": self.sessionId,
            "query": query,
            "intentId": "",
            "intentName": data['intent']['name'],
            "confidence": data['intent']['confidence'],
            "action": actionJson,
            "answer": answer,
            "status": status
        }

        #保存历史意图，用于做多意图关联
        if complete == True:
            self.history_intents.append(responseJson)

        print("response is :", responseJson)
        lastResponseJson = responseJson
        return responseJson

    def querySolr(self,question):
        question = None
        s = pysolr.Solr('http://ai-test.vigortech.cn:8983/solr/chat_bot')
        response = s.search(question)

        print(len(response))
        if len(response) == 0:
            return None

        # Print the name of each document.
        answer = response.docs[0]
        return answer



