import time


class CustomLogger:
    def __init__(self):
        self.file_path = "/scripts/proxy_out/gitlab_proxy.txt"

    def write_to_file(self, content):
        with open(self.file_path, "a") as f:
            f.write(content)

    def request(self, flow):
        content = (
            "========REQUEST========\n"
            f"Method: {flow.request.method}\n"
            f"URL: {flow.request.pretty_url}\n"
            f"Request Data: {flow.request.text}\n"
        )
        self.write_to_file(content)

    def response(self, flow):
        content = (
            "========RESPONSE========\n"
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Status Code: {flow.response.status_code}\n"
            f"Response Data: {flow.response.text}\n"
        )
        self.write_to_file(content)


addons = [CustomLogger()]
