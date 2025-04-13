import os

import yaml

# 获取当前文件所在目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")


# 读取 YAML 配置文件
with open(CONFIG_PATH, "r", encoding="utf-8") as file:
    config = yaml.safe_load(file)
