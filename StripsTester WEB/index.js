const app = require('./app');

const server = app.listen(3000, () => {
  console.log("HTTP Server started! Made by Marcel Jancar.");
  console.log(`Express is running on port ${server.address().port}`);
});