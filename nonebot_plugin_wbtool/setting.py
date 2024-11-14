from nonebot import on_command
from nonebot.internal.matcher import Matcher
from nonebot.typing import T_State
from nonebot.internal.params import ArgStr
from loguru import logger

from .config import Tool, Config, UserData


wbsetting = on_command("wbset", aliases={"微博设置"})

@wbsetting.handle()
async def setting(event, matcher: Matcher, state: T_State):
    user_id = event.get_user_id()
    user_data = Config.plugin_data.users.get(user_id, None)
    if not user_data:
        user_data = Config.plugin_data.users.setdefault(user_id, UserData())
    state['user_id'] = user_id
    state['user'] = user_data
    msg = ""
    msg += "请发送想要设置的微博功能开关或账号："
    msg += f"\n1. 微博签到与兑换：{'开' if user_data.enable_weibo else '关'}"
    count = 1
    if len(user_data.weibo) > 0:
        for users in user_data.weibo:
            for k_u, v_u in users.items():
                if k_u == 'name':
                    count += 1
                    msg += f"\n{count}. {str(v_u)}"
    msg += "\n发送“添加账号”或已有账号名称进行添加/修改"
    msg += "\n发送“删除账号”进行账号删除"
    msg += "\n\n🚪发送“退出”即可退出"
    await wbsetting.send(msg)
    state["setting_item"] = "setting_wbitem"

@wbsetting.got('setting_wb')
async def id(event, state: T_State, setting_wb=ArgStr()):
    if setting_wb == '退出':
        await wbsetting.finish('🚪已成功退出')

    if state["setting_item"] == "setting_wbitem":
        user: UserData = state["user"]
        if setting_wb == "1":
            user.enable_weibo = not user.enable_weibo
            Config.write_plugin_data()
            await wbsetting.finish(f"微博签到与兑换功能已 {'✅开启' if user.enable_weibo else '❌关闭'}")
        elif setting_wb == '添加账号':
            await wbsetting.send(
                "参数说明：\n"
                "  cookie必填SUB,SUBP\n"
                "  params必填s,gsid,aid,from\n"
                "  参数以 ; 相连\n"
                "  如 xxx: a=x;b=x;\n"
                "发送以下格式进行添加：\n"
                "name:名称|cookie:xxx|params:xxx\n\n"
                "🚪发送“退出”即可退出"
            )
            state["setting_item"] = "setting_weibo_account"
        elif setting_wb == '删除账号':
            msg = ""
            for usr in user.weibo:
                msg += f"{usr['name']}\n"

            await wbsetting.send(
                "选择想要删除的账号：\n"
                f"{msg}\n"
                "🚪发送“退出”即可退出"
            )
            state["setting_item"] = "del_weibo_account"
        else:
            await wbsetting.send(
                "更新账号：\n"
                "  cookie必填SUB,SUBP\n"
                "  params必填s,gsid,aid,from,c\n"
                "  参数以 ; 相连\n"
                "  如 xxx: a=x;b=x;\n"
                "发送以下格式进行添加：\n"
                "cookie和params选填，name必填\n"
                "name:名称|(cookie:xxx)|(params:xxx)\n\n"
                "🚪发送“退出”即可退出"
            )
            state["setting_item"] = "setting_weibo_account"


@wbsetting.got('set_value')
async def setValue(event, state: T_State, set_value=ArgStr()):
    if set_value == '退出':
        await wbsetting.finish('已成功退出')

    if state["setting_item"] == "setting_weibo_account":
        user: UserData = state["user"]
        userdata_dict = Tool.weibo_user_dict(set_value)
        if len(user.weibo) > 0:
            for usr in user.weibo:
                if usr['name'] == userdata_dict['name']:
                    usr.update(userdata_dict)
                else:
                    user.weibo.append(userdata_dict)
        elif len(user.weibo) == 0:
            user.weibo.append(userdata_dict)
        Config.write_plugin_data()
        await wbsetting.finish(f"{userdata_dict['name']}微博账号设置成功")

    elif state["setting_item"] == "del_weibo_account":
        user: UserData = state["user"]
        if len(user.weibo) > 0:
            print(user.weibo)
            for usr in user.weibo:
                if usr['name'] == set_value:
                    user.weibo.remove(usr)
            Config.write_plugin_data()
            await wbsetting.finish(f"{set_value}微博账号成功删除")