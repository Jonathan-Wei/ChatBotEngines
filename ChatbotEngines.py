# coding=utf-8
import requests
import json
from ChatbotMySQL import *
import pysolr
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

answer = ""
complete = False
result_entities = {}
actionJson={}
lastResponseJson = {}
entities_question = {}


# noinspection PyGlobalUndefined
class ChatbotEngines:
    # 安全回答
    global_answer = "不好意思，您的回答不详细！"

    def __init__(self, app, token, agentId):
        self.token = token
        self.agentId = agentId
        self.intents = []
        self.history_intents = []
        self.solrUrl = app.config['SOLR_SERVER_URL']
        self.nluServer = app.config['NLU_SERVER']

        self.n = ChatbotMySQL(app.config['MODEL_DB_HOST'], app.config['MODEL_DB_USERNAME'],
                              app.config['MODEL_DB_PASSWORD'], app.config['MODEL_DB_PORT'])

        self.n.selectDb(app.config['MODEL_DB'])
        self.n.query("""select `name` from robot_scene""")
        r = self.n.fetchAll()

        for result in r:
            self.intents.append(result['name'])

    def request(self, question):
        if self.validate():
            r = requests.get(self.nluServer + question)
            data = json.loads(r.text)

            return json.dumps(self.action(data, question))
        else:
            print("用户未登陆，请登陆之后再做请求")

    def getSlotQuestions(self, intent):
        global entities_question
        self.n.query(
            'SELECT type_name as slot,message as slot_question from robot_scene_slot where int_id in (select id from robot_scene WHERE `name` =\'' + intent + '\')')
        r = self.n.fetchAll()

        for result in r:
            entities_question[result['slot']] = result['slot_question']

    #验证用户token
    def validate(self):
        self.n.query("select * from `sys_user_config` where `token`=\'"+self.token+"\'")
        r = self.n.fetchAll()

        if r is None:
            return False
        else:
            return True


    def action(self, data, query):
        global history_intents,answer,actionJson,lastResponseJson,existHistory,result_entities

        #查询用户匹配的意图信息
        self.n.query("select * from user_scene_info where user_token = \'"+self.token+"\' and complete = False")
        r = self.n.fetchRow()
        if r is not None:
            existHistory = True
            lastResponseJson = json.loads(r['last_response_json'])
            #history_intents = json.loads(r['history_intents'])
            result_entities = json.loads(r['entities'])
        else:
            existHistory = False

        # 获取实体列表
        entities = data['entities']

        if data['intent']['confidence'] > 0.4 and unicode(data['intent']['name']) in self.intents:
            print('意图识别成功！')
            status = {"code": 200, "error_type": "意图识别成功"}
        else:
            print('意图识别失败')
            print(data)
            status = {"code": 500, "error_type": "意图识别失败"}
            answer = ChatbotEngines.global_answer
            if len(lastResponseJson) > 0:
                if lastResponseJson['status']['code'] == 200:
                    lastResponseJson['status'] = status
                    lastResponseJson['answer'] = answer + lastResponseJson['answer']

                print("last response is :", lastResponseJson)
                return lastResponseJson

        if len(entities_question) == 0:
            self.getSlotQuestions(data['intent']['name'])


        complete = False
        if status['code'] == 200:
            #如果没有solt，则直接查询solr
            if len(entities_question) == 0:
                complete = True
            else:
                if len(entities) == 0:
                    answer = entities_question.items[-1]
                else:
                    if len(entities_question) == len(entities):
                        complete = True
                        answer = "action complete"
                    else:
                        for (k, v) in entities_question.items():
                            isMatch = False
                            for entity in entities:
                                if entity['entity'] == k:
                                    isMatch = True
                                    result_entities[k]=v
                                    break

                            if not isMatch:
                                for (k1,v1) in result_entities.items():
                                    if k1 == k:
                                        isMatch = True
                                        break

                                if isMatch:
                                    answer = entities_question[k]

                                    complete = False

                        if len(result_entities) == len(entities_question):
                            complete = True
                            answer = "action complete"

                parametersJson = []
                for (k2,v2) in result_entities.items():
                    parametersJson.append({"entity":k2, "value":v2})

                actionJson = {"name": "", "complete": complete, "parameters": parametersJson}

        #如果响应问题中包含参数，则替换;
        #例如确认问题：您申请了${date}去${address}的出差申请，是否确认提交？
        slots = actionJson['parameters']
        if "${" in answer:
            for slot in slots:
                answer = answer.replace('${' + slot['entity'] + "}", slot['value'])

        # 如果complete=True，则调用solr查询具体信息，填充answer属性
        if complete:
            if len(entities_question) != 0:
                self.n.query(
                    'select answer from robot_scene WHERE `name` =\'' + data['intent']['name'] + '\'')
                r = self.n.fetchRow()
                question = r['answer']
                # 通过配置的ai回复进行问题组装

                for slot in slots:
                    question = question.replace('${' + slot['entity'] + "}", slot['value'])

                answer = self.querySolr(question)
            else:
                answer = self.querySolr(query)

        # 检查是否有数据权限

        responseJson = {
            "sessionId": self.token,
            "query": query,
            "intentId": "",
            "intentName": data['intent']['name'],
            "confidence": data['intent']['confidence'],
            "action": actionJson,
            "answer": answer,
            "status": status
        }

        # 保存历史意图，用于做多意图关联
        if complete:
            result_entities = {}
            self.history_intents.append(responseJson)

        print("response is :", responseJson)
        lastResponseJson = responseJson

        # 保存result_entities、responseJson、history_intents
        sql = ''
        if existHistory:
            sql = "UPDATE user_scene_info set entities =\'"+json.dumps(result_entities)+"\',last_response_json = \'"+json.dumps(responseJson)+"\',complete = "+str(complete)+" WHERE user_token = \'"+self.token+"\'"
            print(sql)
            self.n.update(sql)
        else:
            sql = "INSERT INTO user_scene_info (user_token,entities,last_response_json,complete) VALUES(\'"+self.token+"\',\'"+json.dumps(result_entities)+"\',\'"+json.dumps(responseJson)+"\',"+str(complete)+")"
            print(sql)
            self.n.insert(sql)

        return responseJson

    def querySolr(self, question):
        s = pysolr.Solr(self.solrUrl,timeout=10)
        response = s.search(question)

        print(len(response))
        if len(response) == 0:
            return None

        # Print the name of each document.
        answer = response.docs[0]
        return answer
