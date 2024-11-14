import nonebot
from nonebot import require
from nonebot.plugin import PluginMetadata

require("nonebot_plugin_saa")
require("nonebot_plugin_apscheduler")

from typing import (Union, Iterable)
from nonebot import on_command, require
from nonebot.adapters.onebot.v11 import MessageSegment 
from nonebot.internal.matcher import Matcher

from loguru import logger
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_saa import Image

from .sdk import WeiboCdk
from .config import *
from .setting import *
from .checkin import WeiboCheckIn


__plugin_meta__ = PluginMetadata(
    name="微博超话工具",
    description="每日手动/自动进行超话签到，领取超话签到的CDK奖励",
    type="application",
    supported_adapters={"~onebot.v11", "~qq"},
    usage=
    f"wb签到 -- 手动超话签到\n"
    f"wbcdk -- 发送已领取的CDK给用户\n"
    f"wbset -- 设置超话签到/领取CDK的账户参数",
)


manually_weibo_sign_check = on_command('wb签到', priority=5, block=True)

@manually_weibo_sign_check.handle()
async def weibo_sign(event: Union[GeneralMessageEvent], matcher: Matcher):
    user_id = event.get_user_id()
    user = Config.plugin_data.users.get(user_id)
    await weibo_checkin_check(user=user, user_ids=[user_id], matcher=matcher)


async def weibo_checkin_check(user: UserData, user_ids: Iterable[str], matcher: Matcher = None):
    """
    :param user: 用户对象
    :param user_ids: 发送通知的所有用户ID
    :param matcher: nonebot ``Matcher``
    """
    if user.enable_weibo:
        for user_data in user.weibo:
            msg = await WeiboCheckIn.CheckIn(user_data)
            if matcher:
                await matcher.send(message=msg)
            else:
                for user_id in user_ids:
                    await send_private_msg(user_id=user_id, message=msg)
    else:
        message = "未开启微博自动签到功能"
        if matcher:
            await matcher.send(message)
            
async def weibo_cdk_check(user: UserData, user_ids: Iterable[str], mode=0, matcher: Matcher = None):
    """
    是否开启微博兑换码功能的函数，并发送给用户任务执行消息。

    :param user: 用户对象
    :param user_ids: 发送通知的所有用户ID
    :param matcher: nonebot ``Matcher``
    """

    if user.enable_weibo:
        # account = UserAccount(account) 
        for user_data in user.weibo:
            msg, img = None, None
            start = True
            weibo = WeiboCdk(user_data)
            ticket_id = await weibo.get_ticket_id
            if mode == 1:
                if isinstance(ticket_id, dict):
                    await weibo_checkin_check(user=user, user_ids=user_ids)
                else:
                    start = False
            if start:
                try:
                    for key, value in ticket_id.items():
                        one_id = {key: value}
                        result = await weibo.get_code_list(one_id)
                        if isinstance(result, tuple):
                            msg, img = result
                        else:
                            msg = result
                        if matcher:
                            if img:
                                onebot_img_msg = MessageSegment.image(await get_file(img))
                                messages = msg + onebot_img_msg
                            else:
                                messages = msg
                            await matcher.send(messages)
                        else:
                            if img and '无' not in msg:
                                saa_img = Image(await get_file(img))
                                messages = msg + saa_img
                                for user_id in user_ids:
                                    logger.info(f"检测到当前超话有兑换码，正在给{user_id}推送信息中")
                                    await send_private_msg(user_id=user_id, message=messages)
                except Exception:
                    pass
    else:
        message = "未开启微博兑换功能"
        if matcher:
            await matcher.send(message)

async def send_qqGroup(bot, event, msgs_list):
    def build_forward_msg(msg):
        #受限于LLOnebot，合并转发消息只能使用bot的身份无法自定义
        return {"type": "node", "data": {"nickname": "流萤", "user_id": "114514", "content": msg}}  
    messages = [build_forward_msg(msg) for msg in msgs_list]
    await bot.call_api("send_group_msg", group_id=event.group_id, message={"type": "at","data": {"qq": str(event.user_id)}})
    await bot.call_api("send_group_forward_msg", group_id=event.group_id, messages=messages)


manually_weibo_help = on_command('wbhelp', priority=5, block=True)

@manually_weibo_help.handle()
async def setting(event, matcher: Matcher):
    await manually_weibo_help.finish(
                f"{PLUGIN.metadata.name}\n" 
                f"{PLUGIN.metadata.description}\n"
                "具体用法：\n"
                f"{PLUGIN.metadata.usage}\n"
            )


@scheduler.scheduled_job("cron",
                         hour='7',
                         minute='30',
                         id="daily_WeiboSign")
async def auto_WeiboSign():
    logger.info(f"开始执行微博自动任务")
    users_data = Tool.get_data()
    users_list = list(users_data.keys())
    for account in users_list:
        await weibo_cdk_check(user_id=account)
    logger.info(f"每日微博自动任务执行完成")