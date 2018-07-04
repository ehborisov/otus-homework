#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import parameterized
from mock import MagicMock
import copy

from . import test_constants
from scoring_server import api
from scoring_server import store


class RequestStub(object):
    pass


class ApiTests(unittest.TestCase):

    def setUp(self):
        self.context = {}
        self.headers = {}
        self.store_stub = MagicMock(store.Store)
        self.store_stub.cache_get.side_effect = lambda x: None
        self.store_stub.cache_set.side_effect = lambda x, y, z: None
        self.store_stub.get.side_effect = lambda x: None

    def get_response(self, request):
        return api.main_method_handler(
            {"body": request, "headers": self.headers}, self.context,
            self.store_stub)

    def test_empty_request(self):
        expected_message = ('Request does not have required fields: '
                            'account, arguments, login, method, token')
        with self.assertRaisesRegexp(TypeError, expected_message):
            _, code = self.get_response({})

    def test_valid_score(self):
        request = test_constants.VALID_SCORE_REQUEST.copy()
        response, code = self.get_response(request)
        self.assertEqual(code, api.OK)
        self.assertDictEqual(response, {'score': 5.0})

    def test_invalid_token(self):
        request = test_constants.VALID_SCORE_REQUEST.copy()
        request['token'] = 'invalid_token'
        _, code = self.get_response(request)
        self.assertEqual(code, api.FORBIDDEN)

    def test_admin_score(self):
        admin_score = 42
        request = test_constants.VALID_SCORE_REQUEST.copy()
        request['login'] = 'admin'
        request['token'] = test_constants.generate_admin_token()
        response, code = self.get_response(request)
        self.assertEqual(code, api.OK)
        self.assertDictEqual(response, {'score': admin_score})

    def test_invalid_admin_token(self):
        request = test_constants.VALID_SCORE_REQUEST.copy()
        request['login'] = 'admin'
        request['token'] = 'invalid_token'
        _, code = self.get_response(request)
        self.assertEqual(code, api.FORBIDDEN)

    def test_valid_client_interests(self):
        request = test_constants.VALID_INTERESTS_REQUEST.copy()
        response, code = self.get_response(request)
        self.assertEqual(code, api.OK)
        self.assertEqual(len(response.items()), 4)

    @parameterized.parameterized.expand([
        ('invalid_arguments', {'arguments': [1]},
         "'arguments' request param must be a valid json object"),

        ('account_field_invalid_type', {'account': 1},
         "'account' request param must be of a char type"),

        ('login_field_invalid_type', {'login': 1},
         "'login' request param must be of a char type"),

        ('method_field_invalid_type', {'method': 1},
         "'method' request param must be of a char type"),

        ('token_field_invalid_type', {'token': 1},
         "'token' request param must be of a char type"),

        ('method_name_is_none', {'method': None},
         "'method' request param is not nullable!"),
    ])
    def test_method_parameters_validation(
            self, _, invalid_params, expected_error):
        request = test_constants.VALID_SCORE_REQUEST.copy()
        request.update(invalid_params)
        with self.assertRaisesRegexp(ValueError, expected_error):
            self.get_response(request)

    @parameterized.parameterized.expand([
        ('client_ids_is_not_a_list', {'client_ids': {'a': 1}},
         "'client_ids' request field must be a list."),

        ('id_is_not_numeric', {'client_ids': [1, 2, '3a']},
         "'client_ids' request field must contain only numeric ids."),

        ('wrong_date_format', {'date': '01.13.2018'},
         "time data '01.13.2018' does not match format '%d.%m.%Y'")
    ])
    def test_interest_request_params_validation(self, _, params,
                                                expected_error):
        request = copy.deepcopy(test_constants.VALID_INTERESTS_REQUEST)
        request['arguments'].update(params)
        with self.assertRaisesRegexp(ValueError, expected_error):
            self.get_response(request)

    def test_interest_request_client_ids_is_required(self):
        request = copy.deepcopy(test_constants.VALID_INTERESTS_REQUEST)
        request['arguments'].pop('client_ids')
        with self.assertRaisesRegexp(TypeError, 'Request does not have '
                                                'required fields: client_ids'):
            self.get_response(request)


class FieldsTests(unittest.TestCase):

    @parameterized.parameterized.expand([
        ('first_name_is_invalid', api.CharField, 1,
         "'field' request param must be of a char type"),

        ('last_name_is_invalid', api.CharField, 1,
         "'field' request param must be of a char type"),

        ('email_is_invalid', api.EmailField, 'zzzzz',
         "'field' request param must be a sting containing '@' symbol."),

        ('phone_is_invalid_len', api.PhoneField, 333,
         "'field' request field must contain a valid 11 digit phone."),

        ('phone_is_invalid_starting_number', api.PhoneField, 12345678901,
         "'field' request field must be a phone number starting with 7"),

        ('too_old', api.BirthDayField, '01.01.1930',
         "'field' request field is invalid - too old ʕ •ᴥ•ʔ╭∩╮."),

        ('birthday_is_invalid', api.BirthDayField, '01.13.1930',
         "time data '01.13.1930' does not match format '%d.%m.%Y'"),

        ('gender_is_invalid', api.GenderField, '@',
         "'field' request field must be a number."),

        ('gender_is_unknown', api.GenderField, 666,
         "'field' request field is an unknown gender code."),
    ])
    def test_score_request_params_validation(self, _, field_class, value, expected_error):
        with self.assertRaisesRegexp(ValueError, expected_error):
            field = field_class()
            field.name = 'field'
            field.__set__(RequestStub(), value)



if __name__ == "__main__":
    unittest.main()
