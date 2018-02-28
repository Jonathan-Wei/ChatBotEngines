#-*- coding=utf-8 -*-
import sys
import datetime
import re
import json
reload(sys)
import logging
sys.setdefaultencoding('utf-8')

logger = logging.getLogger(__name__)

cityJson = None
citys = []
areas = {}

class ChatbotUtils:

    def __init__(self):
        global cityJson

        if cityJson is None:
            with open("./city.json", 'r') as load_f:
                cityJson = json.load(load_f)

            if cityJson is not None:
                for item in cityJson:
                    for city in item['city']:
                        citys.append(city['name'])
                        areas[city['name']] = city['area']


    def listToMap(self,params):
        result = {}
        for item in params:
            result[item['entity']]=item['value']

        return result

    def toGetDate(self,dateStr):
        resultDate = ''
        today = datetime.date.today()  # 获取当前日期, 因为要求时分秒为0, 所以不要求时间
        weekday = today.weekday()  # 获取当前周的排序, 周一为0, 周日为6
        monday_delta = datetime.timedelta(weekday)  # 当前日期距离周一的时间差
        sunday_delta = datetime.timedelta(7 - weekday)  # 当前日期距离下周一的时间差
        monday = today - monday_delta  # 获取这周一日期
        next_monday = today + sunday_delta  # 获取下周一日期

        if dateStr == '今天':
            resultDate = today
        elif dateStr == '明天':
            resultDate = today + datetime.timedelta(1)
        elif dateStr == '后天':
            resultDate = today + datetime.timedelta(2)
        elif dateStr == '大后天':
            resultDate = today + datetime.timedelta(3)
        elif dateStr =='下周一' or dateStr =='下星期一' :
            resultDate = next_monday
        elif dateStr == '下周二' or dateStr =='下星期二':
            resultDate = today + datetime.timedelta(7 - weekday + 1)

        elif dateStr == '下周三' or dateStr =='下星期三':
            resultDate = today + datetime.timedelta(7 - weekday + 2)

        elif dateStr == '下周四' or dateStr =='下星期四':
            resultDate = today + datetime.timedelta(7 - weekday + 3)

        elif dateStr == '下周五' or dateStr =='下星期五':
            resultDate = today + datetime.timedelta(7 - weekday + 4)

        elif dateStr == '下周六' or dateStr =='下星期六':
            resultDate = today + datetime.timedelta(7 - weekday + 5)

        elif dateStr == '下周日' or dateStr =='下星期日' or dateStr =='下星期天' or dateStr =='下周天':
            resultDate = today + datetime.timedelta(7 - weekday + 6)
        elif dateStr == '周一' or dateStr == '星期一':
            resultDate = monday

        elif dateStr == '周二' or dateStr =='星期二':
            resultDate = today - datetime.timedelta(weekday + 1)
        elif dateStr == '周三' or dateStr == '星期三':
            resultDate = today - datetime.timedelta(weekday + 2)
        elif dateStr == '周四' or dateStr =='星期四':
            resultDate = today - datetime.timedelta(weekday + 3)
        elif dateStr == '周五' or dateStr =='星期五':
            resultDate =  today - datetime.timedelta(weekday + 4)
        elif dateStr == '周六' or dateStr =='星期六':
            resultDate = today - datetime.timedelta(weekday + 5)
        elif dateStr == '周日' or dateStr =='星期日' or dateStr =='星期天' or dateStr =='周天':
            resultDate = today - datetime.timedelta(weekday + 6)
        else:
            return None
            #resultDate = dateStr
        return resultDate

    def matchCity(self,city):
        if city in citys:
            return True
        else:
            for item in citys:
                if city in item:
                    return True

            return False

    def matchAreaByCity(self,city,area):
        if city is None:
            for (k,v) in areas.items():
                for item in v:
                    if area == item :
                        return True
        else:
            if city in citys:
                areaArray = areas[city]
                if area in areaArray:
                    return True
                else:
                    return False
            else:
                for (k,v) in areas[city]:
                    if city in k:
                        if area in v:
                            return True
                return False

    def matchComfirm(self,comfirm):
        if comfirm == '是的' or comfirm == '对的' or comfirm =='对' or comfirm == '是' or comfirm == '好' or comfirm =='好的' or comfirm == '嗯' or comfirm == 'ok':
            return True
        elif comfirm == '不用' or comfirm == '不需要' or comfirm =='不了' or comfirm == '不' or comfirm == 'no' or comfirm == '不确定':
            return False
        else:
            return None

    def matchSlot(self):
        None

    def weatherConvert(self,details):
        resultDetails = []
        for detail in details:
            if detail['weather'] == '晴':
                detail['weather'] = 1
            elif detail['weather'] == '阴':
                detail['weather'] = 2
            elif detail['weather'] == '多云':
                detail['weather'] = 3
            elif detail['weather'] == '小雨':
                detail['weather'] = 4
            elif detail['weather'] == '中到大雨':
                detail['weather'] = 5
            elif detail['weather'] == '雷阵雨':
                detail['weather'] = 6

            resultDetails.append(detail)

        return resultDetails

    def simulation(self,type):
        if type == '制度':
            return {
                "status":{
                    "code":200,
                    "msg":"您的APP不是最新版本，请升级！"
                },
                "data":[{
                        "type":"11",  #列表项
                        "message":"公司制度",
                        "content":{
                            "title":"公司制度",
                            "details":[
                                {"msg":"作息时间"},
                                {"msg":"考勤规则"},
                                {"msg":"考勤规律"},
                                {"msg":"矿工定义"}
                            ]
                        }
                    }
                ]
            }
        elif type == '给我一张图片':
            return {
                "status":{
                    "code": 200,
                    "msg": "您的APP不是最新版本，请升级！"
                },
                "data":[{
                    "type":"1",
                    "fileName":"five_month_report.jpg",
                    "thumbnailUrl":"http://ai-test.vigortech.cn:5888/static/WechatIMG725.png",
                    "url":"http://ai-test.vigortech.cn:5888/static/WechatIMG725.png",
                    "message":"五月份报表图"
		        }]
            }
        elif type == '给我一份pdf文档':
            return {
                "status": {
                    "code": 200,
                    "msg": "您的APP不是最新版本，请升级！"
                },
                "data": [{
                    "type":"2",
                    "fileName":"考勤制度.pdf",
                    "url":"http://ai-test.vigortech.cn:5888/static/50YearsDataScience.pdf",
                    "message":"考勤制度文档"
                }]
            }
        elif type == '给我一份doc文档':
            return {
                "status": {
                    "code": 200,
                    "msg": "您的APP不是最新版本，请升级！"
                },
                "data": [{
                    "type":"3",
                    "fileName":"考勤制度.doc",
                    "url":"http://ai-test.vigortech.cn:5888/static/微服务目前接口文档.pptx",
                    "message":"考勤制度文档"
                }]
            }
        elif type == '给我一份ppt文档':
            return {
                "status": {
                    "code": 200,
                    "msg": "您的APP不是最新版本，请升级！"
                },
                "data": [{
                    "type":"4",
                    "fileName":"考勤制度.ppt",
                    "url":"http://ai-test.vigortech.cn:5888/static/蛇口复古装饰品公司.pptx",
                    "message":"考勤制度文档"
                }]
            }
        elif type == '给我一份excel文档':
            return {
                "status": {
                    "code": 200,
                    "msg": "您的APP不是最新版本，请升级！"
                },
                "data": [{
                    "type":"5",
                    "fileName":"考勤制度.xls",
                    "url":"http://ai-test.vigortech.cn:5888/static/实时流数据采集问题列表.xlsx",
                    "message":"考勤制度文档"
                }]
            }

    def RegularMatchUrl(url):
        pattern = re.match(
            r'(http|ftp|https):\/\/[\w\-_]+(\.[\w\-_]+)+([\w\-\.,@?^=%&amp;:/~\+#]*[\w\-\@?^=%&amp;/~\+#])?', url,
            re.IGNORECASE)
        if pattern:
            print url
            return True
        else:
            print "invalid url"
            return False



if __name__ == '__main__':
    utils = ChatbotUtils()
    #print(datetime.strptime("1月10号", "%m月%d号"))
    print(utils.toGetDate('"1月10号"'))
    #print('8,72'.split(","))

