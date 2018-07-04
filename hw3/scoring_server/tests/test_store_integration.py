#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

import copy
from scoring_server import api
from scoring_server import store
from . import test_constants


class StoreIntegrationTest(unittest.TestCase):

    def setUp(self):
        self.context = {}
        self.headers = {}
        self.store = store.Store()

    def get_response(self, request):
        return api.main_method_handler(
            {"body": request, "headers": self.headers},
            self.context, self.store)

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
        total_items_before = int(self.store.client.get_stats()[0][1]['total_items'])
        request1 = copy.deepcopy(test_constants.VALID_SCORE_REQUEST)
        _, _ = self.get_response(request1)
        request2 = copy.deepcopy(test_constants.VALID_SCORE_REQUEST)
        request2['arguments']['birthday'] = '01.01.1989'
        _, _ = self.get_response(request2)
        total_items_after = int(self.store.client.get_stats()[0][1]['total_items'])
        self.assertEqual(total_items_after - total_items_before, 2)

    def test_interests_with_store(self):
        self.store.cache_set('i:1', "{\"i\": [\"drink\", \"sleep\"]}", 100)
        self.store.cache_set('i:2', "{\"i\": [\"spam\", \"eggs\"]}", 100)
        expected_response = {
            1: {'i': ['drink', 'sleep']},
            2: {'i': ['spam', 'eggs']}
        }
        request_ids = [1, 2]

        request = copy.deepcopy(test_constants.VALID_INTERESTS_REQUEST)
        request['arguments']['client_ids'] = request_ids
        response, _ = self.get_response(request)
        self.assertDictEqual(response, expected_response)

    def test_interests_with_store_error(self):
        request = copy.deepcopy(test_constants.VALID_INTERESTS_REQUEST)
        with self.assertRaises(store.StoreError):
            _, _ = self.get_response(request)

    def tearDown(self):
        self.store.client.flush_all()