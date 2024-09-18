import random
import re
import json
import copy
from datetime import date
from urllib.parse import unquote
import httpx
from nonebot import on_command, require
from nonebot.internal.matcher import Matcher
from nonebot.typing import T_State
from nonebot.internal.params import ArgStr
from loguru import logger
from nonebot_plugin_saa import Text, TargetQQPrivate, enable_auto_select_bot

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

class WeiboCode:
    def __init__(self, user_data: dict):
        self.params = tool.cookie_to_dict(user_data['params'].replace('&', ';')) if user_data['params'] else None
        """params: s=xxxxxx; gsid=xxxxxx; aid=xxxxxx; from=xxxxxx"""
        self.cookie = tool.cookie_to_dict(user_data['cookie'])
        self.container_id = {'原神': '100808fc439dedbb06ca5fd858848e521b8716',
                             '崩铁': '100808e1f868bf9980f09ab6908787d7eaf0f0'}
        self.ua = 'WeiboOverseas/4.4.6 (iPhone; iOS 14.0.1; Scale/2.00)'
        self.headers = {'User-Agent': self.ua}
        self.follow_data_url = 'https://api.weibo.cn/2/cardlist'
        self.sign_url = 'https://api.weibo.cn/2/page/button'
        self.event_url = 'https://m.weibo.cn/api/container/getIndex?containerid={container_id}_-_activity_list'
        self.draw_url = 'https://games.weibo.cn/prize/aj/lottery'

    @property
    async def get_ticket_id(self):
        logger.info('开始获取微博兑换码ticket_id')
        ticket_id = {}
        for key, value in self.container_id.items():
            url = self.event_url.replace('{container_id}', value)
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
            responses = response.json()
            group = tool.nested_lookup(responses, 'group', fetch_first=True)
            if group:
                ticket_id[key] = {}
                ticket_id[key]['id'] = [i
                                        for id in group
                                        for i in re.findall(r'ticket_id=(\d*)', unquote(unquote(id['scheme'])))]
                ticket_id[key]['img'] = group[random.randint(0, len(group) - 1)]['pic']
            else:
                logger.info(f'{key}超话当前没有兑换码')
        if not ticket_id:
            return "超话无兑换码活动"
        else:
            return ticket_id

    async def get_code(self, id: str):
        url = self.draw_url
        self.headers.update({
            'Referer': f'https://games.weibo.cn/prize/lottery?ua={self.ua}&from=10E2295010&ticket_id={id}&ext='
        })
        data = {
            'ext': '', 'ticket_id': id, 'aid': self.params['aid'], 'from': self.params['from']
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=data, headers=self.headers, cookies=self.cookie)
        if response.status_code == 200:
            responses = response.json()
            code = responses['data']['prize_data']['card_no'] if responses['msg'] == 'success' or responses[
                'msg'] == 'recently' else False
            if responses['msg'] == 'fail':
                responses['msg'] = responses['data']['fail_desc1']
            result = {'success': True, 'id': id, 'code': code} if code else {'success': False, 'id': id,
                                                                             'response': responses['msg']}
            return result['code'] if result['success'] else responses['msg']
        else:
            return '获取失败，请重新设置wb_cookie'

    async def get_code_list(self):
        ticket_id = await self.get_ticket_id  # 有活动则返回一个dict，没活动则返回一个str
        '''
        ticket_id = {
            '原神/崩铁': {
                'id': [],
                'img': ''
            }
        }
        '''
        if isinstance(ticket_id, dict):
            msg = ""
            code = {key: [] for key in ticket_id.keys()}
            for key, value in ticket_id.items():
                for k, v in value.items():
                    if k == 'id':
                        for item in v:
                            code[key].append(await self.get_code(item))
                    elif k == 'img':
                        img = v
            for key, values in code.items():
                msg += f"<{key}>超话兑换码：" \
                       "\n1️⃣" \
                       f"  \n{values[0]}" \
                       "\n2️⃣" \
                       f"  \n{values[1]}" \
                       "\n3️⃣" \
                       f"  \n{values[2]}"
            return msg, img
        else:
            return ticket_id