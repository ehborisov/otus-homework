#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import selectors
import multiprocessing
import asyncio
import socket
import signal
import mimetypes
import os

from contextlib import closing
from datetime import datetime
from enum import Enum
from optparse import OptionParser
from wsgiref.handlers import format_date_time
from urllib import request
from urllib.parse import unquote
from time import mktime

HTTP_HEADERS_ENDING = '\r\n\r\n'
RESPONSE_LINE_ENDING = '\r\n'
HTTP_VERSION_STRING = 'HTTP/1.1'

PLAIN_TEXT_EMPTY_CONTENT = [
    'Content-Type: text/plain; charset=utf-8',
    'Content-Length: {}'
]


class Error(Exception):
    """Parent exception class for server module."""
    pass


class BadRequestError(Error):
    """Request has an unexpected structure and is not parseable."""
    pass


class HttpCode(Enum):
    BAD_REQUEST = (400, 'Bad Request')
    OK = (200, 'OK')
    FORBIDDEN = (403, 'Forbidden')
    NOT_FOUND = (404, 'Not Found')
    NOT_ALLOWED = (405, 'Method Not Allowed')
    SERVER_ERROR = (500, 'Internal Server Error')

    def __init__(self, code, short_message):
        self.code = code
        self.short_message = short_message

    def to_response_line(self):
        return ' '.join([HTTP_VERSION_STRING, str(self.code),
                         self.short_message])


def _generate_response_lines(http_code, headers):
    lines = [http_code.to_response_line()] + headers
    response_string = RESPONSE_LINE_ENDING.join(lines) + HTTP_HEADERS_ENDING
    return response_string.encode()


def _parse_headers(header_lines):
    headers = {}
    for line in header_lines:
        line.strip()
        if line:
            header, value = line.split(': ')
            headers[header] = value
    return headers


def _parse_path(resource_string):
    decoded = unquote(resource_string)
    path = decoded
    if '?' in decoded:
        path, unused_query_string = decoded.split('?')
    if path.endswith('/'):
        path = path + 'index.html'
    if path.startswith('/'):
        path = path[1:]
    return path


class DIYHTTPServer(object):
    def __init__(self, address, port, root, worker_count):
        self.address = address
        self.port = port
        self.root = os.path.abspath(root)
        self.worker_count = worker_count
        self._workers = set()

    def _serve(self, sock):
        selector = selectors.EpollSelector()
        loop = asyncio.SelectorEventLoop(selector)
        coro = asyncio.start_server(self._connection_handler, sock=sock)
        server = loop.run_until_complete(coro)
        loop.add_signal_handler(signal.SIGTERM, loop.stop)
        loop.add_signal_handler(signal.SIGINT, loop.stop)
        logging.info(
            f'Starting server worker at http://{self.address}:{self.port}')
        try:
            loop.run_forever()
        finally:
            logging.info('Closing server worker...')
            server.close()
            coro.close()
            loop.run_until_complete(coro)

    def terminate(self, unused_signum, unused_frame):
        logging.info('Termination arequest received, shutting down workers.')
        for worker in self._workers:
            worker.terminate()

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.address, self.port))

        signal.signal(signal.SIGINT, self.terminate)
        signal.signal(signal.SIGTERM, self.terminate)
        for _ in range(self.worker_count):
            worker = multiprocessing.Process(
                target=self._serve, kwargs=dict(sock=sock))
            worker.daemon = True
            worker.start()
            self._workers.add(worker)
        sock.close()

        for worker in self._workers:
            worker.join()

    async def _connection_handler(self, reader, writer):
        with closing(writer) as client_writer:
            address = client_writer.get_extra_info('peername')
            logging.info('Accepted connection from %s.', address)
            raw_request = None
            content = None
            headers = PLAIN_TEXT_EMPTY_CONTENT
            while True:
                try:
                    raw_request = await reader.readuntil(
                        HTTP_HEADERS_ENDING.encode())
                    if raw_request:
                        break
                except asyncio.IncompleteReadError:
                    break
            try:
                method, resource, response_headers = self._tokenize_request(
                    raw_request)
                path = _parse_path(resource)
                if method in ['GET', 'HEAD']:
                    code, headers = self._create_get_or_head_response(
                        path, response_headers)
                    if method == 'GET' and code == HttpCode.OK:
                        with open(os.path.join(self.root, path), 'rb') as fd:
                            try:
                                content = await self._read_data(fd)
                            except IOError:
                                logging.error('Error on reading requested file %s contents.', path)
                                raise
                else:
                    code = HttpCode.NOT_ALLOWED
            except BadRequestError as e:
                logging.exception(e)
                code = HttpCode.BAD_REQUEST
            except Exception as e:
                logging.exception(e)
                code = HttpCode.SERVER_ERROR
            client_writer.write(_generate_response_lines(code, headers))
            if content:
                client_writer.write(content)
            await client_writer.drain()

    def _tokenize_request(self, raw_request):
        if not raw_request:
            raise Exception('Error on reading request data, no data was read')
        decoded_request = raw_request.decode('utf-8')
        lines = decoded_request.split(RESPONSE_LINE_ENDING)
        request_line, header_lines = lines[0], lines[1:]
        request_args = request_line.split()
        if len(request_args) < 2:
            raise BadRequestError('Cannot tokenize request line: %s' % request_line)
        method, resource = request_args[:2]
        headers = _parse_headers(header_lines)
        is_closing = headers.get('Connection', 'close') == 'close'
        date_string = format_date_time(mktime(datetime.now().timetuple()))
        connection = 'close' if is_closing else 'keep-alive'
        response_headers = [
            f'Date: {date_string}',
            'Server: DIY HTTP Server',
            f'Connection: {connection}'
        ]
        return method, resource, response_headers

    def _create_get_or_head_response(self, document_path, headers):
        full_path = os.path.join(self.root, document_path)
        exists = os.path.exists(full_path)
        escaped = exists and '/..' in full_path
        absent_index = not exists and document_path.endswith('index.html')
        if escaped:
            return HttpCode.FORBIDDEN, headers + PLAIN_TEXT_EMPTY_CONTENT
        if not exists or absent_index:
            return HttpCode.NOT_FOUND, headers + PLAIN_TEXT_EMPTY_CONTENT

        path = os.path.join(self.root, document_path)
        content_length = os.path.getsize(path)
        content_type = mimetypes.guess_type(request.pathname2url(path))[0]
        headers.extend([
            f'Content-Length: {content_length}',
            f'Content-Type: {content_type}'
        ])
        return HttpCode.OK, headers

    def _read_data(self, file):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, file.read)


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-w", "--workers", action="store", type=int, default=4)
    parser.add_option("-r", "--root", action="store", type=str, default='.')
    parser.add_option("-l", "--logfile", action="store", type=str,
                      default='/tmp/httpd.log')
    (opts, args) = parser.parse_args()
    logfile = opts.logfile
    logging.basicConfig(filename=logfile, level=logging.INFO,
                        format='[%(asctime)s] %(levelname).1s %(message)s',
                        datefmt='%Y.%m.%d %H:%M:%S')
    server = DIYHTTPServer('127.0.0.1', 80, opts.root, opts.workers)
    server.start()
