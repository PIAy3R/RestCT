from src.Dto.keywords import Method
from src.restrequest import RestRequest

url = "http://127.0.0.1:30080/projects"
verb = Method.POST
payload = {
    "name": "fhseuifaed",
    "template_name": ""
}

headers = {
    "Content-Type": "applications/json",
    "user-agent": "my-app/0.0.1",
    "Authorization": "Bearer 57f1a0567beaaee4e33a17dd231b35d14eba0da866b51067480dded8dd9c899a"
}

sender = RestRequest()
sc, response = sender.send_request(verb, url, headers, payload)
print(sc)
print(response)
