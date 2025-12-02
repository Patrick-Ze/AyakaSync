import os
import json
import logging
import logging.config

# 定义常量
LOGGING_CFG_FILE = os.path.join(os.path.dirname(__file__), "logging_setup.json")


def get_logger(name=None, default_level=logging.INFO):
    """加载配置并设置日志系统"""
    try:
        if os.path.exists(LOGGING_CFG_FILE):
            with open(LOGGING_CFG_FILE, "r") as f:
                config = json.load(f)
            logging.config.dictConfig(config)
        else:
            # 配置文件不存在时的回退机制
            logging.basicConfig(level=default_level)
            logging.warning(
                f"Logging config file not found. Using basic configuration at level {logging.getLevelName(default_level)}."
            )
    except Exception as e:
        # 兜底：如果加载配置文件本身失败 (如 JSON 格式错误)
        logging.basicConfig(level=logging.WARNING)
        logging.error(f"Failed to load logging configuration: {e}")

    return logging.getLogger(name)

# 注意：这个模块本身不应该执行 setup_logging()。
# 应该由主启动文件来调用它。
