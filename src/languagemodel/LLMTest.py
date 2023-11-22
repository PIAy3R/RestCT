import unittest
import requests

class MyTestCase(unittest.TestCase):
    def test_send_request(self):
        # Define the base host
        self.base_host = "https://127.0.0.1:31080/api/v4"

        # Define the rquest url
        self.url = self.base_host + "/projects/50/repository/commits"

        # Define the http request method
        self.method = "POST"

        # Define the request payload
        self.data = {"commit_message": "commit message",
                     "actions": '[ { "action" : "create" , "file_path": "app/app.js", "content" : "puts \"Hello, world!\" }, { "action" : "delete", "file_path": "app/views.py" }, { "action" : "move", "file_path": "doc/api/index.md", "previous_path": "docs/api/README.md" }, { "action" : "update", "file_path": "app/models/model.py", "content" : "class Bag(object)\n def __init__(self):\n """Create bag.\n See how you can use this API easily now?\n By the way, we changed the file description that can be seen in a commit.\n"""} ]',
                     "branch": "my_branch"}

        # Define the http request header. It needs authentication info
        self.header = {"Content-Type": "application/x-www-form-urlencoded",
                       "Authorization": "Bearer 8b5bfc9f6c6a47c430c03cf2ea6a693972654ffa94b7483d5ded5300ff395689"}

        # Send the request
        req = requests.request(method=self.method, url=self.url, data=self.data, headers=self.header)

        # Validate the response status code is 201
        self.assertEqual(req.status_code, 201, msg='test case failed')


if __name__ == '__main__':
    unittest.main()
