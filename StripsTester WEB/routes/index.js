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
    var connection = await MongoClient.connect(db_url, {useNewUrlParser: true});
    var dbo = connection.db("stripstester");

    var test_devices = await dbo.collection("test_device").find({}).toArray();

    for (const element of test_devices) {
        var index = test_devices.indexOf(element);

        test_devices[index]['extra'] = await dbo.collection("test_count").findOne({'test_device': ObjectId(element['_id'])});

        // Check if extra parameter exists for that test device.
        if (test_devices[index]['extra'] != null) {
            // Check if counter is not null
            if (test_devices[index]['extra']['good_today'] != 0 || test_devices[index]['extra']['good_today'] != 0) {
                var midnight = new Date();
                midnight.setHours(0, 0, 0, 0);

                // Check if last test if exceeded today date
                if (test_devices[index]['extra']['today_date'] < midnight) {
                    console.log("Test device " + test_devices[index]['name'] + " today counter reset to zero");

                    // Update count collection and set good_today and bad_today to zero.
                    try {
                        await dbo.collection("test_count").updateOne({'test_device': ObjectId(element['_id'])}, {'$set': {'good_today': 0, 'bad_today': 0}});
                        // Get fresh data
                        test_devices[index]['extra'] = await dbo.collection("test_count").findOne({'test_device': ObjectId(element['_id'])});
                    } catch (error) {
                        console.log(error);
                    }
                }
            }
        }
    }

    res.setHeader('Content-Type', 'application/json');
    res.json(test_devices);

    await connection.close();
});

// Get server UTC time (cannot trust client time)
router.get('/time', (req, res) => {
    var utc_time = Math.floor((new Date()).getTime());

    res.setHeader('Content-Type', 'application/json');
    res.json({'time': utc_time});
});

router.get('/db', (req, res) => {
    var id = req.query.tid;  // Get ID from URL

    MongoClient.connect(db_url, {useNewUrlParser: true}, function (err, db) {
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

    MongoClient.connect(db_url, {useNewUrlParser: true}, function (err, db) {
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

    MongoClient.connect(db_url, {useNewUrlParser: true}, function (err, db) {
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


router.post('/delmeas', async (req, res, next) => { // Asynchronous because of nested queries
    var id = req.body.tid;  // Get ID from POST

    res.setHeader('Content-Type', 'application/json');

    var connection = await MongoClient.connect(db_url, {useNewUrlParser: true});
    var dbo = connection.db("stripstester");

    var test_device_id = await dbo.collection("test_info").findOne({'_id': ObjectId(id)});

    var result = await dbo.collection("test_info").deleteOne({'_id': ObjectId(id)});

    res.setHeader('Content-Type', 'application/json');
    res.json({'success': result['deletedCount']});

    await connection.close();

    // If delete success, recreate counter for that TN
    if (result['deletedCount']) recreate_count(test_device_id['test_device']);
});


async function recreate_count(test_device_id) {
    var connection = await MongoClient.connect(db_url, {useNewUrlParser: true});
    var dbo = connection.db("stripstester");

    var good = await dbo.collection("test_info").find({'test_device': ObjectId(test_device_id), 'result': 1}).count();
    var bad = await dbo.collection("test_info").find({'test_device': ObjectId(test_device_id), 'result': 0}).count();

    var midnight = new Date(); midnight.setHours(0, 0, 0, 0);

    var good_today = await dbo.collection("test_info").find({'test_device': ObjectId(test_device_id), 'result': 1, 'datetime': {'$gt': midnight}}).count();
    var bad_today = await dbo.collection("test_info").find({'test_device': ObjectId(test_device_id), 'result': 0, 'datetime': {'$gt': midnight}}).count();
    //console.log(good, bad, good_today, bad_today);

    var today_date = await dbo.collection("test_info").find({'test_device': ObjectId(test_device_id)}).sort({'_id': -1}).limit(1)[0];
    if (today_date == null) today_date = midnight;

    // Update count collection and set good_today and bad_today to zero.
    try {
        await dbo.collection("test_count").updateOne({'test_device': ObjectId(test_device_id)}, {'$set': {'good': good, 'bad': bad, 'good_today': good_today, 'bad_today': bad_today, 'today_date': today_date}});
        //console.log("Successful recreated counters.");
    } catch (error) {
        //console.log(error);
    }

    await connection.close();
}

module.exports = router;