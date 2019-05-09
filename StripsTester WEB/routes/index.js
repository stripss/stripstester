const express = require('express');
var path = require('path');

const router = express.Router();

router.get('/', (req, res) => {
  //res.send('It works!');
  res.sendFile('/home/marcel/.public/index.html');
});

router.get('/test', (req, res) => {
  //res.send('It works!');
  res.sendFile('/home/marcel/.public/index.html');
});

module.exports = router;