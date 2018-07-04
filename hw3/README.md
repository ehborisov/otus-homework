Simple scoring API
===========================

This scoring api is made from the provided skeleton, main objective was
to build a hierarchy of classes that would implement validation logic
for different request parameters.

Usage:

To start a local server run (--log specifies a file to output server logs)

    python scoring_server/api.py --log /tmp/log.txt

Start a memcached container:

    docker run --name test-memcached -d -p 11211:11211 memcached

The server has one main endpoint `method` that provides two different
functions depending on a `method` parameter in the request:

use `online_score` to get response from online_score method:

request example:

    curl -X POST  -H "Content-Type: application/json" -d '{"account": "account1", "login": "login", "method": "online_score",
    "token": "178a72ced8d6581bc798d502288f9d29dd211c49231588656a1e72bc0123425d894808d42be9627d589b45851061173be3b215f44e503d0edc89ec6a6e65280f",
    "arguments": {"phone": "71234567890", "email": "aaa@some.hz", "first_name": "Egor", "last_name": "Borisov",
    "birthday": "01.01.1990", "gender": 1}}' http://127.0.0.1:8080/method

response example:

    {"code": 200, "response": {"score": 5.0}}

use `clients_interests` to get response from clients_interests method:

    curl -X POST  -H "Content-Type: application/json" -d '{"account": "account1", "login": "admin", "method": "clients_interests",
    "token": "feed42fae0d470f118813457dab6299a2e61fccabb81b0e2e7cfbfc2af8c2fad3ee5fc474a160e90fcb367a7d8943fe9a8cc3cc0d93de7576d1c1b2eeacd9e22",
    "arguments": {"client_ids": [1,2,3,4], "date": "01.01.2018"}}' http://127.0.0.1:8080/method/

response example:

    {"code": 200, "response": {"1": ["travel", "geek"], "2": ["sport", "cars"], "3": ["books", "sport"], "4": ["hi-tech", "cinema"]}}

Tests
-----
You can execute unit tests by invoking `tox` (tox-docker plugin is used to start a memcached container to use for
integration tests), that will also invoke a flake8 lint check.