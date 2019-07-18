const express = require('express');
const path = require('path');
const HOMEDIR = path.join(__dirname, '..');
const router = express.Router();
const MongoClient = require('mongodb').MongoClient;
const ObjectId = require('mongodb').ObjectID;

const db_url = 'mongodb://172.30.129.19:27017/';

router.get('/', (req, res) => { // Respond with HTML page
    res.sendFile(path.join(HOMEDIR, 'public', 'index.html'));
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
    var connection = await MongoClient.connect(db_url,{ useNewUrlParser: true });
    var dbo = connection.db("stripstester");

    var test_devices = await dbo.collection("test_device").find({}).toArray();

    var date_at_midnight = new Date(new Date().setHours(0, 0, 0, 0));

    for (const element of test_devices) {
        var index = test_devices.indexOf(element);

        var good = await dbo.collection("test_info").find({'test_device': ObjectId(element['_id']), "result": 1}).count();

        var bad = await dbo.collection("test_info").find({'test_device': ObjectId(element['_id']), "result": 0}).count();
        var good_today = await dbo.collection("test_info").find({'test_device': ObjectId(element['_id']), "result": 1, "datetime": {"$gt": date_at_midnight}}).count();
        var bad_today = await dbo.collection("test_info").find({'test_device': ObjectId(element['_id']), "result": 0, "datetime": {"$gt": date_at_midnight}}).count();

        var last_test = await dbo.collection("test_info").find({'test_device': ObjectId(element['_id'])}).sort({"_id": -1}).limit(1).toArray();

        if (last_test.length) test_devices[index]['last_test'] = last_test[0]['datetime'];

        test_devices[index]['extra'] = {good: good, bad: bad, good_today: good_today, bad_today: bad_today};
    }

    res.setHeader('Content-Type', 'application/json');
    res.json(test_devices);

    await connection.close();
});

router.get('/db', (req, res) => {
    var id = req.query.tid;  // Get ID from URL

    MongoClient.connect(db_url,{ useNewUrlParser: true }, function (err, db) {
        if (err) throw err;
        var dbo = db.db("stripstester");

        dbo.collection("test_device").findOne({'name': id}, function (err, result) {
            if (err) throw err;
            //console.log(result['_id']);
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

router.get('/tn', (req, res) => {

    MongoClient.connect(db_url,{ useNewUrlParser: true }, function (err, db) {
        if (err) throw err;
        var dbo = db.db("stripstester");

        dbo.collection("test_device").find({}).toArray(function (err, result) {
            if (err) throw err;

            res.setHeader('Content-Type', 'application/json');
            res.json(result);
            //console.log(result);
            db.close();
        });
    });
});

router.get('/idinfo', (req, res) => {
    var id = req.query.id;

    MongoClient.connect(db_url,{ useNewUrlParser: true }, function (err, db) {
        if (err) throw err;
        var dbo = db.db("stripstester");

        dbo.collection("test_info").find({'_id': ObjectId(id)}).toArray(function (err, result) {
            if (err) throw err;

            res.setHeader('Content-Type', 'application/json');
            res.json(result);
            //console.log(result);
            db.close();
        });
    });
});

router.post('/delmeas', (req, res) => { // Respond with HTML page
    var id = req.body.tid;  // Get ID from POST

    res.setHeader('Content-Type', 'application/json');
    MongoClient.connect(db_url,{ useNewUrlParser: true }, function (err, db) {
        if (err) throw err;
        var dbo = db.db("stripstester");

        dbo.collection("test_info").deleteOne({'_id': ObjectId(id)}, function (err, result) {
            res.setHeader('Content-Type', 'application/json');

            if (err) throw err;
            //console.log("Measurement deleted for id " + id + " with success of " + result['deletedCount']);
            res.json({'success': result['deletedCount']});

            db.close();
        });
    });
});

module.exports = router;