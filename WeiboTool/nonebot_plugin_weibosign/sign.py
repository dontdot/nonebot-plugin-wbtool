import httpx
import asyncio
import json
import re
import copy
from .config import Config
from datetime import date


async def format_chaohua_data(data: list):
    '''
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
    '''

    #去除杂项字典
    data = [ch for ch in data if ch.get('card_type') == '8']
    CHAOHUA_list = []
    for onedata in data:
        ch_id = re.findall("(?<=containerid=).*?(?=&)", onedata['scheme'])
        one_dict = {
            'title_sub': onedata['title_sub'],
            'id': ch_id[0],
            'is_sign': onedata['buttons'][0]['name']  # '已签' / '签到'
        }
        CHAOHUA_list.append(one_dict)
    return CHAOHUA_list



async def ch_list(params_data: dict, user_data: dict):

    try:
        url = 'https://api.weibo.cn/2/cardlist?'
        params = {
            "containerid": "100803_-_followsuper",
            "fid": "100803_-_followsuper",
            "since_id": '',
            "cout": 20,
        }
        params.update(params_data)
        headers = {
            "User-Agent": "Mi+10_12_WeiboIntlAndroid_6020",
            "Host": "api.weibo.cn"
        }
        for k, v in user_data.items():
            cookies = Config.cookie_to_dict(v['wb_cookie'])
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, params=params, cookies=cookies)
            json_chdata = json.load(res)['cards'][0]['card_group']
            list_data = await format_chaohua_data(json_chdata)
            v['CHdata_list'] = list_data
        await Config.set_data(user_data)
        return list_data
    except KeyError:
        return '找不到超话列表'
    except IndexError:
        return '超话列表为空'
    except Exception as e:
        # print(f'{type(e)}: {e}')
        return  e

async def sign(param: str, user_data: dict):

    url = 'https://api.weibo.cn/2/page/button'
    request_url = 'http://i.huati.weibo.com/mobile/super/active_checkin?pageid={containerid}'
    headers = {
        "User-Agent": "Mi+10_12_WeiboIntlAndroid_6020",
        'Referer': 'https://m.weibo.cn'
    }

    param_d = Config.cookie_to_dict(param)

    params = {
        "gsid": param_d['gsid'] if 'gsid' in param_d else None,        # 账号身份验证
        "s": param_d['s'] if 's' in param_d else None,                 # 校验参数
        "from": param_d['from'] if 'from' in param_d else None,        # 客户端身份验证
        "c": param_d['c'] if 'c' in param_d else None,                 # 客户端身份验证
        "aid": param_d['aid'] if 'aid' in param_d else None,           # 作用未知
    }

    msg = f'{date.today()}\n' \
            '微博超话签到：\n'
    try:
        chaohua_list = await ch_list(params, user_data)
        if not isinstance(chaohua_list, list):
            return f'签到失败请重新签到\n{chaohua_list}'
        for ch in chaohua_list:
            params_copy = copy.deepcopy(params)
            if ch['is_sign'] == '签到':
                params_copy['request_url'] = request_url.format(containerid=ch['id'])
                async with httpx.AsyncClient() as client:
                    res = await client.get(url, headers=headers, params=params_copy, timeout=10)
                res_data = json.loads(res.text)
                if 'msg' in res_data and 'errmsg' not in res_data:      # 今日首次签到成功                
                    msg += f"{ch['title_sub']}  ✅\n"
                elif 'errmsg' in res_data :                             # 签到出错
                    # msg = f"{res_data['errmsg']}\n"
                    msg += f"{ch['title_sub']}  ❌\n"
                    msg += f"--{res_data['errmsg']}\n"
            elif ch['is_sign'] == '已签':                               # 今日再次进行签到，且之前已经签到成功
                msg += f"{ch['title_sub']}  ✅\n"
        return msg
    except Exception as e:
        return f'签到失败请重新签到,{e}'

# if __name__ == "__main__" :           # 留备云函数用
#     asyncio.run(sign())