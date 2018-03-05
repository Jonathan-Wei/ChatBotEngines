#-*- coding=utf-8 -*-
from ChatbotMySQL import *
from ChatbotMicroservices import *
from ChatbotUtils import *
from ChatbotResponse import *
from collections import OrderedDict
from flask import g
import sys
reload(sys)
import logging
sys.setdefaultencoding('utf-8')

logger = logging.getLogger(__name__)

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
        self.response.contentData = []

        # 是否存在历史意图
        self.checkExistHistoryIntent()

        # 判断是否ruleContent 是否空
            #不为空  判断是否已经匹配参数及调用历史意图信息，进行询问
        # if len(self.response.intentFlowInfo.intentFlowContent)>0 or not self.response.intentFlowInfo.intentFlowComplete:
        if len(self.response.intentFlowInfo.intentFlowContent) > 0:# and not self.response.intentFlowInfo.intentFlowComplete:
            if self.response.currentQuestionType == self.response.RULE_ASK_TYPE and self.response.intentFlowInfo.intentFlowComplete:
                self.ruleInspection(query)
            else:
                self.ruleCompleteCheck(query)
        else:
            #保存当前问题类型
            if self.response.currentQuestionType == self.response.PRE_ASK_TYPE:
                self.preInspection(query)
            elif self.response.currentQuestionType == self.response.POST_ASK_TYPE:
                self.postInspection(query)
            else:
                confidence = None
                # 查询前置意图
                intent = data['intent']['name']
                if self.response.currentQuestionType == self.response.INIT_TYPE:
                    # 当后置意图为空，检查前置意图
                    self.n.query("select mark.`name` as `input`,mark.ask as question,scene.`name` as intent from robot_scene_mark as mark,robot_scene as scene where mark.id = (select `input` from robot_scene where `name` = \'"+intent+"\') and mark.int_id = scene.id")
                    r = self.n.fetchRow()
                    input = None
                    if r is not None:
                        input = r['input']
                        self.response.pre_question = r['question']

                    if input is not None:
                        self.response.currentQuestionType = self.response.PRE_ASK_TYPE
                        content = {"type": 0, "message": self.response.pre_question}
                        self.response.status = {"code": 200, "msg": "触发前置意图"}
                        self.response.lastEntities = data['entities']
                        self.response.lastIntent = data['intent']['name']
                        #输入不为空触发直接返回输入验证问题
                        self.response.returnJson = {'status': self.response.status, 'data': [content]}
                        # 存储responsejson
                        return self.response.returnJson

                if self.response.currentQuestionType == self.response.SLOT_ASK_TYPE: #状态未2时，表示填充solt状态
                    intent = self.response.lastResponseJson['intentName']
                    self.slotStuff(query)
                else:
                    self.response.entities = data['entities']
                    confidence = data['intent']['confidence']

                #无前置意图直接走正常流程
                self.response.responseJson = self.intentAction(intent,confidence,query)
                if self.response.responseJson['currentQuestionType'] != self.response.POST_ASK_TYPE:
                    if self.response.responseJson['action']['complete']:
                        self.response.entities = []
                        self.response.currentQuestionType = self.response.INIT_TYPE # 初始意图识别状态。
                    else:
                        self.response.currentQuestionType = self.response.SLOT_ASK_TYPE

                # 构建接口服务与app端对接
                self.response.returnJson = {'status': self.response.responseJson['status'], 'data': self.response.contentData}
        self.response.lastResponseJson = self.response.responseJson

        # 获取历史的details，用于酒店名称匹配以及机票名称匹配
        for content in self.response.contentData:
            if content.has_key('content') and content['content'].has_key('details') and content['content']['details'] is not None:
                self.response.historyInfo.historyDetails.append(content['content']['details'])

        g._users.setUser(self.token, self.response)
        return self.response.returnJson

    # 意图处理
    def intentAction(self,intent,confidence,query):

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
        # 历史意图是否一致
        # 当意图被切换时，更新需要询问的solt,需要保存历史的意图信息。
        if self.response.currentQuestionType!=self.response.SLOT_ASK_TYPE:
            if len(self.response.entities_question) == 0 or len(self.response.lastResponseJson) >0 and self.response.lastResponseJson['intentName'] != intent:
                # 保存历史意图信息。
                self.response.result_entities = {}
                self.response.entities_question = {}
                self.response.entities_types ={}
                self.getSlotQuestions(intent)
                if len(self.response.lastResponseJson) > 0:
                    self.response.entities = []
                    self.response.result_entities = self.matchSlot();
                    for (k,v) in self.response.result_entities.items():
                        self.response.entities.append({"entity":k,"value":v})

        self.response.complete = False

        if self.response.status['code'] == 200:
            # slot信息收集
            self.collectSlotInfo()
        # 如果响应问题中包含参数，则替换;
        # 例如确认问题：您申请了${date}去${address}的出差申请，是否确认提交？
        if len(self.response.actionJson) > 0:
            slots = self.response.actionJson['parameters']
            if self.response.answer is not None and "${" in self.response.answer:
                for slot in slots:
                    self.response.answer = self.response.answer.replace('${' + slot['entity'] + "}", slot['value'])

        self.intentCompleteCheck(slots,query,intent,confidence)

        self.response.lastResponseJson = self.response.responseJson
        print("response is :", self.response.responseJson)

        return self.response.responseJson

    #流程信息
    def processAction(self,intent):
        global result
        if len(self.response.intentFlowInfo.intentFlowContent) == 0 :
            self.response.intentFlowInfo.intentFlowContent = self.getIntentFlow(intent)

        if len(self.response.intentFlowInfo.intentFlowContent) > 0:
            self.response.intentFlowInfo.intentFlowComplete = True
            if self.response.intentFlowInfo.intentFlowContent.has_key(unicode(intent)):
                self.response.intentFlowInfo.intentFlowContent[unicode(intent)] = True

            #获取下一个意图
            current_intent = ''
            for (k,v) in self.response.intentFlowInfo.intentFlowContent.items():
                if not v:
                    current_intent = k
                    self.response.intentFlowInfo.intentFlowComplete = False
                    break
            # result_entites 转换成entities
            if not self.response.intentFlowInfo.intentFlowComplete:
                self.response.currentQuestionType = self.response.INIT_TYPE

                result = self.intentAction(current_intent, None, None)
                if result['action']['complete'] and self.response.intentFlowInfo.intentFlowContent.has_key(result['intentName']):
                    self.response.intentFlowInfo.intentFlowContent[result['intentName']] = True

            return result
        return None

    #后置检查，
    def afterCheck(self,intent):
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
            #if check not in self.response.historyIntentsTag:
            if not self.response.historyInfo.matchHistoryIntent(check):
                self.response.currentQuestionType = self.response.POST_ASK_TYPE
                content = {"type": 0, "message": self.response.pre_question}
                self.response.status = {"code": 200, "msg": "触发后置意图"}
                self.response.contentData.append(content)
                return True
            else:
                return False

            #插入/更新意图信息
    ## 参数 existHistory、 result_entities、responseJson、history_intents
    def updateUserSceneInfo(self,intent,existHistory,result_entities,responseJson,complete):
        if existHistory:
            sql = "UPDATE history_scene_info set entities =\'"+json.dumps(result_entities,ensure_ascii=False).encode("utf8")+"\',last_response_json = \'"+json.dumps(responseJson,ensure_ascii=False).encode("utf8")+"\',history_intents = \'"+json.dumps(self.response.historyInfo.historyIntentsInfo,ensure_ascii=False).encode("utf8")+"\',complete = "+str(complete)+" WHERE user_token = \'"+self.token+"\' and intent = \'"+intent+"\'"
            print(sql)
            self.n.update(sql)
        else:
            sql = "INSERT INTO history_scene_info (user_token,entities,intent,last_response_json,history_intents,complete) VALUES(\'"+self.token+"\',\'"+json.dumps(result_entities,ensure_ascii=False).encode("utf8")+"\',\'"+intent+"\',\'"+json.dumps(responseJson,ensure_ascii=False).encode("utf8")+"\',\'"+json.dumps(self.response.historyInfo.historyIntentsInfo,ensure_ascii=False).encode("utf8")+"\',"+str(complete)+")"
            print(sql)
            self.n.insert(sql)

    # slot 填充
    def matchSlot(self):
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
        intents = self.response.historyInfo.getHistoryIntents()
        for intent in intents:
            self.response.entities = intent['responseJson']['action']['parameters']
            self.response.entities_types = intent['responseJson']['lastEntitiesType']

            for entity in self.response.entities:
                for (k,v) in self.response.entities_types.items():
                    if k == entity['entity']:
                        slots[self.response.entities_types[k]] = entity['value']
                        break

        return slots

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
            if self.utils.matchComfirm(query) is None:
                ruleMatchType = None
            elif self.utils.matchComfirm(query):
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
            if self.utils.matchComfirm(query) is None:
                return None
            else:
                if self.utils.matchComfirm(query):
                    return "确定"
                else:
                    return "否定"

    # 获取意图流程
    def getIntentFlow(self,intent):
        intentFlow = OrderedDict()
        self.n.query("select * from robot_process WHERE trigger_intent = \'"+intent+"\' and del_flag = 0")
        r = self.n.fetchRow()

        if r is not None:
            intents = json.loads(r['content'],encoding="utf8")
            for item in intents:
                intentFlow[item['itName']] = False

            if intentFlow.has_key(unicode(intent)):
                self.response.intentFlowInfo.intentFlow = intentFlow
                self.response.intentFlowInfo.comfirmAction = r['y_action']
                self.response.intentFlowInfo.negativeAction = r['n_action']
                self.response.intentFlowInfo.ask = r['ask']
                return intentFlow
        else:
            return None



    # 检查意图是否存在流程中，且是否为已完成意图
    def checkIntentInFlow(self,intent):
        if self.response.intentFlowInfo.intentFlowContent.has_key(intent) and self.response.intentFlowInfo.intentFlowContent[intent] == True:
            return True
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
        self.response.lastEntities = {}
        self.response.entities = []
        self.response.status = {}
        self.response.responseJson = {}
        self.response.currentQuestionType = self.response.INIT_TYPE

        self.response.pre_question = None
        self.response.curslot = None
        self.response.historyInfo = ChatbotHistoryInfo()

        self.returnJson = {}
        self.existHistory = False

        self.response.intentFlowInfo = ChatbotIntentFlow()

    # 删除缓存
    def delete(self):
        self.response = ChatbotResponse()
        g._users.setUser(self.token, self.response)

        self.n.deleteCache("delete from history_scene_info where user_token ='%s' " % self.token)

    # 执行动作
    def executeAction(self):
        isSuccess = False
        if self.response.historyInfo.historyActions is None and len(self.response.historyInfo.historyActions) == 0:
            return None

        for (k,action) in self.response.historyInfo.historyActions.items():
            responseContent = self.microservice.route(self.username,k,action['params'])
            isSuccess = self.actionResultCheck(action['intent'],k,responseContent)
            if isSuccess:
                action['complete'] = True
                self.response.historyInfo.historyActions[k] = action

        if isSuccess:
            self.response.responseJson['status'] = {"code": 200, "msg": "规则动作执行完成！"}

        return isSuccess

    def actionResultCheck(self,intent,action,responseContent):
        content = ''
        reRunIntent = self.actionContentCheck(intent, action, responseContent)
        if reRunIntent is not None:
            if len(self.response.intentFlowInfo.intentFlowContent) > 0:  # 当存在意图流程的情况下
                # 返回结果检测有问题，则重制结果有问题的流程为false,整体流程也为false
                self.response.intentFlowInfo.intentFlowContent[self.response.responseJson['intentName']] = False
                # 当存在  酒店查询--》订购酒店 时，订购酒店失败，需要重新订购，重新订购需要给予用户重新查询酒店的信息。
                self.response.intentFlowInfo.intentFlowContent[reRunIntent] = False
                self.response.intentFlowInfo.intentFlowComplete = False

            # 清空对应意图的slot
            self.response.result_entities = {}
            self.response.entities_question = {}
            self.response.entities_types = {}
            self.response.complete = False
            self.response.entities = []
            self.response.curslot = ''
            self.getSlotQuestions(intent)

            self.response.currentQuestionType = self.response.SLOT_ASK_TYPE
            self.collectSlotInfo()

            # 执行意图查询

            self.response.contentData = []
            if responseContent['data'] is not None and len(responseContent['data'])>0  and responseContent['data']['message'] is not None:
                content = responseContent['data']['message']
                self.response.contentData.append({"type": 0, "message": content})

            # 如果响应问题中包含参数，则替换;
            # 例如确认问题：您申请了${date}去${address}的出差申请，是否确认提交？
            if len(self.response.actionJson) > 0:
                slots = self.response.actionJson['parameters']
                if self.response.answer is not None and "${" in self.response.answer:
                    for slot in slots:
                        self.response.answer = self.response.answer.replace('${' + slot['entity'] + "}",
                                                                            slot['value'])

            self.intentCompleteCheck(slots, None, intent, None)

            self.response.lastResponseJson = self.response.responseJson

            isSuccess = False
        else:
            if responseContent is not None and responseContent.has_key('message'):#and not responseContent.has_key('data'):
                content = content + responseContent['message'] + "。"

                self.response.contentData.append({"type": 0, "message": content})

            isSuccess = True

        return isSuccess

    # 参数替换
    def variableReplace(self,ask,params):
        if ask is not None and "${" in ask:
            for (k, v) in params.items():
                ask = ask.replace('${' + k + "}", v)

        return ask

    # 检查历史意图
    def checkExistHistoryIntent(self):
        # 是否存在历史意图
        if self.response.currentQuestionType != self.response.SLOT_ASK_TYPE:
            self.n.query(
                "select * from history_scene_info where user_token = \'" + self.token + "\' and complete = False")
            r = self.n.fetchRow()
            if r is not None:
                self.response.existHistory = True
                if len(self.response.lastResponseJson) == 0:
                    self.response.lastResponseJson = json.loads(r['last_response_json'], encoding="utf8")
                    self.response.historyIntentsInfo = json.loads(r['history_intents'], encoding="utf8")
                    self.response.result_entities = json.loads(r['entities'], encoding="utf8")
            else:
                self.response.existHistory = False
        else:
            self.response.existHistory = True

    # 收集slot
    def collectSlotInfo(self):
        # 如果没有slot，则直接查询solr
        # 当当前问题类型是0且无slot问题时complete为True
        if self.response.currentQuestionType == self.response.INIT_TYPE and len(self.response.entities_question) == 0:
            self.response.complete = True
        else:
            if self.response.entities is None or len(self.response.entities) == 0:
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

    # 前置检查
    def preInspection(self,query):
        # 获取历史input
        ruleMatch = self.ruleMatch(self.response.pre_question, query)
        # 获取否定触发的动作，触发酒店/机票查询
        self.n.query(
            "select scene.id,scene.`name`,mark.y_hint,mark.y_action,mark.in_hint,mark.in_action from robot_scene as scene,robot_scene_mark as mark where scene.`name` = \'" + self.response.lastIntent + "\' and mark.id = scene.input")
        r = self.n.fetchRow()
        if ruleMatch == '确定':
            nextIntent = r['y_action']
            # 获取对应的规则
            self.response.intentFlowInfo.intentFlowContent = self.getIntentFlow(nextIntent)

            self.response.currentQuestionType = self.response.INIT_TYPE
            self.response.responseJson = self.intentAction(nextIntent, None,query)
        elif ruleMatch == '否定':
            self.response.contentData.append({"type": 0, "message": r['in_hint']})
            nextIntent = r['in_action']
            self.response.responseJson = self.intentAction(nextIntent,
                                                           None, query)
        # 后置意图匹配后，检查后置的complete是否为true，不为true则更新currenQuestionType = 2
        if self.response.responseJson['action']['complete']:
            self.response.entities = []
            self.response.currentQuestionType = self.response.INIT_TYPE  # 初始意图识别状态。
        else:
            self.response.currentQuestionType = self.response.SLOT_ASK_TYPE
        self.response.returnJson = {'status': self.response.responseJson['status'], 'data': self.response.contentData}

    # 后置检查
    def postInspection(self,query):
        self.response.pre_question = self.response.lastResponseJson['pre_question']
        # 获取历史input
        ruleMatch = self.ruleMatch(self.response.pre_question, query)
        if ruleMatch == '确定':
            # 获取对应的规则
            self.response.intentFlowInfo.intentFlowContent = self.getIntentFlow(self.response.lastResponseJson['lastIntent'])

            if self.response.intentFlowInfo.intentFlowContent is not None and len(self.response.intentFlowInfo.intentFlowContent) > 0 and self.response.intentFlowInfo.intentFlowContent.has_key(self.response.lastResponseJson['intentName']):
                self.response.intentFlowInfo.intentFlowContent[self.response.lastResponseJson['intentName']] = True

            self.response.currentQuestionType = self.response.INIT_TYPE
            self.response.responseJson = self.intentAction(self.response.lastResponseJson['lastIntent'], None,
                                                           query)

            # 后置意图匹配后，检查后置的complete是否为true，不为true则更新currenQuestionType = 2
            if self.response.responseJson['action']['complete']:
                self.response.entities = []
                self.response.currentQuestionType = self.response.INIT_TYPE # 初始意图识别状态。
            else:
                self.response.currentQuestionType = self.response.SLOT_ASK_TYPE

            self.response.returnJson = {'status': self.response.responseJson['status'], 'data': self.response.contentData}
        elif ruleMatch == '否定':
            self.response.currentQuestionType = self.response.INIT_TYPE
            self.response.returnJson = {'status': self.response.responseJson['status'],
                                        'data': [{"type": 0, "message": "好的"}]}
            # 清空历史缓存
            self.resetHistoryIntent()

    #意图完成后检查
    def intentCompleteAfterCheck(self, intent, tag):
        if self.response.complete:
            # # 添加历史意图
            self.response.historyInfo.addHistoryIntent(intent,tag,self.response.responseJson)

            self.response.currentQuestionType = self.response.INIT_TYPE
            #后置检查
            if not self.afterCheck(intent):
                # 查询关联规则
                result = self.processAction(intent)
                if result is not None:
                    self.response.responseJson = result
            else:
                self.response.responseJson['currentQuestionType'] = self.response.POST_ASK_TYPE

    # 意图完成检查
    def intentCompleteCheck(self,slots,query,intent,confidence):
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
                        # self.response.historyInfo.historyActions.append({
                        #     "intent": self.response.responseJson['intentName'],
                        #     "action": actionName,
                        #     "params": self.utils.listToMap(slots),
                        #     "complete":False
                        # })
                        self.response.historyInfo.historyActions[actionName] = {
                            "intent": self.response.responseJson['intentName'],
                            "params": self.utils.listToMap(slots),
                            "complete":False
                        }
                    else:
                        # 这里需要做微服务适配
                        content = self.microservice.route(self.username, intent, self.utils.listToMap(slots))
                        self.actionResultCheck(intent,actionName,content)
        else:
            content = {"type": 0, "message": self.response.answer}

        self.responseJsonStuff(content, query, intent, confidence)

        # 保存result_entities、responseJson、history_intents
        self.updateUserSceneInfo(intent, self.response.existHistory, self.response.result_entities,
                                 self.response.responseJson, self.response.complete)
        self.response.lastResponseJson = self.response.responseJson

        self.intentCompleteAfterCheck(intent, tag)


    # 规则完成检查
    def ruleCompleteCheck(self,query):
        # 如果当前意图完成，则匹配将参数匹配给下一个意图。
        if self.response.lastResponseJson['action']['complete']:
            for (k, v) in self.response.intentFlowInfo.intentFlowContent.items():
                if k == self.response.lastResponseJson['intentName']:
                    self.response.intentFlowInfo.intentFlowContent[k] = True

            for (k, v) in self.response.intentFlowInfo.intentFlowContent.items():
                if v is False:
                    current_intent = k
                    self.response.intentFlowInfo.intentFlowComplete = False
                    break
        else:
            current_intent = self.response.lastResponseJson['intentName']

        if not self.response.intentFlowInfo.intentFlowComplete:
            if not self.response.lastResponseJson['action']['complete']:
                ruleMatch = self.ruleMatch(self.response.lastResponseJson['slotType'], query)
                if ruleMatch is None:
                    # 意图判断为空，则重新匹配切换意图
                    if self.response.historyInfo.matchHistoryDetails(query, self.response.lastResponseJson['slot']):
                        if self.response.entities is not None:
                            self.response.entities.append(
                                {'entity': self.response.lastResponseJson['slot'], 'value': query})
                    else:
                        r = requests.get(self.nluServer + query)
                        data = json.loads(r.text)
                        self.response.entities = data['entities']
                        self.response.confidence = data['intent']['confidence']
                        self.response.currentQuestionType = self.response.INIT_TYPE
                else:
                    if ruleMatch in self.response.lastResponseJson['slotType']:  # 规则匹配成功，直接填充entities传到intentAction中
                        if self.response.entities is not None:
                            self.response.entities.append(
                                {'entity': self.response.lastResponseJson['slot'], 'value': query})

                self.response.responseJson = self.intentAction(current_intent, None, query)
                if self.response.responseJson['action']['complete'] and self.response.intentFlowInfo.intentFlowContent.has_key(
                        self.response.responseJson['intentName']):
                    self.response.intentFlowInfo.intentFlowContent[self.response.responseJson['intentName']] = True

                self.response.returnJson = {'status': self.response.responseJson['status'], 'data': self.response.contentData}

                isAllTrue = True
                for (k, v) in self.response.intentFlowInfo.intentFlowContent.items():
                    if v is False:
                        isAllTrue = False
                        break

                if isAllTrue:
                    # 获取所有的slot信息，进行问答匹配
                    params = self.response.historyInfo.getHistorySlots()

                    # 获取规则id，匹配获取对应的询问信息，以及动作
                    ruleInfo = self.response.intentFlowInfo.getIntentFlowInfo()

                    # 设置询问类型为规则询问
                    self.response.currentQuestionType = self.response.RULE_ASK_TYPE
                    # 获取询问问题
                    ask = ruleInfo['ask']

                    ask = self.variableReplace(ask, params)

                    self.response.contentData.append({"type": 0, "message": ask})
                    # 返回询问信息json
                    self.response.returnJson = {'status': self.response.responseJson['status'], 'data': self.response.contentData}

    # 规则询问
    def ruleInspection(self,query):
        # 处理流程询问信息。
        # 获取所有的slot信息，进行问答匹配
        params = self.response.historyInfo.getHistorySlots()
        # 获取规则id，匹配获取对应的询问信息，以及动作
        ruleInfo = self.response.intentFlowInfo.getIntentFlowInfo()
        ask = ruleInfo['ask']
        ask = self.variableReplace(ask, params)

        ruleMatch = self.ruleMatch(ask, query)
        if ruleMatch == '确定':
            action = ruleInfo['action']
            #contentData.append(self.executeAction())

            isSuccess = self.executeAction()
            # 确认则执行后置动作
            # 所有动作完成，则清空，否则不清空
            if isSuccess:
                # 通过动作名称匹配微服务
                content = self.microservice.route(self.username, action, params)
                self.response.contentData.append(content)

                self.response.returnJson = {'status': self.response.responseJson['status'],
                                            'data': self.response.contentData}

                self.resetHistoryIntent()
            else:
                self.response.returnJson = {'status': self.response.responseJson['status'],
                                            'data': self.response.contentData}

        elif ruleMatch == '否定':
            self.resetHistoryIntent()
        else:
            # 提交流程时，当用户回答不匹配时，继续提问
            self.response.returnJson = {'status': self.response.responseJson['status'],
                                        'data': self.global_answer + ask}

    # slot 填充
    def slotStuff(self,query):

        ruleMatch = self.matchType(query)
        # ruleMatch = self.ruleMatch(self.response.lastResponseJson['slotType'],query)
        if ruleMatch is None:  # 意图判断为空，则重新匹配切换意图
            if self.response.historyInfo.matchHistoryDetails(query, self.response.lastResponseJson['slot']):
                if self.response.entities is not None:
                    self.response.entities.append({'entity': self.response.lastResponseJson['slot'], 'value': query})
            else:
                r = requests.get(self.nluServer + query)
                data = json.loads(r.text)
                if self.response.responseJson['intentName'] != data['intent']['name']:
                    self.response.entities = data['entities']
                    self.response.confidence = data['intent']['confidence']
                    self.response.currentQuestionType = self.response.INIT_TYPE
                else:
                    for entity in data['entities']:
                        self.response.entities.append(entity)
        elif ruleMatch in self.response.lastResponseJson['slotType']:  # 规则匹配成功，直接填充entities传到intentAction中
            if self.response.entities is not None:
                self.response.entities.append({'entity': self.response.lastResponseJson['slot'], 'value': query})
        else:
            # 匹配其他的slot信息
            slot = ''
            for (k, v) in self.response.entities_types.items():
                if ruleMatch in v:
                    slot = k
                    break

            if self.response.entities is not None and len(slot) > 0:
                self.response.entities.append({'entity': slot, 'value': query})

    # 填充responseJson
    def responseJsonStuff(self,content,query,intent,confidence):
        if len(content) > 0:
            self.response.contentData.append(content)

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
        if not self.response.complete:
            self.response.responseJson['slot'] = self.response.curslot # 保存历史的slot以及slotType用于模式匹配。
            self.response.responseJson['slotType'] = self.response.entities_types[self.response.curslot]

    # 动作结果检查
    def actionContentCheck(self,intent,action,responseContent):
        nextIntent = None

        self.n.query("select * from robot_scene_mic_service WHERE int_name = \'"+intent+"\' and action_name = \'"+action+"\'")
        result = self.n.fetchRow()
        if result is not None:#当动作内容检查设置不为空时
            type = result['type']
            if responseContent is not None or len(responseContent) > 0:  # and responseContent['data'] is not None:
                # 返回结果数据不为空
                if type == 1: # 判断内容
                    #responseContent['data'] is not None
                    pass
                elif type == 0 : # 判断结果有无
                    if responseContent['data'] is None or len(responseContent['data']) == 0 or (isinstance(responseContent['data'],dict) and responseContent['data'].has_key('data') and responseContent['data']['data'] is None):
                        nextIntent = result['y_result']
                    else:
                        nextIntent = result['n_result']

        return nextIntent