import asyncio
from pathlib import Path
import json
from typing import Optional, Dict
from pydantic import BaseModel, ValidationError
from loguru import logger
from json import JSONDecodeError
import httpx

from typing import (Dict, Union, Optional, Tuple, Any)

import nonebot.log
from nonebot import Adapter, Bot

from nonebot_plugin_saa import MessageSegmentFactory, Text, AggregatedMessageFactory, TargetQQPrivate, \
    TargetQQGuildDirect, enable_auto_select_bot

from nonebot.adapters.onebot.v11 import MessageEvent as OneBotV11MessageEvent, PrivateMessageEvent, GroupMessageEvent, \
    Adapter as OneBotV11Adapter, Bot as OneBotV11Bot
from nonebot.adapters.qq import DirectMessageCreateEvent, MessageCreateEvent, \
    Adapter as QQGuildAdapter, Bot as QQGuildBot, MessageEvent


# 启用 nonebot-plugin-send-anything-anywhere 的自动选择 Bot 功能
enable_auto_select_bot()

GeneralMessageEvent = OneBotV11MessageEvent, MessageCreateEvent, DirectMessageCreateEvent, MessageEvent
"""消息事件类型"""

user_data = {
    'name': '',
    'wb_params': '',
    'wb_cookie': '',
    'CHdata_list': []
}

root_path = Path(__name__).parent.absolute()
'''NoneBot2 机器人根目录'''

data_path = root_path / "data" / "nonebot-plugin-weibosign"
'''插件数据保存目录'''

plugin_data_path = data_path / "weibo_data.json"

class Tool():

    @staticmethod
    def cookie_to_dict(cookie):
        if cookie:
            cookie = dict([line.strip().split('=', 1) if '=' in line else (line.strip(), '') for line in cookie.split(';')])
            return cookie
        return {}
    
    @classmethod
    def dict_to_cookie(cls, cookie):
        print(type(cookie),cookie)
        if not isinstance(cookie, dict):
            cookie_dict = cls.cookie_to_dict(cookie)
        return '; '.join(f'{key}={value}' for key, value in cookie_dict.items())
    
    @classmethod
    def nested_lookup(cls, obj, key, with_keys=False, fetch_first=False):
        result = list(cls._nested_lookup(obj, key, with_keys=with_keys))
        if with_keys:
            values = [v for k, v in cls._nested_lookup(obj, key, with_keys=with_keys)]
            result = {key: values}
        if fetch_first:
            result = result[0] if result else result
        return result

    @classmethod
    def _nested_lookup(cls, obj, key, with_keys=False):
        if isinstance(obj, list):
            for i in obj:
                yield from cls._nested_lookup(i, key, with_keys=with_keys)
        if isinstance(obj, dict):
            for k, v in obj.items():
                if key == k:
                    if with_keys:
                        yield k, v
                    else:
                        yield v
                if isinstance(v, (list, dict)):
                    yield from cls._nested_lookup(v, key, with_keys=with_keys)

    @staticmethod
    def weibo_user_dict(data):
        return dict([line.strip().split(':', 1) for line in data.split('|')])

class UserData(BaseModel):
    enable_weibo: bool = False
    '''是否开启微博功能'''
    weibo: list = []
    '''微博超话签到及兑换用的参数,适配多账号'''
    # def __init__(self, **data: Any):
    #     super().__init__(**data)

class PluginData(BaseModel):
    users: Dict[str, UserData] = {}
    '''所有用户数据'''
    # def __init__(self, **data: Any):
    #     super().__init__(**data)

class Config():
    plugin_data: Optional[PluginData] = None
    """加载出的插件数据对象"""

    @classmethod
    def load_plugin_data(cls):
        """
        加载插件数据文件
        """
        if plugin_data_path.exists() and plugin_data_path.is_file():
            try:
                with open(plugin_data_path, "r") as f:
                    plugin_data_dict = json.load(f)
                # 读取完整的插件数据
                cls.plugin_data = PluginData.parse_obj(plugin_data_dict)
            except (ValidationError, JSONDecodeError):
                logger.exception(f"读取插件数据文件失败，请检查插件数据文件 {plugin_data_path} 格式是否正确")
                raise
            except Exception:
                logger.exception(
                    f"读取插件数据文件失败，请检查插件数据文件 {plugin_data_path} 是否存在且有权限读取和写入")
                raise
        else:
            cls.plugin_data = PluginData()
            try:
                str_data = json.dumps(cls.plugin_data.dict(), indent=4, ensure_ascii=False)
                plugin_data_path.parent.mkdir(parents=True, exist_ok=True)
                with open(plugin_data_path, "w", encoding="utf-8") as f:
                    f.write(str_data)
            except (AttributeError, TypeError, ValueError, PermissionError):
                logger.exception(f"创建插件数据文件失败，请检查是否有权限读取和写入 {plugin_data_path}")
                raise
            else:
                logger.info(f"插件数据文件 {plugin_data_path} 不存在，已创建默认插件数据文件。")

    @classmethod
    def write_plugin_data(cls):
        """
        写入插件数据文件

        :return: 是否成功
        """
        try:
            str_data = json.dumps(cls.plugin_data.dict(), indent=4, ensure_ascii=False)
        except (AttributeError, TypeError, ValueError):
            logger.exception("数据对象序列化失败，可能是数据类型错误")
            return False
        else:
            with open(plugin_data_path, "w", encoding="utf-8") as f:
                f.write(str_data)
            return True

Config.load_plugin_data()


async def send_private_msg(
        user_id: str,
        message: Union[str, MessageSegmentFactory, AggregatedMessageFactory],
        use: Union[Bot, Adapter] = None,
        guild_id: int = None
) -> Tuple[bool, Optional[Exception]]:
    """
    主动发送私信消息

    :param user_id: 目标用户ID
    :param message: 消息内容
    :param use: 使用的Bot或Adapter，为None则使用所有Bot
    :param guild_id: 用户所在频道ID，为None则从用户数据中获取
    :return: (是否发送成功, ActionFailed Exception)
    """
    user_id_int = int(user_id)
    if isinstance(message, str):
        message = Text(message)

    # 整合符合条件的 Bot 对象
    if isinstance(use, (OneBotV11Bot, QQGuildBot)):
        bots = [use]
    elif isinstance(use, (OneBotV11Adapter, QQGuildAdapter)):
        bots = use.bots.values()
    else:
        bots = nonebot.get_bots().values()

    for bot in bots:
        try:
            # 获取 PlatformTarget 对象
            if isinstance(bot, OneBotV11Bot):
                target = TargetQQPrivate(user_id=user_id_int)
                logger.info(
                    f"向用户 {user_id} 发送 QQ 聊天私信 user_id: {user_id_int}")
            else:
                if guild_id is None:
                    if user := PluginDataManager.plugin_data.users.get(user_id):
                        if not (guild_id := user.qq_guild.get(user_id)):
                            logger.error(f"用户 {user_id} 数据中没有任何频道ID")
                            return False, None
                    else:
                        logger.error(
                            f"用户数据中不存在用户 {user_id}，无法获取频道ID")
                        return False, None
                target = TargetQQGuildDirect(recipient_id=user_id_int, source_guild_id=guild_id)
                logger.info(f"向用户 {user_id} 发送 QQ 频道私信"
                            f" recipient_id: {user_id_int}, source_guild_id: {guild_id}")

            await message.send_to(target=target, bot=bot)
        except Exception as e:
            return False, e
        else:
            return True, None
    
async def get_file(url: str, retry: bool = True, max_retries: int = 3, retry_interval: float = 2.0):
    """
    下载文件

    :param url: 文件URL
    :param retry: 是否允许重试
    :param max_retries: 最大重试次数
    :param retry_interval: 重试间隔时间（秒）
    :return: 文件数据，若下载失败则返回 ``None``
    """
    attempt = 0

    while attempt < (max_retries if retry else 1):
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, timeout=10, follow_redirects=True)
                return res.content
        except Exception as e:
            attempt += 1
            logger.exception(f"nonebot-下载文件 - {url} 失败:{e}")
            if attempt < (max_retries if retry else 1):
                await asyncio.sleep(retry_interval)
    return None