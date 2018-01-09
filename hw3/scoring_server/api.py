#!/usr/bin/env python
# -*- coding: utf-8 -*-

import abc
import hashlib
import json
import logging
import numbers
import uuid
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from optparse import OptionParser
from abc import abstractproperty, abstractmethod

import scoring

CLIENTS_INTERESTS_METHOD = 'clients_interests'

ONLINE_SCORE_METHOD = "online_score"

MAX_AGE = 70
AT_SYMBOL = '@'
PHONE_PREFIX = '7'
PHONE_LENGTH = 11

SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}
DATE_PATTERN = '%d.%m.%Y'


class WithCheckedFields(type):
    def __new__(mcs, clsname, bases, methods):
        required_fields = set()
        known_fields = set()
        for key, value in methods.items():
            if isinstance(value, CheckedRequestField):
                value.name = key
                known_fields.add(key)
                if getattr(value, 'is_required', True):
                    required_fields.add(key)
                conditions = []
                for base_class in value.__class__.__mro__:
                    declared_conditions = getattr(base_class, 'conditions', [])
                    if isinstance(declared_conditions, list):
                        conditions.extend(declared_conditions)
                setattr(value, 'conditions', conditions)
        inst = type.__new__(mcs, clsname, bases, methods)
        inst._required = required_fields
        inst._known_fields = known_fields
        return inst


class WithAbcAndCheckedFields(abc.ABCMeta, WithCheckedFields):
    pass


class CheckedRequestField(object):
    __metaclass__ = abc.ABCMeta

    @abstractproperty
    def conditions(self):
        raise NotImplementedError(
            'Subclasses of CheckedRequestField should declare conditions'
            ' for value checking.')

    def __init__(self, **kwargs):
        self.name = None
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __get__(self, instance, owner):
        return instance.__dict__.get(self.name, None)

    def __set__(self, instance, value):
        is_nullable = getattr(self, 'is_nullable', False)
        if not is_nullable and value is None:
            raise ValueError("'%s' request param is not nullable!" % self.name)
        for condition, message in self.conditions:
            if not condition(value):
                raise ValueError(message % self.name)
        instance.__dict__[self.name] = value


class CharField(CheckedRequestField):
    conditions = [
        (lambda value: isinstance(value, basestring),
         "'%s' request param must be of a char type")
    ]


class ArgumentsField(CheckedRequestField):
    conditions = [
        (lambda value: isinstance(value, dict),
         "'%s' request param must be a valid json object"),
    ]


class EmailField(CharField):
    conditions = [
        (lambda value: AT_SYMBOL in value,
         "'%s' request param must be a sting containing '@' symbol."),
    ]


class PhoneField(CheckedRequestField):
    conditions = [
        (lambda value: isinstance(value, basestring) or
                       isinstance(value, numbers.Number),
         "'%s' request field must be of a number or a char type."),
        (lambda value: len(str(value)) == PHONE_LENGTH,
         "'%s' request field must contain a valid 11 digit phone."),
        (lambda value: str(value).startswith(PHONE_PREFIX),
         "'%s' request field must be a phone number starting with 7"),
    ]


class DateField(CheckedRequestField):
    conditions = [
        (lambda v: datetime.strptime(v, DATE_PATTERN),
         "'%s' request field must be a date in DD.MM.YYYY format"),
    ]


class BirthDayField(DateField):
    conditions = [
        (lambda v: datetime.now().year -
                   datetime.strptime(v, DATE_PATTERN).year <= MAX_AGE,
         "'%s' request field is invalid - too old ʕ •ᴥ•ʔ╭∩╮."),
    ]


class GenderField(CheckedRequestField):
    conditions = [
        (lambda value: isinstance(value, numbers.Number),
         "'%s' request field must be a number."),
        (lambda value: value in GENDERS.keys(),
         "'%s' request field is an unknown gender code."),
    ]


class ClientIDsField(CheckedRequestField):
    conditions = [
        (lambda value: isinstance(value, list),
         "'%s' request field must be a list."),
        (lambda value: any(isinstance(x, numbers.Number)
                           for x in value),
         "'%s' request field must contain only numeric ids."),
    ]


class BaseRequest(object):
    __metaclass__ = WithAbcAndCheckedFields
    _required = set()
    _known_fields = set()

    def __init__(self, **kwargs):
        missing_required_fields = self._required.difference(set(kwargs.keys()))
        if missing_required_fields:
            raise TypeError('Request does not have required fields: %s' %
                            ', '.join(missing_required_fields))
        for param, arg in kwargs.iteritems():
            if param in self._known_fields:
                setattr(self, param, arg)
            else:
                logging.info('Got unknown param in request: %s=%s', param, arg)

    @abstractmethod
    def handle(self, base_request, ctx, store):
        raise NotImplementedError('Subclasses of BaseRequest should implement '
                                  'handle method.')


class ClientsInterestsRequest(BaseRequest):
    client_ids = ClientIDsField(required=True)
    date = DateField(required=False, nullable=True)

    def handle(self, base_request, ctx, store):
        ctx['nclients'] = len(self.client_ids)
        response = {}
        for client_id in self.client_ids:
            response[client_id] = scoring.get_interests(store, client_id)
        return response, OK


class OnlineScoreRequest(BaseRequest):
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)

    def handle(self, base_request, ctx, store):
        ctx['has'] = base_request.arguments.keys()
        if base_request.is_admin:
            score = 42
        else:
            score = scoring.get_score(store, self.phone, self.email,
                                      self.birthday, self.gender,
                                      self.first_name, self.last_name)
        response = {'score': score}
        return response, OK


class MethodRequest(BaseRequest):
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN

    def check_auth(self):
        if self.login == ADMIN_LOGIN:
            digest = hashlib.sha512(datetime.now()
                                    .strftime(
                "%Y%m%d%H") + ADMIN_SALT).hexdigest()
        else:
            digest = hashlib.sha512(self.account +
                                    self.login + SALT).hexdigest()
        if digest == self.token:
            return True
        return False

    def handle(self, base_request, ctx, store):
        if not self.check_auth():
            return 'Invalid token', FORBIDDEN
        if self.method == CLIENTS_INTERESTS_METHOD:
            method_request = ClientsInterestsRequest(**self.arguments)
        elif self.method == ONLINE_SCORE_METHOD:
            method_request = OnlineScoreRequest(**self.arguments)
        else:
            return 'Unknown method', INVALID_REQUEST
        return method_request.handle(self, ctx, store)


def main_method_handler(request_params, ctx, store):
    return MethodRequest(**request_params['body']).handle(None, ctx, store)


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {
        "method": main_method_handler
    }
    store = None

    def get_request_id(self, headers):
        return headers.get('HTTP_X_REQUEST_ID', uuid.uuid4().hex)

    def do_POST(self):
        context = {"request_id": self.get_request_id(self.headers)}
        response, code = {}, OK
        try:
            data_string = self.rfile.read(int(self.headers['Content-Length']))
            request_dict = json.loads(data_string)
        except Exception:
            self.handle_response(BAD_REQUEST, {}, context)
            return
        if data_string:
            logging.info("%s: %s %s" % (self.path, data_string,
                                        context["request_id"]))
        if request_dict:
            path = self.path.strip("/")
            if path in self.router:
                try:
                    response, code = self.router[path](
                        {"body": request_dict, "headers": self.headers},
                        context, self.store)
                except (TypeError, ValueError) as e:
                    logging.exception(e)
                    code = INVALID_REQUEST
                    response = e.message
                except Exception as e:
                    logging.exception("Unexpected error: %s" % e)
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND
        self.handle_response(code, response, context)
        return

    def handle_response(self, code, response, context):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {"error": response or ERRORS.get(code, "Unknown Error"),
                 "code": code}
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r))


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-p", "--port", action="store", type=int, default=8080)
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()

    logging.basicConfig(filename=opts.log, level=logging.INFO,
                        format='[%(asctime)s] %(levelname).1s %(message)s',
                        datefmt='%Y.%m.%d %H:%M:%S')
    server = HTTPServer(("localhost", opts.port), MainHTTPHandler)
    logging.info("Starting server at %s" % opts.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
