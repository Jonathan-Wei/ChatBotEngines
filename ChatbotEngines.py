#-*- coding=utf-8 -*-
from ChatbotMySQL import *
from ChatbotMicroservices import *
from ChatbotUtils import *
import pysolr
from collections import OrderedDict
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

answer = ""
complete = False
result_entities = {}
actionJson={}
lastResponseJson = {}
entities_question = OrderedDict()
entities_types = {}
ruleContent = {}
ruleComplete = True
lastEntities = {}
entities = []
status = {}
currentQuestionType = 0
pre_question=None
curslot=None

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

        self.microservice = ChatbotMicroservices()
        self.utils=ChatbotUtils()


        self.n.selectDb(app.config['MODEL_DB'])
        self.n.query("""select `name` from robot_scene""")
        r = self.n.fetchAll()

        for result in r:
            self.intents.append(result['name'])

    def request(self, question):
        if self.validate():
            r = requests.get(self.nluServer + question)
            data = json.loads(r.text)

            #return json.dumps(self.action(data, question))
            return json.dumps(self.preAction(data, question))
        else:
            print("用户未登陆，请登陆之后再做请求")

    def getSlotQuestions(self, intent):
        global entities_question,entities_types
        entities_question = OrderedDict()
        sql = 'SELECT type_name as slot,dict_name as slot_type,message as slot_question from robot_scene_slot where int_id in (select id from robot_scene WHERE `name` =\'' + intent + '\') order by id'
        print(sql)
        self.n.query(sql)
        r = self.n.fetchAll()

        for result in r:
            entities_question[result['slot']] = result['slot_question']
            entities_types[result['slot']] = result['slot_type']

    #验证用户token
    def validate(self):
        self.n.query("select * from `sys_user_config` where `token`=\'"+self.token+"\'")
        r = self.n.fetchAll()

        if r is None:
            return False
        else:
            return True

    def preAction(self,data,query):
        global ruleComplete,ruleContent,lastEntities,entities,currentQuestionType,returnJson,pre_question,lastIntent,status,lastResponseJson,responseJson
        contentData = []

        # 判断是否ruleContent 是否空
            #不为空  判断是否已经匹配参数及调用历史意图信息，进行询问
        if len(ruleContent)>0 or not ruleComplete:
            if lastResponseJson['action']['complete']:
                for (k,v) in ruleContent.items():
                    if k == lastResponseJson['intentName']:
                        ruleContent[k] = True

            for (k,v) in ruleContent.items():
                if v is False:
                    current_intent = k
                    ruleComplete = False
                    break
            if not ruleComplete:
                if not lastResponseJson['action']['complete']:
                    #intentAction(self,data,intent,entities,confidence,query,currentQuestionType):
                    ruleMatch = self.ruleMatch(lastResponseJson['slotType'],query)
                    if ruleMatch in lastResponseJson['slotType']:# 规则匹配成功，直接填充entities传到intentAction中
                        if entities is not None:
                            entities.append({'entity':lastResponseJson['slot'],'value':query})
                    responseJson = self.intentAction(contentData, current_intent, entities, None, query,currentQuestionType)
                    if responseJson['action']['complete'] and ruleContent.has_key(responseJson['intentName']):
                        ruleContent[responseJson['intentName']] = True

                    isAllTrue = True
                    for (k, v) in ruleContent.items():
                        if v is False:
                            isAllTrue = False
                            break

                    if isAllTrue:
                        ruleContent = {}
                        ruleComplete = True
                        currentQuestionType = 0
                    returnJson = {'status': responseJson['status'], 'data': contentData}
        else:
            if len(lastResponseJson)>0 and lastResponseJson['currentQuestionType'] == 3:
                currentQuestionType =3
            #保存当前问题类型
            if currentQuestionType == 1:
                # 获取历史input
                ruleMatch = self.ruleMatch(pre_question, query)
                if ruleMatch == '是否':
                    currentQuestionType = 0
                    responseJson = self.intentAction(contentData, lastIntent,lastEntities,None,query,currentQuestionType)

                    # 后置意图匹配后，检查后置的complete是否为true，不为true则更新currenQuestionType = 2
                    if responseJson['action']['complete']:
                        entities = []
                        currentQuestionType = 0  # 初始意图识别状态。
                    else:
                        currentQuestionType = 2
                    returnJson = {'status': responseJson['status'], 'data': contentData}
            elif currentQuestionType == 3:
                pre_question = lastResponseJson['pre_question']
                # 获取历史input
                ruleMatch = self.ruleMatch(pre_question, query)
                if ruleMatch == '是否':
                    currentQuestionType = 0
                    responseJson = self.intentAction(contentData, lastResponseJson['lastIntent'], lastResponseJson['action']['parameters'], None, query,
                                                     currentQuestionType)

                    # 后置意图匹配后，检查后置的complete是否为true，不为true则更新currenQuestionType = 2
                    if responseJson['action']['complete']:
                        entities = []
                        currentQuestionType = 0  # 初始意图识别状态。
                    else:
                        currentQuestionType = 2

                    returnJson = {'status': responseJson['status'], 'data': contentData}
            else:
                confidence = None
                # 查询前置意图
                intent = data['intent']['name']
                self.n.query("select mark.`name` as `input`,mark.ask as question,scene.`name` as intent from robot_scene_mark as mark,robot_scene as scene where mark.id = (select `input` from robot_scene where `name` = \'"+intent+"\') and mark.int_id = scene.id")
                r = self.n.fetchRow()
                input = None
                if r is not None:
                    input = r['input']
                    pre_question = r['question']
                    lastIntent = r['intent']

                if input is not None:
                    currentQuestionType = 1
                    content = {"type": 0, "message": pre_question}
                    status = {"code": 200, "msg": "触发前置意图"}
                    lastEntities = data['entities']
                    #输入不为空触发直接返回输入验证问题
                    returnJson = {'status': status, 'data': [content]}
                    # 存储responsejson
                    return returnJson

                if currentQuestionType == 2: #状态未2时，表示填充solt状态
                    intent=lastResponseJson['intentName']
                    ruleMatch = self.ruleMatch(lastResponseJson['slotType'],query)

                    if ruleMatch in lastResponseJson['slotType']:# 规则匹配成功，直接填充entities传到intentAction中
                        if entities is not None:
                            entities.append({'entity':lastResponseJson['slot'],'value':query})
                    else:
                        #匹配不成功则进行意图识别判定
                        #匹配规则失败，则获取历史的query + 当前的query组合，再次提问
                        query = lastResponseJson['query']+","+query
                        r = requests.get(self.nluServer + query)
                        data = json.loads(r.text)
                        entities = data['entities']
                        confidence = data['intent']['confidence']
                else:
                    entities = data['entities']
                    confidence = data['intent']['confidence']

                #无前置意图直接走正常流程
                responseJson = self.intentAction(contentData,intent,entities,confidence,query,currentQuestionType)
                if responseJson['currentQuestionType'] != 3:
                    if responseJson['action']['complete']:
                        entities = []
                        currentQuestionType = 0  # 初始意图识别状态。
                    else:
                        currentQuestionType = 2

                # 构建接口服务与app端对接
                returnJson = {'status': responseJson['status'], 'data': contentData}
        lastResponseJson = responseJson

        return returnJson

    # 规则匹配
    def ruleMatch(self,type,query):
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
                ruleMatchType = '是否'

        return ruleMatchType


    # 意图处理
    def intentAction(self,data,intent,entities,confidence,query,currentQuestionType):
        global curslot,history_intents, answer, actionJson, lastResponseJson, existHistory, result_entities, entities_question,status
        # 是否存在历史意图
        if currentQuestionType != 2:
            self.n.query("select * from history_scene_info where user_token = \'" + self.token + "\' and complete = False")
            r = self.n.fetchRow()
            if r is not None:
                existHistory = True
                lastResponseJson = json.loads(r['last_response_json'])
                # history_intents = json.loads(r['history_intents'])
                result_entities = json.loads(r['entities'])
            else:
                existHistory = False
        else:
            existHistory = True

        #历史意图是否一致
        if unicode(intent) in self.intents:
            if confidence is not None:
                if confidence > 0:
                    print('意图识别成功！')
                    status = {"code": 200, "msg": "意图识别成功"}
                else :
                    print('意图识别失败')
                    status = {"code": 500, "msg": "意图识别失败"}
                    answer = ChatbotEngines.global_answer
                    if len(lastResponseJson) > 0:
                        if lastResponseJson['status']['code'] == 200:
                            lastResponseJson['status'] = status
                            lastResponseJson['answer'] = answer + lastResponseJson['answer']

                        print("last response is :", lastResponseJson)
                        return lastResponseJson
            else:
                if currentQuestionType !=2:
                    if lastResponseJson is not None and len(lastResponseJson) > 0:
                        entities = lastResponseJson['action']['parameters']

        # 当意图被切换时，更新需要询问的solt,需要保存历史的意图信息。

        # 如果是收集solt状态，则不匹配意图，不重新填充entities_question
        if currentQuestionType!=2:
            if len(entities_question) == 0 or (len(lastResponseJson) >0  and lastResponseJson['intentName'] != intent):
                 # 保存历史意图信息。
                result_entities = {}
                entities_question = {}
                self.getSlotQuestions(intent)

        complete = False

        if status['code'] == 200:
            # 如果没有solt，则直接查询solr
            if len(entities_question) == 0:
                complete = True
            else:
                if len(entities) == 0:
                    curslot = entities_question.items()[0][0]
                    answer = entities_question.items()[0][1]
                else:
                    for (k, v) in entities_question.items():
                        isMatch = False
                        for entity in entities:
                            if entity['entity'] == k:
                                isMatch = True
                                result_entities[k] = entity['value']
                                break

                        if not isMatch:
                            for (k1, v1) in result_entities.items():
                                if k1 == k:
                                    isMatch = True
                                    break

                        if not isMatch:
                            answer = entities_question[k]
                            curslot = k
                            complete = False
                            break

                    if len(result_entities) == len(entities_question):
                        complete = True

                parametersJson = []
                for (k2, v2) in result_entities.items():
                    parametersJson.append({"entity": k2, "value": v2.decode(sys.getdefaultencoding())})

                actionJson = {"name": "", "complete": complete, "parameters": parametersJson}

        # 如果响应问题中包含参数，则替换;
        # 例如确认问题：您申请了${date}去${address}的出差申请，是否确认提交？
        slots = actionJson['parameters']
        if answer is not None and "${" in answer:
            for slot in slots:
                answer = answer.replace('${' + slot['entity'] + "}", slot['value'])

        # 如果complete=True，则调用solr查询具体信息，填充answer属性
        content = {}
        if complete:

            if len(entities_question) != 0:
                self.n.query(
                    'select answer from robot_scene WHERE `name` =\'' + intent + '\'')
                r = self.n.fetchRow()
                question = r['answer']
                 # 通过配置的ai回复进行问题组装

                for slot in slots:
                    if slot['entity'] != 'comfirm':
                        question = question.replace('${' + slot['entity'] + "}", slot['value'])

                self.n.query(
                    'select `storage` from robot_app WHERE id = (select app_id from robot_scene where `name` =\'' +
                    intent + '\')')

                r = self.n.fetchRow()
                if r is not None:
                    # 这里需要做微服务适配
                    content = self.microservice.route(intent, self.utils.listToMap(slots))
                else:
                    content = {"type": 0, "message": question}
            else:
                content = self.microservice.route(intent, {"question": query})
        else:
            content = {"type": 0, "message": answer}

        data.append(content)
        responseJson = {
            "sessionId": self.token,
            "query": query,
            "intentId": "",
            "intentName": intent,
            "confidence": confidence,
            "action": actionJson,
            "slot":curslot,#保存历史的slot以及slotType用于模式匹配。
            "slotType":entities_types[curslot],
            "currentQuestionType":currentQuestionType,
            "answer": answer,
            "status": status
        }

        # 保存result_entities、responseJson、history_intents
        self.updateUserSceneInfo(intent,existHistory, result_entities, responseJson, complete)
        if complete:
            currentQuestionType = 0
            #后置检查
            if not self.afterCheck(data,intent,currentQuestionType,responseJson):
                # 查询关联规则
                result = self.ruleAction(data, intent, result_entities, currentQuestionType)
                if result is not None:
                    responseJson = result
            else:
                responseJson['currentQuestionType'] = 3

        print("response is :", responseJson)
        lastResponseJson = responseJson

        return responseJson

    #流程信息
    def ruleAction(self,data,intent,result_entities,currentQuestionType):
        global ruleComplete,ruleContent

        current_intent = ''

        self.n.query("select * from robot_scene where `input` = (SELECT output from robot_scene where `name` =\'" + intent + "\')")
        r = self.n.fetchAll()
        if r is not None and len(r) >0:
            for result in r:
                clildIntent = result['name']
                #调用intentAction
                ruleContent[unicode(clildIntent)] = False

            ruleComplete = True
            for (k,v) in ruleContent.items():
                if v is False:
                    current_intent = k
                    ruleComplete = False
                    break

            if not ruleComplete:
                currentQuestionType = 0
                result =  self.intentAction(data,current_intent, result_entities,None, None,currentQuestionType)
                if result['action']['complete'] and ruleContent.has_key(result['intentName']):
                    ruleContent[result['intentName']]=True
            else:
                ruleContent = {}

            isAllTrue = True
            for (k, v) in ruleContent.items():
                if v is False:
                    isAllTrue = False
                    break

            if isAllTrue:
                ruleContent = {}
                ruleComplete = True
                currentQuestionType = 0

            return result

        return None

    #后置检查，
    def afterCheck(self,data,intent,currentQuestionType,responseJson):
        global status
        self.n.query(
            "select mark.`name` as `check`,mark.ask as question,scene.`name` as intent from robot_scene_mark as mark,robot_scene as scene where mark.id =(select `check` from robot_scene WHERE `name` = \'" + intent + "\') and mark.int_id = scene.id")
        r = self.n.fetchRow()
        check = None
        if r is not None:
            check = r['check']
            pre_question = r['question']
            responseJson['pre_question'] = pre_question
            responseJson['lastIntent'] = r['intent']
        else:
            return False

        if check is not None:
            currentQuestionType = 3
            content = {"type": 0, "message": pre_question}
            status = {"code": 200, "msg": "触发后置意图"}
            data.append(content)
            return True

            #插入/更新意图信息
    ## 参数 existHistory、 result_entities、responseJson、history_intents
    def updateUserSceneInfo(self,intent,existHistory,result_entities,responseJson,complete):
        if existHistory:
            sql = "UPDATE history_scene_info set entities =\'"+json.dumps(result_entities)+"\',last_response_json = \'"+json.dumps(responseJson)+"\',complete = "+str(complete)+" WHERE user_token = \'"+self.token+"\' and intent = \'"+intent+"\'"
            print(sql)
            self.n.update(sql)
        else:
            sql = "INSERT INTO history_scene_info (user_token,entities,intent,last_response_json,complete) VALUES(\'"+self.token+"\',\'"+json.dumps(result_entities)+"\',\'"+intent+"\',\'"+json.dumps(responseJson)+"\',"+str(complete)+")"
            print(sql)
            self.n.insert(sql)
