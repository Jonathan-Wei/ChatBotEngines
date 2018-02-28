#-*- coding=utf-8 -*-
from ChatbotMySQL import *
from ChatbotMicroservices import *
from ChatbotUtils import *
from ChatbotHistoryInfo import *
from ChatbotResponse import *
from collections import OrderedDict
from flask import g
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

# noinspection PyGlobalUndefined

class UsersInfo:
    def __init__(self):
        self.users = {}

    def setUser(self, token, user_info):
        self.users[token] = user_info

    def getUser(self, token):
        return self.users.get(token)


class ChatbotEngines:

    # 安全回答
    global_answer = "不好意思，您的回答不详细！"

    def __init__(self, app, token, agentId):
        self.token = token
        self.agentId = agentId
        self.intents = []
        self.solrUrl = app.config['SOLR_SERVER_URL']
        self.nluServer = app.config['NLU_SERVER']

        self.username = ''

        self.response = ChatbotResponse()

        self.n = ChatbotMySQL(app.config['MODEL_DB_HOST'], app.config['MODEL_DB_USERNAME'],
                              app.config['MODEL_DB_PASSWORD'], app.config['MODEL_DB_PORT'])

        self.microservice = ChatbotMicroservices()
        self.utils=ChatbotUtils()

        self.n.selectDb(app.config['MODEL_DB'])
        self.n.query("""select `name` from robot_scene""")
        r = self.n.fetchAll()

        for result in r:
            self.intents.append(result['name'])

    def request(self, question):
        if not g._users.getUser(self.token):
            self.response = ChatbotResponse()
            g._users.setUser(self.token, self.response)
        else:
            self.response = g._users.getUser(self.token)

        if self.validate():
            r = requests.get(self.nluServer + question)
            data = json.loads(r.text)

            return json.dumps(self.preAction(data, question))
        else:
            print("用户未登陆，请登陆之后再做请求")

    def getSlotQuestions(self, intent):
        sql = 'SELECT type_name as slot,dict_name as slot_type,message as slot_question from robot_scene_slot where int_id in (select id from robot_scene WHERE `name` =\'' + intent + '\') order by id'
        self.n.query(sql)
        r = self.n.fetchAll()

        for result in r:
            self.response.entities_question[result['slot']] = result['slot_question']
            self.response.entities_types[result['slot']] = result['slot_type'].decode(sys.getdefaultencoding())

    #验证用户token
    def validate(self):
        self.n.query("select * from `sys_user_config` where `token`=\'"+self.token+"\'")
        r = self.n.fetchRow()

        if r is None:
            return False
        else:
            self.username = r['name']
            return True

    def preAction(self,data,query):
        contentData = []

        # 是否存在历史意图
        if self.response.currentQuestionType != 2:
            self.n.query(
                "select * from history_scene_info where user_token = \'" + self.token + "\' and complete = False")
            r = self.n.fetchRow()
            if r is not None:
                self.response.existHistory = True
                if len(self.response.lastResponseJson) == 0:
                    self.response.lastResponseJson = json.loads(r['last_response_json'],encoding="utf8")
                    self.historyIntentsInfo = json.loads(r['history_intents'],encoding="utf8")
                    self.response.result_entities = json.loads(r['entities'],encoding="utf8")
            else:
                self.response.existHistory = False
        else:
            self.response.existHistory = True

        # 判断是否ruleContent 是否空
            #不为空  判断是否已经匹配参数及调用历史意图信息，进行询问
        if len(self.response.ruleContent)>0 or not self.response.ruleComplete:
            if self.response.currentQuestionType == 4:
                # 处理流程询问信息。
                # 获取所有的slot信息，进行问答匹配
                params = self.getHistorySlots()
                # 获取规则id，匹配获取对应的询问信息，以及动作
                ruleInfo = self.getIntentFlowInfo()
                ask = ruleInfo['ask']
                # if ask is not None and "${" in ask:
                #     for (k, v) in params.items():
                #         ask = ask.replace('${' + k + "}", v)
                ask = self.variableReplace(ask,params)

                ruleMatch = self.ruleMatch(ask, query)
                if ruleMatch == '确定':
                    action = ruleInfo['action']
                    # 通过动作名称匹配微服务
                    content = self.microservice.route(self.username, action, params)
                    contentData.append(content)

                    contentData.append(self.executeAction())
                    self.response.returnJson = {'status': self.response.responseJson['status'], 'data': contentData}
                    # 确认则执行后置动作

                self.resetHistoryIntent()
            else:
                if self.response.lastResponseJson['action']['complete']:
                    for (k,v) in self.response.ruleContent.items():
                        if k == self.response.lastResponseJson['intentName']:
                            self.response.ruleContent[k] = True

                for (k,v) in self.response.ruleContent.items():
                    if v is False:
                        current_intent = k
                        self.response.ruleComplete = False
                        break
                if not self.response.ruleComplete:
                    if not self.response.lastResponseJson['action']['complete']:
                        #intentAction(self,data,intent,entities,confidence,query,currentQuestionType):
                        ruleMatch = self.ruleMatch(self.response.lastResponseJson['slotType'],query)
                        if ruleMatch is None:
                            #意图判断为空，则重新匹配切换意图
                            if self.matchHistoryDetails(query,self.response.lastResponseJson['slot']):
                                if self.response.entities is not None:
                                    self.response.entities.append({'entity': self.response.lastResponseJson['slot'], 'value': query})
                            else:
                                r = requests.get(self.nluServer + query)
                                data = json.loads(r.text)
                                self.response.entities = data['entities']
                                confidence = data['intent']['confidence']
                                self.response.currentQuestionType = 0
                        else:
                            if ruleMatch in self.response.lastResponseJson['slotType']:# 规则匹配成功，直接填充entities传到intentAction中
                                if self.response.entities is not None:
                                    self.response.entities.append({'entity':self.response.lastResponseJson['slot'],'value':query})

                        self.response.responseJson = self.intentAction(contentData, current_intent, self.response.entities, None, query,self.response.currentQuestionType)
                        if self.response.responseJson['action']['complete'] and self.response.ruleContent.has_key(self.response.responseJson['intentName']):
                            self.response.ruleContent[self.response.responseJson['intentName']] = True

                        self.response.returnJson = {'status': self.response.responseJson['status'], 'data': contentData}

                        isAllTrue = True
                        for (k, v) in self.response.ruleContent.items():
                            if v is False:
                                isAllTrue = False
                                break

                        if isAllTrue:
                            # 获取所有的slot信息，进行问答匹配
                            params = self.getHistorySlots()

                            # 获取规则id，匹配获取对应的询问信息，以及动作
                            ruleInfo = self.getIntentFlowInfo()

                            # 设置询问类型为规则询问
                            self.response.currentQuestionType = 4
                            # 获取询问问题
                            ask = ruleInfo['ask']
                            # if ask is not None and "${" in ask:
                            #     for (k,v) in params.items():
                            #         ask = ask.replace('${' + k + "}", v)
                            ask = self.variableReplace(ask, params)

                            contentData.append({"type":0,"message":ask})
                            # 返回询问信息json
                            self.response.returnJson = {'status': self.response.responseJson['status'], 'data': contentData}
        else:
            if len(self.response.lastResponseJson)>0 and self.response.lastResponseJson['currentQuestionType'] == 3:
                self.response.currentQuestionType =3
            #保存当前问题类型
            if self.response.currentQuestionType == 1:
                # 获取历史input
                ruleMatch = self.ruleMatch(self.response.pre_question, query)
                # 获取否定触发的动作，触发酒店/机票查询
                self.n.query(
                    "select scene.id,scene.`name`,mark.y_hint,mark.y_action,mark.in_hint,mark.in_action from robot_scene as scene,robot_scene_mark as mark where scene.`name` = \'" + self.response.lastIntent + "\' and mark.id = scene.input")
                r = self.n.fetchRow()
                if ruleMatch == '确定':
                    nextIntent = r['y_action']
                    # 获取对应的规则
                    self.response.ruleContent = self.getIntentFlow(nextIntent)

                    self.response.currentQuestionType = 0
                    self.response.responseJson = self.intentAction(contentData, nextIntent,self.response.lastEntities,None,query,self.response.currentQuestionType)
                elif ruleMatch == '否定':
                    contentData.append({"type": 0, "message": r['in_hint']})
                    nextIntent = r['in_action']
                    self.response.responseJson = self.intentAction(contentData, nextIntent,
                                                     None, None, query,
                                                     self.response.currentQuestionType)
                # 后置意图匹配后，检查后置的complete是否为true，不为true则更新currenQuestionType = 2
                if self.response.responseJson['action']['complete']:
                    self.response.entities = []
                    self.response.currentQuestionType = 0  # 初始意图识别状态。
                else:
                    self.response.currentQuestionType = 2
                self.response.returnJson = {'status': self.response.responseJson['status'], 'data': contentData}
            elif self.response.currentQuestionType == 3:
                self.response.pre_question = self.response.lastResponseJson['pre_question']
                # 获取历史input
                ruleMatch = self.ruleMatch(self.response.pre_question, query)
                if ruleMatch == '确定':
                    # 获取对应的规则
                    self.response.ruleContent = self.getIntentFlow(self.response.lastResponseJson['lastIntent'])
                    if self.response.ruleContent.has_key(self.response.lastResponseJson['intentName']):
                        self.response.ruleContent[self.response.lastResponseJson['intentName']] = True

                    self.response.currentQuestionType = 0
                    self.response.responseJson = self.intentAction(contentData, self.response.lastResponseJson['lastIntent'], self.response.lastResponseJson['action']['parameters'], None, query,
                                                                   self.response.currentQuestionType)

                    # 后置意图匹配后，检查后置的complete是否为true，不为true则更新currenQuestionType = 2
                    if self.response.responseJson['action']['complete']:
                        self.response.entities = []
                        self.response.currentQuestionType = 0  # 初始意图识别状态。
                    else:
                        self.response.currentQuestionType = 2

                    self.response.returnJson = {'status': self.response.responseJson['status'], 'data': contentData}
                elif ruleMatch == '否定':
                    self.response.currentQuestionType = 0
                    self.response.returnJson = {'status': self.response.responseJson['status'], 'data': [{"type": 0, "message": "好的"}]}
                    # 清空历史缓存
                    self.resetHistoryIntent()
            else:
                confidence = None
                # 查询前置意图
                intent = data['intent']['name']
                if self.response.currentQuestionType == 0:
                    # 当后置意图为空，检查前置意图
                    self.n.query("select mark.`name` as `input`,mark.ask as question,scene.`name` as intent from robot_scene_mark as mark,robot_scene as scene where mark.id = (select `input` from robot_scene where `name` = \'"+intent+"\') and mark.int_id = scene.id")
                    r = self.n.fetchRow()
                    input = None
                    if r is not None:
                        input = r['input']
                        self.response.pre_question = r['question']

                    if input is not None:
                        self.response.currentQuestionType = 1
                        content = {"type": 0, "message": self.response.pre_question}
                        self.response.status = {"code": 200, "msg": "触发前置意图"}
                        self.response.lastEntities = data['entities']
                        self.response.lastIntent = data['intent']['name']
                        #输入不为空触发直接返回输入验证问题
                        self.response.returnJson = {'status': self.response.status, 'data': [content]}
                        # 存储responsejson
                        return self.response.returnJson

                if self.response.currentQuestionType == 2: #状态未2时，表示填充solt状态
                    intent=self.response.lastResponseJson['intentName']
                    ruleMatch = self.matchType(query)
                    #ruleMatch = self.ruleMatch(self.response.lastResponseJson['slotType'],query)
                    if ruleMatch is None:#意图判断为空，则重新匹配切换意图
                        if self.matchHistoryDetails(query,self.response.lastResponseJson['slot']):
                            if self.response.entities is not None:
                                self.response.entities.append({'entity': self.response.lastResponseJson['slot'], 'value': query})
                        else:
                            r = requests.get(self.nluServer + query)
                            data = json.loads(r.text)
                            self.response.entities = data['entities']
                            confidence = data['intent']['confidence']
                            self.response.currentQuestionType = 0
                    elif ruleMatch in self.response.lastResponseJson['slotType']:# 规则匹配成功，直接填充entities传到intentAction中
                        if self.response.entities is not None:
                            self.response.entities.append({'entity':self.response.lastResponseJson['slot'],'value':query})
                    else:
                        # 匹配其他的slot信息
                        slot = ''
                        for (k, v) in self.response.entities_types.items():
                            if ruleMatch in v:
                                slot = k
                                break

                        if self.response.entities is not None and len(slot) > 0:
                            self.response.entities.append({'entity':slot,'value':self.response.entities_question[slot]})

                else:
                    self.response.entities = data['entities']
                    confidence = data['intent']['confidence']

                #无前置意图直接走正常流程
                self.response.responseJson = self.intentAction(contentData,intent,self.response.entities,confidence,query,self.response.currentQuestionType)
                if self.response.responseJson['currentQuestionType'] != 3:
                    if self.response.responseJson['action']['complete']:
                        self.response.entities = []
                        self.response.currentQuestionType = 0 # 初始意图识别状态。
                    else:
                        self.response.currentQuestionType = 2

                # 构建接口服务与app端对接
                self.response.returnJson = {'status': self.response.responseJson['status'], 'data': contentData}
        self.response.lastResponseJson = self.response.responseJson

        # 获取历史的details，用于酒店名称匹配以及机票名称匹配
        for content in contentData:
            if content.has_key('content') and content['content'].has_key('details'):
                self.response.history_details.append(content['content']['details'])

        g._users.setUser(self.token, self.response)
        return self.response.returnJson

    # 意图处理
    def intentAction(self,data,intent,entities,confidence,query,currentQuestionType):
        #历史意图是否一致
        if unicode(intent) in self.intents:
            if confidence is not None:
                if confidence > 0:
                    print('意图识别成功！')
                    self.response.status = {"code": 200, "msg": "意图识别成功"}
                else :
                    print('意图识别失败')
                    self.response.status = {"code": 500, "msg": "意图识别失败"}
                    self.response.answer = ChatbotEngines.global_answer
                    if len(self.response.lastResponseJson) > 0:
                        if self.response.lastResponseJson['status']['code'] == 200:
                            self.response.lastResponseJson['status'] = self.response.status
                            self.response.lastResponseJson['answer'] = self.response.answer + self.response.lastResponseJson['answer']

                        print("last response is :", self.response.lastResponseJson)
                        return self.response.lastResponseJson

        # 当意图被切换时，更新需要询问的solt,需要保存历史的意图信息。
        if self.response.currentQuestionType!=2:
            if len(self.response.entities_question) == 0 or len(self.response.lastResponseJson) >0 and self.response.lastResponseJson['intentName'] != intent:
                 # 保存历史意图信息。
                self.response.result_entities = {}
                self.response.entities_question = {}
                self.response.entities_types ={}
                self.getSlotQuestions(intent)
                if len(self.response.lastResponseJson) > 0:
                    self.response.entities = []
                    self.response.result_entities = self.matchSlot(self.response.lastResponseJson,self.response.entities_types);
                    for (k,v) in self.response.result_entities.items():
                        self.response.entities.append({"entity":k,"value":v})

        self.response.complete = False

        if self.response.status['code'] == 200:
            # 如果没有solt，则直接查询solr
            # 当当前问题类型是0且无slot问题时complete为True
            if self.response.currentQuestionType == 0 and len(self.response.entities_question) == 0:
                self.response.complete = True
            else:
                if self.response.entities is None or len(self.response.entities) == 0 :
                    self.response.curslot = self.response.entities_question.items()[0][0]
                    self.response.answer = self.response.entities_question.items()[0][1]
                else:
                    for (k, v) in self.response.entities_question.items():
                        isMatch = False
                        # slot与entities的匹配
                        for entity in self.response.entities:
                            if entity['entity'] == k:
                                isMatch = True
                                self.response.result_entities[k] = entity['value']
                                break

                        if not isMatch:
                            # slot与已识别的slot的匹配
                            for (k1, v1) in self.response.result_entities.items():
                                if k1 == k:
                                    isMatch = True
                                    break

                        # 未匹配，则获取未匹配的slot进行询问
                        if not isMatch:
                            self.response.answer = self.response.entities_question[k]
                            self.response.curslot = k
                            self.response.complete = False
                            break

                    if len(self.response.result_entities) == len(self.response.entities_question):
                        self.response.complete = True

                parametersJson = []
                if self.response.result_entities is not None:
                    for (k2, v2) in self.response.result_entities.items():
                        parametersJson.append({"entity": k2, "value": v2.decode(sys.getdefaultencoding())})

                self.response.actionJson = {"name": "", "complete": self.response.complete, "parameters": parametersJson}

        # 如果响应问题中包含参数，则替换;
        # 例如确认问题：您申请了${date}去${address}的出差申请，是否确认提交？
        if len(self.response.actionJson) > 0:
            slots = self.response.actionJson['parameters']
            if self.response.answer is not None and "${" in self.response.answer:
                for slot in slots:
                    self.response.answer = self.response.answer.replace('${' + slot['entity'] + "}", slot['value'])

        # 如果complete=True，则调用solr查询具体信息，填充answer属性
        content = {}
        tag = None
        if self.response.complete:

            # 检查是否有action需要执行，
            self.n.query("select act_name,`output`,flag from robot_scene where `name`  = \'" + intent + "\'")
            r = self.n.fetchRow()
            if r is not None:
                actionName = r['act_name']
                tag = r['output']
                flag = r['flag']
                if actionName is not None and len(actionName) > 0:
                    if flag == 1:
                        self.response.historyAction.append({
                            "action":actionName,
                            "params":self.utils.listToMap(slots)
                        })
                    else:
                        #这里需要做微服务适配
                        content = self.microservice.route(self.username,intent, self.utils.listToMap(slots))
        else:
            content = {"type": 0, "message": self.response.answer}

        if len(content) > 0:
            data.append(content)

        if self.response.complete:
            self.response.responseJson = {
                "sessionId": self.token,
                "query": query,
                "intentId": "",
                "intentName": intent,
                "confidence": confidence,
                "action": self.response.actionJson,
                "currentQuestionType": self.response.currentQuestionType,
                "lastEntitiesType": self.response.entities_types,
                "answer": self.response.answer,
                "status": self.response.status
            }
        else:
            self.response.responseJson = {
                "sessionId": self.token,
                "query": query,
                "intentId": "",
                "intentName": intent,
                "confidence": confidence,
                "action": self.response.actionJson,
                "slot": self.response.curslot,  # 保存历史的slot以及slotType用于模式匹配。
                "slotType": self.response.entities_types[self.response.curslot],
                "currentQuestionType": self.response.currentQuestionType,
                "lastEntitiesType": self.response.entities_types,
                "answer": self.response.answer,
                "status": self.response.status
            }

        # 保存result_entities、responseJson、history_intents
        self.updateUserSceneInfo(intent,self.response.existHistory, self.response.result_entities, self.response.responseJson, self.response.complete)
        self.response.lastResponseJson = self.response.responseJson
        if self.response.complete:
            # 添加历史意图
            self.response.historyIntentsInfo.append({
                "intent":intent,
                "tag":tag,
                "responseJson":self.response.responseJson
            })

            if tag is not None :
                tags = tag.split(",")
                for item in tags:
                    self.response.historyIntentsTag.append(int(item))

            self.response.currentQuestionType = 0
            #后置检查
            if not self.afterCheck(data,intent,self.response.currentQuestionType,self.response.responseJson):
                # 查询关联规则
                result = self.ruleAction(data, intent, self.response.result_entities, self.response.currentQuestionType)
                if result is not None:
                    self.response.responseJson = result
            else:
                self.response.responseJson['currentQuestionType'] = 3
            #
            self.response.lastResponseJson = self.response.responseJson
            self.updateUserSceneInfo(intent, self.response.existHistory, self.response.result_entities,
                                     self.response.responseJson, self.response.complete)

        print("response is :", self.response.responseJson)


        return self.response.responseJson

    #流程信息
    def ruleAction(self,data,intent,result_entities,currentQuestionType):
        global result
        if len(self.response.ruleContent) == 0 :
            self.response.ruleContent = self.getIntentFlow(intent)

        if len(self.response.ruleContent) > 0:
            self.response.ruleComplete = True
            if self.response.ruleContent.has_key(unicode(intent)):
                self.response.ruleContent[unicode(intent)] = True


            #获取下一个意图
            current_intent = ''
            for (k,v) in self.response.ruleContent.items():
                if not v:
                    current_intent = k
                    self.response.ruleComplete = False
                    break
            # result_entites 转换成entities
            if not self.response.ruleComplete:
                self.response.currentQuestionType = 0

                result = self.intentAction(data, current_intent, None, None, None, self.response.currentQuestionType)
                if result['action']['complete'] and self.response.ruleContent.has_key(result['intentName']):
                    self.response.ruleContent[result['intentName']] = True

            return result
        return None

    #后置检查，
    def afterCheck(self,data,intent,currentQuestionType,responseJson):
        self.n.query(
            "select mark.`id` as `check`,mark.ask as question,scene.`name` as intent from robot_scene_mark as mark,robot_scene as scene where mark.id =(select `check` from robot_scene WHERE `name` = \'" + intent + "\') and mark.int_id = scene.id")
        r = self.n.fetchRow()
        check = None
        if r is not None:
            check = r['check']
            self.response.pre_question = r['question']
            self.response.responseJson['pre_question'] = self.response.pre_question
            self.response.responseJson['lastIntent'] = r['intent']
        else:
            return False

        if check is not None:
            if check not in self.response.historyIntentsTag:
                self.response.currentQuestionType = 3
                content = {"type": 0, "message": self.response.pre_question}
                self.response.status = {"code": 200, "msg": "触发后置意图"}
                data.append(content)
                return True
            else:
                return False

            #插入/更新意图信息
    ## 参数 existHistory、 result_entities、responseJson、history_intents
    def updateUserSceneInfo(self,intent,existHistory,result_entities,responseJson,complete):
        if existHistory:
            sql = "UPDATE history_scene_info set entities =\'"+json.dumps(result_entities,ensure_ascii=False).encode("utf8")+"\',last_response_json = \'"+json.dumps(responseJson,ensure_ascii=False).encode("utf8")+"\',history_intents = \'"+json.dumps(self.response.historyIntentsInfo,ensure_ascii=False).encode("utf8")+"\',complete = "+str(complete)+" WHERE user_token = \'"+self.token+"\' and intent = \'"+intent+"\'"
            print(sql)
            self.n.update(sql)
        else:
            sql = "INSERT INTO history_scene_info (user_token,entities,intent,last_response_json,history_intents,complete) VALUES(\'"+self.token+"\',\'"+json.dumps(result_entities,ensure_ascii=False).encode("utf8")+"\',\'"+intent+"\',\'"+json.dumps(responseJson,ensure_ascii=False).encode("utf8")+"\',\'"+json.dumps(self.response.historyIntentsInfo,ensure_ascii=False).encode("utf8")+"\',"+str(complete)+")"
            print(sql)
            self.n.insert(sql)

    # slot 填充
    def matchSlot(self,lastResponseJson,entities_types):
        result = {}
        lastEntitiesType = self.response.lastResponseJson['lastEntitiesType']
        for slot in self.response.lastResponseJson['action']['parameters']:
            slotType = lastEntitiesType[slot['entity']]
            for (k,v) in self.response.entities_types.items():
                if slotType == v:
                    result[k] = slot['value']
                    break

        return result

    #获取历史的所有slotType:slotValue
    def getHistorySlotsByType(self):
        slots = {}
        intents = self.historyIntent.getHistoryIntents()
        for intent in intents:
            self.response.entities = intent['responseJson']['action']['parameters']
            self.response.entities_type = intent['responseJson']['lastEntitiesType']

            for entity in self.response.entities:
                for (k,v) in self.response.entities_types.items():
                    if k == entity['entity']:
                        slots[self.response.entities_types[k]] = entity['value']
                        break

        return slots

    def getHistorySlots(self):
        params = {}
        intents = self.response.historyIntentsInfo
        for intent in intents:
            entities = intent['responseJson']['action']['parameters']
            for entity in entities:
                params[entity['entity']] = entity['value']

        return params




    # 规则匹配
    def ruleMatch(self, type, query):
        ruleMatchType = None
        if '城市' in type:
            if self.utils.matchCity(query):
                ruleMatchType = '城市'

        elif '区域' in type:
            if self.utils.matchAreaByCity(None, query):
                ruleMatchType = '区域'
        elif '时间' in type:
            if self.utils.toGetDate(query) is not None:
                ruleMatchType = '时间'
        elif '是否' in type or '是不是' in type:
            if self.utils.matchComfirm(query):
                ruleMatchType = '确定'
            else:
                ruleMatchType = '否定'

        return ruleMatchType

    def matchType(self,query):
        if self.utils.matchCity(query):
            return "城市"
        elif self.utils.matchAreaByCity(None, query):
            return "区域"
        elif self.utils.toGetDate(query) is not None:
            return "时间"
        else:
            if self.utils.matchComfirm(query):
                return "确定"
            else:
                return "否定"

    # 获取流程询问以及对应的操作
    def getIntentFlowInfo(self):
        return {"ask":"是否提交${date}去${address}的出差申请？","action":"出差申请"}

    # 获取意图流程
    def getIntentFlow(self,intent):
        intentFlow = OrderedDict()
        intentFlow[unicode('出差申请')] = False
        intentFlow[unicode('酒店查询')] = False
        intentFlow[unicode('订购酒店')] = False
        intentFlow[unicode('航班查询')] = False
        intentFlow[unicode('订购机票')] = False
        if intentFlow.has_key(unicode(intent)):
            return intentFlow

    # 检查意图是否存在流程中，且是否为已完成意图
    def checkIntentInFlow(self,intent):
        if self.response.ruleContent.has_key(intent) and self.response.ruleContent[intent] == True:
            return True
        else:
            return False

    # 匹配历史详情，查询是否存在对应的酒店/机票信息
    def matchHistoryDetails(self,query,slot):
        if len(self.response.history_details) > 0 :
            for details in self.response.history_details:
                for detail in details:
                    for (k,v) in detail.items():
                        if k == slot and (query.upper() in v):
                            return True
                            break
        else:
            return False

    def resetHistoryIntent(self):
        self.response.answer = ""
        self.response.complete = False
        self.response.result_entities = {}
        self.response.actionJson = {}
        self.response.lastResponseJson = {}
        self.response.entities_question = OrderedDict()
        self.response.entities_types = {}
        self.response.ruleContent = OrderedDict()
        self.response.ruleComplete = True
        self.response.lastEntities = {}
        self.response.entities = []
        self.response.status = {}
        self.response.responseJson = {}
        self.response.currentQuestionType = 0

        self.response.pre_question = None
        self.response.curslot = None
        self.response.history_details = []
        # 历史意图
        self.response.historyIntentsInfo = []
        self.response.historyIntentsTag = []

        self.returnJson = {}
        self.existHistory = False

    # 删除缓存
    def delete(self):
        self.response = ChatbotResponse()
        g._users.setUser(self.token, self.response)

        self.n.deleteCache("delete from history_scene_info where user_token ='%s' " % self.token)

    # 执行动作
    def executeAction(self):
        if self.response.historyAction is None and len(self.response.historyAction) == 0:
            return None

        content = ''
        for action in self.response.historyAction:
            responseContent = self.microservice.route(self.username,action['action'],action['params'])
            if responseContent is not None and responseContent.has_key('message'):
                content = content + responseContent['message']+"。"

        return {"type": 0, "message": content}

    # 参数替换
    def variableReplace(self,ask,params):
        if ask is not None and "${" in ask:
            for (k, v) in params.items():
                ask = ask.replace('${' + k + "}", v)

        return ask


