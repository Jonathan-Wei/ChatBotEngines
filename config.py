#config.py：程序的配置
import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:

    MODEL_DB_USERNAME="root"
    MODEL_DB_PASSWORD="123456"
    MODEL_DB_PORT=3306
    MODEL_DB="chatrobot"

    PLATFORM_DB_USERNAME = "root"
    PLATFORM_DB_PASSWORD = "123456"
    PLATFORM_DB_PORT = 3306

    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    NLU_SERVER="http://localhost:5000/parse?q="
    SOLR_SERVER_URL="http://ai-test.vigortech.cn:8983/solr/chat_bot"
    MODEL_DB_HOST = "119.23.127.239"
    PLATFORM_DB_HOST=""


class TestingConfig(Config):
    MODEL_DB_HOST = "127.0.0.1"
    PLATFORM_DB_HOST = ""

class ProductionConfig(Config):
    MODEL_DB_HOST = ""
    PLATFORM_DB_HOST = ""

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}