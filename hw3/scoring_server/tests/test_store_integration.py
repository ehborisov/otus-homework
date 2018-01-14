#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import test_constants
import copy
from hw3.scoring_server import api
from hw3.scoring_server import store


class StoreMock:
    def __init__(self):
        self.store = {}

    def cache_set(self, key, score, _):
        self.store[key] = score

    def cache_get(self, key):
        return self.store.get(key, None)

    def get(self, key):
        if key not in self.store:
            raise store.StoreError
        return self.store.get(key)


class StoreTest(unittest.TestCase):

    def setUp(self):
        self.context = {}
        self.headers = {}
        self.store_mock = StoreMock()

    def get_response(self, request):
        return api.main_method_handler(
            {"body": request, "headers": self.headers},
            self.context, self.store_mock)

    def test_cached_score_is_used(self):
        request = copy.deepcopy(test_constants.VALID_SCORE_REQUEST)
        response, _ = self.get_response(request)
        first_score = response['score']
        new_request = copy.deepcopy(test_constants.VALID_SCORE_REQUEST.copy())
        new_request['phone'] = None
        second_response, _ = self.get_response(new_request)
        cached_score = second_response['score']
        self.assertEqual(first_score, cached_score)
        self.assertEqual(cached_score, 5.0)

    def test_caching_key_parameters_differ(self):
        request1 = copy.deepcopy(test_constants.VALID_SCORE_REQUEST)
        _, _ = self.get_response(request1)
        request2 = copy.deepcopy(test_constants.VALID_SCORE_REQUEST)
        request2['arguments']['birthday'] = '01.01.1989'
        _, _ = self.get_response(request2)
        self.assertEqual(len(self.store_mock.store.keys()), 2)

    def test_interests_with_store(self):
        store_interests = {
            'i:1': "{\"i\": [\"drink\", \"sleep\"]}",
            'i:2': "{\"i\": [\"spam\", \"eggs\"]}"
        }
        expected_response = {
            1: {'i': ['drink', 'sleep']},
            2: {'i': ['spam', 'eggs']}
        }
        self.store_mock.store.update(store_interests)
        request_ids = [1, 2]

        request = copy.deepcopy(test_constants.VALID_INTERESTS_REQUEST)
        request['arguments']['client_ids'] = request_ids
        response, _ = self.get_response(request)
        self.assertDictEqual(response, expected_response)

    def test_interests_with_store_error(self):
        request = copy.deepcopy(test_constants.VALID_INTERESTS_REQUEST)
        with self.assertRaises(store.StoreError):
            _, _ = self.get_response(request)
