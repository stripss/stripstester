import pymongo

class Database:
    def __init__(self):
        self.mongo = pymongo.MongoClient("mongodb://172.30.129.19:27017/")
        #print(myclient.list_database_names())
        self.db = self.mongo["stripstester"]

    def create_test_device(self, test_device_name):
        collection = self.db["test_device"]
        data = {"name": test_device_name, "nests": 2, "description": "silence"}
        collection.update(data,data,upsert=True)

        for x in collection.find():
            print(x)


    # New test has been done.
    def insert_test_info(self, data):
        # get date time
        collection = self.db["test_info"]
        id = collection.insert_one(data)
        print("[TesterDB] Test info saved successfully. ({})" . format(id))

    # New test has been done.
    def insert_test_data(self, data):
        # get date time
        collection = self.db["test_info"]
        id = collection.insert_one(data)
        print("[TesterDB] Test info saved successfully. ({})".format(id))
