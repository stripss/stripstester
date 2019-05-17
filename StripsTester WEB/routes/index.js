const express = require('express');
const path = require('path');
const HOMEDIR  = path.join(__dirname,'..');
const router = express.Router();

router.get('/', (req, res) => {
  //res.send('It works!');
  res.sendFile(path.join(HOMEDIR,'public','index.html'));
});

router.get('/post', (req, res) => {
  //res.send('It works!');
  res.sendFile(path.join(HOMEDIR,'public','test.html'));
});

module.exports = router;