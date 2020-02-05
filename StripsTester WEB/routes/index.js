const express = require('express');
const path = require('path');
const HOMEDIR = path.join(__dirname, '..');
const router = express.Router();
const MongoClient = require('mongodb').MongoClient;
const ObjectId = require('mongodb').ObjectID;
const multer = require('multer');
const fs = require('fs');
const moment = require('moment');

const db_url = 'mongodb://172.30.129.19:27017/';

// SET STORAGE
var storage = multer.diskStorage({
    destination: function (req, file, cb) {
        cb(null, path.join(HOMEDIR, 'public', 'media'));
    },

    filename: function (req, file, cb) {
        // Remove illegal characters
        file.originalname = file.originalname.replace(/(?!\.[^.]+$)\.|[^\w.]+/g, '').toLowerCase();

        cb(null, Date.now() + '-' + file.originalname);
    }
});

var upload = multer({storage: storage});

router.get('/', (req, res) => { // Respond with HTML page
    res.sendFile(path.join(HOMEDIR, 'public', 'index.html'));
});

router.post('/login', (req, res) => { // Respond with HTML page
    var password = req.body.input_pass;  // Get hashed pass from POST

    res.setHeader('Content-Type', 'application/json');
    if (password == "admin") {  // AUTH success
        res.json({'logged': true});
    } else {
        res.json({'logged': false});
    }
});

router.post("/upload_file", upload.single('fileName'), (req, res, next) => {
    console.log(req.file);

    let file = req.file;  // Extra file uploaded

    // Throw OK if file is not valid, so the procedure can continue on client side
    if (!file) {
        res.sendStatus(200);
        return;
    }

    // Upload file
    res.send(file);
});

router.post('/add_new_help', async (req, res, next) => { // Respond with HTML page
    var title = req.body.title;  // Title
    var test_device = req.body.test_device;  // Test device
    var description = req.body.description;  // Description
    var author = req.body.author;
    var link = req.body.link;

    // Date of creation in UNIX format
    var date_of_creation = Math.floor((new Date()).getTime());

    var connection = await MongoClient.connect(db_url, {useNewUrlParser: true});
    var dbo = connection.db("stripstester");

    console.log(title, test_device, description, author, date_of_creation);

    // If ID is not specified, use help for all test devices
    if (test_device == 'vse' || test_device == '') test_device = -1;

    if (test_device != -1) {
        test_device = await dbo.collection("test_device").findOne({'name': test_device});
        test_device = test_device._id;
    }

    var result = await dbo.collection("test_help").insertOne({
        'title': title,
        'test_device': test_device,
        'link': link,
        'description': description,
        'author': author,
        'date_of_creation': date_of_creation
    });

    res.setHeader('Content-Type', 'application/json');
    res.json({'result': result.insertedCount});

    await connection.close();
});

router.post('/add_new_calibration', async (req, res, next) => { // Respond with HTML page
    var test_device = req.body.test_device;  // Test device
    var description = req.body.description;  // Description
    var author = req.body.author;
    var link = req.body.link;

    // Date of creation in UNIX format
    var date = Math.floor((new Date()).getTime());

    var connection = await MongoClient.connect(db_url, {useNewUrlParser: true});
    var dbo = connection.db("stripstester");

    test_device = await dbo.collection("test_device").findOne({'name': test_device});
    test_device = test_device._id;

    var result = await dbo.collection("test_calibration").insertOne({
        'test_device': test_device,
        'link': link,
        'description': description,
        'author': author,
        'date': date
    });

    res.setHeader('Content-Type', 'application/json');
    res.json({'result': result.insertedCount});

    await connection.close();
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
    var date_from = new Date(req.query.date_from);
    var date_to = new Date(req.query.date_to);

    date_from = moment(date_from).toDate();
    date_to = moment(date_to).endOf('day').toDate();

    MongoClient.connect(db_url, {useNewUrlParser: true}, function (err, db) {
        if (err) throw err;
        var dbo = db.db("stripstester");

        dbo.collection("test_device").findOne({'name': id}, function (err, result) {
            if (err) throw err;
            //console.log(result['_id']);
            dbo.collection("test_info").find({'test_device': ObjectId(result['_id']), 'datetime': {'$gte': date_from, '$lte': date_to}}).sort('datetime', -1).toArray(function (err, result) {
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

router.get('/help', (req, res) => {
    MongoClient.connect(db_url, {useNewUrlParser: true}, function (err, db) {
        if (err) throw err;
        var dbo = db.db("stripstester");

        dbo.collection("test_help").find({}).toArray(function (err, result) {
            if (err) throw err;

            res.setHeader('Content-Type', 'application/json');
            res.json(result);
            //console.log(result);
            db.close();
        });
    });
});

router.get('/calibration', (req, res) => {
    var tid = req.query.tid;  // Get ID of TN

    MongoClient.connect(db_url, {useNewUrlParser: true}, function (err, db) {
        if (err) throw err;
        var dbo = db.db("stripstester");

        dbo.collection("test_device").findOne({'name': tid}, function (err, result) {
            if (err) throw err;

            dbo.collection("test_calibration").find({'test_device': ObjectId(result['_id'])}).toArray(function (err, result) {
                if (err) throw err;

                res.setHeader('Content-Type', 'application/json');
                res.json(result);
                //console.log(result);
                db.close();
            });
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


router.post('/delcal', async (req, res, next) => { // Asynchronous because of nested queries
    var id = req.body.tid;  // Get ID from POST

    res.setHeader('Content-Type', 'application/json');

    var connection = await MongoClient.connect(db_url, {useNewUrlParser: true});
    var dbo = connection.db("stripstester");

    var current_calibration = await dbo.collection("test_calibration").findOne({'_id': ObjectId(id)});

    if (current_calibration['link']) {  // File detected
        try {
            fs.unlinkSync(path.join(HOMEDIR, 'public', current_calibration['link']));
            //file removed
        } catch (err) {
            console.error(err)
        }
    }

    var result = await dbo.collection("test_calibration").deleteOne({'_id': ObjectId(id)});

    res.setHeader('Content-Type', 'application/json');
    res.json({'success': result['deletedCount']});

    await connection.close();
});

router.post('/delhelp', async (req, res) => {
    var id = req.body.id;  // Get ID from POST

    var connection = await MongoClient.connect(db_url, {useNewUrlParser: true});
    var dbo = connection.db("stripstester");

    var current_help = await dbo.collection("test_help").findOne({'_id': ObjectId(id)});

    if (current_help['link']) {
        try {
            fs.unlinkSync(path.join(HOMEDIR, 'public', current_help['link']));
            //file removed
        } catch (err) {
            console.error(err)
        }
    }
    // Check if current_help is defined
    // Delete file current_help[link]

    var result = await dbo.collection("test_help").deleteOne({'_id': ObjectId(id)});

    res.setHeader('Content-Type', 'application/json');
    res.json({'success': result['deletedCount']});

    await connection.close();
});


async function recreate_count(test_device_id) {
    var connection = await MongoClient.connect(db_url, {useNewUrlParser: true});
    var dbo = connection.db("stripstester");

    var good = await dbo.collection("test_info").find({'test_device': ObjectId(test_device_id), 'result': 1}).count();
    var bad = await dbo.collection("test_info").find({'test_device': ObjectId(test_device_id), 'result': 0}).count();

    var midnight = new Date();
    midnight.setHours(0, 0, 0, 0);

    var good_today = await dbo.collection("test_info").find({'test_device': ObjectId(test_device_id), 'result': 1, 'datetime': {'$gt': midnight}}).count();
    var bad_today = await dbo.collection("test_info").find({'test_device': ObjectId(test_device_id), 'result': 0, 'datetime': {'$gt': midnight}}).count();
    //console.log(good, bad, good_today, bad_today);

    var today_date = await dbo.collection("test_info").find({'test_device': ObjectId(test_device_id)}).sort({'_id': -1}).limit(1)[0];
    if (today_date == null) today_date = midnight;

    // Update count collection and set good_today and bad_today to zero.
    try {
        await dbo.collection("test_count").updateOne({'test_device': ObjectId(test_device_id)}, {
            '$set': {
                'good': good,
                'bad': bad,
                'good_today': good_today,
                'bad_today': bad_today,
                'today_date': today_date
            }
        });
        //console.log("Successful recreated counters.");
    } catch (error) {
        //console.log(error);
    }

    await connection.close();
}

module.exports = router;