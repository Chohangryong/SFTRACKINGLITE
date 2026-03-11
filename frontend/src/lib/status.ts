export const statusPalette: Record<string, { label: string; color: string }> = {
  NO_TRACKING: { label: 'No Tracking', color: 'default' },
  NO_ROUTE: { label: 'No Route', color: 'default' },
  REGISTERED: { label: 'Registered', color: 'blue' },
  SHIPPED: { label: 'Shipped', color: 'processing' },
  ARRIVED: { label: 'Arrived', color: 'gold' },
  COLLECTED: { label: 'Collected', color: 'green' },
  CANCELED: { label: 'Canceled', color: 'red' },
  IN_TRANSIT: { label: 'In Transit', color: 'processing' },
  OUT_FOR_DELIVERY: { label: 'Out For Delivery', color: 'gold' },
  DELIVERED: { label: 'Delivered', color: 'green' },
  EXCEPTION: { label: 'Exception', color: 'red' },
  EXPIRED: { label: 'Expired', color: 'volcano' },
  QUERY_UNAVAILABLE: { label: '\uC870\uD68C\uBD88\uAC00', color: 'orange' },
  QUERY_FAILED: { label: 'Query Failed', color: 'magenta' },
  UNKNOWN_OPCODE: { label: 'Unknown Opcode', color: 'purple' },
}

export function statusMeta(status: string) {
  return statusPalette[status] ?? { label: status, color: 'default' }
}
