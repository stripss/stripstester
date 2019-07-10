const express = require('express');
const bodyParser = require('body-parser');
const routes = require('./routes/index');
const path = require('path');

const app = express();

app.use(express.static(path.join(__dirname, 'public'))); //  "public" off of current is root
app.use(express.static(path.join(__dirname, 'public', 'img'))); //  "public" off of current is root

// Body parser helps parsing POST data
app.use(express.json());
app.use(express.urlencoded({ extended: false }));

app.use('/', routes);  // Used for middleware (called every time a server request is sent to the server)

module.exports = app;