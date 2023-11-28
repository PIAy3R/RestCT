import requests

from src.Dto.keywords import Method

url = "http://127.0.0.1:30080/api/v4/projects"
verb = Method.POST
payload = {
    "name": "fhseuifaed",
    "template_name": ""
}

headers = {
    'Content-Type': 'applications/json',
    'Authorization': 'Bearer 57f1a0567beaaee4e33a17dd231b35d14eba0da866b51067480dded8dd9c899a'
}

feedback = requests.post(url=url, headers=headers, params=payload)
# sender = RestRequest()
# s, r = sender.send_request(Method.POST, url, headers)
# sc, response = sender.send_request(verb=verb, url=url, headers=headers, query=payload)
print(feedback)
