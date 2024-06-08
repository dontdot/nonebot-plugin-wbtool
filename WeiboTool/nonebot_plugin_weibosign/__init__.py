from nonebot import on_command, require
from nonebot.internal.matcher import Matcher
from nonebot.typing import T_State
from nonebot.internal.params import ArgStr
# from nonebot.adapters.onebot.v11 import *
from loguru import logger
from nonebot_plugin_saa import Text, TargetQQPrivate, enable_auto_select_bot

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

from .config import Config
from .sign import sign as ch_sign

enable_auto_select_bot()

wbsign = on_command("wbsign", aliases={"超话签到"})
wbsetting = on_command("wbset", aliases={"微博设置"})

@wbsign.handle()
async def _(event, matcher: Matcher):
    """
    手动签到
    """
    account = event.get_user_id()
    await sign(user_id=account, matcher=matcher)


async def sign(user_id: str, matcher: Matcher = None):
    config = Config()
    user_data = await config.load(user_id)      # {qq: {k1:v1, k2:v2}}
    one_userData = user_data[user_id]
    if not one_userData['wb_params'] or not one_userData['wb_cookie']:
        if matcher:
            await matcher.send('⚠️请配置微博相关参数，输入/wbhelp进行查询帮助')
            return
    msg = str(await ch_sign(one_userData['wb_params'], user_data))
    if matcher:
        await matcher.send(msg)
    else:
        message = Text(msg)
        target = TargetQQPrivate(user_id=int(user_id))
        await message.send_to(target=target)


@wbsetting.handle()
async def setting(event, matcher: Matcher, state: T_State):
    user_id = event.get_user_id()
    config = Config()
    user_data = await config.load(user_id)
    state['user_id'] = user_id
    state['user_data'] = user_data
    acc_set = f'当前设置账号{user_id}\n'
    acc_set += f'账号数据：{user_data}\n'
    acc_set += f'1、设置微博params\n'
    acc_set += f'2、设置微博cookie\n'
    acc_set += f'发送退出即可退出设置\n'
    await matcher.send(acc_set)

@wbsetting.got('setting_id')
async def id(event, state: T_State, setting_id=ArgStr()):
    if setting_id == '退出':
        await wbsetting.finish('已成功退出')
    elif setting_id == '1':
        await wbsetting.send(
            "请微博params：\n"
            "发送格式不带params=\n"
            "参数必须带gsid、s、c、from"
            "\n\n🚪发送“退出”即可退出"
        )
        state['setting_value'] = 'params_value'
    elif setting_id == '2':
        await wbsetting.send(
            "请微博cookie：\n"
            "发送格式不带cookie=\n"
            "参数必须带SUBP、SUB"
            "\n\n🚪发送“退出”即可退出"
        )
        state['setting_value'] = 'cookie_value'

@wbsetting.got('set_value')
async def setValue(event, state: T_State, set_value=ArgStr()):
    if set_value == '退出':
        await wbsetting.finish('已成功退出')
    user: str = state['user_id']
    user_data = state['user_data']
    if state['setting_value'] == 'params_value':
        params = str(set_value)
        if '&amp;' in params:
            params = params.replace('&amp;', ';')
        user_data[user]['wb_params'] = params
        await Config.set_data(user_data)
        await wbsetting.finish("设置微博params成功")
    elif state['setting_value'] == 'cookie_value':
        cookie = str(set_value)
        user_data[user]['wb_cookie'] = cookie
        await Config.set_data(user_data)
        await wbsetting.finish("设置微博cookie成功")

@scheduler.scheduled_job("cron",
                         hour='7',
                         minute='30',
                         id="daily_WeiboSign")
async def auto_WeiboSign():
    logger.info(f"开始执行微博自动任务")
    users_data = Config.get_data()
    users_list = list(users_data.keys())
    for account in users_list:
        await sign(user_id=account)
    logger.info(f"每日微博自动任务执行完成")
