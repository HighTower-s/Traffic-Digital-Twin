import { VehicleCounters } from './vehicleCounters';

describe('VehicleCounters', () => {
  it('starts at zero for every type and direction', () => {
    const counters = new VehicleCounters();
    const stats = counters.getStats();

    expect(stats.totals).toEqual({ in: 0, out: 0, all: 0 });
    expect(stats.byType).toEqual({
      car: { in: 0, out: 0 },
      truck: { in: 0, out: 0 },
      motorcycle: { in: 0, out: 0 },
      bus: { in: 0, out: 0 },
    });
    expect(stats.cameraId).toBe('');
  });

  it('records a single event under the right type and direction', () => {
    const counters = new VehicleCounters();
    counters.record('car', 'in', 'cam-chalongkrung-01');

    const stats = counters.getStats();
    expect(stats.byType.car).toEqual({ in: 1, out: 0 });
    expect(stats.byType.truck).toEqual({ in: 0, out: 0 });
    expect(stats.totals).toEqual({ in: 1, out: 0, all: 1 });
  });

  it('accumulates multiple events across types and directions', () => {
    const counters = new VehicleCounters();
    counters.record('car', 'in', 'cam-01');
    counters.record('car', 'out', 'cam-01');
    counters.record('truck', 'out', 'cam-01');
    counters.record('motorcycle', 'in', 'cam-01');
    counters.record('bus', 'in', 'cam-01');

    const stats = counters.getStats();
    expect(stats.byType).toEqual({
      car: { in: 1, out: 1 },
      truck: { in: 0, out: 1 },
      motorcycle: { in: 1, out: 0 },
      bus: { in: 1, out: 0 },
    });
    expect(stats.totals).toEqual({ in: 3, out: 2, all: 5 });
  });

  it('sets cameraId from the first recorded event and keeps it', () => {
    const counters = new VehicleCounters();
    counters.record('car', 'in', 'cam-first');
    counters.record('truck', 'out', 'cam-second');

    expect(counters.getStats().cameraId).toBe('cam-first');
  });

  it('reset() zeroes counts and clears cameraId', () => {
    const counters = new VehicleCounters();
    counters.record('car', 'in', 'cam-01');

    counters.reset();
    const afterReset = counters.getStats();

    expect(afterReset.totals).toEqual({ in: 0, out: 0, all: 0 });
    expect(afterReset.cameraId).toBe('');
    expect(() => new Date(afterReset.since).toISOString()).not.toThrow();
  });

  it('getStats() returns independent snapshots, not shared mutable state', () => {
    const counters = new VehicleCounters();
    counters.record('car', 'in', 'cam-01');

    const snapshot = counters.getStats();
    snapshot.byType.car.in = 999;

    expect(counters.getStats().byType.car.in).toBe(1);
  });
});
