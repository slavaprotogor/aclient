import copy
import json
import logging

import asyncio
import aiohttp


class AClientError(Exception):
    pass


class AClientStatusError(AClientError):
    pass


class AClient:
    """ Асинхронный клиент """

    headers_default = {
        'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36')
    }
    encoding_default = 'utf-8'
    methods = ('get', 'post', 'put', 'patch', 'delete')

    def __init__(self, url_start, headers: dict=None):

        self._url_start = url_start
        self._headers = self.headers_default

        if headers:
            if not isinstance(headers, dict):
                raise TypeError('The parameter "headers" must be a dict')
            self._headers.update(headers)

        self._loop = asyncio.get_event_loop()
        self._tasks = []
        self._method = None

        self._logger = logging.getLogger(self.__class__.__name__)
        self._session = self._get_session()

    def _get_session(self):
        connector = aiohttp.TCPConnector(limit=None)
        return aiohttp.ClientSession(connector=connector)

    def _get_content(self, response, content):
        if response.content_type == 'application/json':
            if content:
                return json.loads(content.decode(response.charset or self.encoding_default))
            return {}
        elif response.content_type in ('text/html', 'text/plain'):
            return content.decode(response.charset or self.encoding_default)
        else:
            return content

    async def _request(self, method, url, params, headers=None):
        session_header = copy.deepcopy(self._headers)
        if headers:
            session_header.update(headers)

        try:
            async with getattr(self._session, method)(url=url, **params, headers=session_header) as response:
                if response.status > 299 or response.status < 200:
                    self._logger.warning('Method: %s, url: %s, request params: %s, status: %s',
                                         method, url, params, response.status)
                    return {'error': f'Response status {response.status}'}

                content = await response.read()
                return self._get_content(response, content)

        except aiohttp.ClientError as e:
            self._logger.warning('Method: %s, url: %s, request params: %s, error: %s',
                                 method, url, params, e)
            return {'error': str(e)}
        except Exception as e:
            self._logger.exception('Method: %s, url: %s, request params: %s, error: %s',
                                   method, url, params, e)
            return {'error': str(e)}

    def __getattr__(self, attr):
        if attr not in self.methods:
            raise AttributeError('The attribute "attr" does not exist')
        self._method = attr

        return self._add_task

    def _url_builder(self, url_end):
        return self._url_start.rstrip('/') + '/' + url_end.lstrip('/')

    def _add_task(self, url, params=None, headers=None, token=None):
        if not isinstance(url, str):
            raise TypeError('The arg "url" must be a str')
        if params is not None and not isinstance(params, dict):
            raise TypeError('The arg "params" must be a dict')
        if headers is not None and not isinstance(headers, dict):
            raise TypeError('The arg "headers" must be a dict')
        if token is not None and not isinstance(token, str):
            raise TypeError('The arg "token" must be a str')
        if params is None:
            params = {}

        if token:
            header_token = {
                'Authorization': f'Bearer {token}',
            }
            if headers is None:
                headers = header_token
            else:
                headers.update(header_token)

        self._tasks.append(self._request(self._method, self._url_builder(url), params, headers))
        return self

    def result(self):
        try:
            if len(self._tasks) == 1:
                return self._loop.run_until_complete(self._tasks[0])
            elif len(self._tasks) > 1:
                conurrent_tasks = asyncio.gather(*self._tasks)
                self._loop.run_until_complete(conurrent_tasks)
                return conurrent_tasks.result()
            else:
                raise ValueError('The task queue must not be empty')
        except Exception as e:
            self._logger.exception('Error: %s', e)
        finally:
            self._tasks = []

    def close(self):
        try:
            return self._loop.run_until_complete(self._session.close())
        except Exception as e:
            self._logger.exception('Error: %s', e)

if __name__ == '__main__':

    client = AClient('http://selfapi.s1.220-volt.ru/api/v3/')

    result = client.get(
        '/loyalty/220000387500/'
    ).get(
        '/cities/code/7800000000000/'
    ).get(
        '/cities/1/'
    ).get(
        '/include_html/page_title/'
    ).get(
        '/regions/',
        {
            'params': {'limit': 4},
        },
        token='<token>',
    ).result()

    print(result)

    client.close()

