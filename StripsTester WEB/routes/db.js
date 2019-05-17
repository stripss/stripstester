const express = require('express');
const path = require('path');
const HOMEDIR  = path.join(__dirname,'..');
const router = express.Router();
/*
var MongoClient = require('mongodb').MongoClient;

var url = 'mongodb://172.30.129.19:27017/';


  MongoClient.connect(url, function(err, db) {

        console.log(db.listCollections);
        db.close();
      });

*/
router.post('/test', (req, res) => {
    console.log(req.body.texta);
    var texta = req.body.texta;

    //res.send('It works! You wrote: ' + req.body.texta + '.');
    res.send(texta);
});


module.exports = router;