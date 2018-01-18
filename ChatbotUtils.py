#-*- coding=utf-8 -*-
import sys
import datetime
reload(sys)
sys.setdefaultencoding('utf-8')

class ChatbotUtils:

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
            resultDate = dateStr
        return resultDate

if __name__ == '__main__':
    utils = ChatbotUtils()
    print(utils.toGetDate('下周日'))

