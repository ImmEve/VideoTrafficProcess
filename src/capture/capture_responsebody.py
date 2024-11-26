import configparser
from mitmproxy import http


class Mitm:
    def __init__(self):
        conf = configparser.ConfigParser()
        conf.read('src/config.conf', encoding='UTF-8')
        self.responsebody_filepath = conf.get('capture', 'responsebody_path') + 'log.csv'

    def response(self, flow: http.HTTPFlow) -> None:
        if 'videoplayback' in flow.request.pretty_url:
            response_body_size = len(flow.response.content)
            if response_body_size > 1000:
                with open(self.responsebody_filepath, 'a') as f:
                    f.write(str(response_body_size) + '\n')
                print(f"Response body size: {response_body_size} bytes")


addons = [Mitm()]
