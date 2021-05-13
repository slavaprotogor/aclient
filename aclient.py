import os
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

        self._logger = logging.getLogger(self.__class__.__name__)

    async def _request(self, method, url, params, headers=None):
        session_header = copy.deepcopy(self._headers)
        if headers:
            session_header.update(headers)

        async with aiohttp.ClientSession(headers=session_header) as session:
            try:
                async with getattr(session, method)(url=url, **params) as response:
                    if response.status > 299 or 200 > response.status:
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
        return self._add(attr)

    def _get_content(self, response, content):
        if response.content_type == 'application/json':
            if content:
                return json.loads(content.decode(response.charset or self.encoding_default))
            return {}
        elif response.content_type in ('text/html', 'text/plain'):
            return content.decode(response.charset or self.encoding_default)
        else:
            return content

    def _url_builder(self, url_end):
        return self._url_start.rstrip('/') + '/' + url_end.lstrip('/')

    def _add(self, method):

        def _add_task(url, params=None, headers=None):
            if params is None:
                params = {}
            self._tasks.append(self._request(method, self._url_builder(url), params, headers))

        return _add_task

    def get_result(self):
        try:
            concurrent_tasks = asyncio.gather(*self._tasks)
            self._loop.run_until_complete(concurrent_tasks)
            return concurrent_tasks.result()
        except Exception as e:
            self._logger.exception('Error: %s', e)


if __name__ == '__main__':
    client = AClient('http://localhost:8000/api/v3/')
    client.get('/loyalty/220000387500/')
    client.get('/cities/code/7800000000000/')
    client.get('/cities/1/')
    client.get('/include_html/page_title/')
    client.get(
        '/regions/',
        {
            'params': {'limit': 4},
        },
        headers={
            'Authorization': 'Bearer <token>',
        }
    )
    client.put(
        '/include_html/test_name/',
        headers={
            'Authorization': 'Bearer <token>',
        }
    )
    client.post(
        '/delivery/shortest_terms/7800000000000/',
        {
            'data': {
                'code': [8199, 556646],
            }
        },
        headers={
            'Authorization': 'Bearer <token>',
        }
    )
    result = client.get_result()
    print(result)
