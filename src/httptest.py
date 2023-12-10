from src.Dto.keywords import Method
from src.restrequest import RestRequest

url = "http://127.0.0.1:30080/api/v4/projects"
verb = Method.POST
payload = {
    "name": "dwadawd",
    "template_name": ""
}
body = {
    "cadence": "daily",
    "enabled": "true",
    "keep_n": "string",
    "older_than": "1",
}

headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Authorization': 'Bearer 57f1a0567beaaee4e33a17dd231b35d14eba0da866b51067480dded8dd9c899a'
}

kwargs = dict()
kwargs["query"] = payload
kwargs["json"] = body

sender = RestRequest()
s, r = sender.send_request(Method.POST, url, headers, **kwargs)

print(s)
print(r)
