from flask import Flask
from ChatbotEngines import *
from ChatbotMySQL import *

app = Flask(__name__)


@app.route('/api/<line>')
def hello_world(line):

    engines = ChatbotEngines("sessionId", "agentId")
    result = engines.request(line)
    return result


if __name__ == '__main__':
    app.run(debug=False,port=5888,host='0.0.0.0')
