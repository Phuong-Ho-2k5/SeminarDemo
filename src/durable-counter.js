import { DurableObject } from 'cloudflare:workers';

export const COUNTER_NAME = 'seminar-demo-2';

export class PersistentCounter extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.memoryCounter = 0;
    this.instanceId = crypto.randomUUID();
    this.sql = ctx.storage.sql;
    this.sql.exec(`CREATE TABLE IF NOT EXISTS counter (
      id INTEGER PRIMARY KEY CHECK (id = 1),
      value INTEGER NOT NULL CHECK (value >= 0)
    )`);
    this.sql.exec('INSERT OR IGNORE INTO counter (id, value) VALUES (1, 0)');
  }

  read() {
    return {
      memory_value: this.memoryCounter,
      durable_value: this.sql.exec('SELECT value FROM counter WHERE id = 1').one().value,
      instance_id: this.instanceId,
      object_id: this.ctx.id.toString(),
      counter_name: COUNTER_NAME,
    };
  }

  increment() {
    // Synchronous SQL + RAM update: no await where another call can interleave.
    this.sql.exec('UPDATE counter SET value = value + 1 WHERE id = 1 RETURNING value').one();
    this.memoryCounter++;
    return this.read();
  }

  resetData() {
    this.sql.exec('UPDATE counter SET value = 0 WHERE id = 1');
    this.memoryCounter = 0;
    return this.read();
  }

  async restartForDemo() {
    await this.ctx.storage.sync();
    console.warn(JSON.stringify({ event: 'SEMINAR_RESTART', object_id: this.ctx.id.toString(),
      instance_id: this.instanceId }));
    // Never catch this inside the object, reset RAM by hand, or change its name.
    this.ctx.abort('SEMINAR_RESTART');
  }
}
