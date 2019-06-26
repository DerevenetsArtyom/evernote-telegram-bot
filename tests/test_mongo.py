import unittest
from unittest import expectedFailure

from evernotebot.bot.storage import Mongo


connection_string = "mongodb://127.0.0.1:27017/"

class TestMongoStorage(unittest.TestCase):
    def setUp(self):
        self.db_name = "test_mongo_storage"
        self.client = Mongo(connection_string, db_name=self.db_name,
                            collection_name="test")

    def tearDown(self):
        self.client._driver.drop_database(self.db_name)

    def test_create(self):
        data = {"id": 1, "name": "test"}
        self.client.create(data)
        data = self.client.get(1)
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["name"], "test")

    @expectedFailure
    def test_save_not_existed(self):
        data = {"id": 2, "name": "Batman"}
        self.client.save(data)

    def test_save(self):
        data = {"id": 3, "name": "Batman"}
        self.client.create(data)
        data["name"] = "Joker"
        self.client.save(data)
        data = self.client.get(3)
        self.assertEqual(data["name"], "Joker")

