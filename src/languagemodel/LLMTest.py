# import json
# import os
# import csv
#
# message_set = set()
# count = 0
# # 打开 CSV 文件
# with open('/Users/naariah/Experiment/SaveRequests/Branch/requests/operation_0.csv', 'r') as file:
#     # 创建 CSV 读取器
#     csv_reader = csv.reader(file)
#
#     # 读取 CSV 文件内容
#     for row in csv_reader:
#         if row[-2] != 'statuscode' and int(row[-2]) >= 400:
#             message_set.add(row[-1])
#
#
# print(message_set)
# print(len(message_set))
import json

import requests

url = "http://127.0.0.1:30080/api/v4/projects/5/repository/commits"

method = "POST"

data = {
  "branch": "main",
  "commit_message": "some commit message",
  "actions": [
    {
      "action": "create",
      "file_path": "foo/bar",
      "content": "some content"
    }
  ]
}

header = {
  "Content-Type": "application/json",
  "Authorization": "Bearer f1fbccf0beb0dc4fbd3bee28436ab13a19705992484023b74024eb6fc65d9787"
}

req = requests.post(url=url, data=json.dumps(data), headers=header)

print(req.text)
print(req.status_code)
