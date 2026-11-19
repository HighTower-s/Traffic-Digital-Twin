import express, { Express } from 'express';
import path from 'node:path';

export function createApp(): Express {
  const app = express();
  app.use(express.json());
  app.use(express.static(path.join(__dirname, 'view')));
  return app;
}
