import os
import pathlib
import json


user_data = {
    'wb_params': '',
    'wb_cookie': '',
    'CHdata_list': []
}

class Config():

    @staticmethod
    def cookie_to_dict(cookie):
        if cookie and '&' in cookie:
            cookie = cookie.replace('&', ';')
        if cookie and '=' in cookie:
            cookie = dict([line.strip().split('=', 1) for line in cookie.split(';')])
        return cookie

    @staticmethod
    def get_data():
        if not os.path.exists('data/weibo_sign/weibo_config.json'):
            pathlib.Path('data/weibo_sign').mkdir(parents=True, exist_ok=True)
            users: dict = {}
            with open('data/weibo_sign/weibo_config.json', 'w', encoding='utf-8') as f:
                json.dump(users, f, indent=4)
        with open('data/weibo_sign/weibo_config.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    
    @staticmethod
    async def set_data(user_data: dict):
        with open('data/weibo_sign/weibo_config.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        data.update(user_data)
        with open('data/weibo_sign/weibo_config.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    @staticmethod
    async def load(account: str):
        userdata = Config.get_data()
        if account not in userdata:
            new_accDate = {account: user_data}
            userdata.update(new_accDate)
            OneUser_data = new_accDate
        else:
            OneUser_data = {account: userdata[account]}
        return OneUser_data
