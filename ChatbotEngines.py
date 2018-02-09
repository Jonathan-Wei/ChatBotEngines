#-*- coding=utf-8 -*-
from ChatbotMySQL import *
from ChatbotMicroservices import *
from ChatbotUtils import *
from ChatbotHistoryInfo import *
from collections import OrderedDict
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

answer = ""
complete = False  # 单个意图是否complete
result_entities = {}   #已识别的slot（entities）信息
actionJson={}
lastResponseJson = {}  # 上一次响应信息
entities_question = OrderedDict()  #slot提问信息
entities_types = {} # slot提问类型
ruleContent = OrderedDict() #规则内容
ruleComplete = True    #规则是否完整执行
lastEntities = {}
entities = []  #识别的entities
status = {}
responseJson ={}  # 响应信息
currentQuestionType = 0

pre_question=None   #上一次的问题信息
curslot=None
history_details = []  # 历史详情，用于酒店-航班的选择匹配
# 历史意图
historyIntentsInfo = []  # 历史意图信息
historyIntentsTag = []    # 历史意图输出标签信息

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

        self.username = ''

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

            return json.dumps(self.preAction(data, question))
        else:
            print("用户未登陆，请登陆之后再做请求")

    def getSlotQuestions(self, intent):
        global entities_question,entities_types
        entities_question = OrderedDict()
        sql = 'SELECT type_name as slot,dict_name as slot_type,message as slot_question from robot_scene_slot where int_id in (select id from robot_scene WHERE `name` =\'' + intent + '\') order by id'
        self.n.query(sql)
        r = self.n.fetchAll()

        for result in r:
            entities_question[result['slot']] = result['slot_question']
            entities_types[result['slot']] = result['slot_type']

        # 字段匹配

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
        global ruleComplete,ruleContent,lastEntities,entities,currentQuestionType,returnJson,pre_question,lastIntent,status,lastResponseJson,responseJson,history_details
        contentData = []

        # 判断是否ruleContent 是否空
            #不为空  判断是否已经匹配参数及调用历史意图信息，进行询问
        if len(ruleContent)>0 or not ruleComplete:
            if currentQuestionType == 4:
                # 处理流程询问信息。
                # 获取所有的slot信息，进行问答匹配
                params = self.getHistorySlots()
                # 获取规则id，匹配获取对应的询问信息，以及动作
                ruleInfo = self.getIntentFlowInfo()
                ask = ruleInfo['ask']
                if ask is not None and "${" in ask:
                    for (k, v) in params.items():
                        ask = ask.replace('${' + k + "}", v)

                ruleMatch = self.ruleMatch(ask, query)
                if ruleMatch == '确定':
                    action = ruleInfo['action']
                    # 通过动作名称匹配微服务
                    content = self.microservice.route(self.username, action, params)
                    contentData.append(content)
                    returnJson = {'status': responseJson['status'], 'data': contentData}
                self.resetHistoryIntent()
            else:
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
                        if ruleMatch is None:
                            #意图判断为空，则重新匹配切换意图
                            if self.matchHistoryDetails(query,lastResponseJson['slot']):
                                if entities is not None:
                                    entities.append({'entity': lastResponseJson['slot'], 'value': query})
                            else:
                                r = requests.get(self.nluServer + query)
                                data = json.loads(r.text)
                                entities = data['entities']
                                confidence = data['intent']['confidence']
                                currentQuestionType = 0
                        else:
                            if ruleMatch in lastResponseJson['slotType']:# 规则匹配成功，直接填充entities传到intentAction中
                                if entities is not None:
                                    entities.append({'entity':lastResponseJson['slot'],'value':query})

                        responseJson = self.intentAction(contentData, current_intent, entities, None, query,currentQuestionType)
                        if responseJson['action']['complete'] and ruleContent.has_key(responseJson['intentName']):
                            ruleContent[responseJson['intentName']] = True

                        returnJson = {'status': responseJson['status'], 'data': contentData}

                        isAllTrue = True
                        for (k, v) in ruleContent.items():
                            if v is False:
                                isAllTrue = False
                                break

                        if isAllTrue:
                            # 获取所有的slot信息，进行问答匹配
                            params = self.getHistorySlots()

                            # 获取规则id，匹配获取对应的询问信息，以及动作
                            ruleInfo = self.getIntentFlowInfo()

                            # 设置询问类型为规则询问
                            currentQuestionType = 4
                            # 获取询问问题
                            ask = ruleInfo['ask']
                            if ask is not None and "${" in ask:
                                for (k,v) in params.items():
                                    ask = ask.replace('${' + k + "}", v)

                            contentData.append({"type":0,"message":ask})
                            # 返回询问信息json
                            returnJson = {'status': responseJson['status'], 'data': contentData}
        else:
            if len(lastResponseJson)>0 and lastResponseJson['currentQuestionType'] == 3:
                currentQuestionType =3
            #保存当前问题类型
            if currentQuestionType == 1:
                # 获取历史input
                ruleMatch = self.ruleMatch(pre_question, query)
                # 获取否定触发的动作，触发酒店/机票查询
                self.n.query(
                    "select scene.id,scene.`name`,mark.y_hint,mark.y_action,mark.in_hint,mark.in_action from robot_scene as scene,robot_scene_mark as mark where scene.`name` = \'" + lastIntent + "\' and mark.id = scene.input")
                r = self.n.fetchRow()
                if ruleMatch == '确定':
                    nextIntent = r['y_action']
                    # 获取对应的规则
                    ruleContent = self.getIntentFlow(nextIntent)

                    currentQuestionType = 0
                    responseJson = self.intentAction(contentData, nextIntent,lastEntities,None,query,currentQuestionType)
                elif ruleMatch == '否定':
                    contentData.append({"type": 0, "message": r['in_hint']})
                    nextIntent = r['in_action']
                    responseJson = self.intentAction(contentData, nextIntent,
                                                     None, None, query,
                                                     currentQuestionType)
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
                if ruleMatch == '确定':
                    # 获取对应的规则
                    ruleContent = self.getIntentFlow(lastResponseJson['lastIntent'])
                    if ruleContent.has_key(lastResponseJson['intentName']):
                        ruleContent[lastResponseJson['intentName']] = True

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
                elif ruleMatch == '否定':
                    currentQuestionType = 0
                    returnJson = {'status': responseJson['status'], 'data': [{"type": 0, "message": "好的"}]}
                    # 清空历史缓存
                    self.resetHistoryIntent()
            else:
                confidence = None
                # 查询前置意图
                intent = data['intent']['name']
                if currentQuestionType == 0:
                    # 当后置意图为空，检查前置意图
                    self.n.query("select mark.`name` as `input`,mark.ask as question,scene.`name` as intent from robot_scene_mark as mark,robot_scene as scene where mark.id = (select `input` from robot_scene where `name` = \'"+intent+"\') and mark.int_id = scene.id")
                    r = self.n.fetchRow()
                    input = None
                    if r is not None:
                        input = r['input']
                        pre_question = r['question']

                    if input is not None:
                        currentQuestionType = 1
                        content = {"type": 0, "message": pre_question}
                        status = {"code": 200, "msg": "触发前置意图"}
                        lastEntities = data['entities']
                        lastIntent = data['intent']['name']
                        #输入不为空触发直接返回输入验证问题
                        returnJson = {'status': status, 'data': [content]}
                        # 存储responsejson
                        return returnJson

                if currentQuestionType == 2: #状态未2时，表示填充solt状态
                    intent=lastResponseJson['intentName']
                    ruleMatch = self.ruleMatch(lastResponseJson['slotType'],query)
                    if ruleMatch is None:#意图判断为空，则重新匹配切换意图
                        if self.matchHistoryDetails(query,lastResponseJson['slot']):
                            if entities is not None:
                                entities.append({'entity': lastResponseJson['slot'], 'value': query})
                        else:
                            r = requests.get(self.nluServer + query)
                            data = json.loads(r.text)
                            entities = data['entities']
                            confidence = data['intent']['confidence']
                            currentQuestionType = 0
                    elif ruleMatch in lastResponseJson['slotType']:# 规则匹配成功，直接填充entities传到intentAction中
                        if entities is not None:
                            entities.append({'entity':lastResponseJson['slot'],'value':query})
                else:
                    entities = data['entities']
                    confidence = data['intent']['confidence']

                #无前置意图直接走正常流程
                responseJson = self.intentAction(contentData,intent,entities,confidence,query,currentQuestionType)
                if responseJson['currentQuestionType'] != 3:
                    if responseJson['action']['complete']:
                        entities = []
                        currentQuestionType = 0 # 初始意图识别状态。
                    else:
                        currentQuestionType = 2

                # 构建接口服务与app端对接
                returnJson = {'status': responseJson['status'], 'data': contentData}
        lastResponseJson = responseJson

        # 获取历史的details，用于酒店名称匹配以及机票名称匹配
        for content in contentData:
            if content.has_key('content') and content['content'].has_key('details'):
                history_details.append(content['content']['details'])

        return returnJson

    # 意图处理
    def intentAction(self,data,intent,entities,confidence,query,currentQuestionType):
        global curslot,history_intents,answer,actionJson,responseJson,lastResponseJson, existHistory, result_entities, entities_question,entities_types,status,historyIntentsInfo,historyIntentsTag
        # 是否存在历史意图
        if currentQuestionType != 2:
            self.n.query("select * from history_scene_info where user_token = \'" + self.token + "\' and complete = False")
            r = self.n.fetchRow()
            if r is not None:
                existHistory = True
                lastResponseJson = json.loads(r['last_response_json'])
                self.historyIntentsInfo = json.loads(r['history_intents'])
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

        # 当意图被切换时，更新需要询问的solt,需要保存历史的意图信息。
        if currentQuestionType!=2:
            if len(entities_question) == 0 or len(lastResponseJson) >0 and lastResponseJson['intentName'] != intent:
                 # 保存历史意图信息。
                result_entities = {}
                entities_question = {}
                entities_types ={}
                self.getSlotQuestions(intent)
                if len(lastResponseJson) > 0:
                    entities = []
                    result_entities = self.matchSlot(lastResponseJson,entities_types);
                    for (k,v) in result_entities.items():
                        entities.append({"entity":k,"value":v})

        complete = False

        if status['code'] == 200:
            # 如果没有solt，则直接查询solr
            # 当当前问题类型是0且无slot问题时complete为True
            if currentQuestionType == 0 and len(entities_question) == 0:
                complete = True
            else:
                if entities is None or len(entities) == 0 :
                    curslot = entities_question.items()[0][0]
                    answer = entities_question.items()[0][1]
                else:
                    for (k, v) in entities_question.items():
                        isMatch = False
                        # slot与entities的匹配
                        for entity in entities:
                            if entity['entity'] == k:
                                isMatch = True
                                result_entities[k] = entity['value']
                                break

                        if not isMatch:
                            # slot与已识别的slot的匹配
                            for (k1, v1) in result_entities.items():
                                if k1 == k:
                                    isMatch = True
                                    break

                        # 未匹配，则获取未匹配的slot进行询问
                        if not isMatch:
                            answer = entities_question[k]
                            curslot = k
                            complete = False
                            break

                    if len(result_entities) == len(entities_question):
                        complete = True

                parametersJson = []
                if result_entities is not None:
                    for (k2, v2) in result_entities.items():
                        parametersJson.append({"entity": k2, "value": v2.decode(sys.getdefaultencoding())})

                actionJson = {"name": "", "complete": complete, "parameters": parametersJson}

        # 如果响应问题中包含参数，则替换;
        # 例如确认问题：您申请了${date}去${address}的出差申请，是否确认提交？
        if len(actionJson) > 0:
            slots = actionJson['parameters']
            if answer is not None and "${" in answer:
                for slot in slots:
                    answer = answer.replace('${' + slot['entity'] + "}", slot['value'])

        # 如果complete=True，则调用solr查询具体信息，填充answer属性
        content = {}
        tag = None
        if complete:
            # 检查是否有action需要执行
            self.n.query("select act_name,`output` from robot_scene where `name`  = \'" + intent + "\'")
            r = self.n.fetchRow()
            if r is not None:
                actionName = r['act_name']
                tag = r['output']
                if actionName is not None and len(actionName) > 0:
                    #这里需要做微服务适配
                    content = self.microservice.route(self.username,intent, self.utils.listToMap(slots))
        else:
            content = {"type": 0, "message": answer}

        if len(content) > 0:
            data.append(content)

        if complete:
            responseJson = {
                "sessionId": self.token,
                "query": query,
                "intentId": "",
                "intentName": intent,
                "confidence": confidence,
                "action": actionJson,
                "currentQuestionType": currentQuestionType,
                "lastEntitiesType": entities_types,
                "answer": answer,
                "status": status
            }
        else:
            responseJson = {
                "sessionId": self.token,
                "query": query,
                "intentId": "",
                "intentName": intent,
                "confidence": confidence,
                "action": actionJson,
                "slot": curslot,  # 保存历史的slot以及slotType用于模式匹配。
                "slotType": entities_types[curslot],
                "currentQuestionType": currentQuestionType,
                "lastEntitiesType": entities_types,
                "answer": answer,
                "status": status
            }

        # 保存result_entities、responseJson、history_intents
        self.updateUserSceneInfo(intent,existHistory, result_entities, responseJson, complete)
        lastResponseJson = responseJson
        if complete:
            # 添加历史意图
            historyIntentsInfo.append({
                "intent":intent,
                "tag":tag,
                "responseJson":responseJson
            })
            if tag is not None :
                tags = tag.split(",")
                for item in tags:
                    historyIntentsTag.append(int(item))

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
        global ruleComplete,ruleContent,result
        if len(ruleContent) == 0 :
            ruleContent = self.getIntentFlow(intent)

        if len(ruleContent) > 0:
            ruleComplete = True
            if ruleContent.has_key(unicode(intent)):
                ruleContent[unicode(intent)] = True


            #获取下一个意图
            current_intent = ''
            for (k,v) in ruleContent.items():
                if not v:
                    current_intent = k
                    ruleComplete = False
                    break
            # result_entites 转换成entities
            if not ruleComplete:
                currentQuestionType = 0

                result = self.intentAction(data, current_intent, None, None, None, currentQuestionType)
                if result['action']['complete'] and ruleContent.has_key(result['intentName']):
                    ruleContent[result['intentName']] = True

            return result
        return None

    #后置检查，
    def afterCheck(self,data,intent,currentQuestionType,responseJson):
        global status
        self.n.query(
            "select mark.`id` as `check`,mark.ask as question,scene.`name` as intent from robot_scene_mark as mark,robot_scene as scene where mark.id =(select `check` from robot_scene WHERE `name` = \'" + intent + "\') and mark.int_id = scene.id")
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
            if check not in historyIntentsTag:
                currentQuestionType = 3
                content = {"type": 0, "message": pre_question}
                status = {"code": 200, "msg": "触发后置意图"}
                data.append(content)
                return True
            else:
                return False

            #插入/更新意图信息
    ## 参数 existHistory、 result_entities、responseJson、history_intents
    def updateUserSceneInfo(self,intent,existHistory,result_entities,responseJson,complete):
        if existHistory:
            sql = "UPDATE history_scene_info set entities =\'"+json.dumps(result_entities)+"\',last_response_json = \'"+json.dumps(responseJson)+"\',history_intents = \'"+json.dumps(historyIntentsInfo)+"\',complete = "+str(complete)+" WHERE user_token = \'"+self.token+"\' and intent = \'"+intent+"\'"
            print(sql)
            self.n.update(sql)
        else:
            sql = "INSERT INTO history_scene_info (user_token,entities,intent,last_response_json,history_intents,complete) VALUES(\'"+self.token+"\',\'"+json.dumps(result_entities)+"\',\'"+intent+"\',\'"+json.dumps(responseJson)+"\',\'"+json.dumps(historyIntentsInfo)+"\',"+str(complete)+")"
            print(sql)
            self.n.insert(sql)

    # slot 填充
    def matchSlot(self,lastResponseJson,entities_types):
        result = {}
        lastEntitiesType = lastResponseJson['lastEntitiesType']
        for slot in lastResponseJson['action']['parameters']:
            slotType = lastEntitiesType[slot['entity']]
            for (k,v) in entities_types.items():
                if slotType == v:
                    result[k] = slot['value']
                    break

        return result

    #获取历史的所有slotType:slotValue
    def getHistorySlotsByType(self):
        slots = {}
        intents = self.historyIntent.getHistoryIntents()
        for intent in intents:
            entities = intent['responseJson']['action']['parameters']
            entities_type = intent['responseJson']['lastEntitiesType']

            for entity in entities:
                for (k,v) in entities_types.items():
                    if k == entity['entity']:
                        slots[entities_types[k]] = entity['value']
                        break

        return slots

    def getHistorySlots(self):
        params = {}
        intents = historyIntentsInfo
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
        if ruleContent.has_key(intent) and ruleContent[intent] == True:
            return True
        else:
            return False

    # 匹配历史详情，查询是否存在对应的酒店/机票信息
    def matchHistoryDetails(self,query,slot):
        global history_details
        if len(history_details) > 0 :
            for details in history_details:
                for detail in details:
                    for (k,v) in detail.items():
                        if k == slot and (query in v):
                            return True
                            break
        else:
            return False

    def resetHistoryIntent(self):
        global answer,complete,result_entities,actionJson,lastResponseJson,entities,entities_question,entities_types,ruleContent,ruleComplete,lastEntities,status,responseJson,currentQuestionType,history_details,historyIntentsInfo,historyIntentsTag
        answer = ""
        complete = False
        result_entities = {}
        actionJson = {}
        lastResponseJson = {}
        entities_question = OrderedDict()
        entities_types = {}
        ruleContent = OrderedDict()
        ruleComplete = True
        lastEntities = {}
        entities = []
        status = {}
        responseJson = {}
        currentQuestionType = 0

        pre_question = None
        curslot = None
        history_details = []
        # 历史意图
        historyIntentsInfo = []
        historyIntentsTag = []

