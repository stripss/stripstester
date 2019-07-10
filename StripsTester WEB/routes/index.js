const express = require('express');
const path = require('path');
const HOMEDIR = path.join(__dirname, '..');
const router = express.Router();
const MongoClient = require('mongodb').MongoClient;
const ObjectId = require('mongodb').ObjectID;

const db_url = 'mongodb://172.30.129.19:27017/';

router.get('/', (req, res) => { // Respond with HTML page
    res.sendFile(path.join(HOMEDIR, 'public', 'index_debug.html'));
});

router.post('/login', (req, res) => { // Respond with HTML page
    var password = req.body.input_pass;  // Get hashed pass from POST

    res.setHeader('Content-Type', 'application/json');
    if (password == "admin") {  // AUTH success
        res.json({'logged': true});
    }
    else {
        res.json({'logged': false});
    }
});

router.get('/stats', async (req, res, next) => { // Asynchronous because of nested queries
    var connection = await MongoClient.connect(db_url);
    var dbo = connection.db("stripstester");

    var test_devices = await dbo.collection("test_device").find({}).toArray();
    var counter = 0;

    for (const element of test_devices) {

        //console.log(json_data[json_data.length-1].good);
        var good = await dbo.collection("test_info").find({'test_device': ObjectId(element['_id']), "result": 1}).count();
        var bad = await dbo.collection("test_info").find({'test_device': ObjectId(element['_id']), "result": 0}).count();

        test_devices[counter]['extra'] = {good: good, bad: bad};

        counter++;
    }

    res.setHeader('Content-Type', 'application/json');
    res.json(test_devices);

    await connection.close();
});

router.get('/db', (req, res) => {
    var id = req.query.tid;  // Get ID from URL

    MongoClient.connect(db_url, function (err, db) {
        if (err) throw err;
        var dbo = db.db("stripstester");

        dbo.collection("test_device").findOne({'name': id}, function (err, result) {
            if (err) throw err;
            console.log(result['_id']);
            dbo.collection("test_info").find({'test_device': ObjectId(result['_id'])}).sort('datetime', -1).toArray(function (err, result) {
                if (err) throw err;

                res.setHeader('Content-Type', 'application/json');
                res.json(result);
                //console.log(result);
                db.close();
            });
        });
    });


//res.send(path.join(HOMEDIR,'public','test.html'));
});

module.exports = router;