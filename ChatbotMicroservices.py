#-*- coding=utf-8 -*-
import sys
import pysolr
import requests
import json
from ChatbotUtils import *
reload(sys)
sys.setdefaultencoding('utf-8')

class ChatbotMicroservices:

    def __init__(self):#,app):
        self.utils = ChatbotUtils()
        self.microservice_host="119.23.175.190"  #172.18.84.72 #app.config['MICROSERVICE_HOST']
        self.microservice_port="8008"#app.config['MICROSERVICE_PORT']
        self.solrUrl = "http://ai-test.vigortech.cn:8983/solr/chat_bot"#app.config['SOLR_SERVER_URL']

    def route(self,intent,params):
        responseJson = {}
        url = "http://" + self.microservice_host+":"+self.microservice_port
        if intent == '天气':
            url=url+"/travel/queryWheatherInfo"
            type = 6
            message = "天气信息"
            title = params['city']
            requestParams = {
                "city":params['city']
            }
            details = self.requst(url,requestParams).json()['data'][0:7]

            responseJson['type'] = type
            responseJson['message'] = message
            responseJson['content'] = {
                "title":title,
                "details":details
            }
            return responseJson
        elif intent == '出差申请':
            url = url + "/travel/insertOAInfo"
            type = 0
            requestParams = {
                'businessTrip':'项目交流',
                'employeeName':'mao',
                'travelPlace':params['address'],
                'travelDate':'2018-01-20'
            }
            details = self.requst(url, requestParams).json()
            if details['code'] == 0:
                message = details['message']
                responseJson['type'] = type
                responseJson['message'] = message
                return responseJson
        elif intent == '酒店查询':
            url = url + "/travel/queryHotelInfo"
            type = 7
            message = "酒店信息"
            title = params['hotelCity'] +" "+params['hotelArea']
            details = self.requst(url, params).json()['data'][0:5]

            resultDetails = []
            i = 0
            for detail in details:
                detail['date'] = '2018-01-19'
                if i ==0 :
                    detail['haveStayed'] = 1
                else:
                    detail['haveStayed'] = 0
                resultDetails.append(detail)
                i=i+1

            responseJson['type'] = type
            responseJson['message'] = message
            responseJson['content'] = {
                "title": title,
                "details": details
            }
            return responseJson
        elif intent == '航班查询':
            url = url+"/travel/queryFlightInfo"
            type = 8
            message = "航班信息"
            params['departureDate'] = '2018-01-16'
            details = self.requst(url, params).json()['data'][0:5]
            title = params['departureCity']+"-"+params['terminusCity']
            responseJson['type'] = type
            responseJson['message'] = message
            responseJson['content'] = {
                "title": title,
                "details": details
            }
            return responseJson
        elif intent == '订购机票':
            #customerNumber=12345678998&customerName=hewei&departureDate=2017-01-21 17:25:00&flightNumber=CZ3568
            url = url + "/travel/inserAirfareOrder"
            type = 0
            r = self.requst(url, params).json()
            responseJson['type'] = type
            responseJson['message'] = r['message']+"订单序号："+r['orderSerial']
            return responseJson
        elif intent == '订购酒店':
            # hotelName = 深圳景田酒店&customerNumber=12691999664&customerName=qinbojing2& arrivalDate=2018-01-17
            url = url + "/travel/insertHoteOrder"
            r = self.requst(url, params).json()
            type = 0
            responseJson['type'] = type
            responseJson['message'] = r['message'] + "订单序号：" + r['orderSerial']
            return responseJson
        else:
            question = params['question']
            return self.querySolr(question)

    def requst(self,url,params):
        paramsStr=""
        for (k,v) in params.items():
            paramsStr = paramsStr + k.encode(sys.getdefaultencoding())+"="+str(v.encode(sys.getdefaultencoding()))+"&"

        paramsStr=paramsStr[0:-1]
        url = url+"?"+paramsStr
        print(url)
        r=requests.get(url)
        return r


    def querySolr(self, question):

        s = pysolr.Solr(self.solrUrl,timeout=10)
        response = s.search(question)#,**{
            #'df':'txt_content_cn'
        #}

        print(len(response))
        if len(response) == 0:
            return None

        # Print the name of each document.
        answer = response.docs[0]
        type = answer['info_type_s']

        if type == 'img':
            data = {
                "fileName":answer['img_name_s'],
                "type":1,
                "thumbnailUrl":answer['file_path_s'],
                "url":"",
                "message":answer['answer']}
        elif type == 'file' :
            fileName = answer['file_name_s']
            fileType = 0
            if answer['file_type_s'] == 'pdf':
               fileType = 2
            elif answer['file_type_s'] == 'doc':
                fileType = 3
            elif answer['file_type_s'] == 'ppt':
                fileType = 4
            elif answer['file_type_s'] == 'excel':
                fileType = 5

            data = {
                "fileName":fileName,
                "type":fileType,
                "thumbnailUrl":"",
                "url":answer['file_path_s'],
                "message":answer['answer']}
        elif type == 'txt':
            data = {
                "fileName":"",
                "type":0,
                "thumbnailUrl":"",
                "url":'',
                "message":answer['txt_content_cn']
            }
        return data


if __name__ == '__main__':
    mic = ChatbotMicroservices()
    print(json.dumps(mic.route("出差申请",{"question":"我明天要去北京出差"})))
