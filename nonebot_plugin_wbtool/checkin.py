import httpx
import asyncio
import json
import re
import copy
import time
from datetime import date
from typing import Dict, Any
from loguru import logger
from .config import Tool, Config


class WeiboCheckIn:

    @staticmethod
    async def format_chaohua_data(data: list):
        """
        单个超话社区格式：
        {
            "card_type": "8",
            "itemid": "follow_super_follow_1_0",
            "scheme": "sinaweibo://pageinfo?containerid=100808e1f868bf9980f09ab6908787d7eaf0f0&extparam=%E5%B4%A9%E5%9D%8F%E6%98%9F%E7%A9%B9%E9%93%81%E9%81%93%23tabbar_follow%3D5032140432213196",
            "title_sub": "崩坏星穹铁道",
            "pic": "https://wx4.sinaimg.cn/thumbnail/008lgPsGly8hph0wdgemlj30sg0sgtcv.jpg",
            "pic_corner_radius": 6,
            "name_font_size": 16,
            "pic_size": 58,
            "top_padding": 12,
            "bottom_padding": 12,
            "buttons": [
                {
                    "type": "default",
                    "params": {
                        "action": "/2/page/button?request_url=http%3A%2F%2Fi.huati.weibo.com%2Fmobile%2Fsuper%2Factive_fcheckin%3Fpageid%3D100808e1f868bf9980f09ab6908787d7eaf0f0%26container_id%3D100808e1f868bf9980f09ab6908787d7eaf0f0%26scheme_type%3D1%26source%3Dfollow"
                    },
                    "actionlog": {
                        "act_code": 3142,
                        "fid": "100803_-_followsuper"
                    },
                    "pic": "https://h5.sinaimg.cn/upload/100/582/2020/04/14/supertopic_fans_icon_register.png",
                    "name": "签到"
                }
            ],
            "title_flag_pic": "https://n.sinaimg.cn/default/944aebbe/20220831/active_level_v.png",
            "desc1": "等级 LV.7",
            "desc2": "#崩坏星穹铁道[超话]##崩坏星穹铁道# \n哈哈哈哈，米哈游，你好事做尽啊。哈哈哈哈 ​",
            "openurl": "",
            "cleaned": true
        },
        """
        # 去除杂项字典
        data = [ch for ch in data if ch.get('card_type') == '8']
        chaohua_list = []
        for onedata in data:
            try:
                ch_id = re.findall("(?<=containerid=)[^&]+", onedata['scheme'])
                one_dict = {
                    'title_sub': onedata.get('title_sub', None),
                    'id': ch_id[0] if ch_id else None,
                    'is_sign': onedata['buttons'][0]['name'] if onedata.get('buttons') else None # '已签' / '签到'
                }
                chaohua_list.append(one_dict)
            except Exception as e:
                logger.error(f"{type(e)}:{e}")
        return chaohua_list

    @classmethod
    async def update_wbcookies(cls, params_data: dict):
        try:
            headers = {
                'Host': 'api.weibo.cn',
                'x-engine-type': '114.0.5735.246',
                'user-agent': 'Mi 10_12_weibo_14.2.2_android',
            }
            params_data['ua'] = 'Mi+10_12_WeiboIntlAndroid_6020'
            async with httpx.AsyncClient() as client:
                res = await client.get('https://api.weibo.cn/2/account/getcookie', headers=headers, params=params_data)
            json_res = res.json()['cookie']['.weibo.com'].replace('\n',';')
            new_cookie = Tool.dict_to_cookie(json_res)
            return new_cookie
        except Exception as e:
            logger.error(f'{type(e)}: {e}')
            return e

    @classmethod
    async def ch_list(cls, params_data: dict, wb_userdata: dict):

        try:
            url = 'https://api.weibo.cn/2/cardlist?'
            params = {
                "containerid": "100803_-_followsuper",
                "fid": "100803_-_followsuper",
                "since_id": '',
                "cout": 20,
            }
            params.update(params_data)
            params['ul_ctime'] = int(time.time() * 1000)
            headers = {
                "User-Agent": "Mi+10_12_WeiboIntlAndroid_6020",
                "Host": "api.weibo.cn"
            }
            cookies = Tool.cookie_to_dict(wb_userdata['cookie'])
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, params=params, cookies=cookies)
            json_chdata = res.json()['cards'][0]['card_group']
            list_data = await cls.format_chaohua_data(json_chdata)
            wb_userdata['CHdata_list'] = list_data
            wb_userdata['cookie'] = await cls.update_wbcookies(params_data)
            Config.write_plugin_data()
            return list_data
        except KeyError:
            return '找不到超话列表'
        except IndexError:
            return '超话列表为空'
        except ValueError:
            return '可能是微博相关参数出错，请重新设置'
        except Exception as e:
            # print(f'{type(e)}: {e}')
            return e

    @classmethod
    async def CheckIn(cls, wb_userdata: dict):

        url = 'https://api.weibo.cn/2/page/button'
        request_url = 'http://i.huati.weibo.com/mobile/super/active_checkin?pageid={containerid}'
        headers = {
            "User-Agent": "Mi+10_12_WeiboIntlAndroid_6020",
            'Referer': 'https://m.weibo.cn'
        }

        param_d = Tool.cookie_to_dict(wb_userdata['params'])
        cookie = Tool.cookie_to_dict(wb_userdata['cookie'])

        params: Dict[str, Any] = {
            "gsid": None,  # 账号身份验证
            "s": None,  # 校验参数
            "from": None,  # 客户端身份验证
            "c": None,  # 客户端身份验证
            "aid": None,  # 作用未知
            "ua": "Xiaomi-Mi%2010__weibo__14.2.2__android__android12"
        }
        params.update(param_d)

        msg = f'{date.today()}\n' \
              '微博超话签到：\n'
        try:
            chaohua_list = await WeiboCheckIn.ch_list(params, wb_userdata)
            if not isinstance(chaohua_list, list):
                return f'签到失败请重新签到\n{chaohua_list}'
            is_geetest = False
            for ch in chaohua_list:
                if is_geetest:
                    break
                params_copy = copy.deepcopy(params)
                if ch['is_sign'] == '签到':
                    params_copy['request_url'] = request_url.format(containerid=ch['id'])
                    params_copy['ul_ctime'] = int(time.time() * 1000)
                    pd = True
                    while pd:
                        async with httpx.AsyncClient() as client:
                            res = await client.get(url, headers=headers, cookies=cookie, params=params_copy, timeout=10)
                        res_data = json.loads(res.text)
                        logger.info(f'微博签到返回：{res_data}')
                        if str(res_data.get('result')) == '402004':
                            msg += '点击链接进行验证后再次签到\n'
                            msg += res_data.get('scheme')
                            is_geetest = True
                            break
                        elif str(res_data.get('errno')) == '402003':
                            continue
                        elif str(res_data.get('result')) == '1':
                            msg += f"{ch['title_sub']}  ✅\n"
                            pd = False
                        else:
                            msg += f"{ch['title_sub']}  ❌\n"
                            msg += f"--{res_data['errmsg'] if res_data.get('errmsg') else res_data['msg']}\n"
                            pd = False
                elif ch['is_sign'] == '已签':  # 今日再次进行签到，且之前已经签到成功
                    msg += f"{ch['title_sub']}  ✅\n"
            return msg
        except Exception as e:
            return f'签到失败请重新签到\n{type(e).__name__}:{e}'

# if __name__ == "__main__" :           # 留备云函数用
#     asyncio.run(sign())