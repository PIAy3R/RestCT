import unittest

import requests


class APITestCase(unittest.TestCase):
    def test_send_request(self):
        # This is a test case for a RESTful API
        # The base url is "http://127.0.0.1:30080/api/v4"
        # The url of the api is "/projects"
        # The http method of this request is post
        # This request need a Bearer token, the token is "57f1a0567beaaee4e33a17dd231b35d14eba0da866b51067480dded8dd9c899a"
        # This test case is to create a project gitlab project
        # The parameters may be used are:
        # {"name": "name","in": "query","description": "The name of the new project. Either path or name is required, not both.","type": "string"}
        # {"name": "path","in": "query","description": "Repository name for new project. Generated based on name if not provided (generated as lowercase with dashes).","type": "string"}
        # {"name": "import_url","in": "query","description": "URL to import repository from. Either import_url or template_name is required, not both","type": "string"}
        # {"name": "template_name","in": "query","description": "When used withoutuse_custom_template, name of abuilt-in project template. When used withuse_custom_template, name of a custom project template.","type": "string",}
        # Use the parameters above to create a test case(not all parameters are needed), make sure the test case can pass, pay attention to constraints described in description.

        base_url = "http://127.0.0.1:30080/api/v4"

        # The url of the api is "/projects"
        url = base_url + "/projects"

        # The http method of this request is post
        method = "POST"

        # This request need a Bearer token, the token is "8b5bfc9f6c6a47c430c03cf2ea6a693972654ffa94b7483d5ded5300ff395689"
        headers = {"Authorization": "Bearer 57f1a0567beaaee4e33a17dd231b35d14eba0da866b51067480dded8dd9c899a"}

        # The parameters may be used are:
        params = {
            "name": "test_project2",
            "path": "test_project2",
            "import_url": "https://gitlab.com/gitlab-org/gitlab-test.git"
        }

        # Use the parameters above to create a test case(not all parameters are needed), make sure the test case can pass, pay attention to constraints described in description.
        response = requests.request(method=method, url=url, headers=headers, params=params)

        # Check the response status code
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "test_project2")
        self.assertEqual(response.json()["path"], "test_project2")


if __name__ == "__main__":
    unittest.main()
