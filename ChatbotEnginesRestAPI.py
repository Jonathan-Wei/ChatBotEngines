from flask import Flask
from config import config   #加载配置文件
from ChatbotEngines import *

FLASK_CONFIG='development' #运行环境（开发环境）

app = Flask(__name__)
app.config.from_object(config[FLASK_CONFIG])
config[FLASK_CONFIG].init_app(app)

@app.route('/api/<line>')
def hello_world(line):

    engines = ChatbotEngines(app,"sessionId", "agentId")
    result = engines.request(line)
    return result


if __name__ == '__main__':
    app.run(debug=False,port=5888,host='0.0.0.0')
