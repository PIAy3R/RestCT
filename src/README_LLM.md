# LLM Used in RestCT
## API Key
## Proxy
When use the RestCT added LLM, if you need to use proxy to visit the openai service, 
sometimes you will meet the OpenaiConnectionError. To resolve this problem, you need
to change the source code of the openai package.
- First you need to find the env you need to use. We use Anaconda3 environment and MacOS
as example, suppose we create a virtual environment named llm, python version is 3.9, 
the path to the openai package is 
`/Users/{your_user_name}/anaconda3/envs/llm/lib/python3.9/site-packages/openai`
- Open the `api_requestor.py` in the package folder
- Find the code below
```
if not hasattr(_thread_context, "session"):
    _thread_context.session = _make_session()
```
- Add proxy to the code, the code after add look like this. The number follow the localhost
is the port of your proxy, remember to replace it.
```
if not hasattr(_thread_context, "session"):
    proxy = {
        'http': 'http://localhost:7890',
        'https': 'http://localhost:7890'
    }
    _thread_context.session = _make_session()

```
- When you call GPT, remember to add the code below to your code. Also remember to replace the
port.
```
os.environ["http_proxy"] = "http://localhost:7890"
os.environ["https_proxy"] = "http://localhost:7890"
```
After doing this, you can use the openai api via proxy.