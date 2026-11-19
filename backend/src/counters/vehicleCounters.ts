import { Direction, VEHICLE_TYPES, VehicleType } from '../constants';

interface DirectionCounts {
  in: number;
  out: number;
}

export interface VehicleStats {
  cameraId: string;
  since: string;
  totals: { in: number; out: number; all: number };
  byType: Record<VehicleType, DirectionCounts>;
}

function emptyCounts(): Record<VehicleType, DirectionCounts> {
  const counts = {} as Record<VehicleType, DirectionCounts>;
  for (const type of VEHICLE_TYPES) {
    counts[type] = { in: 0, out: 0 };
  }
  return counts;
}

// In-memory only — resets on server restart. Never let counting delay the
// Socket.io broadcast in the ingest controller.
export class VehicleCounters {
  private counts: Record<VehicleType, DirectionCounts> = emptyCounts();
  private cameraId = '';
  private since: string = new Date().toISOString();

  record(type: VehicleType, direction: Direction, cameraId: string): void {
    this.counts[type][direction] += 1;
    if (this.cameraId === '') {
      this.cameraId = cameraId;
    }
  }

  getStats(): VehicleStats {
    const totals = { in: 0, out: 0, all: 0 };
    const byType = {} as Record<VehicleType, DirectionCounts>;

    for (const type of VEHICLE_TYPES) {
      const typeCounts = this.counts[type];
      totals.in += typeCounts.in;
      totals.out += typeCounts.out;
      byType[type] = { ...typeCounts };
    }
    totals.all = totals.in + totals.out;

    return { cameraId: this.cameraId, since: this.since, totals, byType };
  }

  reset(): void {
    this.counts = emptyCounts();
    this.cameraId = '';
    this.since = new Date().toISOString();
  }
}

export const vehicleCounters = new VehicleCounters();
