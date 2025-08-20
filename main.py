import json
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.event.filter import EventMessageType
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.message_components import Plain, At
from astrbot.core.message.components import At as CoreAt

@register("autoat", "YourName", "自动回at插件", "1.0.0")
class AutoAtPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config
        
        # 基本设置
        self.my_qq = self.config.get("my_qq", "123456789") if self.config else "123456789"
        self.enable_reply_message = self.config.get("enable_reply_message", False) if self.config else False
        self.reply_message = self.config.get("reply_message", "收到！") if self.config else "收到！"
        
        # 解析管理员白名单
        admin_whitelist_str = self.config.get("admin_whitelist", "123456789") if self.config else "123456789"
        try:
            # 简单的逗号分隔格式
            self.admin_whitelist = [qq.strip() for qq in admin_whitelist_str.split(",") if qq.strip()]
            if not self.admin_whitelist:
                raise ValueError("管理员白名单不能为空")
        except Exception as e:
            logger.error(f"管理员白名单配置解析失败: {e}")
            self.admin_whitelist = ["123456789"]
        
        # 解析监控配置 - 新的简化格式
        self.monitor_configs = []
        if self.config:
            monitor_config_str = self.config.get("monitor_config", "987654321:111111111")
            try:
                # 解析简化格式：群号:用户1,用户2
                lines = [line.strip() for line in monitor_config_str.split('\n') if line.strip()]
                for line in lines:
                    if ':' not in line:
                        logger.warning(f"忽略格式错误的配置行: {line}")
                        continue
                    
                    group_id, users_str = line.split(':', 1)
                    group_id = group_id.strip()
                    users = [user.strip() for user in users_str.split(',') if user.strip()]
                    
                    if group_id and users:
                        self.monitor_configs.append({
                            "group_id": group_id,
                            "users": users
                        })
                    else:
                        logger.warning(f"忽略空的群号或用户列表: {line}")
                        
                if not self.monitor_configs:
                    raise ValueError("没有有效的监控配置")
                        
            except Exception as e:
                logger.error(f"监控配置解析失败: {e}")
                # 使用默认配置
                self.monitor_configs = [{"group_id": "987654321", "users": ["111111111"]}]
        else:
            # 无配置时使用默认配置
            self.monitor_configs = [{"group_id": "987654321", "users": ["111111111"]}]

    def is_admin(self, user_id: str) -> bool:
        """检查用户是否为管理员"""
        return str(user_id) in [str(admin_id) for admin_id in self.admin_whitelist]

    async def initialize(self):
        """插件初始化"""
        logger.info(f"AutoAt插件已启动:")
        logger.info(f"  - 我的QQ号: {self.my_qq}")
        logger.info(f"  - 管理员白名单: {', '.join(map(str, self.admin_whitelist))}")
        logger.info(f"  - 自定义回复消息: {'启用' if self.enable_reply_message else '禁用'}")
        if self.enable_reply_message:
            logger.info(f"  - 回复消息内容: {self.reply_message}")
        logger.info(f"  - 监控配置:")
        
        for i, config_item in enumerate(self.monitor_configs, 1):
            group_id = config_item["group_id"]
            users = config_item["users"]
            logger.info(f"    {i}. 群聊 {group_id}: 监控用户 {', '.join(users)}")

    def is_target_message(self, group_id: str, sender_id: str) -> bool:
        """检查是否为目标群聊的目标用户发送的消息"""
        for config_item in self.monitor_configs:
            if config_item["group_id"] == group_id and sender_id in config_item["users"]:
                return True
        return False

    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def check_at_message(self, event: AstrMessageEvent):
        """检测at消息并自动回复"""
        
        # 检查是否为目标群聊的目标用户
        if not self.is_target_message(event.get_group_id(), event.get_sender_id()):
            return
            
        # 获取消息链
        message_chain = event.get_messages()
        
        # 检查消息中是否包含对我的at
        has_at_me = False
        for component in message_chain:
            if isinstance(component, CoreAt) and str(component.qq) == str(self.my_qq):
                has_at_me = True
                break
                
        if has_at_me:
            logger.info(f"检测到用户 {event.get_sender_id()} 在群 {event.get_group_id()} 中at了我")
            
            # 构建回复消息
            reply_components = [At(qq=event.get_sender_id())]  # at目标用户
            
            # 如果启用了自定义回复消息，则添加文字内容
            if self.enable_reply_message and self.reply_message:
                reply_components.append(Plain(f" {self.reply_message}"))
            
            # 发送回复
            yield event.chain_result(reply_components)

    @filter.command_group("autoat", "自动回at插件管理")
    async def autoat_commands(self):
        """自动回at插件命令组"""
        pass

    @autoat_commands.command("状态", alias=["status", "info"])
    async def show_status(self, event: AstrMessageEvent):
        """显示插件状态和配置"""
        # 检查权限
        if not self.is_admin(event.get_sender_id()):
            yield event.plain_result("❌ 权限不足，只有管理员可以查看插件状态")
            return
            
        status_text = "📋 AutoAt插件状态:\n\n"
        status_text += f"🤖 我的QQ号: {self.my_qq}\n"
        status_text += f"👑 管理员列表: {', '.join(map(str, self.admin_whitelist))}\n"
        status_text += f"💬 自定义回复: {'✅启用' if self.enable_reply_message else '❌禁用'}\n"
        
        if self.enable_reply_message:
            status_text += f"📝 回复内容: {self.reply_message}\n"
        
        status_text += f"\n📊 监控配置 (共{len(self.monitor_configs)}项):\n"
        
        for i, config_item in enumerate(self.monitor_configs, 1):
            group_id = config_item["group_id"]
            users = config_item["users"]
            status_text += f"{i}. 群聊 {group_id}\n"
            status_text += f"   👥 监控用户: {', '.join(users)}\n"
        
        yield event.plain_result(status_text)

    @autoat_commands.command("测试", alias=["test"])
    async def test_command(self, event: AstrMessageEvent):
        """测试指令"""
        # 检查权限
        if not self.is_admin(event.get_sender_id()):
            yield event.plain_result("❌ 权限不足，只有管理员可以执行测试命令")
            return
            
        yield event.plain_result("✅ AutoAt插件运行正常！")

    @autoat_commands.command("添加管理员", alias=["add_admin"])
    async def add_admin(self, event: AstrMessageEvent, qq_id: str):
        """添加管理员"""
        # 检查权限
        if not self.is_admin(event.get_sender_id()):
            yield event.plain_result("❌ 权限不足，只有现有管理员可以添加新管理员")
            return
            
        if qq_id in [str(admin_id) for admin_id in self.admin_whitelist]:
            yield event.plain_result(f"❌ 用户 {qq_id} 已经是管理员了")
            return
            
        self.admin_whitelist.append(qq_id)
        # 这里可以选择保存到配置文件，但需要重启才能生效
        yield event.plain_result(f"✅ 已添加 {qq_id} 为管理员（重启插件后永久生效）")

    @autoat_commands.command("移除管理员", alias=["remove_admin"])
    async def remove_admin(self, event: AstrMessageEvent, qq_id: str):
        """移除管理员"""
        # 检查权限
        if not self.is_admin(event.get_sender_id()):
            yield event.plain_result("❌ 权限不足，只有管理员可以移除管理员")
            return
            
        if qq_id not in [str(admin_id) for admin_id in self.admin_whitelist]:
            yield event.plain_result(f"❌ 用户 {qq_id} 不是管理员")
            return
            
        # 防止移除最后一个管理员
        if len(self.admin_whitelist) <= 1:
            yield event.plain_result("❌ 不能移除最后一个管理员")
            return
            
        self.admin_whitelist = [admin_id for admin_id in self.admin_whitelist if str(admin_id) != str(qq_id)]
        yield event.plain_result(f"✅ 已移除 {qq_id} 的管理员权限（重启插件后永久生效）")

    async def terminate(self):
        """插件销毁"""
        logger.info("AutoAt插件已停止")