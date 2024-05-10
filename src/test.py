# import time
#
# from src.swagger import SwaggerParser
# from src.config import Config
# from idl import IDL
# import json
# import os
#
# branch_path = "/Users/naariah/Documents/Python_Codes/api-suts/specifications/v3/gitlab-branch-13.json"
# language_path = "/Users/naariah/Documents/Python_Codes/api-suts/specifications/v3/languageTool.json"
# config = Config()
# config.swagger = language_path
# parser = SwaggerParser(config)
# operations = parser.extract()
# idl = IDL("IF body.language == 'auto' THEN body.preferredVariants", operations[0])
# idl.to_constraint()
# print(operations[0])

def risky_function():
    # 这是一个可能会抛出异常的函数
    # 例如，模拟一个随机失败的操作
    import random
    if random.randint(0, 1):
        raise Exception("函数执行失败")
    else:
        return "函数执行成功"


# 使用循环和异常处理来持续尝试执行函数
while True:
    try:
        result = risky_function()  # 尝试执行函数
        print(result)
        break  # 如果成功，退出循环
    except Exception as e:
        print(f"尝试失败: {e}")  # 打印错误信息，并继续尝试
