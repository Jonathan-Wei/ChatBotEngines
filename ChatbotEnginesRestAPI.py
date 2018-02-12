#-*- coding=utf-8 -*-
import datetime
from flask import Flask,session, redirect, url_for, escape, request, g
from config import config   #加载配置文件
from ChatbotEngines import *
from ChatbotUtils import *
from rasa_nlu.converters import load_data
from rasa_nlu.config import RasaNLUConfig
from rasa_nlu.model import Trainer
import json
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

FLASK_CONFIG='development' #运行环境（开发环境）

app = Flask(__name__)
app.config.from_object(config[FLASK_CONFIG])
config[FLASK_CONFIG].init_app(app)

users = UsersInfo()

@app.route('/api/<line>')
def chat(line):
    g._users = users

    utils = ChatbotUtils()

    if utils.simulation(line) is not None:
        return json.dumps(utils.simulation(line))
    token = request.headers['token']
    engines = ChatbotEngines(app, token, "agentId")
    if u'清除历史记录' == line:
        engines.delete()
        result = json.dumps({'status':{"code": 200, "msg": "触发前置意图"},'data': [{"type":0,"message":u"清除成功"}]})
    else:
        result = engines.request(line)
    return result


@app.route('/model/<appName>/<trainingData>')
def chatbot(appName,trainingData):
    model_directory = ""
    #获取存储路径图
    dataPath = app.config['NLU_SERVER_TRAINING_DATA_PATH']
    #将配置生成配置文件
    training_data_file = dataPath + appName + "_training.json"
    trainingData = json.loads(trainingData)
    with open(training_data_file, 'w') as f:
        json.dump(trainingData, f)

    try:
        #训练模型
        training_data = load_data(training_data_file)
        trainer = Trainer(RasaNLUConfig(app.config['NLU_SERVER_TRAINER_PATH']),skip_validation=True)
        trainer.train(training_data)
        #设置模型存储路径及名称
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        fixed_model_name = appName + "_" + timestamp
        model_directory = trainer.persist(app.config['NLU_MODEL_STORE_PATH'],project_name=appName,fixed_model_name=fixed_model_name)
        print(model_directory)
        #persist(self, path, persistor=None, project_name=None,
                #fixed_model_name=None):
    except Exception as e:
        print("Error: 模型训练失败"+e.message)
    else:
        print("Success: 模型训练成功")

    return model_directory


if __name__ == '__main__':
    app.run(debug=False,port=5888,host='0.0.0.0')
