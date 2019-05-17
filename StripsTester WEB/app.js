const express = require('express');
const bodyParser = require('body-parser');
const routes = require('./routes/index');
const db = require('./routes/db');

const app = express();

app.use(express.static(__dirname + '/public'));

// Body parser helps parsing POST data
app.use(bodyParser.urlencoded({ extended: false })); //support parsing of application/x-www-form-urlencoded post data
app.use(bodyParser.json()); // support parsing of application/json type post data

app.use('/', routes);  // Used for middleware (called every time a server request is sent to the server)
app.use('/db', db);  // Used for middleware (called every time a server request is sent to the server)

module.exports = app;