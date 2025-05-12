import os

class Config:
    API_ID = int(os.environ.get("API_ID", "14853951"))
    API_HASH = os.environ.get("API_HASH", "0a33bc287078d4dace12aaecc8e73545")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "7845318227:AAGfr0cikK92HY-DhIGMVTD3L0VeaKktUp8")

    BOT_USERNAME = os.environ.get("BOT_USERNAME", "CyberFilterBot")
    BOT_NAME = os.environ.get("BOT_NAME", "Auto Filter Bot")

    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1002614983879"))
    DB_CHANNEL = int(os.environ.get("DB_CHANNEL", "-1002511163521"))
    OWNER_ID = int(os.environ.get("OWNER_ID", "6887303054"))

    MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://CyberBunny:Bunny2008@cyberbunny.5yyorwj.mongodb.net/?retryWrites=true&w=majority&appName=CyberBunny")

    # Optional settings
    START_PIC = os.environ.get("START_PIC", "")
