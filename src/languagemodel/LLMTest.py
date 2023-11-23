import json
import unittest
import requests


def test_send_request():
    import requests

    url = "http://127.0.0.1:30080/api/v4/projects/66/repository/commits"
    headers = {
        "Authorization": "Bearer 454b2df560464ffc22dfc606f66a63b7ed9fc33000e57d2acb6c1f23bd37c61a",
        "Content-Type": "application/json",
    }

    payload = {
        "branch": "main",
        "commit_message": "some commit message",
        "actions": [
            {
                "action": "create",
                "file_path": "foo/bar",
                "content": "some content",
            },
            {
                "action": "delete",
                "file_path": "foo/bar",
            },
        ],
    }

    response = requests.post(url, headers=headers, json=payload)

    print(response.status_code)
    print(response.text)


if __name__ == '__main__':
    test_send_request()
