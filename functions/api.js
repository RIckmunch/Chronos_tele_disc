const serverless = require('serverless-http');
const express = require('express');
const app = express();

// Middleware
app.use(express.json());

// Routes
app.get('/api/health', (req, res) => {
  res.json({ status: 'OK', message: 'Chronos Discord Bot API is running' });
});

app.post('/api/webhook', (req, res) => {
  // Handle Discord webhooks here
  console.log('Webhook received:', req.body);
  res.json({ received: true });
});

// Export the serverless function
module.exports.handler = serverless(app);